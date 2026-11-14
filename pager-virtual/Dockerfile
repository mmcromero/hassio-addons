FROM --platform=linux/arm64 node:20-alpine

RUN apk add --no-cache python3 make g++

WORKDIR /app

COPY package.json ./
RUN npm install --omit=dev

COPY src/ ./src/

ENV NODE_ENV=production
ENV DATA_PATH="/data"
ENV PORT=8095
ENV HOST=0.0.0.0

EXPOSE 8095

CMD ["node", "src/server.js"]
