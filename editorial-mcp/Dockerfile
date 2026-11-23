FROM tailscale/tailscale:v1.104.7
RUN apk add --no-cache python3 ca-certificates py3-cryptography
WORKDIR /app
COPY server.py run.py funnel_probe.py test_server.py test_multi_server.py test_diagnostics.py test_host_file_bridge.py test_funnel_probe.py test_share_pwa.py drive_queue.py test_drive_queue.py /app/
COPY share/ /app/share/
RUN python3 -m py_compile server.py run.py funnel_probe.py test_server.py test_multi_server.py test_diagnostics.py test_host_file_bridge.py test_funnel_probe.py test_share_pwa.py drive_queue.py test_drive_queue.py
RUN python3 -m unittest -v test_server test_multi_server test_diagnostics test_host_file_bridge test_funnel_probe test_share_pwa test_drive_queue
ENTRYPOINT ["python3", "-u", "/app/run.py"]
