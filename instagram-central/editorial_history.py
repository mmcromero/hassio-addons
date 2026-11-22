"""Explicit, resumable per-account history import. Never publishes or deletes remotely."""
from datetime import datetime, timezone
import hashlib
import json
import secrets
import threading
import time
from urllib.parse import urlsplit, parse_qsl
from urllib.request import Request, build_opener
from urllib.error import HTTPError, URLError

import editorial_core as core
import editorial_graph as graph
import instagram_connection

LIMIT=25*1024*1024
_OPEN=build_opener(instagram_connection._NoGraphRedirect()).open
ACTIVE=('queued','running')


def safe_link(value):
    if not isinstance(value,str) or len(value)>400: return None
    p=urlsplit(value)
    if p.scheme=='https' and p.netloc in ('www.instagram.com','instagram.com') and not p.query and not p.fragment and p.path.startswith(('/p/','/reel/','/stories/')):
        return value
    return None


def download(url, *, opener=None):
    if not isinstance(url,str) or len(url)>8192 or any(c.isspace() or ord(c)<32 for c in url):
        raise core.EditorialError('Endereço de mídia inválido.')
    try:
        p=urlsplit(url);host=p.hostname or '';port=p.port
    except ValueError: raise core.EditorialError('Endereço de mídia inválido.') from None
    if (p.scheme!='https' or p.username or p.password or port not in (None,443) or p.fragment
            or not any(host==base or host.endswith('.'+base) for base in ('cdninstagram.com','fbcdn.net'))
            or any(k.lower() in ('access_token','appsecret_proof') for k,_ in parse_qsl(p.query,max_num_fields=100))):
        raise core.EditorialError('O endereço de mídia não pertence aos CDNs permitidos da Meta.')
    started=time.monotonic();chunks=[];size=0
    try:
        with (opener or _OPEN)(Request(url,headers={'User-Agent':'CentralInstagram-History/1'}),timeout=12) as response:
            length=response.headers.get('Content-Length')
            if length and int(length)>LIMIT: raise core.EditorialError('Mídia acima do limite de 25 MiB.')
            while True:
                if time.monotonic()-started>20: raise core.EditorialError('Tempo de download excedido.')
                chunk=response.read(min(64*1024,LIMIT+1-size))
                if not chunk: break
                chunks.append(chunk);size+=len(chunk)
                if size>LIMIT: raise core.EditorialError('Mídia acima do limite de 25 MiB.')
    except (OSError,ValueError,HTTPError,URLError):
        raise core.EditorialError('Não foi possível baixar a mídia nesta consulta.') from None
    raw=b''.join(chunks)
    mime='image/png' if raw.startswith(b'\x89PNG\r\n\x1a\n') else 'image/jpeg' if raw.startswith(b'\xff\xd8\xff') else 'video/mp4' if len(raw)>=12 and raw[4:8]==b'ftyp' else ''
    # Same validation/re-encoding as authenticated library uploads.
    from editorial_http import validated_upload
    return validated_upload(raw,mime)


def record(raw, now):
    if not isinstance(raw,dict): raise graph.PublishingError('invalid_response')
    remote=graph.identifier(raw.get('id'));caption=raw.get('caption','')
    if not isinstance(caption,str) or len(caption)>2200: raise graph.PublishingError('invalid_response')
    try:
        dt=datetime.fromisoformat(raw['timestamp'].replace('Z','+00:00'))
        if dt.tzinfo is None: raise ValueError()
        stamp=int(dt.timestamp())
        if not 0<stamp<=now+86400: raise ValueError()
    except (KeyError,TypeError,ValueError,AttributeError,OverflowError): raise graph.PublishingError('invalid_response') from None
    kind=raw.get('media_type');product=raw.get('media_product_type')
    fmt='carousel' if kind=='CAROUSEL_ALBUM' else 'story' if product=='STORY' else 'reel' if product=='REELS' else 'feed'
    if kind not in ('IMAGE','VIDEO','CAROUSEL_ALBUM'): raise graph.PublishingError('invalid_response')
    children=raw.get('children')
    media=children.get('data') if kind=='CAROUSEL_ALBUM' and isinstance(children,dict) else [raw] if kind!='CAROUSEL_ALBUM' else None
    if not isinstance(media,list) or not 1<=len(media)<=20: raise graph.PublishingError('invalid_response')
    items=[]
    for i,item in enumerate(media):
        if not isinstance(item,dict): raise graph.PublishingError('invalid_response')
        mid=graph.identifier(item.get('id'))
        if mid in {m['id'] for m in items}: raise graph.PublishingError('invalid_response')
        alt=item.get('alt_text')
        if alt is not None and (not isinstance(alt,str) or len(alt)>1000): raise graph.PublishingError('invalid_response')
        items.append({'id':mid,'position':i,'url':item.get('media_url'),'thumbnail':item.get('thumbnail_url'),'alt':alt or ''})
    values=graph.PublishingAPI._counts(raw,(('like_count','likes'),('comments_count','comments')))
    if 'shares_count' in raw or 'saved_count' in raw:
        values['extra']=graph.PublishingAPI._counts(raw,(('shares_count','shares'),('saved_count','saves')))
    return {'id':remote,'caption':caption,'timestamp':stamp,'format':fmt,'kind':kind,
            'permalink':safe_link(raw.get('permalink')),'media':items,'values':values}


