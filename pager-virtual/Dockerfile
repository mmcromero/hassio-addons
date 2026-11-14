ARG BUILD_FROM=ghcr.io/home-assistant/aarch64-base:latest
FROM $BUILD_FROM

# Instala Node.js, npm e ferramentas de compilação C++ necessárias para SQLite WAL
RUN apk add --no-cache \
    nodejs \
    npm \
    python3 \
    make \
    g++

WORKDIR /app

# Copia manifestos de pacotes
COPY package.json ./

# Instala dependências de produção compilando o better-sqlite3 nativamente para ARM64
RUN npm install --omit=dev

# Copia código-fonte da aplicação
COPY src/ ./src/
COPY run.sh /run.sh

RUN chmod a+x /run.sh

# Porta padrão de escuta
EXPOSE 8095

# Variável de apontamento para armazenamento persistente no Home Assistant
ENV DATA_PATH="/data"

CMD [ "/run.sh" ]
