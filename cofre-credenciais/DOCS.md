# Fábrica de Ideias — Cofre de Credenciais

Este pacote executa o Vaultwarden, servidor compatível com os clientes Bitwarden, no Home Assistant OS.

## Estado desta candidata

- Versão instalada do pacote HA: `0.1.0-rc.3`
- Servidor: Vaultwarden `1.37.5`, imagem multi-arquitetura fixada por digest.
- Arquitetura declarada: `aarch64` e `amd64`.
- Persistência: `/data` (SQLite e anexos).
- Interface: não usa Home Assistant Ingress.
- Porta interna do serviço web: `7277/tcp`; mapeamento para a rede do host desativado por padrão.
- Acesso configurado: `https://romeropi.duckdns.org:8443/cofre`, reutilizando o domínio/certificado HTTPS já existentes e o include `/share/nginx_proxy_default_cofre.conf` no NGINX 4.5.3. A rota foi testada via TLS no listener interno do NGINX; a alcançabilidade WAN a partir de uma rede externa independente ainda não foi verificada.

## Proteções padrão

- Cadastro público de contas: desativado.
- Convites: desativados.
- Vaultwarden Send: desativado.
- Cadastro via SSO: desativado.
- Criação de organizações: desativada.
- Painel administrativo `/admin`: desativado.
- Nenhum token administrativo é gerado ou impresso nos logs.
- A porta 7277 não é publicada no host pelo manifesto.

**Não coloque credenciais reais ainda.** Conta proprietária e MFA foram configurados e o login com segundo fator foi testado; ainda faltam homologação dos clientes/sincronização, backup cifrado externo, restauração isolada e revisão independente.

## Primeiro acesso — procedimento controlado

1. Abrir `https://romeropi.duckdns.org:8443/cofre` e confirmar que a tela de login carrega pelo acesso externo.
2. Na configuração do app, habilitar `allow_signups` temporariamente e reiniciar o app.
3. Abrir a rota HTTPS e criar somente a conta do proprietário.
4. Ativar autenticação de dois fatores (TOTP) na conta e guardar o código de recuperação em local seguro.
5. Voltar à configuração do app, desabilitar `allow_signups` e reiniciar.
6. Confirmar no log `Self-registration: false` e testar login em janela anônima, verificando a exigência do segundo fator.
7. Só depois de backup/restore e revisão independente aprovados considerar a migração de credenciais reais.

**Estado do bootstrap (28/11/2026): CONCLUÍDO.** Conta proprietária criada; TOTP ativado; código de recuperação guardado pelo proprietário; login em janela anônima com segundo fator confirmado pelo proprietário; `allow_signups=false` reaplicado e confirmado no Supervisor (`Self-registration: false`); add-on `0.1.0-rc.3` iniciado. Não houve armazenamento de senha mestra, segredo TOTP ou código de recuperação em logs/documentação. Não deixar `allow_signups` habilitado após criar a conta do proprietário.

## Configuração

- `ssl`: manter `false` quando o NGINX externo terminar TLS; a comunicação interna entre proxy e app será HTTP na rede privada de add-ons.
- `domain`: já configurado como `https://romeropi.duckdns.org:8443/cofre`. O Vaultwarden 1.37.5 suporta o prefixo de caminho via `DOMAIN`.
- `request_size_limit`: limite de requisições JSON do Rocket; o limite de upload também deverá ser definido no vhost externo do NGINX.
- `log_level`: manter `info` em operação normal.

O app não oferece Ingress. Não habilitar acesso público direto à porta 7277. Não criar redirecionamento de porta no roteador. O certificado wildcard `*.romeropi.duckdns.org` já está configurado no DuckDNS; não foi necessário emitir outro certificado para a rota.

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

Build e inicialização no Raspberry Pi 4 e rota TLS interna no NGINX: PASS. Pendentes: alcance WAN independente, WebSocket com cliente, sincronização multi-cliente, consumo de recursos, backup/restore, recuperação e atualização controlada. MFA/TOTP e login com segundo fator foram concluídos pelo proprietário em 28/11/2026.


## Estado de acesso — 28/11/2026

O Supervisor confirma NGINX 4.5.3 com domínio `romeropi.duckdns.org`, porta externa 8443 e include customizado ativo. DuckDNS confirma SAN `*.romeropi.duckdns.org`, válido até 19/02/2027. A rota candidata usa o caminho `/cofre`; ainda não foi criada. A tela de autenticação só será exposta após autorização específica e teste do include.


## Implementação da rota — 28/11/2026

- Arquivo: `/share/nginx_proxy_default_cofre.conf`
- SHA-256: `f8efa7c53fce11f7bb2b1198aef1320ba68da63c0346ddf9b31f56029c5d925c`
- NGINX 4.5.3 reiniciado; estado `started`.
- Vaultwarden `DOMAIN` configurado para a URL pública com prefixo `/cofre`.
- Teste TLS no listener interno do NGINX, com SNI e Host corretos: TLS verify result 0; Web Vault HTTP 200; CSS HTTP 200; API config HTTP 200; cadastro desativado; painel administrativo desativado.
- A porta 7277 continua sem mapeamento no host.
- Nenhuma conta ou credencial real foi criada.

O arquivo de rota usa WebSocket Upgrade/Connection, preserva o caminho `/cofre`, encaminha para o hostname interno do app e aplica limite de upload local de 10 MB. Não alterar ou substituir os outros includes existentes.


### Include NGINX implantado

Arquivo runtime: `/share/nginx_proxy_default_cofre.conf`.

```nginx
# Cofre de Credenciais — Vaultwarden via HTTPS no prefixo /cofre
location = /cofre {
    return 308 /cofre/;
}

location ^~ /cofre/ {
    proxy_pass http://45c28620-cofre-credenciais:7277;

    proxy_http_version 1.1;
    proxy_set_header Host $forward_host;
    proxy_set_header X-Forwarded-Host $forward_host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header Origin $http_origin;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection $connection_upgrade;

    proxy_buffering off;
    proxy_read_timeout 3600s;
    proxy_send_timeout 3600s;
    proxy_redirect off;
    client_max_body_size 10m;
}
```

SHA-256 do arquivo runtime: `f8efa7c53fce11f7bb2b1198aef1320ba68da63c0346ddf9b31f56029c5d925c`. O NGINX inclui esse arquivo no contexto do servidor HTTPS por meio de `nginx_proxy_default*.conf`. Preserve os outros includes; não publicar a porta interna 7277.


## Bootstrap da conta proprietária e MFA — 28/11/2026

- Proprietário confirmou criação da conta no Web Vault.
- Código de recuperação visualizado e guardado pelo proprietário; nenhum código foi enviado ao chat ou registrado.
- Aplicativo autenticador TOTP ativado pelo proprietário.
- Login em janela anônima confirmado pelo proprietário, com solicitação e validação do segundo fator.
- Cadastro público voltou a `allow_signups=false`; Supervisor confirmou `Self-registration: false` após reinício.
- Estado atual do add-on: `0.1.0-rc.3`, `started`; porta interna 7277 sem mapeamento no host; painel `/admin` desativado.
- Nenhuma senha mestra, semente TOTP, código de recuperação ou credencial real foi coletada ou registrada.
- Próximo gate obrigatório antes de importar credenciais reais: plano de backup cifrado externo, teste de restauração isolada (SQLite + anexos), recuperação e revisão de segurança; em paralelo, homologar cliente desktop/extensão/mobile e sincronização.
