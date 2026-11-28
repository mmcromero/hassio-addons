FROM node:24.19.0-bookworm-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --strict-ssl=true
COPY . .
RUN mkdir -p dist && npm test && npm run build && node scripts/verify-ha-source-schema.mjs && npm prune --omit=dev --ignore-scripts --no-audit && \
    node scripts/verify-portable-runtime.mjs && \
    chmod -R a+rX /app/dist /app/dist-server /app/assets/fonts /app/node_modules && \
    chmod a+r /app/package.json /app/pilot-build.json

FROM node:24.19.0-bookworm-slim
LABEL org.opencontainers.image.revision="d20af4c496d515e6a252894ee6ef12f1ec5967ae" \
      org.opencontainers.image.version="0.2.0-dev.40" \
      org.opencontainers.image.created="2026-11-28T20:16:20.442Z" \
      org.opencontainers.image.source="https://github.com/mmcromero/fabricacao_e_orcamentos" \
      dev.artesao.distribution="home-assistant"
WORKDIR /app
ENV NODE_ENV=production DATA_DIR=/data HOST=0.0.0.0 PORT=8099 PILOT_OPTIONS_FILE=/data/options.json
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/package.json ./
COPY --from=build /app/release.json ./release.json
COPY --from=build /app/pilot-build.json ./pilot-build.json
COPY --from=build /app/dist ./dist
COPY --from=build /app/dist-server ./dist-server
COPY --from=build /app/assets/fonts ./assets/fonts
EXPOSE 8099
CMD ["node", "dist-server/pilot/index.js"]
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD ["node", "dist-server/pilot/healthcheck.js"]
