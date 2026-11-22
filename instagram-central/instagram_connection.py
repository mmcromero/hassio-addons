"""Meta Unified Login Graph calls for an Instagram professional account.

Only the fixed graph.facebook.com host is used. No Direct send, n8n or
WhatsApp API exists here. Provider responses and authorization tokens are
never logged or reflected to the browser.
"""
import json
import re
import time
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen, build_opener, HTTPRedirectHandler

MAX_GRAPH_RESPONSE = 64 * 1024
GRAPH_VERSION = re.compile(r"v[0-9]{1,2}\.0\Z")
IG_ACCOUNT = re.compile(r"[0-9]{8,30}\Z")


class _NoGraphRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_GRAPH_OPEN = build_opener(_NoGraphRedirect()).open


class ConnectionError(Exception):
    """Sanitized provider error, without credentials or response content."""


class GraphError(ConnectionError):
    """Only fixed categories and numeric provider codes may leave this module."""
    def __init__(self, reason, http_status=None, provider_code=None, provider_subcode=None):
        super().__init__('Meta diagnostic request failed')
        self.details = {'reason': reason, 'http_status': http_status,
                        'provider_code': provider_code, 'provider_subcode': provider_subcode}


def _graph_error(obj, http_status=None):
    error = obj.get('error') if isinstance(obj, dict) else None
    error = error if isinstance(error, dict) else {}
    number = lambda value: value if type(value) is int and 0 <= value <= 2**31-1 else None
    code, subcode = number(error.get('code')), number(error.get('error_subcode'))
    message = error.get('message')
    # Match a documented error only to produce a fixed label; never retain text.
    disabled = (isinstance(message, str) and 'disabled access' in message.lower()
                and 'messag' in message.lower() and 'instagram' in message.lower())
    reason = ('message_access_disabled' if disabled else 'token_invalid' if code == 190
              else 'permission_denied' if code in (10, 200)
              else 'unsupported_request' if code == 100 else 'provider_error')
    return GraphError(reason, http_status, code, subcode)


def request_graph(version, path, token, method="GET", fields=None, opener=urlopen, timeout=12):
    if not GRAPH_VERSION.fullmatch(str(version or "")):
        raise ConnectionError("Invalid Meta Graph version")
    if not isinstance(token, str) or not 20 <= len(token) <= 8192:
        raise ConnectionError("Token not configured")
    # Never accept a caller-provided host, URL or arbitrary Graph path.
    if path in ("/me/assigned_instagram_accounts", "/me"):
        if method != "GET":
            raise ConnectionError("Graph method not permitted")
    elif re.fullmatch(r"/[0-9]{8,30}/subscribed_apps", path) and method in ('GET', 'POST'):
        pass
    elif re.fullmatch(r"/[0-9]{8,30}/conversations", path) and method == 'GET':
        if fields != {'platform': 'instagram', 'fields': 'id', 'limit': '1'}:
            raise ConnectionError('Conversation diagnostic must not read message content')
    elif path == '/debug_token' and method == 'GET':
        if (not isinstance(fields, dict) or set(fields) != {'input_token'}
                or not isinstance(fields['input_token'], str)
                or not 20 <= len(fields['input_token']) <= 8192):
            raise ConnectionError('Invalid token diagnostic')
    elif re.fullmatch(r'/[0-9]{8,30}/subscriptions', path) and method == 'GET':
        if fields not in (None, {}):
            raise ConnectionError('Invalid app subscription diagnostic')
    else:
        raise ConnectionError("Graph request not permitted")
    if method not in ("GET", "POST"):
        raise ConnectionError("Graph method not permitted")
    if fields is None:
        fields = {}
    if not isinstance(fields, dict):
        raise ConnectionError("Invalid Graph fields")
    params = urlencode(fields)
    url = "https://graph.facebook.com/" + version + path
    data = None
    if method == "GET":
        if params:
            url += "?" + params
    else:
        data = params.encode("ascii")
    req = Request(url, data=data, method=method, headers={
        "Authorization": "Bearer " + token,
        "Accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded"})
    try:
        # Never forward a token/app secret to a redirect destination.
        open_request = _GRAPH_OPEN if opener is urlopen else opener
        with open_request(req, timeout=timeout) as response:
            raw = response.read(MAX_GRAPH_RESPONSE + 1)
        if len(raw) > MAX_GRAPH_RESPONSE:
            raise GraphError('invalid_response')
        obj = json.loads(raw)
    except ConnectionError:
        raise
    except (ValueError, UnicodeError):
        raise GraphError('invalid_response') from None
    except HTTPError as exc:
        try:
            raw = exc.read(MAX_GRAPH_RESPONSE + 1)
            obj = json.loads(raw) if len(raw) <= MAX_GRAPH_RESPONSE else None
        except Exception:
            obj = None
        finally:
            exc.close()
        raise _graph_error(obj, exc.code) from None
    except Exception:
        raise GraphError('transport_error') from None
    if not isinstance(obj, dict) or "error" in obj:
        raise _graph_error(obj)
    return obj


