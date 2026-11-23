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
from funnel_probe import drain_daemon, collect_probes

STATE = Path('/data/editorial-mcp-tailnet')
RUNTIME = Path('/run/editorial-mcp')
SOCKET = RUNTIME / 'tailscaled.sock'
NODE = 'central-editorial-mcp'
PORT = 8765
STOP = threading.Event()


def sanitize_netcheck(output):
    """Return only coarse yes/no states; never emit IPs, ports, or DERP locations."""
    allowed = ('UDP', 'IPv4', 'IPv6', 'MappingVariesByDestIP', 'PortMapping')
    facts = []
    for line in output.splitlines():
        key, sep, value = line.partition(':')
        key = key.strip().lstrip('*').strip()
        if not sep or key not in allowed:
            continue
        normalized = value.strip().lower()
        if normalized.startswith('yes') or normalized in ('true', 'available'):
            state = 'yes'
        elif normalized.startswith('no') or normalized in ('false', 'unavailable', 'none'):
            state = 'no'
        elif key == 'PortMapping' and normalized:
            state = 'yes'
        else:
            state = 'unknown'
        facts.append(key+'='+state)
    return facts


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


def diagnostic(label, *args):
    """Emit only allowlisted health facts; never dump raw CLI output or peer identities."""
    try:
        result = cli(*args, capture_output=True, text=True, timeout=15)
        stdout = result.stdout or ''
        stderr = result.stderr or ''
        if label == 'version':
            match = re.search(r'([0-9]+\.[0-9]+\.[0-9]+)', stdout)
            print('DIAG version='+ (match.group(1) if match else 'unparsed') +
                  ' rc='+str(result.returncode), flush=True)
        elif label == 'status':
            try:
                data = json.loads(stdout)
            except (ValueError, TypeError):
                data = {}
            self_info = data.get('Self') or {}
            peers = data.get('Peer') or {}
            ingress = [p for p in peers.values()
                       if 'tag:ingress' in (p.get('Tags') or [])]
            online = sum(1 for p in ingress if p.get('Online') is True)
            capmap = self_info.get('CapMap') or {}
            funnel_cap = any('funnel' in str(key).lower() for key in capmap)
            print('DIAG status rc='+str(result.returncode)+
                  ' backend='+str(data.get('BackendState', 'unknown'))+
                  ' self_online='+str(self_info.get('Online', 'unknown'))+
                  ' self_name_ok='+str(self_info.get('HostName') == NODE)+
                  ' funnel_cap='+str(funnel_cap)+
                  ' ingress_peers='+str(len(ingress))+
                  ' ingress_online='+str(online), flush=True)
        elif label in ('funnel', 'serve'):
            low = stdout.lower()
            print('DIAG '+label+' rc='+str(result.returncode)+
                  ' output_present='+str(bool(stdout.strip()))+
                  ' says_funnel_on='+str('funnel on' in low)+
                  ' mentions_443='+str('443' in stdout)+
                  ' stderr_present='+str(bool(stderr.strip())), flush=True)
        elif label == 'netcheck':
            facts = sanitize_netcheck(stdout)
            print('DIAG netcheck rc='+str(result.returncode)+
                  ' '+(' '.join(facts) if facts else 'facts=unavailable'), flush=True)
    except Exception as exc:
        print('DIAG '+label+' error='+type(exc).__name__, flush=True)


def collect_diagnostics():
    diagnostic('version', 'version')
    diagnostic('status', 'status', '--json')
    diagnostic('funnel', 'funnel', 'status', '--json')
    diagnostic('serve', 'serve', 'status', '--json')
    diagnostic('netcheck', 'netcheck')


def diagnostics_enabled(options):
    """Missing option stays disabled for installations upgraded from 0.1.0."""
    return isinstance(options, dict) and options.get('diagnostics_enabled') is True


def daemon_command():
    # Tailscale v1.104.7 only derives VarRoot from --state when the parent
    # directory is named tailscale. Explicitly retain this app's private root.
    return ['tailscaled', '--tun=userspace-networking',
            '--socket='+str(SOCKET), '--state='+str(STATE/'tailscaled.state'),
            '--statedir='+str(STATE)]


def start():
    os.umask(0o077)
    opts = json.loads(Path('/data/options.json').read_text())
    origin = opts.get('central_url', '')
    collect_diagnostics_enabled = diagnostics_enabled(opts)
    # Validate before starting any tunnel. No host ports or Supervisor access.
    http = make_server(origin, port=PORT)
    daemon = None
    worker = None
    try:
        if opts.get('funnel_enabled') is True:
            STATE.mkdir(mode=0o700, parents=True, exist_ok=True)
            RUNTIME.mkdir(mode=0o700, parents=True, exist_ok=True)
            daemon = subprocess.Popen(daemon_command(),
                        stdout=subprocess.PIPE if collect_diagnostics_enabled else subprocess.DEVNULL,
                        stderr=subprocess.STDOUT, text=True, errors='replace')
            if collect_diagnostics_enabled:
                threading.Thread(target=drain_daemon, args=(daemon.stdout,), daemon=True).start()
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
            if collect_diagnostics_enabled:
                collect_diagnostics()
                threading.Thread(target=collect_probes, args=(cli, host, PORT), daemon=True).start()
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
