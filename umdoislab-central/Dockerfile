FROM ghcr.io/home-assistant/base:3.24
RUN apk add --no-cache python3
WORKDIR /app
COPY server.py /app/server.py
COPY accounts.py /app/accounts.py
COPY evolution_adapter.py /app/evolution_adapter.py
COPY n8n_outbox.py /app/n8n_outbox.py
COPY recovery_reconcile.py /app/recovery_reconcile.py
COPY evolution_history.py /app/evolution_history.py
COPY outgoing_verification.py /app/outgoing_verification.py
COPY recovery_worker.py /app/recovery_worker.py
COPY static /app/static
CMD ["python3", "-u", "/app/server.py"]
