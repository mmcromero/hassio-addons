FROM ghcr.io/home-assistant/base-debian:bookworm

ARG BUILD_ARCH
ARG BUILD_VERSION
ARG DEBIAN_FRONTEND=noninteractive

LABEL \
  io.hass.type="app" \
  io.hass.arch="\${BUILD_ARCH}" \
  io.hass.version="\${BUILD_VERSION}"

RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl git gnupg python3 \
 && rm -rf /var/lib/apt/lists/*

RUN install -d -m 0755 /etc/apt/keyrings \
 && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key \
    | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
 && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg arch=$(dpkg --print-architecture)] https://deb.nodesource.com/node_22.x nodistro main" \
    > /etc/apt/sources.list.d/nodesource.list \
 && apt-get update \
 && apt-get install -y --no-install-recommends nodejs \
 && node --version \
 && npm --version \
 && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /opt/browser-tools /opt/pw-cache \
 && npm install --prefix /opt/browser-tools --no-save --no-package-lock --no-audit --no-fund playwright@1.57.0 \
 && PLAYWRIGHT_BROWSERS_PATH=/opt/pw-cache \
    /opt/browser-tools/node_modules/.bin/playwright install --with-deps chromium

ENV PLAYWRIGHT_BROWSERS_PATH=/opt/pw-cache
WORKDIR /app
COPY config.yaml /app/config.yaml
COPY server.js /app/server.js
COPY run-validation.sh /app/run-validation.sh
COPY git-askpass.sh /app/git-askpass.sh
COPY public/ /app/public/
RUN chmod 0755 /app/run-validation.sh /app/git-askpass.sh \
 && node --check /app/server.js

EXPOSE 8099
CMD ["node", "/app/server.js"]
