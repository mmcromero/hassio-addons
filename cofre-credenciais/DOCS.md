# Fábrica de Ideias — Cofre de Credenciais

Este pacote executa o Vaultwarden, servidor compatível com os clientes Bitwarden, no Home Assistant OS.

## Estado desta candidata

- Versão do pacote HA: `0.1.0-rc.1`
- Servidor: Vaultwarden `1.37.5`, imagem multi-arquitetura fixada por digest.
- Arquitetura declarada: `aarch64` e `amd64`.
- Persistência: `/data` (SQLite e anexos).
- Interface: não usa Home Assistant Ingress.
- Porta interna do serviço web: `7277/tcp`; mapeamento para a rede do host desativado por padrão.
- Acesso previsto: `https://romeropi.duckdns.org:8443/cofre`, reutilizando o domínio/certificado HTTPS já existentes e um include de rota no NGINX. A rota ainda precisa ser configurada e homologada.

## Proteções padrão

- Cadastro público de contas: desativado.
- Convites: desativados.
- Vaultwarden Send: desativado.
- Cadastro via SSO: desativado.
- Criação de organizações: desativada.
- Painel administrativo `/admin`: desativado.
- Nenhum token administrativo é gerado ou impresso nos logs.
- A porta 7277 não é publicada no host pelo manifesto.

**Não coloque credenciais reais nesta candidata.** A POC inicial deve usar apenas uma conta e dados fictícios até a homologação de HTTPS, autenticação, backup e restauração.

## Primeiro acesso — procedimento controlado

1. Concluir e testar a rota `https://romeropi.duckdns.org:8443/cofre` no NGINX existente antes de permitir o cadastro.
2. Na configuração do app, habilitar `allow_signups` temporariamente e reiniciar o app.
3. Abrir o hostname HTTPS e criar somente a conta do proprietário.
4. Ativar autenticação de dois fatores (TOTP) na conta e testar um segundo dispositivo.
5. Voltar à configuração do app, desabilitar `allow_signups` e reiniciar.
6. Confirmar que uma tentativa de novo cadastro é recusada.
7. Só depois de backup/restore e revisão independente aprovados considerar a migração de credenciais reais.

Não deixar `allow_signups` habilitado após criar a conta do proprietário.

## Configuração

- `ssl`: manter `false` quando o NGINX externo terminar TLS; a comunicação interna entre proxy e app será HTTP na rede privada de add-ons.
- `domain`: preencher com `https://romeropi.duckdns.org:8443/cofre` após adicionar e testar o include NGINX. O Vaultwarden 1.37.5 suporta o prefixo de caminho via `DOMAIN`.
- `request_size_limit`: limite de requisições JSON do Rocket; o limite de upload também deverá ser definido no vhost externo do NGINX.
- `log_level`: manter `info` em operação normal.

O app não oferece Ingress. Não habilitar acesso público direto à porta 7277. Não criar redirecionamento de porta no roteador. O certificado wildcard `*.romeropi.duckdns.org` já está configurado no DuckDNS; não é necessário emitir outro certificado para a rota proposta.

## Clientes

Use clientes Bitwarden compatíveis (desktop, extensão de navegador ou celular) e configure o servidor como auto-hospedado usando o hostname HTTPS definido. A compatibilidade da versão de cada cliente será validada durante a POC.

## Dados, backup e recuperação

Os dados do Vaultwarden ficam em `/data`. A configuração do app, isoladamente, não é backup do cofre. Antes de cadastrar qualquer credencial real, é obrigatório:
- incluir o volume de dados no plano de backup;
- gerar cópia criptografada fora do Home Assistant;
- testar restauração em ambiente isolado;
- conferir banco SQLite e anexos após a restauração;
- documentar recuperação em caso de perda da senha mestra ou comprometimento de dispositivo.

Não copiar `/data` para o Git, Issues, logs ou arquivos não criptografados.

## Origem e licenças

O empacotamento HA deriva do projeto Home Assistant Community App Vaultwarden, licenciado MIT, com alterações de configuração e inicialização identificadas no histórico deste catálogo. O servidor Vaultwarden é distribuído sob GNU AGPL v3. Os avisos e textos integrais estão nos arquivos `LICENSE-ADDON-MIT.md` e `LICENSE-VAULTWARDEN-AGPL-3.0.txt`.

- Wrapper HA: https://github.com/hassio-addons/app-vaultwarden
- Servidor: https://github.com/dani-garcia/vaultwarden
- Não é um produto oficial da Bitwarden, Inc.

## Homologação pendente

Build e inicialização no Raspberry Pi 4, acesso HTTPS via proxy, WebSocket, bloqueio de cadastro, MFA, consumo de recursos, persistência, backup/restore e atualização controlada.


## Estado de acesso — 28/11/2026

O Supervisor confirma NGINX 4.5.3 com domínio `romeropi.duckdns.org`, porta externa 8443 e include customizado ativo. DuckDNS confirma SAN `*.romeropi.duckdns.org`, válido até 19/02/2027. A rota candidata usa o caminho `/cofre`; ainda não foi criada. A tela de autenticação só será exposta após autorização específica e teste do include.
