"""Bounded, read-only Google Drive transport. No URLs or file paths from the client."""
import hashlib
import json
import re
import time

from editorial_connections import DRIVE_ID, Denied

MAX_BYTES = 4 * 1024 * 1024
MIMES = ('image/png', 'image/jpeg', 'video/mp4')
FOLDER = 'application/vnd.google-apps.folder'
_FIELDS = 'id,name,mimeType,size,parents,trashed,version,sha256Checksum,capabilities(canDownload),permissions(type,role)'


def valid_id(value):
    return isinstance(value, str) and DRIVE_ID.fullmatch(value) is not None


def manifest(item):
    if (not isinstance(item, dict) or set(item) != {'fileId', 'mime', 'bytes', 'sha256'}
            or not valid_id(item['fileId']) or item['mime'] not in MIMES
            or type(item['bytes']) is not int or not 1 <= item['bytes'] <= MAX_BYTES
            or not isinstance(item['sha256'], str) or not re.fullmatch(r'[0-9a-f]{64}', item['sha256'])):
        raise Denied('Manifesto de arquivo Drive inválido.')
    return item


class Reader:
    """Transport object constructed with an administrator-supplied service account."""
    def __init__(self, session):
        self.session = session

    def get(self, fid, *, media=False, limit=65536):
        if not valid_id(fid):
            raise Denied('Arquivo Drive inválido.')
        params = {'supportsAllDrives': 'true'}
        params.update({'alt': 'media'} if media else {'fields': _FIELDS})
        try:
            with self.session.get('https://www.googleapis.com/drive/v3/files/' + fid,
                                  params=params, stream=True, allow_redirects=False,
                                  timeout=(5, 8)) as response:
                if response.status_code != 200:
                    raise Denied('Arquivo Drive indisponível ou acesso recusado.')
                output = bytearray()
                deadline = time.monotonic() + 12
                for chunk in response.iter_content(65536):
                    if len(output) + len(chunk) > limit or time.monotonic() > deadline:
                        raise Denied('Arquivo Drive acima do limite ou leitura interrompida.')
                    output.extend(chunk)
            return bytes(output) if media else json.loads(output)
        except Denied:
            raise
        except Exception:
            raise Denied('Não foi possível ler o Drive privado.') from None


def _folder(record, fid):
    if (not isinstance(record, dict) or record.get('id') != fid
            or record.get('mimeType') != FOLDER or record.get('trashed') is not False):
        raise Denied('Pasta Drive inválida.')
    _reject_broad(record)


def _reject_broad(record):
    # A reader may not receive all permission metadata. Do not assert privacy
    # from omissions; the installation owner must restrict the folder ACL.
    if any(p.get('type') in ('anyone', 'domain') for p in record.get('permissions', [])
           if isinstance(p, dict)):
        raise Denied('Arquivo ou pasta com compartilhamento amplo recusado.')


def read_verified(reader, root, account, item):
    manifest(item)
    if not valid_id(root):
        raise Denied('Pasta Drive ainda não configurada para esta conexão.')
    root_info = reader.get(root)
    _folder(root_info, root)
    file_id, size = item['fileId'], item['bytes']
    before = reader.get(file_id)
    if (not isinstance(before, dict) or before.get('id') != file_id
            or before.get('mimeType') != item['mime'] or before.get('trashed') is not False
            or before.get('size') != str(size) or not isinstance(before.get('version'), str)
            or before.get('capabilities', {}).get('canDownload') is not True):
        raise Denied('Metadados Drive não correspondem ao arquivo aprovado.')
    _reject_broad(before)
    parents = before.get('parents')
    if not isinstance(parents, list) or len(parents) != 1 or not valid_id(parents[0]) or parents[0] == root:
        raise Denied('Coloque o arquivo na subpasta da conta autorizada.')
    folder = reader.get(parents[0])
    _folder(folder, parents[0])
    if folder.get('parents') != [root] or folder.get('name') != account:
        raise Denied('Arquivo fora da pasta da conta autorizada.')
    checksum = before.get('sha256Checksum')
    if checksum is not None and checksum != item['sha256']:
        raise Denied('SHA-256 do Drive diferente do manifesto.')
    raw = reader.get(file_id, media=True, limit=size + 1)
    if len(raw) != size or hashlib.sha256(raw).hexdigest() != item['sha256']:
        raise Denied('Bytes recebidos não correspondem ao arquivo aprovado.')
    # Re-read both objects to catch changes to content/placement during download.
    after, parent_after = reader.get(file_id), reader.get(parents[0])
    root_after = reader.get(root)
    # Comparing versions and metadata conservatively fails closed on file moves.
    if after != before or parent_after != folder or root_after != root_info:
        raise Denied('O arquivo ou sua pasta mudou durante a leitura; confirme novamente.')
    return raw


def download(service_account_json, root, account, item):
    if not isinstance(service_account_json, str) or not service_account_json or len(service_account_json) > 65536:
        raise Denied('Identidade técnica do Drive ainda não configurada.')
    try:
        import requests
        from google.oauth2 import service_account
        from google.auth.transport.requests import AuthorizedSession, Request
        info = json.loads(service_account_json)
        if (not isinstance(info, dict) or info.get('type') != 'service_account'
                or info.get('token_uri') != 'https://oauth2.googleapis.com/token'
                or not re.fullmatch(r'[A-Za-z0-9._-]+@[A-Za-z0-9.-]+\.gserviceaccount\.com', info.get('client_email', ''))
                or info.get('universe_domain', 'googleapis.com') != 'googleapis.com'):
            raise Denied('Identidade técnica do Drive inválida.')
        credentials = service_account.Credentials.from_service_account_info(
            info, scopes=['https://www.googleapis.com/auth/drive.readonly'])
        with requests.Session() as auth_session:
            auth_session.trust_env = False
            with AuthorizedSession(credentials, auth_request=Request(session=auth_session),
                                   max_refresh_attempts=0, refresh_timeout=8) as session:
                session.trust_env = False
                return read_verified(Reader(session), root, account, item)
    except Denied:
        raise
    except Exception:
        raise Denied('Não foi possível autenticar a identidade técnica do Drive.') from None