def diagnose_receiving(cfg, credential):
    """Read only this verified account's subscription and one conversation ID.

    Provider results, conversation IDs and unrelated apps are never returned.
    No sends, subscription writes, routing changes, or provider URL pagination.
    """
    account_id = cfg.get('instagram_account_id')
    app_id = cfg.get('meta_app_id')
    report = {'checked_at': int(time.time()), 'subscription': {'status': 'unknown'},
              'conversations': {'status': 'unknown'}}
    if (not credential_status(credential, cfg)['account_verified']
            or not IG_ACCOUNT.fullmatch(str(account_id or ''))
            or not IG_ACCOUNT.fullmatch(str(app_id or ''))):
        report['subscription']['reason'] = 'configuration_incomplete'
        report['conversations']['reason'] = 'configuration_incomplete'
        return report
    token, version = credential.get('access_token'), cfg.get('meta_graph_version')
    for key, path, fields in (
            ('subscription', '/' + account_id + '/subscribed_apps',
             {'fields': 'app_id,subscribed_fields', 'limit': '100'}),
            ('conversations', '/' + account_id + '/conversations',
             {'platform': 'instagram', 'fields': 'id', 'limit': '1'})):
        try:
            data = request_graph(version, path, token, fields=fields, timeout=5)
            entries = data.get('data')
            if not isinstance(entries, list) or len(entries) > (100 if key == 'subscription' else 1):
                raise GraphError('invalid_response')
            if key == 'conversations':
                if any(not isinstance(item, dict) or not isinstance(item.get('id'), str)
                       or not 1 <= len(item['id']) <= 256 for item in entries):
                    raise GraphError('invalid_response')
                report[key] = {'status': 'confirmed', 'conversation_found': bool(entries)}
                continue
            matches = [item for item in entries if isinstance(item, dict) and item.get('app_id') == app_id]
            if len(matches) > 1:
                raise GraphError('invalid_response')
            if not matches:
                # No match in an incomplete page is not proof of absence.
                paging = data.get('paging')
                incomplete = (paging is not None and (not isinstance(paging, dict) or bool(paging.get('next'))))
                malformed = any(not isinstance(item, dict) or not isinstance(item.get('app_id'), str)
                                for item in entries)
                report[key] = {'status': 'unknown' if incomplete or malformed else 'absent'}
                continue
            subscribed = matches[0].get('subscribed_fields')
            if (not isinstance(subscribed, list) or len(subscribed) > 100
                    or any(not isinstance(field, str) or len(field) > 100 for field in subscribed)):
                raise GraphError('invalid_response')
            report[key] = {'status': 'confirmed', 'messages': 'messages' in subscribed}
        except GraphError as exc:
            report[key] = {'status': 'error', **exc.details}
        except ConnectionError:
            report[key] = {'status': 'error', 'reason': 'request_unavailable'}
    report.update(diagnose_app_metadata(cfg, credential))
    return report


def callback_origin(value):
    """Public origin only; never keep credentials, callback path or query values."""
    if not isinstance(value, str) or len(value) > 2048:
        raise GraphError('invalid_response')
    try:
        parsed = urlsplit(value)
        host, port = parsed.hostname, parsed.port
        if (parsed.scheme not in ('https', 'http') or parsed.username is not None
                or parsed.password is not None or not host or len(host) > 253
                or not all(re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', label)
                           for label in host.split('.'))):
            raise ValueError('Invalid callback')
        origin = parsed.scheme + '://' + host + (':' + str(port) if port is not None else '')
        return {'callback_origin': origin, 'callback_https': parsed.scheme == 'https',
                'callback_path_matches': parsed.path == '/webhook/instagram',
                'callback_extra': bool(parsed.query or parsed.fragment)}
    except ValueError:
        raise GraphError('invalid_response') from None


