FROM tailscale/tailscale:v1.104.7
RUN apk add --no-cache python3 ca-certificates
WORKDIR /app
COPY server.py run.py test_server.py test_run_diagnostics.py test_host_file_bridge.py /app/
RUN python3 -m py_compile server.py run.py test_server.py test_run_diagnostics.py test_host_file_bridge.py
RUN python3 -m unittest -v test_server test_run_diagnostics test_host_file_bridge
RUN python3 -m unittest -v test_server test_run_diagnostics
ENTRYPOINT ["python3", "-u", "/app/run.py"]
