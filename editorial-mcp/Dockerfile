FROM tailscale/tailscale:v1.104.7
RUN apk add --no-cache python3 ca-certificates
WORKDIR /app
COPY server.py run.py funnel_probe.py test_server.py test_diagnostics.py test_host_file_bridge.py test_funnel_probe.py /app/
RUN python3 -m py_compile server.py run.py funnel_probe.py test_server.py test_diagnostics.py test_host_file_bridge.py test_funnel_probe.py
RUN python3 -m unittest -v test_server test_diagnostics test_host_file_bridge test_funnel_probe
ENTRYPOINT ["python3", "-u", "/app/run.py"]
