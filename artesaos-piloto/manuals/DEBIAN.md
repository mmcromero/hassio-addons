> **0.2.0-dev.25 — entrada e boas-vindas:** consulte [PRIMEIRO-ACESSO.md](PRIMEIRO-ACESSO.md). Atualização de interface sem mudanças de slug, volumes, autenticação ou schemas. Instalação continua manual. Notas antigas abaixo são históricas.

> Desenvolvimento **0.2.0-dev.16 — UX-Loading-01**: feedback visual de espera,
> sem mudanças de autenticação/schema/regras comerciais. Nível 1 preservado.
> Nenhuma distribuição/deploy nesta entrega. Guia/testes em docs/UX-Loading-01.md.

> Desenvolvimento **0.2.0-dev.15 — PWA-01 online**: manifest/ícones de instalação,
> sem consulta/venda offline. HA-UX-001 altera apresentação da contingência; identidade
> técnica e schemas preservados. Sem distribuição/deploy neste pacote. Nível 1
> permanece vigente. Procedimento e testes em docs/PWA-01.md no repositório; estados
> e versões anteriores abaixo são históricos quando houver divergência.

> Distribuição **0.2.0-dev.14**: inclui R1.1 e ferramentas operacionais por fase;
> schemas tenant11/control4/interest2/support2/legal3 e base 0.1.23 inalterados.
> Forja principal; HA ARM64 para instalação manual. Publicação não comprova instalação.
> Nível 1: backup recomendado, sem certificação obrigatória. As notas de versões
> antigas abaixo são históricas; verificar o estado atual em docs/operacao/DISTRIBUICOES.json.

> Operação vigente: Forja 01 é o servidor principal. Procedimentos de atualização
> e metadados em ATUALIZACOES.md; recuperação em RECUPERACAO.md. Exemplos dev.11 e
> notebook abaixo são históricos. Não inferir estado real a partir deles.

> Versão corrente: **0.2.0-dev.13**. Ver [estabilização e convites](ESTABILIZACAO-CONVITES.md).
> Pix aceita telefone BR com DDD; confirmação/erro aparece junto ao formulário.
> Migração incremental control4; demais schemas preservados. Manuais/evidências
> de versões anteriores abaixo são históricos. Não atualizar instalações reais
> sem autorização específica e backup consistente.

> Versão corrente: **0.2.0-dev.12**. Ver [administração dinâmica](ADMINISTRACAO-DINAMICA.md).
> Migrações tenant 11/legal 3, demais schemas preservados. Backup integral inclui
> documentos, aceites e PDFs em pilot-legal.sqlite. Não fazer downgrade sobre banco
> migrado. Instruções/evidências de versões anteriores abaixo são históricas.

# Debian independente — preparação e instalação

Referência **0.2.0-dev.11**, notebook Samsung NP670Z5E-XD1BR com HD existente.
Alternativa independente: falta do notebook não bloqueia correções/pacotes/HA.
Executar no notebook somente após autorização específica; nenhum passo foi aplicado
nele em C1/C2. Não comprar hardware, formatar, remover serviços ou testar saúde/estresse
individual do HD como pré-requisito automático.

## Requisitos e escolha técnica

Docker Engine + plugin **Docker Compose v2 ou posterior**, Python 3.12+ (helper usa
filtro seguro de extração), tar/gzip e sha256sum, Linux amd64. Node 24.19.0 e npm
estão na imagem; não instalar Node global nem compilar dependências no notebook se
usar a imagem fornecida. Compose permite manter o mesmo runtime do HA e o mesmo
schema, com dados próprios. Não altera a administração Google do HA.

Inspeção inicial não destrutiva: `uname -m`, `cat /etc/os-release`, `free -h`,
`df -h`, `docker version`, `docker compose version`, `python3 --version`.
Capacidade de CPU/RAM/espaço e desempenho do notebook não foram medidos. A imagem
pré-construída é amd64; não tentar carregá-la como ARM. Não instalar/atualizar o
Debian ou Docker automaticamente. A instalação desses pré-requisitos é intervenção
separada autorizada, seguindo a documentação oficial para a versão real do Debian.

