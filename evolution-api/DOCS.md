# Guia de instalação e operação — Evolution API

## Requisitos

- Home Assistant OS com Supervisor em Raspberry Pi 4 de arquitetura `aarch64`.
- Memória e espaço em disco suficientes para Node.js, PostgreSQL e sessões.
- n8n acessível pela rede dos containers do Supervisor, se usar webhooks.
- Porta 8080 livre no host; verifique conflitos antes de instalar.

## Configuração no Home Assistant

| Opção | Obrigatória | Função |
| --- | --- | --- |
| `api_key` | Sim | Chave global privada da Evolution API |
| `server_url` | Sim | URL pela qual clientes acessam a API; padrão `http://homeassistant.local:8080` |
| `webhook_url` | Não | URL de entrada do n8n, por exemplo `http://homeassistant.local:5678/webhook/whatsapp` |

A opção `api_key` inicia vazia por segurança. Preencha antes de iniciar. Não envie a chave para logs, GitHub ou prints.

## Acesso

- API e Manager: `http://homeassistant.local:8080/manager` (ou IP real do host).
- O Home Assistant publica a porta 8080/tcp do add-on; **não** use encaminhamento de porta na Internet sem TLS e proteção de acesso.
- `homeassistant.local` pode não resolver de dentro do add-on. Se o webhook falhar, use um endereço realmente alcançável pelos containers (p. ex. IP local estável do HA) e valide no ambiente.
- No n8n, crie e ative um workflow Webhook com método e caminho compatíveis. A existência do serviço na porta 5678 não garante que o endpoint `/webhook/whatsapp` exista.
- Eventos globais habilitados quando `webhook_url` está preenchida: `MESSAGES_UPSERT`.

## Persistência

- `/data/postgres`: arquivos PostgreSQL.
- `/data/postgres-password`: senha local gerada no primeiro início.
- `/data/instances`: sessões da Evolution, via link de `/evolution/instances`.

O Supervisor preserva `/data` nas reinicializações normais, mas **não garante** por si só recuperação de sessões após falha, restauração incompatível ou mudanças do WhatsApp.

## Backup e atualização

Antes de atualizar, faça backup consistente com o serviço parado e inclua os três caminhos acima. Um backup comum dos arquivos enquanto PostgreSQL está gravando pode ser inconsistente. Faça ensaio de restauração. Não exclua o banco ou o arquivo de senha isoladamente.

Alterar a versão Alpine/PostgreSQL pode exigir migração de banco. Não atualize a tag de imagem nem o pacote PostgreSQL automaticamente. A imagem está fixada em `evoapicloud/evolution-api:v2.3.7`; o comportamento do QR ainda precisa de homologação.

## Verificação em Raspberry Pi 4

1. Conferir build `aarch64` e logs de inicialização do PostgreSQL.
2. Abrir Manager e validar acesso autenticado.
3. Criar instância, escanear QR e validar conexão real.
4. Enviar/receber texto e mídias previstas no uso real.
5. Receber webhook no n8n.
6. Reiniciar add-on e dispositivo; verificar preservação da sessão.
7. Fazer backup, restauração de teste e conferir os dados.

Não declarar o add-on estável até concluir esses testes.
