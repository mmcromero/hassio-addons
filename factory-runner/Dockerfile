# Offline validation stage: every Docker build must run the local regressions.
# No GitHub Actions and no credentials are required.
FROM alpine:3.23 AS validation
# Optional build-only CA for managed proxies; never disable TLS verification
# or copy the laboratory trust bundle into the runtime image.
RUN --mount=type=secret,id=build_ca \
    if [ -s /run/secrets/build_ca ]; then export SSL_CERT_FILE=/run/secrets/build_ca; fi; \
    apk add --no-cache python3 bash jq git bubblewrap su-exec
WORKDIR /app
COPY server.py autonomous_dev.py rc_fastlane.py sandbox_export.py declarative_export.py declarative_runtime_probe.py runtime_probe.py controlled_worker.py landlock_probe.py trusted_export_plan.py run.sh /app/
COPY projects/ /app/projects/
COPY tests/ /app/tests/
RUN chmod -R a+rX /app \
 && python3 -m py_compile /app/server.py /app/rc_fastlane.py /app/sandbox_export.py /app/declarative_export.py /app/declarative_runtime_probe.py /app/runtime_probe.py /app/controlled_worker.py /app/landlock_probe.py /app/trusted_export_plan.py /app/autonomous_dev.py \
 && python3 -m unittest discover -s /app/tests -p 'test_factory_runner_*.py' -v

# Separate runtime image. No test suite or test credentials in final image.
FROM alpine:3.23
RUN --mount=type=secret,id=build_ca \
    if [ -s /run/secrets/build_ca ]; then export SSL_CERT_FILE=/run/secrets/build_ca; fi; \
    apk add --no-cache python3 bash jq git bubblewrap su-exec
RUN addgroup -S runner && adduser -S -D -H -G runner -s /sbin/nologin runner
WORKDIR /app
COPY --from=validation /app/server.py /app/autonomous_dev.py /app/rc_fastlane.py /app/sandbox_export.py /app/declarative_export.py /app/runtime_probe.py /app/controlled_worker.py /app/landlock_probe.py /app/run.sh /app/
COPY --from=validation /app/projects/ /app/projects/
RUN test -r /app/declarative_runtime_probe.py && test -r /app/controlled_worker.py && test -r /app/landlock_probe.py && test -r /app/runtime_probe.py \
 && chmod -R a+rX /app && chmod 0755 /app/run.sh
EXPOSE 9876
CMD ["/bin/bash", "/app/run.sh"]
