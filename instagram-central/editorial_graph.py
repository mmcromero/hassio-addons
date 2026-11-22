"""Account-bound publishing client. No arbitrary hosts or remote error bodies."""
import json
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, build_opener

import instagram_connection as connection

ID = re.compile(r"[0-9]{8,30}\Z")
VERSION = re.compile(r"v[0-9]{1,3}\.0\Z")
_OPEN = build_opener(connection._NoGraphRedirect()).open
MAX_RESPONSE = 64 * 1024


class PublishingError(Exception):
    def __init__(self, reason, *, code=None, subcode=None, ambiguous=False, stage=None):
        self.reason = reason
        self.code = code if type(code) is int else None
        self.subcode = subcode if type(subcode) is int else None
        self.ambiguous = ambiguous
        self.stage = stage
        super().__init__(reason)


def identifier(value):
    if not isinstance(value, str) or not ID.fullmatch(value):
        raise PublishingError('invalid_response')
    return value


class PublishingAPI:
    def __init__(self, cfg, credential, *, opener=None):
        self.account = identifier(cfg.get('instagram_account_id'))
        self.version = cfg.get('meta_graph_version')
        self.token = credential.get('access_token')
        if (not VERSION.fullmatch(str(self.version or '')) or
                not isinstance(self.token, str) or not 20 <= len(self.token) <= 8192 or
                not connection.credential_status(credential, cfg)['account_verified']):
            raise PublishingError('connection_required')
        self.opener = opener or _OPEN

    def _request(self, method, path, fields=None, *, stage=None, max_response=MAX_RESPONSE, timeout=12):
        params = urlencode(fields or {}).encode()
        url = 'https://graph.facebook.com/' + self.version + path
        if method == 'GET' and params:
            url += '?' + params.decode()
        request = Request(url, data=params if method == 'POST' else None, method=method,
                          headers={'Authorization': 'Bearer ' + self.token,
                                   'Content-Type': 'application/x-www-form-urlencoded'})
        try:
            with self.opener(request, timeout=timeout) as response:
                raw = response.read(max_response + 1)
            if len(raw) > max_response:
                raise ValueError()
            data = json.loads(raw)
            if not isinstance(data, dict) or 'error' in data:
                raise ValueError()
            return data
        except HTTPError as error:
            code = subcode = None
            try:
                raw = error.read(MAX_RESPONSE + 1)
                if len(raw) <= MAX_RESPONSE:
                    details = json.loads(raw).get('error', {})
                    code, subcode = details.get('code'), details.get('error_subcode')
            except (ValueError, TypeError, AttributeError, OSError):
                pass
            raise PublishingError('meta_rejected', code=code, subcode=subcode,
                                  ambiguous=error.code >= 500, stage=stage) from None
        except (URLError, TimeoutError, OSError):
            raise PublishingError('network_unavailable', ambiguous=True, stage=stage) from None
        except (ValueError, TypeError):
            raise PublishingError('invalid_response', ambiguous=True, stage=stage) from None

    def profile(self):
        # Facebook Login's IGUser does not document account_type. Request only
        # the identity fields already supported by this connection flow.
        data = self._request('GET', '/' + self.account, {'fields': 'id,username'}, stage='profile')
        if data.get('id') != self.account:
            raise PublishingError('account_mismatch')
        return data

    def check_delete(self, cfg, credential):
        """Read-only capability and live ownership checks, before any DELETE."""
        app = identifier(cfg.get('meta_app_id'))
        secret = cfg.get('meta_app_secret')
        if not isinstance(secret, str) or not 16 <= len(secret) <= 128 or '|' in secret or any(c.isspace() for c in secret):
            raise PublishingError('connection_required')
        try:
            token = connection.request_graph(self.version, '/debug_token', app + '|' + secret,
                fields={'input_token': self.token}, timeout=5).get('data')
        except connection.ConnectionError:
            raise PublishingError('check_unavailable', stage='delete') from None
        if not isinstance(token, dict) or token.get('is_valid') is not True or token.get('app_id') != app:
            raise PublishingError('token_invalid')
        scopes = token.get('scopes')
        if not isinstance(scopes, list) or not {'instagram_basic', 'instagram_manage_contents'} <= {s for s in scopes if isinstance(s, str)}:
            raise PublishingError('delete_permission_required')

    def check_media_owner(self, remote):
        remote = identifier(remote)
        data = self._request('GET', '/' + remote, {'fields': 'id,owner,username'}, stage='delete', timeout=6)
        if data.get('id') != remote:
            raise PublishingError('invalid_response', stage='delete')
        owner = data.get('owner')
        owner_id = owner.get('id') if isinstance(owner, dict) else owner
        if owner_id is not None:
            if owner_id != self.account:
                raise PublishingError('delete_owner_mismatch')
            return
        # Meta may omit owner. Compare with the current profile, never a stale
        # configured username or merely a token that can access several accounts.
        profile = self._request('GET', '/' + self.account, {'fields': 'id,username'}, stage='delete', timeout=6)
        username = profile.get('username')
        if (profile.get('id') != self.account or not isinstance(username, str) or not username or
                not isinstance(data.get('username'), str) or username.lower() != data['username'].lower()):
            raise PublishingError('delete_owner_mismatch')

    def delete_media(self, remote):
        remote = identifier(remote)
        result = self._request('DELETE', '/' + remote, stage='delete', timeout=6)
        if result.get('success') is not True or ('deleted_id' in result and result['deleted_id'] != remote):
            raise PublishingError('invalid_response', ambiguous=True, stage='delete')
        return True

    def check_limit(self):
        data = self._request('GET', '/' + self.account + '/content_publishing_limit',
                             {'fields': 'quota_usage,config'}, stage='limit')
        rows = data.get('data')
        if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
            raise PublishingError('invalid_response')
        usage = rows[0].get('quota_usage')
        total = rows[0].get('config', {}).get('quota_total')
        if type(usage) is not int or type(total) is not int or not 0 <= usage or total < 1:
            raise PublishingError('invalid_response')
        if usage >= total:
            raise PublishingError('publishing_limit')

    def metrics(self, remote, *, expanded=False):
        remote = identifier(remote)
        data = self._request('GET', '/' + remote, {'fields': 'id,like_count,comments_count'}, stage='metrics')
        if data.get('id') != remote:
            raise PublishingError('invalid_response', stage='metrics')
        result = {}
        for source, target in (('like_count', 'likes'), ('comments_count', 'comments')):
            value = data.get(source)
            if value is not None and (type(value) is not int or not 0 <= value <= 2**63-1):
                raise PublishingError('invalid_response', stage='metrics')
            result[target] = value
        if expanded:
            try:
                extra = self._request('GET', '/' + remote, {'fields': 'id,shares_count,saved_count'}, stage='metrics')
                if extra.get('id') != remote: raise PublishingError('invalid_response')
                result['extra'] = self._counts(extra, (('shares_count', 'shares'), ('saved_count', 'saves')))
                result['extraError'] = ''
            except PublishingError:
                result['extraError'] = 'A Meta não disponibilizou compartilhamentos e salvamentos nesta consulta.'
        return result

    @staticmethod
    def _counts(data, fields):
        result = {}
        for source, target in fields:
            value = data.get(source)
            if value is not None and (type(value) is not int or not 0 <= value <= 2**63-1):
                raise PublishingError('invalid_response')
            result[target] = value
        return result

    def history_page(self, after=None, *, expanded=False):
        fields = ('id,caption,media_type,media_product_type,timestamp,permalink,like_count,comments_count,'
                  'media_url,thumbnail_url,alt_text,children.limit(20){id,media_type,media_url,thumbnail_url,alt_text}')
        if expanded: fields += ',shares_count,saved_count'
        params = {'fields': fields, 'limit': '25'}
        if after:
            if not isinstance(after, str) or len(after) > 8192 or any(ord(c)<32 for c in after):
                raise PublishingError('invalid_response')
            params['after'] = after
        return self._request('GET', '/' + self.account + '/media', params, stage='history', max_response=1024*1024)

    def create(self, fields):
        allowed = {'image_url', 'video_url', 'caption', 'media_type', 'is_carousel_item', 'children'}
        if not fields or not set(fields) <= allowed:
            raise PublishingError('invalid_request')
        return identifier(self._request('POST', '/' + self.account + '/media', fields, stage='create').get('id'))

    def status(self, container):
        value = self._request('GET', '/' + identifier(container), {'fields': 'status_code'}, stage='status').get('status_code')
        if value not in ('IN_PROGRESS', 'FINISHED', 'ERROR', 'EXPIRED', 'PUBLISHED'):
            raise PublishingError('invalid_response', ambiguous=True)
        return value

    def permalink(self, remote):
        value = self._request('GET', '/' + identifier(remote), {'fields': 'permalink'}, stage='permalink').get('permalink')
        if isinstance(value, str) and len(value) < 400:
            parsed = urlsplit(value)
            if (parsed.scheme == 'https' and parsed.netloc in ('www.instagram.com', 'instagram.com')
                    and not parsed.query and not parsed.fragment
                    and re.fullmatch(r'/(p|reel|stories)/[A-Za-z0-9_/-]{3,250}', parsed.path)):
                return value
        return None

    def publish(self, container):
        # A lost/malformed response is ambiguous; the worker must reconcile it.
        value = self._request('POST', '/' + self.account + '/media_publish',
                              {'creation_id': identifier(container)}, stage='publish')
        try:
            return identifier(value.get('id'))
        except PublishingError:
            raise PublishingError('invalid_response', ambiguous=True) from None


