#!/usr/bin/env python3
"""Generate a dedicated hostname on the existing NGINX HTTPS listener. Never install/reload."""
import argparse
from pathlib import Path
import re
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from origin_configuration import public_origin

HOST = re.compile(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)*\Z')


def generate(public_url, ha_host, upstream, certfile='fullchain.pem', keyfile='privkey.pem'):
    origin = public_origin({'public_base_url': public_url})
    if not origin:
        raise ValueError('public HTTPS origin required')
    from urllib.parse import urlsplit
    url = urlsplit(origin)
    if (not HOST.fullmatch(url.hostname) or not HOST.fullmatch(ha_host)
            or len(upstream) > 253 or not HOST.fullmatch(upstream)
            or url.hostname == ha_host):
        raise ValueError('dedicated hostname and valid upstream required')
    for name in (certfile, keyfile):
        if not re.fullmatch(r'[A-Za-z0-9_-][A-Za-z0-9_.-]*\.pem', name):
            raise ValueError('certificate filename must be a simple PEM filename')
    authority = url.netloc
    # Included at HTTP level via customize.servers, never customize.default.
    result = f'''# Central Instagram — generated, NOT installed; certificate SAN must cover {url.hostname}.
# /share/nginx_proxy/instagram.conf, via customize.servers (HTTP context).
# Reuses existing HTTPS listener 443 (external URL {origin}); no new public port.
limit_req_zone $binary_remote_addr zone=ig_central_login:1m rate=5r/m;
server {{
    listen 443 ssl;
    listen [::]:443 ssl;
    server_name {url.hostname};
    ssl_certificate /ssl/{certfile};
    ssl_certificate_key /ssl/{keyfile};
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_session_tickets off;
    access_log off;
    error_log /dev/null;
    server_tokens off;
    if ($http_host !~* "^{re.escape(authority)}$") {{ return 421; }}
    if ($ssl_server_name != "{url.hostname}") {{ return 421; }}
    add_header X-Content-Type-Options nosniff always;
    add_header X-Frame-Options DENY always;
    add_header Referrer-Policy no-referrer always;
    add_header Strict-Transport-Security "max-age=31536000" always;
    client_max_body_size 256k;
    client_header_timeout 15s;
    client_body_timeout 30s;
    keepalive_timeout 15s;
    proxy_http_version 1.1;
    proxy_set_header Host $http_host;
    proxy_set_header X-Forwarded-Proto https;
    proxy_set_header X-Forwarded-For $remote_addr;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-Host "";
    proxy_set_header X-Forwarded-Prefix "";
    proxy_set_header Forwarded "";
    proxy_set_header Connection "";
    proxy_redirect off;
    proxy_connect_timeout 5s;
    proxy_read_timeout 30s;
    proxy_buffering off;
    proxy_cache off;
'''
    routes = [('/', 'GET'), ('/panel', 'GET'), ('/panel/account-context', 'GET'),
              ('/panel/handoff', 'POST'), ('/panel/automation/policy', 'POST'), ('/panel/meta/check', 'POST'),
              ('/panel/meta/subscribe', 'POST'), ('/auth/login', 'POST'), ('/auth/logout', 'POST'),
              ('/oauth/meta/status', 'GET'), ('/oauth/meta/start', 'GET'),
              ('/oauth/meta/callback', 'GET'), ('/editorial', 'GET'), ('/editorial/', 'GET'),
              ('/editorial/editorial.js', 'GET'), ('/editorial/editorial.css', 'GET'),
              ('/editorial/api/csrf', 'GET'), ('/editorial/api/state', 'GET'),
              ('/editorial/api/drafts', 'POST'), ('/editorial/api/media', 'POST')]
    def location(selector, methods, extra=''):
        return (f'    location {selector} {{\n        limit_except {methods} {{ deny all; }}\n'
                + extra + f'        proxy_pass http://{upstream}:8099;\n    }}\n')
    for path, methods in routes:
        extra = ''
        if path == '/auth/login':
            extra = ('        client_max_body_size 4k;\n'
                     '        limit_req zone=ig_central_login burst=5 nodelay;\n'
                     '        limit_req_status 429;\n')
        if path == '/editorial/api/media': extra = '        client_max_body_size 25m;\n'
        if path == '/oauth/meta/callback': extra = '        proxy_read_timeout 60s;\n'
        result += location('= '+path, methods, extra)
    result += location('= /accounts', 'GET POST', '        client_max_body_size 4k;\n')
    account_id = r'[a-z][a-z0-9_-]{1,39}'
    result += location('~ "^/accounts/' + account_id + '$"', 'GET')
    for path, methods in routes:
        if path in ('/auth/login', '/oauth/meta/callback'):
            continue
        extra = '        client_max_body_size 25m;\n' if path == '/editorial/api/media' else ''
        result += location('~ "^/accounts/' + account_id + re.escape(path) + '$"', methods, extra)
    for stem in ('', '/accounts/' + account_id):
        result += location('~ "^' + stem + '/editorial/media/[0-9a-f]{32}$"', 'GET')
        result += location('~ "^' + stem + '/editorial/api/posts/[0-9a-f]{32}/(approve|schedule|cancel)$"', 'POST')
    return result + '    location / { return 404; }\n}\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--public-url', required=True)
    parser.add_argument('--ha-host', required=True)
    parser.add_argument('--upstream-host', required=True)
    parser.add_argument('--certfile', default='fullchain.pem')
    parser.add_argument('--keyfile', default='privkey.pem')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        result = generate(args.public_url, args.ha_host, args.upstream_host, args.certfile, args.keyfile)
    except ValueError as exc:
        parser.error(str(exc))
    with args.output.open('x', encoding='utf-8') as stream: stream.write(result)
    print('Candidate generated only. Verify certificate SAN, include and nginx -t before operator activation.')


if __name__ == '__main__': main()
