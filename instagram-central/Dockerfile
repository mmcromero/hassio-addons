FROM ghcr.io/home-assistant/base:3.24
RUN apk add --no-cache python3
WORKDIR /app
COPY server.py panel_actions.py policy.py /app/
COPY tests/test_smoke.py /app/test_smoke.py
# The Supervisor runs this during an authorized device build: no external network.
RUN python3 -m py_compile server.py panel_actions.py policy.py test_smoke.py \
    && python3 -m unittest -v test_smoke
CMD ["python3", "-u", "/app/server.py"]
