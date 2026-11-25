FROM ghcr.io/home-assistant/base:3.24 AS runtime-base
RUN apk add --no-cache python3
WORKDIR /app
COPY server.py /app/server.py
COPY stage2_bridge.py /app/stage2_bridge.py
COPY accounts.py /app/accounts.py
COPY evolution_adapter.py /app/evolution_adapter.py
COPY n8n_outbox.py /app/n8n_outbox.py
COPY recovery_reconcile.py /app/recovery_reconcile.py
COPY evolution_history.py /app/evolution_history.py
COPY outgoing_verification.py /app/outgoing_verification.py
COPY recovery_worker.py /app/recovery_worker.py
COPY static /app/static
# The validation stage runs only during image build, never against the installed database.
FROM runtime-base AS validation
COPY test_accounts.py \
    test_central.py \
    test_central_lab_no_send.py \
    test_central_outbox_integration.py \
    test_dual_history.py \
    test_evolution_adapter.py \
    test_evolution_history.py \
    test_evolution_ingress.py \
    test_handoff_confirm.py \
    test_n8n_outbox.py \
    test_outgoing_pn_lid.py \
    test_outgoing_verification.py \
    test_recovery_reconcile.py \
    test_recovery_worker.py \
    test_scoped_recovery.py \
    test_stage2_server.py /app/
COPY tests/test_stage2_bridge.py /app/tests/test_stage2_bridge.py
RUN export CENTRAL_DATA_DIR=/tmp/central-stage2-validation-data CENTRAL_OPTIONS=/tmp/central-stage2-validation-options.json; \
    python3 -m py_compile /app/*.py /app/tests/test_stage2_bridge.py \
    && python3 -m unittest discover -s /app -p 'test_*.py' -v \
    && python3 -m unittest discover -s /app/tests -p 'test_stage2_bridge.py' -v \
    && echo PASS > /tmp/central-stage2-validation

# Copy the validation marker to make a successful validation stage mandatory.
# Test files and temporary databases do not enter the final runtime image.
FROM runtime-base AS runtime
COPY --from=validation /tmp/central-stage2-validation /app/.stage2-validation
CMD ["python3", "-u", "/app/server.py"]
