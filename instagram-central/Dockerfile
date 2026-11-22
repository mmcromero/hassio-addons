FROM ghcr.io/home-assistant/base:3.24
RUN apk add --no-cache python3 py3-cryptography py3-pillow tzdata
WORKDIR /app
COPY server.py origin_configuration.py panel_actions.py policy.py oauth_meta.py panel_login.py instagram_connection.py account_registry.py account_management.py editorial_core.py editorial_http.py editorial_graph.py editorial_delivery.py editorial_publishing.py /app/
COPY editorial-ui/ /app/editorial-ui/
COPY tests/ /app/tests/
COPY tools/ /app/tools/
COPY proxy/instagram.conf /app/proxy/instagram.conf
COPY config.yaml /app/config.yaml
# Fast device build: syntax smoke only. Run behavior checks in development,
# proportionate to the change; do not repeat the full suite on the HA device.
RUN python3 -m py_compile server.py origin_configuration.py panel_actions.py policy.py oauth_meta.py panel_login.py instagram_connection.py account_registry.py account_management.py editorial_core.py editorial_http.py editorial_graph.py editorial_delivery.py editorial_publishing.py
CMD ["python3", "-u", "/app/server.py"]
