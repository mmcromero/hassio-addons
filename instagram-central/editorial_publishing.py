"""Durable per-account publishing; only explicitly authorized posts execute."""
import hashlib
from io import BytesIO
import json
import secrets
import threading
import time
from PIL import Image

import editorial_core as core
import editorial_delivery as delivery
import editorial_graph as graph
import instagram_connection

MESSAGES = {
    'connection_required': 'Conecte e verifique esta conta na Central antes de publicar.',
    'token_invalid': 'O token desta conta não está válido para o aplicativo configurado. Reconecte esta conta.',
    'permission_required': 'Falta conceder instagram_content_publish a esta conta. Inclua a permissão na configuração Meta e reconecte esta conta.',
    'delivery_not_configured': 'Não foi possível confirmar o endereço HTTPS de entrega das mídias na configuração do aplicativo Meta.',
    'account_mismatch': 'A identidade da conta mudou. A publicação foi interrompida para evitar envio para outra conta.',
    'check_unavailable': 'Não foi possível conferir o acesso de publicação na Meta. Tente verificar novamente.',
    'network_unavailable': 'A comunicação com a Meta falhou. Confira o resultado antes de tentar publicar novamente.',
    'invalid_response': 'A Meta retornou uma resposta inesperada. Confira o resultado antes de tentar novamente.',
    'meta_rejected': 'A Meta recusou a operação. Confira as permissões e os requisitos da mídia.',
    'publishing_limit': 'O limite de publicações desta conta foi atingido. Escolha outro horário.',
    'processing_failed': 'A Meta não conseguiu preparar a mídia. Revise formato, dimensões e duração.',
    'processing_timeout': 'A mídia não ficou pronta no prazo. Verifique o resultado antes de tentar novamente.',
    'confirmation_required': 'O envio pode ter sido aceito pela Meta. Verifique o resultado; ele não será repetido automaticamente.',
    'internal_error': 'A publicação foi interrompida. Verifique o resultado antes de tentar novamente.',
}


def message(error):
    text = MESSAGES.get(error.reason, MESSAGES['internal_error'])
    stages = {'profile': 'consulta da identidade da conta', 'token': 'verificação do token',
              'subscription': 'consulta da configuração de entrega', 'limit': 'consulta do limite de publicação',
              'create': 'preparação da mídia', 'status': 'consulta do processamento',
              'publish': 'confirmação da publicação', 'permalink': 'consulta do link publicado'}
    stage = stages.get(error.stage)
    if error.reason == 'meta_rejected' and stage:
        text = 'A Meta recusou a ' + stage + '. A publicação não foi confirmada.'
    number = str(error.code) + ('/' + str(error.subcode) if error.subcode is not None else '') if error.code is not None else ''
    return text + (' Código Meta: ' + number + '.' if number else '')