def diagnose_app_metadata(cfg, credential):
    """Read app/token metadata. Generic subscriptions may not expose Instagram.

    Absence here is unknown, not proof that the Dashboard has no subscription.
    The app credential exists only in memory and never replaces the OAuth token.
    """
    result = {key: {'status': 'unknown', 'reason': 'configuration_incomplete'}
              for key in ('token_metadata', 'app_subscription')}
    app_id, secret = cfg.get('meta_app_id'), cfg.get('meta_app_secret')
    if (not credential_status(credential, cfg)['account_verified']
            or not IG_ACCOUNT.fullmatch(str(app_id or ''))
            or not isinstance(secret, str) or not 16 <= len(secret) <= 128
            or any(char.isspace() for char in secret) or '|' in secret):
        return result
    app_credential = app_id + '|' + secret
    for key, path, fields in (
            ('token_metadata', '/debug_token', {'input_token': credential.get('access_token')}),
            ('app_subscription', '/' + app_id + '/subscriptions', None)):
        try:
            data = request_graph(cfg.get('meta_graph_version'), path, app_credential,
                                 fields=fields, timeout=5)
            if key == 'token_metadata':
                part = data.get('data')
                if not isinstance(part, dict) or type(part.get('is_valid')) is not bool:
                    raise GraphError('invalid_response')
                value = {'status': 'confirmed', 'token_is_valid': part['is_valid']}
                if 'app_id' in part:
                    if not isinstance(part['app_id'], str) or not IG_ACCOUNT.fullmatch(part['app_id']):
                        raise GraphError('invalid_response')
                    value['app_matches'] = part['app_id'] == app_id
                if 'scopes' in part:
                    scopes = part['scopes']
                    if (not isinstance(scopes, list) or len(scopes) > 256
                            or any(not isinstance(scope, str) or len(scope) > 100 for scope in scopes)):
                        raise GraphError('invalid_response')
                    value.update(basic_granted='instagram_basic' in scopes,
                                 messages_granted='instagram_manage_messages' in scopes)
                result[key] = value
                continue
            entries = data.get('data')
            if not isinstance(entries, list) or len(entries) > 100:
                raise GraphError('invalid_response')
            matches = [item for item in entries if isinstance(item, dict) and item.get('object') == 'instagram']
            if not matches:
                result[key] = {'status': 'unknown', 'reason': 'app_subscription_not_exposed'}
                continue
            if len(matches) != 1:
                raise GraphError('invalid_response')
            part = matches[0]
            value = {'status': 'confirmed'}
            if 'active' in part:
                if type(part['active']) is not bool:
                    raise GraphError('invalid_response')
                value['active'] = part['active']
            if 'fields' in part:
                names = part['fields']
                if not isinstance(names, list) or len(names) > 100:
                    raise GraphError('invalid_response')
                names = [item.get('name') if isinstance(item, dict) else item for item in names]
                if any(not isinstance(name, str) or len(name) > 100 for name in names):
                    raise GraphError('invalid_response')
                value['messages'] = 'messages' in names
            if 'callback_url' in part:
                value.update(callback_origin(part['callback_url']))
            result[key] = value
        except GraphError as exc:
            result[key] = {'status': 'error', **exc.details}
        except ConnectionError:
            result[key] = {'status': 'error', 'reason': 'request_unavailable'}
    return result


def safe_diagnostics(report):
    """Strict output allowlist, including reports read back from local storage."""
    if (not isinstance(report, dict) or type(report.get('checked_at')) is not int
            or not 1 <= report['checked_at'] <= 4102444800):
        return None
    clean = {'checked_at': report['checked_at']}
    reasons = {'configuration_incomplete', 'invalid_response', 'message_access_disabled',
               'permission_denied', 'token_invalid', 'unsupported_request',
               'provider_error', 'transport_error', 'request_unavailable', 'app_subscription_not_exposed'}
    for key in ('subscription', 'conversations', 'token_metadata', 'app_subscription'):
        part = report.get(key)
        part = part if isinstance(part, dict) else {}
        status = part.get('status')
        value = {'status': status if status in ('confirmed', 'absent', 'unknown', 'error') else 'unknown'}
        if isinstance(part.get('reason'), str) and part['reason'] in reasons:
            value['reason'] = part['reason']
        for code in ('http_status', 'provider_code', 'provider_subcode'):
            if type(part.get(code)) is int and 0 <= part[code] <= 2**31-1:
                value[code] = part[code]
        for flag in ('messages', 'conversation_found', 'token_is_valid', 'app_matches',
                     'basic_granted', 'messages_granted', 'active', 'callback_https',
                     'callback_path_matches', 'callback_extra'):
            if type(part.get(flag)) is bool:
                value[flag] = part[flag]
        if key == 'app_subscription' and isinstance(part.get('callback_origin'), str):
            try:
                origin = callback_origin(part['callback_origin'])['callback_origin']
                # Stored input must be an origin already, not a URL to sanitize.
                if part['callback_origin'] == origin:
                    value['callback_origin'] = origin
            except GraphError:
                pass
        clean[key] = value
    return clean


