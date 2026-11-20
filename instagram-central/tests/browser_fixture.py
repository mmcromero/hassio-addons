"""Loopback-only browser fixture. Synthetic data and no enabled integrations."""
import json
from pathlib import Path
import sys
from http.server import ThreadingHTTPServer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server

server.DATA_DIR = Path(sys.argv[1])
server.DB_PATH = server.DATA_DIR / "instagram.sqlite3"
server.settings = lambda: {"instagram_account_id": "synthetic-1", "panel_password": "browser_fixture_password_only_123",
                          "meta_oauth_enabled": False, "ingress_enabled": False, "drafts_enabled": False}
body = json.dumps({"object": "instagram", "entry": [{"messaging": [{"sender": {"id": "synthetic-customer"},
    "recipient": {"id": "synthetic-1"}, "message": {"mid": "synthetic-mid", "text": "Mensagem sintética para regressão"}}]}]}).encode()
server.persist(body, "synthetic-1")
http = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
print(json.dumps({"url": "http://127.0.0.1:" + str(http.server_address[1])}), flush=True)
http.serve_forever()