## Conteúdo e preparação nova

O tar.gz Debian contém `app/` (mesmo código do HA), `image.tar` quando fornecido,
compose.yaml, modelos sem segredos, manage.py, release.json, SHA256SUMS e manuais.
Nenhum banco/conta do HA é importado. A extração não inicia serviços.

Após autorização, em pasta de preparação de acesso restrito:

```sh
sha256sum --ignore-missing -c SHA256SUMS
tar -tzf artesao-digital-debian-0.2.0-dev.11.tar.gz
tar -xzf artesao-digital-debian-0.2.0-dev.11.tar.gz
cd artesao-digital-debian
python3 manage.py verify
```

Mover o diretório para um caminho estável, por exemplo `/opt/artesao-digital`, com
permissão de administração local. Não reutilizar pasta que tenha dados. Escolher
UID/GID do processo (padrão 1000:1000), então:

```sh
python3 manage.py initialize --uid 1000 --gid 1000
```

Se não for root, UID/GID devem corresponder ao usuário que executa; root pode criar
os diretórios com dono indicado. O helper recusa instalação parcial/existente,
cria `data/`, `config/`, `private-codes/` em 0700 e `.env`/config em 0600. Não inicia
Docker, não instala serviços nem apaga algo. Diretórios podem ser preparados por
administrador local autorizado se houver erro de permissão; não aplicar chmod 777.

Editar **config/options.json** localmente, com dono/0600 preservados:
`public_url=https://SEU-ENDERECO/artesaos-piloto/`, `google_client_id` e
`google_client_secret` de cliente OAuth próprio do Debian. Não enviar segredos ao
chat ou Git. `.env` tem só UID/GID/porta. Nunca montar volumes/config/chaves do HA.

## Imagem, partida e reinício

```sh
docker load --input image.tar
docker compose config --quiet
docker compose up -d --no-build
docker compose ps
docker compose logs --tail 50 artesao
```

A imagem deve ser `artesao-digital:0.2.0-dev.11`. Se o pacote não incluir image.tar,
a alternativa é `docker compose build` a partir de app/, exigindo internet para
registro/npm, e depois `docker compose up -d --no-build`. Não trocar versões de
Node/dependências por conveniência. No ambiente de desenvolvimento com CA de proxy,
usar segredo BuildKit `proxy_ca`; não desabilitar validação TLS.

O Compose fixa modo `debian`, processo não root, rootfs somente leitura, sem
capacidades extras, /tmp temporário, restart=unless-stopped e porta publicada apenas
em **127.0.0.1:8099**. Volumes data/config/códigos são dessa instalação. Serviço Docker
precisa iniciar no boot (confirmar estado com `systemctl is-enabled docker`);
configurá-lo apenas na intervenção real autorizada. Após reiniciar, validar login,
versão e dados. Healthcheck confirma resposta HTTP interna, não Google externo.

## Primeiro Acesso e recuperação local

Com config pronta e diretórios privados, emitir pelo console da mesma instalação:

```sh
docker compose run --rm --no-deps --entrypoint node artesao dist-server/pilot/local-admin-console.js setup-code /data /run/private-codes/ativacao-001
```

O comando grava em arquivo 0600; não imprime o código. Ler **localmente**
`private-codes/ativacao-001` com acesso administrativo seguro, sem transmitir/logar.
Abrir `https://SEU-ENDERECO/artesaos-piloto/admin/login`: antes do administrador,
aparece Primeiro Acesso. Informar e-mail, senha exclusiva (12–128 caracteres),
confirmação e código. Código dura 30 minutos, tem uso único e novo código invalida
anterior. Após criar o único administrador, setup fecha e login usa e-mail/senha.
Remover apenas o arquivo temporário de código usado, por decisão do operador local.