def check_connection(cfg, credential, *, api_factory=PublishingAPI, graph=connection.request_graph):
    """GETs only. Do not infer App Review from scopes or require messaging."""
    api = api_factory(cfg, credential)
    app_id = identifier(cfg.get('meta_app_id'))
    secret = cfg.get('meta_app_secret')
    if not isinstance(secret, str) or not 16 <= len(secret) <= 128 or '|' in secret or any(c.isspace() for c in secret):
        raise PublishingError('connection_required')
    stage = 'token'
    try:
        token = graph(cfg['meta_graph_version'], '/debug_token', app_id + '|' + secret,
                      fields={'input_token': credential['access_token']}, timeout=5).get('data')
        if (not isinstance(token, dict) or token.get('is_valid') is not True or
                token.get('app_id') != app_id):
            raise PublishingError('token_invalid')
        scopes = token.get('scopes')
        if (not isinstance(scopes, list) or
                not {'instagram_basic', 'instagram_content_publish'} <= set(s for s in scopes if isinstance(s, str))):
            raise PublishingError('permission_required')
        stage = 'subscription'
        subscriptions = graph(cfg['meta_graph_version'], '/' + app_id + '/subscriptions',
                              app_id + '|' + secret, timeout=5).get('data')
    except connection.ConnectionError:
        raise PublishingError('check_unavailable', stage=stage) from None
    matches = [item for item in subscriptions if isinstance(item, dict) and item.get('object') == 'instagram'] if isinstance(subscriptions, list) else []
    if len(matches) != 1:
        raise PublishingError('delivery_not_configured')
    callback = connection.callback_origin(matches[0].get('callback_url'))
    if not callback.get('callback_https') or not callback.get('callback_path_matches') or callback.get('callback_extra'):
        raise PublishingError('delivery_not_configured')
    profile = api.profile()
    if str(profile.get('username', '')).lower() != str(cfg.get('instagram_expected_username', '')).lower().lstrip('@'):
        raise PublishingError('account_mismatch')
    kind = profile.get('account_type')
    # Unknown is not a negative capability. Meta enforces Story eligibility
    # when creating the container; do not block every account at preflight.
    stories = kind == 'BUSINESS' if kind in ('BUSINESS', 'MEDIA_CREATOR', 'CREATOR', 'PERSONAL') else None
    return {'origin': callback['callback_origin'], 'stories': stories}