def verify_access(cfg, token, opener=urlopen):
    """Check exact IG asset assigned to a Unified Login system-user token."""
    expected_id = cfg.get("instagram_account_id")
    discover = cfg.get('allow_account_discovery') is True and expected_id is None
    if not discover and (not isinstance(expected_id, str) or not IG_ACCOUNT.fullmatch(expected_id)):
        raise ConnectionError("Instagram account not configured")
    expected_username = str(cfg.get("instagram_expected_username") or "umdoislab").lower().lstrip("@")
    if not re.fullmatch(r'[a-z0-9._]{1,30}', expected_username):
        raise ConnectionError('Instagram account name not configured')
    version = cfg.get("meta_graph_version")
    candidates = {}
    after = None
    seen = set()
    complete = False
    for _ in range(20):
        fields = {"fields": "id,username", "limit": "100"}
        if after is not None:
            fields['after'] = after
        accounts = request_graph(version, "/me/assigned_instagram_accounts", token, fields=fields, opener=opener)
        entries = accounts.get("data")
        if not isinstance(entries, list) or len(entries) > 100:
            raise ConnectionError("Invalid Meta account list")
        for item in entries:
            if not isinstance(item, dict):
                continue
            item_id, username = item.get('id'), item.get('username')
            match = (isinstance(username, str) and username.lower().lstrip('@') == expected_username) if discover else item_id == expected_id
            if match:
                if not isinstance(item_id, str) or not IG_ACCOUNT.fullmatch(item_id):
                    raise ConnectionError('Invalid Instagram identity')
                candidates[item_id] = item
        paging = accounts.get('paging') or {}
        if not isinstance(paging, dict):
            raise ConnectionError('Invalid account pagination')
        cursors = paging.get('cursors') or {}
        if not isinstance(cursors, dict):
            raise ConnectionError('Invalid account pagination')
        cursor = cursors.get('after')
        if not entries or (not cursor and not paging.get('next')):
            complete = True
            break
        if not isinstance(cursor, str) or not 1 <= len(cursor) <= 2048 or cursor in seen:
            raise ConnectionError('Invalid or repeated account cursor')
        seen.add(cursor)
        after = cursor
    if not complete:
        raise ConnectionError('Account discovery exceeded safety limit')
    if len(candidates) != 1:
        raise ConnectionError("Expected Instagram account was not granted")
    match = next(iter(candidates.values()))
    expected_id, username = match['id'], match.get('username')
    if not isinstance(username, str) or username.lower().lstrip("@") != expected_username:
        raise ConnectionError("Instagram account name mismatch")
    business = request_graph(version, "/me", token,
        fields={"fields": "client_business_id"}, opener=opener)
    business_id = business.get("client_business_id")
    if not isinstance(business_id, str) or not IG_ACCOUNT.fullmatch(business_id):
        raise ConnectionError("Business portfolio access not verified")
    return {"business_id": cfg.get("business_id", "umdoislab"),
            "account_id": expected_id, "username": username,
            "client_business_id": business_id, "verified_at": int(time.time())}


def subscribe_messages(cfg, credential, opener=urlopen):
    """Opt-in subscribe only to messages; never sends customer messages."""
    account_id = cfg.get("instagram_account_id")
    if not isinstance(account_id, str) or not IG_ACCOUNT.fullmatch(account_id):
        raise ConnectionError("Instagram account not configured")
    if (not isinstance(credential, dict) or credential.get("account_id") != account_id
            or credential.get("business_id", "umdoislab") != cfg.get("business_id", "umdoislab")):
        raise ConnectionError("Account must be verified")
    if not (isinstance(cfg.get("meta_verify_token"), str) and len(cfg["meta_verify_token"]) >= 24
            and isinstance(cfg.get("meta_app_secret"), str) and len(cfg["meta_app_secret"]) >= 16
            and cfg.get("ingress_enabled") is True):
        raise ConnectionError("Webhook not enabled or verified")
    data = request_graph(cfg.get("meta_graph_version"),
        "/" + account_id + "/subscribed_apps", credential.get("access_token"),
        method="POST", fields={"subscribed_fields": "messages"}, opener=opener)
    if data.get("success") is not True:
        raise ConnectionError("Meta subscription was not accepted")
    return int(time.time())


def credential_status(credential, cfg):
    """Never claim live webhooks or messaging from the mere existence of a token."""
    if not isinstance(credential, dict):
        return {"account_verified": False, "subscription_requested": False}
    account_id = cfg.get("instagram_account_id")
    username = credential.get("username")
    verified = (credential.get("business_id", "umdoislab") == cfg.get("business_id", "umdoislab")
                and isinstance(account_id, str)
                and credential.get("account_id") == account_id
                and isinstance(username, str) and username.lower().lstrip("@") ==
                    str(cfg.get("instagram_expected_username") or "umdoislab").lower().lstrip("@")
                and isinstance(credential.get("verified_at"), int)
                and credential["verified_at"] > 0)
    return {"account_verified": bool(verified),
            "subscription_requested": bool(verified and credential.get("subscribed_at"))}