Para recuperar administrador existente, sem apagar banco nem editar SQLite:

```sh
docker compose run --rm --no-deps --entrypoint node artesao dist-server/pilot/local-admin-console.js recovery-code /data /run/private-codes/recuperacao-001
```

Usar `/artesaos-piloto/admin/recover`, e-mail atual, senha nova/confirmada e código.
Recuperação revoga sessões administrativas. Não cria outro administrador nem muda
Google comum. Não reutilizar nome de arquivo; códigos não entram em backups.

## URL externa, HTTPS, DuckDNS e Google — roteiro de implantação pendente

O notebook estará em rede isolada da doméstica; o acesso deve usar URL pública HTTPS,
inclusive a partir de casa. Diagnosticar IP público/CGNAT antes de prometer acesso.
Não alterar roteador, firewall, proxy ou DNS em C1/C2.

- Obter endereço DuckDNS e configurar atualização do DNS por mecanismo aprovado;
  token fica fora do pacote/Git e não em linha de comando/log. Domínio .com.br futuro
  usa a mesma aplicação: mudar URL externa/configuração e callback, não o negócio.
- Definir proxy reverso **na mesma máquina** para encaminhar somente
  `/artesaos-piloto/` a `http://127.0.0.1:8099`, preservando prefixo/Host. Caso o proxy
  esteja em outra máquina, o bind local atual não atende: revisar topologia e ACL
  separadamente, sem publicar 8099 para a internet por tentativa.
- Provisionar certificado válido (ex.: ACME/Let's Encrypt pelo proxy aprovado),
  renovação automática e teste de renovação. DNS-01 pode exigir segredo privado;
  HTTP-01 precisa porta 80 durante validação. Porta 443 deve ser a entrada pública;
  80 só quando necessário ao método aprovado/redirecionamento. Não presumir portas
  liberadas nem contornar CGNAT sem solução de acesso escolhida pelo operador.
- No proxy, não registrar query strings/códigos OAuth nem cookies. Não servir pastas
  data/config/private-codes. Não expor Docker/socket, debug, SQLite ou console bruto.
  Exemplo orientativo Nginx, adaptado ao virtual host/certificado real:

```nginx
location /artesaos-piloto/ {
    proxy_pass http://127.0.0.1:8099;
    proxy_set_header Host $http_host;
    proxy_set_header X-Forwarded-Proto https;
    proxy_set_header X-Forwarded-For $remote_addr;
    proxy_set_header Connection "";
    proxy_redirect off;
    proxy_buffering off;
    access_log off;
    client_max_body_size 3m;
}
```

Não aplicar esse exemplo ao proxy HA. HTTPS termina no proxy; cookies são Secure,
HttpOnly/SameSite conforme sessão, CSRF exige origem exata. App mantém trustProxy=false:
cabeçalhos não concedem autorização; limites por IP podem agrupar usuários sob o
proxy. Configurar limite adicional no proxy de implantação, preservando callbacks.
Criar cliente OAuth Web próprio do Debian com callback exato
`https://SEU-ENDERECO/artesaos-piloto/auth/google/callback` e público de teste permitido.
Não substituir cliente/URLs HA. Google comum exige convite da administração local.
Testar acesso por rede celular e rede doméstica isolada, certificado/renovação,
primeiro e novo login, cookies, logout e isolamento. Tudo isso depende de autorização
e validação física; o pacote não configura DNS/TLS/rede automaticamente.

## Atualização e backup

Seguir ATUALIZACOES.md e RECUPERACAO.md. Nunca `docker compose down -v`, nunca apagar
data para resolver login. A pasta de versão/código pode mudar; dados/config precisam
ser preservados no caminho estável. Backup inclui chaves, todos os bancos e opções;
restauração só em pasta nova. Voltar ao HA significa usar seus dados próprios, não
sincronizar as operações feitas no Debian.
