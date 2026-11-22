"""Loopback-only fake Meta publisher for browser validation. Never installed as runtime."""
from datetime import datetime, timedelta, timezone
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import sys
import threading
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server
from editorial_publishing import PublisherHub
from test_editorial_publishing import FakeMeta, png

server.DATA_DIR = Path(sys.argv[1]); server.DB_PATH = server.DATA_DIR/'instagram.sqlite3'
password = 'synthetic-browser-publication-password'
server.settings = lambda: {'instagram_account_id': '17841400000000001', 'panel_password': password,
    'meta_app_id': '17830000000000000', 'meta_app_secret': 'synthetic-only-secret',
    'meta_graph_version': 'v27.0', 'meta_oauth_enabled': False, 'ingress_enabled': False}
with server.database() as db:
    server.account_registry.ensure_primary(db, '17841400000000001')
    second = server.account_registry.provision(db, 'second_account', 'Segunda conta')
    server.account_registry.bind_verified(db, second, '17841400000000002', 'second_account')
def credentials(business='umdoislab'):
    cfg = server.meta_configuration_for_business(business)
    return {'business_id': business, 'account_id': cfg['instagram_account_id'],
            'username': cfg['instagram_expected_username'], 'verified_at': 1,
            'access_token': 'synthetic-browser-token-'+business}
server._meta_credential = credentials
meta = FakeMeta();meta.delivery = server.PUBLICATION_DELIVERY
hub = PublisherHub(server.meta_configuration_for_business, credentials, server.editorial_store_for_business,
    lambda: ['umdoislab', second], server.PUBLICATION_DELIVERY, api_factory=meta.client,
    checker=lambda *a, **k: {'origin': 'https://callback.example:8443', 'stories': True})
server.PUBLICATIONS = hub
for business, caption in [('umdoislab', 'Conteúdo da primeira conta'), (second, 'Conteúdo da segunda conta')]:
    store = server.editorial_store_for_business(business)
    mid = store.add_media(png(), 'png')
    post = store.save_draft('feed', caption, [mid]);store.approve(post)
    if business == 'umdoislab':
        legacy = store.save_draft('feed', 'Agendamento antigo sem autorização', [mid]);store.approve(legacy)
        store.schedule(legacy, datetime.now(timezone.utc)+timedelta(days=1))
class Handler(server.Handler):
    def do_POST(self):
        # Let Chromium report actual uploaded bytes while the server is still
        # validating/storing the synthetic file. This is a test fixture only.
        if self.path.endswith('/editorial/api/media'):
            time.sleep(.8)
        super().do_POST()
    def do_GET(self):
        if self.path == '/__publication_test':
            return self.respond(200, {'published': meta.published, 'calls': [item[:2] for item in meta.calls]})
        super().do_GET()
http = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
threading.Thread(target=hub.run, daemon=True).start()
print(json.dumps({'url': 'http://127.0.0.1:'+str(http.server_address[1]), 'second': second}), flush=True)
http.serve_forever()
