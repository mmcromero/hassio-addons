FROM ghcr.io/home-assistant/base:3.24
RUN apk add --no-cache python3 py3-cryptography py3-pillow tzdata
WORKDIR /app
COPY server.py origin_configuration.py panel_actions.py policy.py oauth_meta.py panel_login.py instagram_connection.py account_registry.py editorial_core.py editorial_http.py /app/
COPY editorial-ui/ /app/editorial-ui/
COPY tests/ /app/tests/
COPY tools/ /app/tools/
COPY proxy/instagram.conf /app/proxy/instagram.conf
COPY config.yaml /app/config.yaml
# The Supervisor runs this during an authorized device build: no external network.
RUN python3 -m py_compile server.py origin_configuration.py panel_actions.py policy.py oauth_meta.py panel_login.py instagram_connection.py account_registry.py editorial_core.py editorial_http.py tests/test_smoke.py tests/test_oauth_meta.py tests/test_http.py tests/test_panel_login.py tests/test_instagram_connection.py tests/test_account_registry.py tests/test_editorial_core.py tests/test_multicontas_integration.py \
    && python3 -m unittest discover -v -s tests -p 'test_*.py'
CMD ["python3", "-u", "/app/server.py"]
