FROM tailscale/tailscale:v1.104.7
RUN apk add --no-cache python3 ca-certificates
WORKDIR /app
COPY server.py run.py test_server.py /app/
RUN python3 -m py_compile server.py run.py test_server.py
ENTRYPOINT ["python3", "-u", "/app/run.py"]
