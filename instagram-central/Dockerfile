FROM ghcr.io/home-assistant/base:3.24
RUN apk add --no-cache python3 py3-cryptography
WORKDIR /app
COPY server.py panel_actions.py policy.py oauth_meta.py panel_login.py /app/
COPY tests/test_smoke.py tests/test_oauth_meta.py tests/test_http.py tests/test_panel_login.py /app/tests/
# The Supervisor runs this during an authorized device build: no external network.
RUN python3 -m py_compile server.py panel_actions.py policy.py oauth_meta.py panel_login.py tests/test_smoke.py tests/test_oauth_meta.py tests/test_http.py tests/test_panel_login.py \
    && python3 -m unittest discover -v -s tests -p 'test_*.py'
CMD ["python3", "-u", "/app/server.py"]
