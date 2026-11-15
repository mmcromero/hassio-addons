"""Fixture do getter WebUI original do Home Assistant Supervisor 2026.01.1.
Origem: https://github.com/home-assistant/supervisor/blob/ec0f7c2b9ca3de7793fbbbcefa5bba5b9820efda/supervisor/addons/addon.py
SHA-256 do arquivo de origem: 90c22fd86fae820a06bf1ee20c306bf97f5860476b186be201e70af51423d725
RE_WEBUI e getter abaixo preservam o código original; apenas modelo/entrada são isolados.
Licença Apache-2.0: ver HA-SUPERVISOR-LICENSE.txt nesta pasta.
"""
import json
import re
import sys

RE_WEBUI = re.compile(
    r"^(?:(?P<s_prefix>https?)|\[PROTO:(?P<t_proto>\w+)\])"
    r":\/\/\[HOST\]:\[PORT:(?P<t_port>\d+)\](?P<s_suffix>.*)$"
)


class StoreModel:
    def __init__(self, data):
        self.template = data['webui']
        self.ports = data['ports']
        self.options = data.get('options', {})

    @property
    def webui(self):
        return self.template


class SupervisorAddon(StoreModel):
    @property
    def webui(self) -> str | None:
        """Return URL to webui or None."""
        url = super().webui
        if not url or not (webui := RE_WEBUI.match(url)):
            return None

        # extract arguments
        t_port = webui.group("t_port")
        t_proto = webui.group("t_proto")
        s_prefix = webui.group("s_prefix") or ""
        s_suffix = webui.group("s_suffix") or ""

        # search host port for this docker port
        if self.ports is None:
            port = t_port
        else:
            port = self.ports.get(f"{t_port}/tcp", t_port)

        # lookup the correct protocol from config
        if t_proto:
            proto = "https" if self.options.get(t_proto) else "http"
        else:
            proto = s_prefix

        return f"{proto}://[HOST]:{port}{s_suffix}"


if __name__ == '__main__':
    data = json.loads(sys.argv[1])
    value = SupervisorAddon(data).webui
    # [HOST] é preenchido pelo frontend; o hostname foi observado na captura real.
    print(value.replace('[HOST]', data['hostname']) if value else '')
