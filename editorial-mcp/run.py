"""Dedicated, unprivileged userspace Tailscale node; never uses the HA node/socket."""
import json
import os
import re
import signal
import subprocess
import threading
import time
from pathlib import Path
from server import make_server

STATE = Path('/data/editorial-mcp-tailnet')
RUNTIME = Path('/run/editorial-mcp')
SOCKET = RUNTIME / 'tailscaled.sock'
NODE = 'central-editorial-mcp'
PORT = 8765
STOP = threading.Event()


def cli(*args, **kwargs):
    return subprocess.run(['tailscale', '--socket='+str(SOCKET), *args], **kwargs)


def status():
    result = cli('status', '--json', capture_output=True, timeout=10)
    if result.returncode != 0 and not result.stdout:
        return {}
    try:
        return json.loads(result.stdout)
    except ValueError:
        return {}


def start():
    os.umask(0o077)
    opts = json.loads(Path('/data/options.json').read_text())
    origin = opts.get('central_url', '')
    # Validate before starting any tunnel. No host ports or Supervisor access.
    http = make_server(origin, port=PORT)
    daemon = None
    worker = None
    try:
        if opts.get('funnel_enabled') is True:
            STATE.mkdir(mode=0o700, parents=True, exist_ok=True)
            RUNTIME.mkdir(mode=0o700, parents=True, exist_ok=True)
            daemon = subprocess.Popen(['tailscaled', '--tun=userspace-networking',
                        '--socket='+str(SOCKET), '--state='+str(STATE/'tailscaled.state')],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            for _ in range(30):
                if daemon.poll() is not None: raise RuntimeError('Daemon dedicado parou')
                if SOCKET.exists(): break
                time.sleep(1)
            else: raise RuntimeError('Socket dedicado indisponível')
            current = status()
            if current.get('BackendState') != 'Running':
                print('Autorize SOMENTE o novo nó central-editorial-mcp pelo link de login abaixo, se solicitado.', flush=True)
                cli('up', '--hostname='+NODE, '--accept-routes=false', '--accept-dns=false',
                    '--ssh=false', '--netfilter-mode=off', '--timeout=600s', timeout=610, check=True)
                current = status()
            self_info = current.get('Self') or {}
            host = str(self_info.get('DNSName','')).rstrip('.').lower()
            if (current.get('BackendState') != 'Running' or self_info.get('HostName') != NODE or
                    not re.fullmatch(r'[a-z0-9.-]+\.ts\.net', host)):
                raise RuntimeError('Identidade dedicada ou nome HTTPS não confirmados')
            http.allowed_hosts.update({host, host+':443'})
            http.allowed_origins.add('https://'+host)
        worker = threading.Thread(target=http.serve_forever, daemon=True)
        worker.start()
        if daemon:
            print('Ativando Funnel somente no nó dedicado, porta 443, destino loopback 8765.', flush=True)
            cli('funnel', '--bg', '--https=443', str(PORT), timeout=120, check=True)
            print('Funnel aceito pelo CLI; URL candidata (acesso externo ainda não testado): https://'+host+'/mcp', flush=True)
        else:
            print('MCP local iniciado; Funnel desativado. Sem exposição pública.', flush=True)
        while not STOP.wait(1):
            if not worker.is_alive() or (daemon and daemon.poll() is not None):
                raise RuntimeError('Processo dedicado interrompido')
    finally:
        if worker and worker.is_alive(): http.shutdown()
        http.server_close()
        if worker: worker.join(timeout=3)
        if daemon and daemon.poll() is None:
            daemon.terminate()
            try: daemon.wait(timeout=5)
            except subprocess.TimeoutExpired: daemon.kill(); daemon.wait()


if __name__ == '__main__':
    signal.signal(signal.SIGTERM, lambda *_: STOP.set())
    signal.signal(signal.SIGINT, lambda *_: STOP.set())
    try:
        start()
    except Exception as exc:
        print('MCP não iniciado: '+type(exc).__name__+'. Confira origem HTTPS, autorização do nó e Funnel nos logs locais.', flush=True)
        raise SystemExit(1)
