#!/usr/bin/env python3
"""Generate only after the separate add-on's actual hostname is known."""
import argparse,re
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--upstream-host',required=True,help='Exact hostname shown in the installed pilot add-on information')
p.add_argument('--output',required=True,type=Path)
a=p.parse_args()
if not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)*',a.upstream_host) or len(a.upstream_host)>253:p.error('Invalid hostname; do not supply a URL, path or port.')
text='''# Include in the EXISTING default HTTPS server, through customize.default.
# Preserve prefix; this is not a standalone nginx.conf and contains no server block.
location = /artesaos-piloto {
    absolute_redirect off;
    return 308 /artesaos-piloto/;
}
location ^~ /artesaos-piloto/ {
    proxy_pass http://UPSTREAM:8099;
    proxy_http_version 1.1;
    proxy_set_header Host $http_host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-For $remote_addr;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_redirect off;
    proxy_connect_timeout 5s;
    proxy_read_timeout 60s;
    client_max_body_size 3m;
    # Authorization codes and search strings must not enter access logs.
    access_log off;
    error_log /dev/null crit;
}
'''.replace('UPSTREAM',a.upstream_host)
with a.output.open('x') as f:f.write(text)
print('Arquivo gerado. Valide com nginx -t no contexto do proxy antes de ativar.')
