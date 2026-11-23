"""Opt-in, bounded Funnel diagnostics. Never emit untrusted log text or keys."""
import http.client
import json
import socket
import ssl
import subprocess
import tempfile
from pathlib import Path


def classify(text):
    s = text.lower()
    if 'no tailscalevarroot' in s:
        return 'certificate_storage_missing'
    if any(x in s for x in ('rate limit', 'ratelimit', 'too many certificates', 'too many requests')):
        return 'rate_limit'
    if 'setdns' in s or 'dns-01' in s or 'dns record' in s:
        return 'dns_challenge'
    if 'certificate' in s or 'acme' in s or 'getcert' in s:
        if any(x in s for x in ('denied', 'not allowed', 'unauthorized', 'forbidden', 'disabled')):
            return 'certificate_policy'
        if any(x in s for x in ('error', 'failed', 'failure', 'unable', 'timeout', 'no certificate')):
            return 'certificate_error'
    if 'tls' in s and any(x in s for x in ('error', 'failed', 'alert', 'handshake')):
        return 'tls_error'
    return 'unclassified'


def drain_daemon(pipe):
    seen = set()
    try:
        for line in pipe:
            category = classify(line)
            if category != 'unclassified' and category not in seen:
                seen.add(category)
                print('DIAG daemon_event=' + category, flush=True)
    finally:
        pipe.close()


def serve_facts(raw, host, port):
    try:
        data = json.loads(raw)
        endpoint = host + ':443'
        tcp = (data.get('TCP') or {}).get('443') or {}
        web = (data.get('Web') or {}).get(endpoint) or {}
        handler = (web.get('Handlers') or {}).get('/') or {}
        proxy = handler.get('Proxy')
        return (tcp.get('HTTPS') is True,
                (data.get('AllowFunnel') or {}).get(endpoint) is True,
                proxy == 'http://127.0.0.1:' + str(port))
    except (ValueError, TypeError, AttributeError):
        return None


def probe_http(host, port):
    conn = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
    try:
        conn.request('GET', '/mcp', headers={'Host': host})
        return conn.getresponse().status
    except OSError:
        return 'unreachable'
    except http.client.HTTPException:
        return 'invalid_http'
    finally:
        conn.close()


def probe_tls(host):
    try:
        with socket.create_connection((host, 443), timeout=8) as tcp:
            # The first handshake may wait for ACME certificate acquisition.
            tcp.settimeout(75)
            with ssl.create_default_context().wrap_socket(tcp, server_hostname=host):
                return 'verified'
    except socket.gaierror:
        return 'dns_error'
    except ssl.SSLCertVerificationError:
        return 'certificate_verification_error'
    except ssl.SSLError:
        return 'tls_handshake_error'
    except TimeoutError:
        return 'timeout'
    except OSError:
        return 'connect_error'


def probe_cert(cli, host):
    # Once per opt-in startup, only after an observed TLS failure. May request a cert.
    # Files have a private temporary directory; no contents or CLI output are logged.
    with tempfile.TemporaryDirectory(prefix='editorial-cert-') as directory:
        cert = str(Path(directory) / 'cert.pem')
        key = str(Path(directory) / 'key.pem')
        try:
            result = cli('cert', '--cert-file='+cert, '--key-file='+key, host,
                         capture_output=True, text=True, timeout=90)
            if result.returncode != 0:
                return 'failed_' + classify((result.stderr or '') + (result.stdout or ''))
            if not (Path(cert).is_file() and Path(key).is_file()):
                return 'missing_output'
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(cert, key)
            return 'certificate_key_pair_ok'
        except subprocess.TimeoutExpired:
            return 'timeout'
        except (OSError, ssl.SSLError):
            return 'certificate_read_error'


def collect_probes(cli, host, port):
    print('DIAG loopback_http=' + str(probe_http(host, port)), flush=True)
    try:
        ips = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        print('DIAG dns_a=' + str(any(x[0] == socket.AF_INET for x in ips)) +
              ' dns_aaaa=' + str(any(x[0] == socket.AF_INET6 for x in ips)), flush=True)
    except OSError:
        print('DIAG dns_resolution=failed', flush=True)
    try:
        result = cli('funnel', 'status', '--json', capture_output=True, text=True, timeout=15)
        facts = serve_facts(result.stdout, host, port) if result.returncode == 0 else None
        print('DIAG funnel_config=' + ('unavailable' if facts is None else
              'https_443=%s public=%s loopback_target=%s' % facts), flush=True)
    except (OSError, subprocess.TimeoutExpired):
        print('DIAG funnel_config=unavailable', flush=True)
    tls = probe_tls(host)
    print('DIAG external_tls=' + tls, flush=True)
    if tls in ('tls_handshake_error', 'certificate_verification_error'):
        print('DIAG certificate_probe=' + probe_cert(cli, host), flush=True)
        print('DIAG external_tls_after_cert=' + probe_tls(host), flush=True)