class PublisherHub:
    def __init__(self, config_for, credential_for, store_for, businesses, media_delivery,
                 *, api_factory=graph.PublishingAPI, checker=graph.check_connection, clock=time.time):
        self.config_for, self.credential_for, self.store_for = config_for, credential_for, store_for
        self.businesses, self.delivery = businesses, media_delivery
        self.api_factory, self.checker, self.clock = api_factory, checker, clock
        self._checks = {}
        self._lock = threading.Lock()
        self.stop = threading.Event()
        self.wake = threading.Event()

    def _identity(self, business):
        cfg, credential = self.config_for(business), self.credential_for(business)
        if not instagram_connection.credential_status(credential, cfg)['account_verified']:
            raise graph.PublishingError('connection_required')
        identity = hashlib.sha256(json.dumps([
            cfg.get('instagram_account_id'), cfg.get('instagram_expected_username'),
            cfg.get('meta_app_id'), cfg.get('meta_app_secret'), cfg.get('meta_graph_version'),
            credential.get('access_token')], sort_keys=True).encode()).hexdigest()
        return cfg, credential, identity

    def check(self, business, *, force=True):
        identity = None
        try:
            cfg, credential, identity = self._identity(business)
            with self._lock:
                cached = self._checks.get(business)
            if not force and cached and cached.get('identity') == identity and cached.get('until', 0) > self.clock():
                return cached
            result = self.checker(cfg, credential, api_factory=self.api_factory)
            value = {**result, 'identity': identity, 'until': self.clock() + 300,
                     'ready': True, 'message': 'Token e permissão de publicação conferidos para esta conta.',
                     'checkedAt': int(self.clock())}
        except graph.PublishingError as error:
            value = {'ready': False, 'message': message(error), 'checkedAt': int(self.clock()),
                     'identity': identity, 'until': self.clock() + 30}
        with self._lock:
            self._checks[business] = value
        return value

    def public_state(self, business):
        with self._lock:
            cached = self._checks.get(business)
        try:
            _, _, identity = self._identity(business)
        except graph.PublishingError as error:
            return {'ready': False, 'message': message(error), 'checkedAt': None}
        if cached and cached.get('identity') == identity and cached.get('until', 0) > self.clock():
            return {key: cached[key] for key in ('ready', 'message', 'checkedAt', 'stories') if key in cached}
        return {'ready': False, 'message': 'Verifique o acesso de publicação desta conta.', 'checkedAt': None}

    def _ready(self, business):
        result = self.check(business, force=False)
        if not result['ready']:
            raise core.EditorialError(result['message'])
        return result

    @staticmethod
    def _post(store, post):
        with store._db() as db:
            row = db.execute('SELECT * FROM posts WHERE id=?', (post,)).fetchone()
            if row is None:
                raise core.EditorialError('Publicação inexistente nesta conta.')
            result = dict(row)
            result['media'] = [dict(item) for item in db.execute('''SELECT a.media_id,m.extension
                FROM attachments a JOIN media m ON m.id=a.media_id WHERE a.post_id=? ORDER BY a.position''', (post,))]
        return result

    def _validate(self, store, post, ready):
        if post['caption_mode'] != 'general':
            raise core.EditorialError('A API do Instagram usa uma legenda geral por carrossel. Escolha Uma legenda para todas as imagens antes de publicar.')
        if post['format'] == 'story':
            if ready.get('stories') is False:
                raise core.EditorialError('Publicação de Stories pela API requer conta do tipo Empresa na Meta.')
            if post['caption']:
                raise core.EditorialError('A API não aplica legenda textual ao Story. Inclua o texto na própria mídia e deixe a legenda vazia.')
        count = len(post['media'])
        if not (2 <= count <= 20 if post['format'] == 'carousel' else count == 1):
            raise core.EditorialError('Confira a quantidade de mídias antes de publicar.')
        for media in post['media']:
            raw, mime = store.read_media(media['media_id'])
            if (post['format'] in ('feed', 'carousel') and mime == 'video/mp4' or
                    post['format'] == 'reel' and mime != 'video/mp4'):
                raise core.EditorialError('Mídia incompatível com o formato escolhido.')
            if mime != 'video/mp4':
                prepared = delivery.image_for_meta(raw)
                if post['format'] in ('feed', 'carousel'):
                    with Image.open(BytesIO(prepared)) as image:
                        ratio = image.width / image.height
                    if not .8 <= ratio <= 1.91:
                        raise core.EditorialError('Imagens de feed e carrossel precisam ter proporção entre 4:5 e 1,91:1. Ajuste a mídia antes de publicar.')

    def queue(self, business, post_id, version, *, when=None, activate=False):
        store = self.store_for(business)
        post = self._post(store, post_id)
        if type(version) is not int or post['version'] != version:
            raise core.EditorialConflict('Conteúdo mudou. Recarregue antes de tentar novamente.')
        clock = int(self.clock())
        scheduled = core._timestamp(when) if when is not None else clock
        if when is not None and scheduled <= clock:
            raise core.EditorialError('Data deve ser futura')
        ready = self._ready(business)
        cfg, _, _ = self._identity(business)
        self._validate(store, post, ready)
        with store._tx() as db:
            store._check_version(db, post_id, version)
            row = db.execute('SELECT * FROM posts WHERE id=?', (post_id,)).fetchone()
            expected = 'scheduled' if activate else 'approved'
            if row['state'] != expected or row['revision'] != row['approved_revision']:
                raise core.EditorialError('Aprove a revisão atual antes de liberar o envio.')
            if activate:
                if row['publish_authorized'] or row['scheduled_at'] <= clock:
                    raise core.EditorialError('Cancele e reagende esta publicação com um horário futuro.')
                scheduled = row['scheduled_at']
            db.execute('''UPDATE posts SET state='scheduled',scheduled_at=?,pending_schedule_at=NULL,
                publish_authorized=1,publication_account_id=?,publication_phase='',publication_data=?,
                publication_next=?,publication_started=NULL,publication_error='',lease_token=NULL,lease_until=NULL
                WHERE id=?''', (scheduled, cfg['instagram_account_id'], json.dumps({'run_id': secrets.token_hex(16)}), scheduled, post_id))
            store._audit(db, post_id, 'publication_authorized')
        self.wake.set()

    def recover(self, business, post_id, version, action, *, confirmed=False):
        store = self.store_for(business)
        post = self._post(store, post_id)
        if post['state'] not in ('failed', 'needs_review'):
            raise core.EditorialError('Esta publicação não está aguardando recuperação.')
        data = json.loads(post['publication_data'])
        if action == 'reset':
            if data.get('issued'):
                raise core.EditorialError('Verifique o resultado na Meta antes de liberar nova tentativa.')
            with store._tx() as db:
                store._check_version(db, post_id, version)
                db.execute('''UPDATE posts SET state='draft',approved_revision=NULL,publish_authorized=0,
                    publication_phase='',publication_data='{}',publication_error='',lease_token=NULL,lease_until=NULL,
                    scheduled_at=NULL WHERE id=?''', (post_id,))
                store._audit(db, post_id, 'returned_to_draft')
            return
        if not data.get('issued') or not data.get('container'):
            raise core.EditorialError('Volte ao rascunho para corrigir esta publicação.')
        self._ready(business)
        cfg, credential, _ = self._identity(business)
        if cfg['instagram_account_id'] != post['publication_account_id']:
            raise core.EditorialError(MESSAGES['account_mismatch'])
        phase = 'confirm'
        if action == 'retry':
            if confirmed is not True:
                raise core.EditorialError('Confirme que verificou no Instagram e que o conteúdo não foi publicado.')
            status = self.api_factory(cfg, credential).status(data['container'])
            if status == 'PUBLISHED':
                phase = 'confirm'
            elif status == 'FINISHED':
                phase = 'ready'
            else:
                raise core.EditorialError('A Meta ainda não confirma um contêiner pronto. Verifique o resultado novamente.')
        data['polls'] = 0
        with store._tx() as db:
            store._check_version(db, post_id, version)
            db.execute('''UPDATE posts SET state='publishing',publication_phase=?,publication_data=?,
                publication_next=?,publication_error='',lease_token=NULL,lease_until=NULL WHERE id=?''',
                (phase, json.dumps(data), int(self.clock()), post_id))
            store._audit(db, post_id, 'publication_recovery_requested')
        self.wake.set()

    def _claim(self, store, clock):
        with store._tx() as db:
            row = db.execute('''SELECT id FROM posts WHERE publish_authorized=1
                AND ((state='scheduled' AND scheduled_at<=?) OR state='publishing')
                AND COALESCE(publication_next,0)<=? AND COALESCE(lease_until,0)<=?
                ORDER BY publication_next,created_at,id LIMIT 1''', (clock, clock, clock)).fetchone()
            if row is None:
                return None
            token = secrets.token_urlsafe(32)
            db.execute("UPDATE posts SET state='publishing',lease_token=?,lease_until=? WHERE id=?",
                       (token, clock + 90, row[0]))
            return row[0], token

    @staticmethod
    def _save(store, post, token, *, state='publishing', phase=None, data=None, next_at=None,
              error='', remote=None):
        with store._tx() as db:
            row = db.execute('SELECT lease_token FROM posts WHERE id=?', (post,)).fetchone()
            if row is None or row[0] != token:
                raise core.EditorialConflict('A reserva desta publicação mudou.')
            db.execute('''UPDATE posts SET state=?,publication_phase=?,publication_data=?,publication_next=?,
                publication_error=?,remote_id=COALESCE(?,remote_id),lease_token=NULL,lease_until=NULL,
                publish_authorized=CASE WHEN ?='published' THEN 0 ELSE publish_authorized END WHERE id=?''',
                (state, phase or '', json.dumps(data or {}), next_at, error, remote, state, post))
            store._audit(db, post, 'publication_' + state)

    def step(self, business):
        store = self.store_for(business)
        clock = int(self.clock())
        claimed = self._claim(store, clock)
        if claimed is None:
            return False
        post_id, lease = claimed
        post = self._post(store, post_id)
        data = json.loads(post['publication_data'])
        phase = post['publication_phase']
        try:
            ready = self._ready(business)
            cfg, credential, _ = self._identity(business)
            if cfg['instagram_account_id'] != post['publication_account_id']:
                raise graph.PublishingError('account_mismatch')
            api = self.api_factory(cfg, credential)
            if not phase:
                self._validate(store, post, ready)
                api.check_limit()
                phase = 'create'
                data.update(children=[], child_ready=0, polls=0)
            elif phase == 'create':
                children = data['children']
                if post['format'] == 'carousel' and len(children) < len(post['media']):
                    media = post['media'][len(children)]
                    url = self.delivery.issue(business, post_id, media['media_id'], ready['origin'])
                    children.append(api.create({'image_url': url, 'is_carousel_item': 'true'}))
                elif post['format'] == 'carousel' and data['child_ready'] < len(children):
                    status = api.status(children[data['child_ready']])
                    if status == 'FINISHED':
                        data['child_ready'] += 1
                        data['polls'] = 0
                    elif status == 'IN_PROGRESS':
                        return self._wait(store, post_id, lease, phase, data, clock)
                    else:
                        raise graph.PublishingError('processing_failed')
                else:
                    fields = {}
                    if post['format'] == 'carousel':
                        fields.update(media_type='CAROUSEL', children=','.join(children))
                    else:
                        media = post['media'][0]
                        url = self.delivery.issue(business, post_id, media['media_id'], ready['origin'])
                        fields['video_url' if media['extension'] == 'mp4' else 'image_url'] = url
                        if post['format'] in ('story', 'reel'):
                            fields['media_type'] = 'STORIES' if post['format'] == 'story' else 'REELS'
                    if post['caption']:
                        fields['caption'] = post['caption']
                    data['container'] = api.create(fields)
                    phase, data['polls'] = 'poll', 0
            elif phase == 'poll':
                status = api.status(data['container'])
                if status == 'FINISHED':
                    phase = 'ready'
                elif status == 'IN_PROGRESS':
                    return self._wait(store, post_id, lease, phase, data, clock)
                else:
                    raise graph.PublishingError('processing_failed')
            elif phase == 'ready':
                # Commit the irreversible-attempt marker BEFORE the network call.
                # A crash here resumes with status reads, never another POST.
                data['issued'] = True
                with store._tx() as db:
                    cur = db.execute('''UPDATE posts SET publication_phase='confirm',publication_data=?
                        WHERE id=? AND lease_token=?''', (json.dumps(data), post_id, lease))
                    if cur.rowcount != 1:
                        raise core.EditorialConflict('Reserva indisponível.')
                phase = 'confirm'
                remote = api.publish(data['container'])
                try:
                    data['permalink'] = api.permalink(remote)
                except graph.PublishingError:
                    pass  # A missing link cannot invalidate a confirmed publication ID.
                self._save(store, post_id, lease, state='published', phase='done', data=data, remote=remote)
                return True
            elif phase == 'confirm':
                status = api.status(data['container'])
                if status == 'PUBLISHED':
                    self._save(store, post_id, lease, state='published', phase='done', data=data)
                    return True
                if status in ('FINISHED', 'IN_PROGRESS'):
                    return self._wait(store, post_id, lease, phase, data, clock)
                raise graph.PublishingError('confirmation_required')
            else:
                raise graph.PublishingError('internal_error')
            self._save(store, post_id, lease, phase=phase, data=data, next_at=clock)
        except graph.PublishingError as error:
            if data.get('issued') and error.ambiguous:
                self._wait(store, post_id, lease, 'confirm', data, clock)
            else:
                self._save(store, post_id, lease, state='needs_review' if data.get('issued') else 'failed',
                           phase=phase, data=data, error=message(error))
        except core.EditorialError as error:
            self._save(store, post_id, lease, state='needs_review' if data.get('issued') else 'failed',
                       phase=phase, data=data, error=str(error))
        except Exception:
            self._save(store, post_id, lease, state='needs_review' if data.get('issued') else 'failed',
                       phase=phase, data=data, error=MESSAGES['internal_error'])
        return True

    def _wait(self, store, post, lease, phase, data, clock):
        data['polls'] = data.get('polls', 0) + 1
        if data['polls'] >= 5:
            self._save(store, post, lease, state='needs_review' if data.get('issued') else 'failed',
                       phase=phase, data=data, error=MESSAGES['confirmation_required' if data.get('issued') else 'processing_timeout'])
        else:
            self._save(store, post, lease, phase=phase, data=data, next_at=clock + 60)
        return True

    def run(self):
        while not self.stop.is_set():
            worked = False
            try:
                businesses = self.businesses()
            except Exception:
                businesses = []
            for business in businesses:
                if self.stop.is_set():
                    return
                try:
                    worked = self.step(business) or worked
                except Exception:
                    # A failed tenant cannot terminate other accounts' worker.
                    # A lease expires for safe status reconciliation on restart.
                    continue
            self.wake.wait(2 if worked else 15)
            self.wake.clear()
