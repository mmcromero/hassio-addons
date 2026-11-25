ARG BUILD_FROM
FROM ${BUILD_FROM}

RUN apk add --no-cache nodejs su-exec jq \
 && addgroup -S portal \
 && adduser -S -D -H -G portal -s /sbin/nologin portal

WORKDIR /app
COPY --chown=portal:portal dist/ /app/dist/
COPY --chown=portal:portal server/ /app/server/
COPY --chown=portal:portal config/portfolio.json /app/config/portfolio.json
COPY --chown=root:root run.sh /app/run.sh

RUN chmod 0755 /app/run.sh \
 && node --version \
 && node -e 'const v=process.versions.node.split(".").map(Number); if(v[0]<20||(v[0]===20&&v[1]<11)) process.exit(1)' \
 && node --check /app/server/index.mjs \
 && node --check /app/server/github.mjs \
 && node --check /app/server/ingress.mjs \
 && test -s /app/dist/index.html

EXPOSE 8099
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
 CMD node -e "fetch('http://127.0.0.1:8099/healthz').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"

CMD ["/app/run.sh"]
