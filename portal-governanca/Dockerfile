# Build completo dentro do Supervisor/Home Assistant: sem checkout irmão ou executor externo.
FROM node:22-alpine AS frontend-build
WORKDIR /build
COPY package.json package-lock.json ./
COPY vendor/design-system ./vendor/design-system
RUN npm ci
COPY index.html tsconfig.json vite.config.ts ./
COPY src ./src
COPY public ./public
COPY tests ./tests
COPY server ./server
COPY scripts ./scripts
COPY config ./config
COPY Dockerfile run.sh ./
COPY config.yaml ./
COPY icon.png logo.png ./
COPY BUILD-PROVENANCE.json ./
RUN npm run build:design-system
RUN npm test -- --reporter=default --reporter=json --outputFile=/build/vitest-results.json
RUN node -e 'const r=require("/build/vitest-results.json"); console.log("[Vitest] "+JSON.stringify({success:r.success,total:r.numTotalTests,passed:r.numPassedTests,failed:r.numFailedTests,pending:r.numPendingTests,suites:r.numTotalTestSuites,passedSuites:r.numPassedTestSuites,failedSuites:r.numFailedTestSuites}));'
RUN npm run build:portal
RUN node -e 'console.log("[Build environment] "+JSON.stringify({architecture:process.arch,node:process.version}));'
RUN node server/build-evidence.mjs

FROM node:22-alpine AS runtime
RUN apk add --no-cache bash su-exec jq \
 && addgroup -S portal \
 && adduser -S -D -H -G portal -s /sbin/nologin portal
WORKDIR /app
COPY --from=frontend-build --chown=portal:portal /build/dist/ /app/dist/
COPY --chown=portal:portal server/ /app/server/
COPY --chown=root:root config/portfolio.json /app/config/portfolio.json
COPY --chown=root:root config/home-assistant-addons.json /app/config/home-assistant-addons.json
COPY --chown=root:root run.sh /app/run.sh
RUN chmod 0755 /app/run.sh \
 && node --version \
 && node -e 'const v=process.versions.node.split(".").map(Number); if(v[0]<20||(v[0]===20&&v[1]<11)) process.exit(1)' \
 && node --check /app/server/index.mjs \
 && node --check /app/server/github.mjs \
 && node --check /app/server/ingress.mjs \
 && node --check /app/server/supervisor-data.mjs \
 && node --check /app/server/supervisor-bridge.mjs \
 && node --check /app/server/runner-bridge.mjs \
 && node --check /app/server/build-evidence.mjs \
 && test -s /app/dist/index.html
EXPOSE 8099
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
 CMD node -e "fetch('http://127.0.0.1:8099/healthz').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"
CMD ["/app/run.sh"]
