#!/usr/bin/with-contenv bashio
# ==============================================================================
# Script de inicialização do Pager Virtual no Home Assistant OS
# ==============================================================================

bashio::log.info "Iniciando Pager Virtual no Raspberry Pi 4..."

# Lê configurações definidas na interface do Add-on do Home Assistant
export PORT=$(bashio::config 'port' '8095')
export LOG_LEVEL=$(bashio::config 'log_level' 'info')
export DATA_PATH="/data"

bashio::log.info "Porta configurada: ${PORT}"
bashio::log.info "Diretório de banco persistente: ${DATA_PATH}"

# Inicia o servidor Fastify da aplicação
cd /app
exec node src/server.js
