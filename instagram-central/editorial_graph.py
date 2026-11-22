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
    def __init__(self, reason, *, code=None, subcode=None, ambiguous=False):
        self.reason = reason
        self.code = code if type(code) is int else None
        self.subcode = subcode if type(subcode) is int else None
        self.ambiguous = ambiguous
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

    def _request(self, method, path, fields=None):
        params = urlencode(fields or {}).encode()
        url = 'https://graph.facebook.com/' + self.version + path
        if method == 'GET' and params:
            url += '?' + params.decode()
        request = Request(url, data=params if method == 'POST' else None, method=method,
                          headers={'Authorization': 'Bearer ' + self.token,
                                   'Content-Type': 'application/x-www-form-urlencoded'})
        try:
            with self.opener(request, timeout=12) as response:
                raw = response.read(MAX_RESPONSE + 1)
            if len(raw) > MAX_RESPONSE:
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
                                  ambiguous=error.code >= 500) from None
        except (URLError, TimeoutError, OSError):
            raise PublishingError('network_unavailable', ambiguous=True) from None
        except (ValueError, TypeError):
            raise PublishingError('invalid_response', ambiguous=True) from None

    def profile(self):
        data = self._request('GET', '/' + self.account, {'fields': 'id,username,account_type'})
        if data.get('id') != self.account:
            raise PublishingError('account_mismatch')
        return data

    def check_limit(self):
        data = self._request('GET', '/' + self.account + '/content_publishing_limit',
                             {'fields': 'quota_usage,config'})
        rows = data.get('data')
        if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
            raise PublishingError('invalid_response')
        usage = rows[0].get('quota_usage')
        total = rows[0].get('config', {}).get('quota_total')
        if type(usage) is not int or type(total) is not int or not 0 <= usage or total < 1:
            raise PublishingError('invalid_response')
        if usage >= total:
            raise PublishingError('publishing_limit')

    def create(self, fields):
        allowed = {'image_url', 'video_url', 'caption', 'media_type', 'is_carousel_item', 'children'}
        if not fields or not set(fields) <= allowed:
            raise PublishingError('invalid_request')
        return identifier(self._request('POST', '/' + self.account + '/media', fields).get('id'))

    def status(self, container):
        value = self._request('GET', '/' + identifier(container), {'fields': 'status_code'}).get('status_code')
        if value not in ('IN_PROGRESS', 'FINISHED', 'ERROR', 'EXPIRED', 'PUBLISHED'):
            raise PublishingError('invalid_response', ambiguous=True)
        return value

    def permalink(self, remote):
        value = self._request('GET', '/' + identifier(remote), {'fields': 'permalink'}).get('permalink')
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
                              {'creation_id': identifier(container)})
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
        subscriptions = graph(cfg['meta_graph_version'], '/' + app_id + '/subscriptions',
                              app_id + '|' + secret, timeout=5).get('data')
    except connection.ConnectionError:
        raise PublishingError('check_unavailable') from None
    matches = [item for item in subscriptions if isinstance(item, dict) and item.get('object') == 'instagram'] if isinstance(subscriptions, list) else []
    if len(matches) != 1:
        raise PublishingError('delivery_not_configured')
    callback = connection.callback_origin(matches[0].get('callback_url'))
    if not callback.get('callback_https') or not callback.get('callback_path_matches') or callback.get('callback_extra'):
        raise PublishingError('delivery_not_configured')
    profile = api.profile()
    if str(profile.get('username', '')).lower() != str(cfg.get('instagram_expected_username', '')).lower().lstrip('@'):
        raise PublishingError('account_mismatch')
    return {'origin': callback['callback_origin'], 'stories': profile.get('account_type') == 'BUSINESS'}
