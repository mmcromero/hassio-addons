# Evolution API — WhatsApp + n8n

Add-on experimental para Home Assistant OS em Raspberry Pi 4 ARM64.

Empacota **Evolution API v2.3.7**, PostgreSQL local e a API/Manager na porta TCP 8080. Não requer PostgreSQL ou Redis externos.

> **Não homologado:** suporte ARM64 da imagem está documentado; funcionamento do QR Code, sessões e acesso ao n8n ainda exige teste no equipamento real.

Configure uma `api_key` forte em **Configuração** antes de iniciar. Consulte [DOCS.md](DOCS.md) para portas, persistência, integração com n8n, backup e limitações.
