# Offline validation stage: every Docker build must run the local regressions.
# No GitHub Actions and no credentials are required.
FROM alpine:3.23 AS validation
# Optional build-only CA for managed proxies; never disable TLS verification
# or copy the laboratory trust bundle into the runtime image.
RUN --mount=type=secret,id=build_ca \
    if [ -s /run/secrets/build_ca ]; then export SSL_CERT_FILE=/run/secrets/build_ca; fi; \
    apk add --no-cache python3 bash jq git bubblewrap su-exec
WORKDIR /app
COPY server.py autonomous_dev.py rc_fastlane.py sandbox_export.py run.sh /app/
COPY projects/ /app/projects/
COPY tests/ /app/tests/
RUN python3 -m py_compile /app/server.py /app/rc_fastlane.py /app/sandbox_export.py /app/autonomous_dev.py \
 && python3 -m unittest discover -s /app/tests -p 'test_factory_runner_*.py' -v

# Separate runtime image. No test suite or test credentials in final image.
FROM alpine:3.23
RUN --mount=type=secret,id=build_ca \
    if [ -s /run/secrets/build_ca ]; then export SSL_CERT_FILE=/run/secrets/build_ca; fi; \
    apk add --no-cache python3 bash jq git bubblewrap su-exec
RUN addgroup -S runner && adduser -S -D -H -G runner -s /sbin/nologin runner
WORKDIR /app
COPY --from=validation /app/server.py /app/autonomous_dev.py /app/rc_fastlane.py /app/sandbox_export.py /app/run.sh /app/
COPY --from=validation /app/projects/ /app/projects/
RUN chmod 0755 /app/run.sh
EXPOSE 9876
CMD ["/bin/bash", "/app/run.sh"]
