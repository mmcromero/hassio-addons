# C1/C2 — preparação e validação da distribuição

Referência **0.2.0-dev.10**, 2026-11-01 UTC. B1–B10 preservadas. C1/C2 concluídas em
ambientes isolados; **primeira instalação real no Home Assistant ainda não autorizada**.
Home Assistant é o ambiente principal de homologação. Debian permanece alternativa
independente; a falta do notebook não bloqueia futuras correções/versões seguras.

## Entregas

- Home Assistant: tar.gz com add-on local `artesaos_piloto`, Dockerfile, código,
  lockfile, manifesto, SHA256SUMS e estes manuais. Instalação/atualização pelo
  Supervisor depende de intervenção futura; o tar não é backup nativo HA.
- Debian: tar.gz com a mesma app/, Compose, imagem Docker amd64 image.tar, modelos
  sem segredos, manage.py e manuais. Extração/verificação não instala/inicia serviços.
- Uma versão e schema comum: tenant=10/control=3/interest=2/support=2/legal=2.
  Hash do negócio e sourceCommit constam em release.json nos dois pacotes.
  Debian registra também imageSourceCommit/imageId/hash da imagem incluída.
- `HOME-ASSISTANT.md`, `DEBIAN.md`, `RECUPERACAO.md`, `ATUALIZACOES.md` acompanham
  cada exportação futura. Este relatório é da referência acima, não certifica futuras
  versões automaticamente. Atualizar testes/relatório a cada nova entrega.
- Nenhum banco, usuário, senha padrão, convite real, opções reais ou código de
  ativação foi incluído nos pacotes. A imagem contém apenas runtime/código/assets.

## Evidência inicial e checkpoints

Branch `codex/artesao-digital-evolucao`, árvore inicialmente limpa. HEAD e consulta
`git ls-remote` coincidiram em `1a36659a9bb18aff489b1a8520a8f91b4e3a4b4e`, fechamento
B10 publicado. Nenhuma alteração preexistente foi descartada. Principal preservada.

- `6f91901`: autorização C1/C2 e diretriz HA principal.
- `1df84e30470806ceeaecbb3e09ffad648d146ec4`: pacotes/manuais/helper inicial.
- `0eba1b7a73b0b5fec1140e68055cbae352f589f4`: testes de artefatos, backup e healthcheck.
- `900a4b3b67dfbe8acb55c348e806c1cf011c9b36`: permissões de assets imutáveis para
  processo Debian sem privilégios e navegador do Primeiro Acesso.
- Commits posteriores de relatório/verificação podem ser consultados no histórico.
  O recibo de entrega em `docs/ARTEFATOS_C1_C2.json` registra hashes dos arquivos
  finais, sem criar referência circular ao próprio conteúdo do pacote.

## Ambiente realmente usado

Docker Engine **28.4.0**, Compose **2.40.3**, imagem **linux/amd64** baseada em
Node **24.19.0 Bookworm slim**. Python **3.12**, Chromium local, diretórios e volumes
sintéticos descartáveis. Lockfile existente, sem novas dependências do aplicativo.
Build mantém validação TLS e CA do ambiente por segredo BuildKit, não na imagem.
Nenhum servidor, credencial Google, rede, HA ou notebook real foi alterado.

## Testes e resultados

