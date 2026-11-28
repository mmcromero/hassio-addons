"""Load Home Assistant app options without writing secrets to the repository."""
import json
import os
import runpy

with open("/data/options.json", "r", encoding="utf-8") as handle:
    options = json.load(handle)

mapping = {
    "filebrowser_url": "FILEBROWSER_URL",
    "filebrowser_api_token": "FILEBROWSER_API_TOKEN",
    "filebrowser_expected_username": "FILEBROWSER_EXPECTED_USERNAME",
    "filebrowser_expected_scope": "FILEBROWSER_EXPECTED_SCOPE",
    "filebrowser_source": "FILEBROWSER_SOURCE",
    "bridge_api_key": "BRIDGE_API_KEY",
    "audit_log": "AUDIT_LOG",
    "port": "PORT",
}
for source, target in mapping.items():
    if source in options and options[source] is not None:
        os.environ[target] = str(options[source])

runpy.run_path("/app/service.py", run_name="__main__")
