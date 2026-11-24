# Offline validation stage: every Docker build must run the local regressions.
# No GitHub Actions and no credentials are required.
FROM alpine:3.23 AS validation
# Optional build-only CA for managed proxies; never disable TLS verification
# or copy the laboratory trust bundle into the runtime image.
RUN --mount=type=secret,id=build_ca \
    if [ -s /run/secrets/build_ca ]; then export SSL_CERT_FILE=/run/secrets/build_ca; fi; \
    apk add --no-cache ca-certificates python3 bash jq git bubblewrap su-exec openssl
WORKDIR /app
COPY approval_service.py owner_ingress_service.py publisher_service.py publisher_ipc.py publisher_permissions.py publication_contract.py owner_approval.py approval_ipc.py owner_consent_ui.py github_bytes_transport.py publication_workflow.py artesao_artifacts.py release_receipt.py release_console.py local_publisher.py server.py autonomous_dev.py rc_fastlane.py artesao_adapter.py artesao_isolated_executor.py sandbox_export.py declarative_export.py declarative_workspace_probe.py declarative_runtime_probe.py factory_e2e_probe.py runtime_api_probe.py workspace_sync.py workspace_askpass.py runtime_probe.py controlled_worker.py landlock_probe.py trusted_export_plan.py ha_ingress_identity.py ha_ingress_server.py owner_bootstrap.py owner_settings_enroll.py run.sh /app/
COPY config.yaml /app/config.yaml
COPY projects/ /app/projects/
COPY tests/ /app/tests/
RUN addgroup -S runner && adduser -S -D -H -G runner -s /sbin/nologin runner && addgroup -S publisher && addgroup -S publisher_clients && addgroup runner publisher && addgroup runner publisher_clients
RUN chmod -R a+rX /app && chmod 0755 /app/workspace_askpass.py \
 && bash -n /app/run.sh \
 && python3 -m py_compile /app/owner_approval.py /app/approval_ipc.py /app/owner_consent_ui.py /app/github_bytes_transport.py /app/publication_workflow.py /app/approval_service.py /app/owner_ingress_service.py /app/publisher_service.py /app/publisher_ipc.py /app/publisher_permissions.py /app/artesao_artifacts.py /app/release_receipt.py /app/release_console.py /app/local_publisher.py /app/server.py /app/rc_fastlane.py /app/artesao_adapter.py /app/artesao_isolated_executor.py /app/sandbox_export.py /app/declarative_export.py /app/declarative_workspace_probe.py /app/declarative_runtime_probe.py /app/factory_e2e_probe.py /app/runtime_api_probe.py /app/workspace_sync.py /app/workspace_askpass.py /app/runtime_probe.py /app/controlled_worker.py /app/landlock_probe.py /app/trusted_export_plan.py /app/ha_ingress_identity.py /app/ha_ingress_server.py /app/owner_bootstrap.py /app/owner_settings_enroll.py /app/publisher_permissions.py /app/autonomous_dev.py \
 && python3 -m unittest discover -s /app/tests -p 'test_factory_runner_*.py' -v \
 && su-exec runner python3 -m unittest discover -s /app/tests -p 'test_factory_runner_workspace_sync.py' -v \
 && su-exec runner python3 -m unittest discover -s /app/tests -p 'test_factory_runner_e2e_probe.py' -v

# Separate runtime image. No test suite or test credentials in final image.
FROM alpine:3.23
RUN --mount=type=secret,id=build_ca \
    if [ -s /run/secrets/build_ca ]; then export SSL_CERT_FILE=/run/secrets/build_ca; fi; \
    apk add --no-cache ca-certificates python3 bash jq git bubblewrap su-exec openssl
RUN addgroup -S runner && adduser -S -D -H -G runner -s /sbin/nologin runner
WORKDIR /app
COPY --from=validation /app/publication_contract.py /app/owner_approval.py /app/approval_ipc.py /app/owner_consent_ui.py /app/github_bytes_transport.py /app/publication_workflow.py /app/release_receipt.py /app/release_console.py /app/server.py /app/autonomous_dev.py /app/rc_fastlane.py /app/artesao_adapter.py /app/sandbox_export.py /app/declarative_export.py /app/declarative_workspace_probe.py /app/declarative_runtime_probe.py /app/factory_e2e_probe.py /app/runtime_api_probe.py /app/workspace_sync.py /app/workspace_askpass.py /app/runtime_probe.py /app/controlled_worker.py /app/landlock_probe.py /app/ha_ingress_identity.py /app/ha_ingress_server.py /app/owner_bootstrap.py /app/owner_settings_enroll.py /app/approval_service.py /app/owner_ingress_service.py /app/publisher_service.py /app/publisher_ipc.py /app/publisher_permissions.py /app/run.sh /app/
COPY --from=validation /app/projects/ /app/projects/
RUN addgroup -S approval && adduser -S -D -H -G approval -s /sbin/nologin approval \
 && addgroup approval runner \
 && addgroup -S publisher && adduser -S -D -H -G publisher -s /sbin/nologin publisher \
 && addgroup -S publisher_clients \
 && addgroup publisher publisher_clients \
 && addgroup runner publisher \
 && addgroup -S owner_ui && adduser -S -D -H -G owner_ui -s /sbin/nologin owner_ui \
 && addgroup -S consent_clients && addgroup approval consent_clients && addgroup publisher consent_clients && addgroup owner_ui consent_clients && addgroup owner_ui runner && addgroup publisher runner && addgroup runner publisher_clients
RUN test -r /app/workspace_sync.py && test -r /app/workspace_askpass.py && test -r /app/declarative_workspace_probe.py && test -r /app/declarative_runtime_probe.py && test -r /app/factory_e2e_probe.py && test -r /app/runtime_api_probe.py && test -r /app/controlled_worker.py && test -r /app/landlock_probe.py && test -r /app/runtime_probe.py \
 && chmod -R a+rX /app && chmod 0755 /app/workspace_askpass.py && chmod 0755 /app/run.sh
EXPOSE 9876
CMD ["/bin/bash", "/app/run.sh"]
