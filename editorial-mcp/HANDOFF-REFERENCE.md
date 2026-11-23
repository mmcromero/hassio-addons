# Continuidade — Central Editorial MCP universal

Este repositório contém o aplicativo MCP, mas o documento mestre da missão fica no repositório de integração.

**Antes de alterar código, leia o handoff completo:**
https://github.com/mmcromero/instagram-automacoes/blob/docs/ig-editorial-drive-bridge-001/docs/HANDOFF-IG-EDITORIAL-DRIVE-MCP-2026-11-22.md

## Estado de código e instalação no checkpoint de 22/11/2026
- Repo: mmcromero/hassio-addons.
- Branch de trabalho: feat/editorial-mcp-transport-001.
- Branch foi criada a partir de main e estava idêntica a main no momento da criação.
- Nenhum código do aplicativo foi alterado nesta branch neste checkpoint.
- App instalado no HA: Fábrica de Softwares - Central Editorial MCP, versão 0.1.0, estado started.
- Configuração lida: central_url=https://instagram.romeropi.duckdns.org:8443; funnel_enabled=false.
- Read Only Mode do HA-MCP está ativo, portanto o assistente não consegue alterar essa configuração.
- Próxima intervenção do proprietário: alterar somente funnel_enabled para true na configuração deste app, mantendo central_url. Depois conferir logs e autorizar apenas o nó dedicado central-editorial-mcp se houver solicitação Tailscale.
- Não modificar o Tailscale principal, HA-MCP, n8n, plugin ChatGPT ou API Central.
- Ainda não existe URL MCP externa homologada, conexão Claude, transferência de mídia por MCP ou recibo real.

## Arquivos de referência obrigatórios
- README.md — instalação, Funnel, configuração do Claude, contrato e segurança.
- CHANGELOG.md — escopo da versão 0.1.0.
- server.py — endpoint MCP e ferramentas.
- run.py — servidor local e nó Tailscale dedicado.
- test_server.py — testes automatizados a executar antes de qualquer release.

## Regras
- Não usar Codex.
- Não reutilizar os túneis OpenAI existentes.
- Não colocar chaves, links de login ou credenciais no Git ou no chat.
- Não publicar diretamente; transferências terminam em revisão.
- Antes de mudanças, registrar evidências iniciais. Depois, registrar testes, commit e resultado final.
- Não considerar iniciado/instalado como prova de acesso público ou compatibilidade real.