| Verificação | Resultado e natureza da evidência |
|---|---|
| Build do código exportado | Aprovado: frontend/backend e cinco versões de schema. Execução real no ambiente de desenvolvimento, da cópia do pacote. |
| Suíte do código exportado | **176 aprovados, zero falhas/skip**. Inclui B1–B10, HA/Google controlado e Debian, concorrência, rollback, sessões/CSRF/contexto e isolamento. node_modules de desenvolvimento compartilhado por symlink só na cópia de teste, não no pacote. |
| Imagem do Dockerfile exportado | Construída de fato em amd64, dependências npm ci/prune, sem segredos/DB. |
| Runtime HA compilado na imagem | Aprovado, sem rede, rootfs somente leitura: administração Google controlada, usuário comum, permissões, migração B9→B10, fabricação/pedido/preparo, PDF com fontes reais, idempotência, backup frio/restauração e recuperação de filho morto durante transação. Não é Supervisor. |
| Runtime Debian compilado na imagem | Mesmos cenários, executados como UID/GID 1000:1000; Primeiro Acesso/código único, login, recuperação por console e revogação de sessão. Google comum controlado preservado. |
| Compose e entrypoint de produção | Criação real de contêiner temporário a partir do pacote, rootfs somente leitura, usuário sem root e bind loopback. Configuração/chaves próprias, console 0600, backup frio pelo helper, restauração/integridade, kill/restart e healthcheck aprovados. |
| Adaptador HA com opções | Contêiner independente com options.json/volume sintéticos, modo HA/Google administrativo, versão e reinício aprovados. Banco marca distribuição própria; nenhum volume Debian compartilhado. |
| Ferramenta de recuperação | **8 testes aprovados**: permissões, recusa de sobrescrita, backup/restore, códigos excluídos, travessia de caminho, symlink, duplicata canônica, arquivo incompleto e falha com retomada do serviço. Chamadas Docker simuladas nesses testes unitários; exercício Compose acima usou Docker real. |
| Navegador B3–B10 no código exportado | Aprovado: fluxo comercial completo, embalagens e cinco grupos, **1280/390 px**, sem overflow/erro JS. Identidades Google e TLS controlados. |
| Navegador Debian na imagem | Aprovado: **1280/390 px**, TLS descartável, código emitido pelo console, Primeiro Acesso, login/logout, bloqueio de setup após criação, recuperação e senha nova; logo carregada. Processo real da imagem, sem notebook ou certificado público real. |
| Upgrade 0.1.15 e 0.1.16 | Código histórico real com dados sintéticos → código atual: sessões/empresa/convites/chaves, reinício e restauração aprovados. Exercícios de código/volume, não atualização nativa Supervisor. |
| Schema e integridade | Cinco scopes compilados testados, checksums históricos e registros B9 preservados no upgrade; integrity_check OK/FKs sem violações. Não houve migrations em produção. |
| Integridade final | SHA256SUMS, release.json/version/schema/hash comum, verificação do helper e leitura/carregamento da imagem devem coincidir no recibo final. Nenhum resultado físico é presumido a partir disso. |

Comandos rastreáveis (raiz do repositório, exceto npm/scripts históricos na app):

```sh
python3 scripts/prepare-distributions.py --output DIRETORIO-NOVO --image-archive IMAGEM.tar
python3 -B scripts/validate-distribution-tools.py
python3 -B scripts/validate-compose-distribution.py --package PACOTE-DEBIAN-EXTRAIDO
python3 -B scripts/validate-debian-package-browser.py --package PACOTE-DEBIAN-EXTRAIDO
# Harness externo montado em /run/c2.mjs, não embutido na imagem:
# docker run ... --read-only --network none ... --entrypoint node IMAGEM /run/c2.mjs home-assistant
# docker run ... --user 1000:1000 ... IMAGEM /run/c2.mjs debian
# Na cópia descartável da app exportada:
npm run build
npm test
python3 -B scripts/verify-material-inventory.py
# Na app do repositório com histórico Git para fixtures antigas:
node --import tsx scripts/verify-pilot-invitation-upgrade.mjs
node --import tsx scripts/verify-pilot-central-invitations-upgrade.mjs
```

## Falhas encontradas e corrigidas antes da conclusão

- Dois testes pressupunham `pilot/config.yaml` da árvore Git; passaram a aceitar o
  caminho `config.yaml` da distribuição, mantendo as mesmas asserções de segurança.
- Healthcheck inicial não enviava o Host configurado e recebia 421: agora usa
  pilotConfig/Host correto, sem remover a guarda de Host/origem nem expor segredos.
- Assets copiados com modo 0600 eram ilegíveis ao Debian sem root: Dockerfile
  normaliza somente código/fontes/logos/dependências imutáveis da imagem. /data,
  config e códigos continuam privados. Fontes, PDF e logo foram testados sem root.
- Seletor do logout administrativo foi corrigido no teste para o aria-label existente;
  UI e autenticação HA não foram substituídas. Fixtures respeitam vínculo de distribuição
  antes de criar dados sintéticos; não contornam a recusa de importar volume HA no Debian.

## Limitações e próxima autorização

Não verificados fisicamente: Supervisor/loja/backup nativo HA, Google e cookies no
domínio real, certificado público/renovação, DuckDNS/IP público/CGNAT/firewall/proxy,
acesso da rede isolada e celular real, Samsung/Debian/boot e desempenho no HD,
ARM/aarch64, impressora/compartilhamento reais. Não foram feitos testes de saúde ou
estresse do HD. Fastify conserva aviso de depreciação preexistente, sem falha funcional.

Não houve release estável/tag/merge principal, instalação real ou inclusão de backlog.
Pacotes/manuais/checksums foram preparados; publicação dos commits protege código e
procedimentos, não instala o aplicativo. Arquivos binários entregues no workspace são
identificados pelo recibo; não são bancos nem backups reais.

**Parar após C1/C2. Próxima ação: aguardar autorização específica para primeira
instalação/homologação real no Home Assistant**, conferindo antes origem/slug atual,
backup protegido/restauração e plano de recuperação local. Debian físico será tratado
em paralelo quando disponível, sem bloquear novas entregas testadas do produto.