class HistoryHub:
    def __init__(self,publisher,*,downloader=download):
        self.publisher=publisher;self.downloader=downloader
        self.stop=threading.Event();self.wake=threading.Event()

    def public_state(self,business):
        store=self.publisher.store_for(business)
        with store._db() as db: row=db.execute('SELECT status,data FROM history_jobs WHERE slot=1').fetchone()
        if not row: return {'status':'idle'}
        data=json.loads(row['data'])
        return {'status':row['status'],**{k:data.get(k) for k in ('phase','download','seen','imported','updated','files','skipped','totalFiles','processedFiles','pages','message','startedAt','checkedAt','cancel')}}

    def start(self,business,*,download_media=True):
        cfg,_,identity=self.publisher._identity(business);store=self.publisher.store_for(business)
        data={'identity':identity,'account':cfg['instagram_account_id'],'download':download_media,'phase':'pages',
              'seen':0,'imported':0,'updated':0,'files':0,'skipped':0,'totalFiles':0,'processedFiles':0,'pages':0,
              'after':None,'cursors':[],'remoteSeen':[],'expanded':True,'message':'Consultando publicações na Meta…',
              'startedAt':int(time.time()*1000),'checkedAt':None,'cancel':False}
        with store._tx() as db:
            row=db.execute('SELECT status FROM history_jobs WHERE slot=1').fetchone()
            if row and row['status'] in ACTIVE: raise core.EditorialConflict('Já existe uma sincronização nesta conta.')
            db.execute("INSERT OR REPLACE INTO history_jobs VALUES(1,?,'queued',?,NULL,0)",(secrets.token_hex(16),json.dumps(data)))
        self.wake.set();return self.public_state(business)

    def cancel(self,business):
        store=self.publisher.store_for(business)
        with store._tx() as db:
            row=db.execute('SELECT data,status FROM history_jobs WHERE slot=1').fetchone()
            if row and row['status'] in ACTIVE:
                data=json.loads(row['data']);data['cancel']=True;data['message']='Cancelamento solicitado; aguardando a consulta atual terminar.'
                db.execute('UPDATE history_jobs SET data=? WHERE slot=1',(json.dumps(data),))
        self.wake.set();return self.public_state(business)

    @staticmethod
    def _guard(db,job,lease):
        row=db.execute('SELECT * FROM history_jobs WHERE slot=1').fetchone()
        if row is None or row['id']!=job or row['lease']!=lease or row['status'] not in ACTIVE:
            raise core.EditorialConflict('A sincronização mudou.')
        if json.loads(row['data']).get('cancel'): raise core.EditorialConflict('Cancelamento solicitado.')

    def _save(self,store,job,lease,data,status='running'):
        with store._tx() as db:
            row=db.execute('SELECT * FROM history_jobs WHERE slot=1').fetchone()
            if row is None or row['id']!=job or row['lease']!=lease: return
            if json.loads(row['data']).get('cancel'):
                data['cancel']=True;status='cancelled';data['message']='Sincronização cancelada. Registros e arquivos já importados foram mantidos.'
            db.execute('UPDATE history_jobs SET status=?,data=?,lease=NULL,lease_until=0 WHERE slot=1',(status,json.dumps(data)))

    def _upsert(self,store,item,account,job,lease):
        details={k:item[k] for k in ('caption','timestamp','kind','permalink')}
        details['seenAt']=int(time.time()*1000)
        with store._tx() as db:
            self._guard(db,job,lease)
            if db.execute("SELECT 1 FROM remote_deletions WHERE remote_id=? AND account_id=? AND status IN ('issued','unknown','confirmed')", (item['id'],account)).fetchone():
                return None
            row=db.execute("SELECT * FROM posts WHERE remote_id=? AND publication_account_id=? AND state='published' ORDER BY created_at LIMIT 1",(item['id'],account)).fetchone()
            created=row is None
            if created:
                if db.execute('SELECT COUNT(*) FROM posts').fetchone()[0]>=1000: raise core.EditorialError('Limite de 1000 publicações locais atingido.')
                post=secrets.token_hex(16)
                db.execute("INSERT INTO posts(id,format,caption,state,remote_id,created_at,publication_account_id,publication_phase,publication_data,source,remote_details) VALUES(?,?,?,'published',?,?,?,'done',?,'instagram',?)",
                           (post,item['format'],item['caption'],item['id'],item['timestamp'],account,json.dumps({'permalink':item['permalink']}),json.dumps(details)))
                store._audit(db,post,'created')
            else:
                post=row['id'];old=json.loads(row['remote_details']);old.pop('seenAt',None)
                compared=dict(details);compared.pop('seenAt',None)
                db.execute('UPDATE posts SET remote_details=? WHERE id=?',(json.dumps(details),post))
                if row['source']=='instagram': db.execute('UPDATE posts SET caption=?,format=? WHERE id=?',(item['caption'],item['format'],post))
                if old!=compared: store._audit(db,post,'history_updated')
            for media in item['media']:
                prior=db.execute('SELECT post_id FROM history_media WHERE remote_id=?',(media['id'],)).fetchone()
                if prior and prior[0]!=post: raise graph.PublishingError('invalid_response')
                existing=db.execute('SELECT media_id FROM attachments WHERE post_id=? AND position=?',(post,media['position'])).fetchone()
                state='done' if existing else 'pending'
                db.execute('''INSERT INTO history_media(remote_id,post_id,position,data,state,media_id) VALUES(?,?,?,?,?,?)
                    ON CONFLICT(remote_id) DO UPDATE SET data=excluded.data,
                    state=CASE WHEN history_media.media_id IS NULL THEN 'pending' ELSE history_media.state END''',
                    (media['id'],post,media['position'],json.dumps(media),state,existing[0] if existing else None))
        store.save_metrics(post,item['id'],values=item['values'])
        return created

    def _media(self,store,row,job,lease):
        item=json.loads(row['data']);created=None;thumbnail=False
        try:
            try: raw,ext=self.downloader(item['url'])
            except core.EditorialError:
                if not item.get('thumbnail'): raise
                raw,ext=self.downloader(item['thumbnail']);thumbnail=True
            with store._db() as db:
                self._guard(db,job,lease)
                existing=db.execute('SELECT id FROM media WHERE digest=? AND extension=?',(hashlib.sha256(raw).hexdigest(),ext)).fetchone()
            mid=existing[0] if existing else store.add_media(raw,ext)
            if not existing: created=mid
            with store._tx() as db:
                self._guard(db,job,lease)
                if not db.execute('SELECT 1 FROM posts WHERE id=?',(row['post_id'],)).fetchone(): raise core.EditorialConflict('Registro removido.')
                db.execute('INSERT OR IGNORE INTO attachments(post_id,media_id,position) VALUES(?,?,?)',(row['post_id'],mid,row['position']))
                db.execute("UPDATE history_media SET state='done',media_id=?,error=? WHERE remote_id=?",(mid,'Miniatura importada; original não baixado.' if thumbnail else '',row['remote_id']))
                store._audit(db,row['post_id'],'history_media_downloaded')
            return True
        except (core.EditorialError,graph.PublishingError):
            if created:
                try: store.delete_media(created)
                except core.EditorialError: pass
            with store._tx() as db:
                self._guard(db,job,lease)
                db.execute("UPDATE history_media SET state='skipped',error='Arquivo indisponível, inválido ou acima dos limites da biblioteca.' WHERE remote_id=?",(row['remote_id'],))
            return False

    def step(self,business):
        store=self.publisher.store_for(business);now=int(time.time());lease=secrets.token_hex(16)
        with store._tx() as db:
            row=db.execute("SELECT * FROM history_jobs WHERE slot=1 AND status IN ('queued','running') AND lease_until<=?",(now,)).fetchone()
            if row is None:return False
            job=row['id'];data=json.loads(row['data'])
            db.execute("UPDATE history_jobs SET status='running',lease=?,lease_until=? WHERE slot=1",(lease,now+90))
        try:
            if data.get('cancel'):
                self._save(store,job,lease,data);return True
            cfg,credential,identity=self.publisher._identity(business)
            if identity!=data['identity'] or cfg['instagram_account_id']!=data['account']:
                raise core.EditorialError('A conexão da conta mudou. Inicie uma nova sincronização para continuar.')
            api=self.publisher.api_factory(cfg,credential)
            if data['phase']=='pages':
                if data['pages']>=100: raise core.EditorialError('Limite de páginas atingido; sincronização incompleta.')
                try: page=api.history_page(data['after'],expanded=data['expanded'])
                except graph.PublishingError as error:
                    if not data['expanded'] or error.reason!='meta_rejected' or error.code not in (10,100,200): raise
                    data['expanded']=False;page=api.history_page(data['after'],expanded=False)
                rows=page.get('data')
                if not isinstance(rows,list) or len(rows)>25: raise graph.PublishingError('invalid_response')
                for raw in rows:
                    item=record(raw,now)
                    if item['id'] in data['remoteSeen']: continue
                    created=self._upsert(store,item,data['account'],job,lease)
                    data['remoteSeen'].append(item['id'])
                    data['seen']+=1;data['skipped' if created is None else 'imported' if created else 'updated']+=1
                data['pages']+=1
                paging=page.get('paging',{})
                if paging.get('next'):
                    if not rows: raise graph.PublishingError('invalid_response')
                    after=paging.get('cursors',{}).get('after')
                    if not isinstance(after,str) or not after or len(after)>8192: raise graph.PublishingError('invalid_response')
                    digest=hashlib.sha256(after.encode()).hexdigest()
                    if digest in data['cursors']: raise graph.PublishingError('invalid_response')
                    data['cursors'].append(digest);data['after']=after
                else:
                    with store._db() as db: data['totalFiles']=db.execute("SELECT COUNT(*) FROM history_media WHERE state='pending'").fetchone()[0]
                    data['phase']='media' if data['download'] and data['totalFiles'] else 'finish'
                data['message']=str(data['seen'])+' publicação(ões) consultada(s).'+(' Contagens adicionais não disponibilizadas pela Meta.' if not data['expanded'] else '')
            elif data['phase']=='media':
                with store._db() as db: pending=db.execute("SELECT * FROM history_media WHERE state='pending' ORDER BY post_id,position LIMIT 1").fetchone()
                if pending:
                    ok=self._media(store,pending,job,lease);data['processedFiles']+=1;data['files' if ok else 'skipped']+=1
                    data['message']='Mídias processadas: '+str(data['processedFiles'])+' de '+str(data['totalFiles'])+'.'
                else:data['phase']='finish'
            if data['phase']=='finish':
                data['checkedAt']=int(time.time()*1000)
                data['message']='Histórico sincronizado: '+str(data['seen'])+' publicação(ões); '+str(data['files'])+' arquivo(s) importado(s).'+(' '+str(data['skipped'])+' arquivo(s) com aviso.' if data['skipped'] else '')+(' Compartilhamentos e salvamentos não disponibilizados nesta conexão.' if not data['expanded'] else '')
                self._save(store,job,lease,data,'completed');return True
            self._save(store,job,lease,data)
        except core.EditorialConflict:
            data['message']='A sincronização foi interrompida porque os dados mudaram. Inicie novamente se necessário.'
            self._save(store,job,lease,data,'failed')
        except (core.EditorialError,graph.PublishingError) as error:
            data['message']=str(error) if isinstance(error,core.EditorialError) else 'Não foi possível consultar o histórico na Meta.'+(' Código Meta: '+str(error.code)+'.' if error.code is not None else '')
            self._save(store,job,lease,data,'failed')
        except Exception:
            data['message']='Sincronização interrompida. Os registros já importados foram mantidos; você pode sincronizar novamente.'
            self._save(store,job,lease,data,'failed')
        return True

    def run(self):
        while not self.stop.is_set():
            worked=False
            try: businesses=self.publisher.businesses()
            except Exception: businesses=[]
            for business in businesses:
                if self.stop.is_set():break
                try: worked=self.step(business) or worked
                except Exception: continue
            self.wake.wait(.05 if worked else 60);self.wake.clear()
