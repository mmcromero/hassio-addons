# Tag fixa: verificar upgrades e compatibilidade antes de alterar.
FROM --platform=linux/arm64 evoapicloud/evolution-api:v2.3.7

ARG BUILD_VERSION=0.1.0
LABEL io.hass.version="${BUILD_VERSION}" \
      io.hass.type="addon" \
      io.hass.arch="aarch64"

RUN apk add --no-cache postgresql postgresql-contrib jq su-exec \
    && rm -rf /evolution/instances \
    && ln -s /data/instances /evolution/instances

COPY run.sh /run.sh
RUN chmod 0755 /run.sh

EXPOSE 8080
ENTRYPOINT ["/bin/sh", "/run.sh"]
