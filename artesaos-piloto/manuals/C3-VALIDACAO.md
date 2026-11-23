# C3 — preparação de atualização no Raspberry Pi 4

Alvo **0.2.0-dev.11**, schema comum inalterado: tenant 10/control 3/interest 2/support 2/
legal 2. Preparação concluída em isolamento; **não é certificação do Pi/Supervisor
real nem autorização de atualizar/promover a principal**. Debian permanece disponível.

## Identidade e estado inicial

Branch `codex/artesao-digital-evolucao`, árvore inicialmente limpa, HEAD/ref efetiva
iguais a `84089c8800856c988efdfed492cd75d635824049` (fechamento C1/C2 publicado).
Nenhuma alteração existente foi descartada ou branch principal modificada.

O operador informou Raspberry Pi 4/aarch64, HAOS 18.3, Core 2026.9.3, Supervisor
2026.09.3, SSD 480 GB; aplicativo 0.1.17, em execução e auto-update desativado.
Hostname `f6379561-artesaos-piloto`. Não houve conexão ao servidor real.

No clone local da distribuição 0.1.17 foram lidos: origem declarada
`https://github.com/mmcromero/fabricacao-e-orcamentos-ha`, pasta `apps/artesaos-piloto`
e slug `artesaos_piloto`. SHA-1 da URL começa em f6379561, coerente com o hostname.
**Origem/identificador reais ainda precisam da consulta somente leitura** descrita
no tutorial. Provável `f6379561_artesaos_piloto`; não deduzir slug pelo hostname.
A origem de distribuição é distinta do repositório funcional onde estes commits
foram publicados. Não foi promovida/alterada a principal de nenhum deles.

## Pacote preparado

- Versão 0.2.0-dev.11 identifica correção/empacotamento posterior ao dev.10. HA e Debian
  mantêm a mesma versão, negócio e schema. Base principal incorporada permanece 0.1.23.
- Add-on específico aarch64 com o **mesmo** slug, nome, data mount `/data`, porta interna
  8099, options.json, prefixo `/artesaos-piloto/`, fluxo Google/admin e permissões.
- Runtime pré-compilado e dependências produtivas em `runtime.tar.gz`, arquivo rastreável
  mesmo quando node_modules está no .gitignore. Fontes e Dockerfile.source incluídos
  para auditoria/reconstrução; Dockerfile final apenas extrai o payload no Node ARM64.
  Não executa npm/Vite/TypeScript no Pi. Base Node 24.19.0 Bookworm fixada por digest.
- Build cruzado usa BUILDPLATFORM na compilação; guard recusa ELF/.node/PE/Mach-O e
  symlinks externos nas dependências produtivas. Node/SQLite nativos vêm da base ARM.
- O arquivo final se destina à pasta `apps/artesaos-piloto/` da origem **confirmada**.
  Não é backup nem importador de add-on da UI. Nenhuma opção/volume real é copiado.
- Dois roteiros: C3-RASPBERRY-PI-ATUALIZACAO.md e C3-RASPBERRY-BACKUP.md. Consulta de
  slug/repositório, atualização pelo painel/local condicionais, backup completo,
  inspeção estrutural somente leitura e retorno compatível foram detalhados.

## Evidências executadas

| Verificação | Resultado e limite |
|---|---|
| App/build automatizados | **179 testes aprovados**, zero falhas/skip, build frontend/backend e schemas aprovado em desenvolvimento AMD64. São testes nativos do código comum, não 179 testes no Pi. |
| Portabilidade | Três cenários novos (JS/WASM/links internos, binário nativo recusado, link externo recusado). Guard do build examinou 4.662 arquivos produtivos sem binários dependentes do host. |
| Construção ARM64 | Imagem de fonte construída para linux/arm64; imagem reconstruída do pacote pré-compilado, sem RUN/npm. Manifesto do add-on só declara aarch64. |
| Identidade do runtime | ARM ELF machine 183, process.arch=arm64, Node v24.19.0 e SQLite 3.53.3 executados sob QEMU **10.2.3/Cortex-A72**. Não é Node AMD64 fingindo ser ARM. |
| Runtime HA funcional ARM | API compilada na imagem: Google/admin controlado, usuário comum, CSRF/permissões, B9→B10, fabricação/pedido/preparo/PDF, idempotência, backup/restauração e rollback de transação interrompida passaram. |
| Versão instalada 0.1.17 | Fixture produzida pelo código publicado `df769be2ecf2bde0ee1ff9a0875dfc59394bf94f`, dois tenants, sessões usuário/admin, convites/contatos e chaves, empresa/configurações, materiais, produtos/preços, clientes, orçamentos/versões/PDF. Atualização no ARM novo preservou esses dados; nenhum estoque/financeiro foi inferido de referências antigas. Integridade/FKs e versões de migração passaram. |
| Recuperação de dados | Backup completo pré-upgrade reabriu no código original 0.1.17. Cópia pós-upgrade restaurou na versão nova em ARM; sessões/chaves preservadas. Nunca foi aberto banco novo com código antigo como “downgrade”. |
| Processo ARM com /data | Em Docker isolado/emulado: entrypoint de servidor via launcher QEMU, volume 0.1.17 sintético, duas contas e admin, HTTP/Host/healthcheck explícito, restart, kill/start e restauração fria passaram. |
| Ferramentas de backup | Oito testes do helper de recuperação passaram. Verificador estrutural de cópia fria não alterou nenhum byte; WAL não vazio e SQLite corrompido foram recusados em cópias temporárias. |
| Debian | Imagem AMD64 0.2.0-dev.11 mantida da mesma fonte. Runtime compilado de regressão com administrador próprio/Google controlado e isolamento testado separadamente; nenhuma instalação física exigida. |
| Integridade de entrega | Manifestos, arquitetura, payload/version/schema e hashes devem coincidir no recibo final `docs/ARTEFATOS_C3.json`. Arquivo fonte de add-on e Debian têm SHA256SUMS próprios. |

QEMU foi extraído para /tmp da imagem de ferramenta tonistiigi/binfmt, digest
`sha256:400a4873b838d1b89194d982c45e5fb3cda4593fbfd7e08a02e76b03b21166f0`.
**Não foi instalado binfmt nem alterado kernel/daemon/servidor real**. Emulação usa
launcher explícito Node/import e encaminhamento de subprocessos; o healthcheck é
invocado por esse launcher. CMD nativo e ciclo do Supervisor exigem o Pi real.
Sem rede nos harnesses de API; processo HTTP só em loopback de contêiner temporário.
Google/TLS reais não foram usados; identidades de teste não entram no runtime.

Comandos de referência: npm test/build na app; prepare-017-upgrade-fixture.mjs para
snapshot descartável; validate-017-arm64-upgrade.mjs/validate-packaged-runtime.mjs
montados externamente na imagem sob flags de teste/QEMU; validate-arm64-process.py;
check-ha-backup-readonly.py; prepare-distributions.py e prepare-ha-aarch64.py.
Scripts de validação nunca são ativados pelo entrypoint de produção.

## Pendências e decisão para a etapa real

- Confirmar **slug completo/origem/version_latest** pela URL/CLI filtrada. Não converter
  a instalação existente para outra origem ou tratar Instalar como Atualizar.
- Publicar o pacote na mesma origem exige autorização de promoção, especialmente se
  envolver a principal do repositório de distribuição. Esta C3 não o fez. O botão
  Atualizar não é produzido pelo simples download do tar.gz.
- Obter/validar backup nativo completo real, cópia externa, chave/kit e restauração,
  memória/espaço livres e acesso de recuperação. Não pedir envio de dados/segredos.
- Supervisor 2026.09.3/HAOS 18.3/Core 2026.9.3 físicos, Docker/registry no Pi, kernel,
  SSD/memória/boot/desempenho, Google/HTTPS/cookies/proxy reais ainda **não verificados**.
  Compatibilidade de manifesto/ISA e testes emulados não certificam esses pontos.
- A C3 não cria nova migração além das já comuns B1–B10, mas o salto desde 0.1.17 é
  real. Retorno exige código **e backup completo anterior compatíveis**; não downgrade
  direto. Dados posteriores ao backup precisam de decisão explícita de preservação.
- Aviso Fastify preexistente e lint Docker sobre plataforma ARM constante permanecem
  informativos. Plataforma constante é intencional no pacote aarch64-only.
- Nenhum teste de saúde/estresse de armazenamento, alteração de redes/credenciais,
  instalação real, force push, merge principal ou backlog futuro foi executado.

**Parar: próxima ação depende de confirmação de identidade/origem e autorização
específica para promoção da fonte e atualização/homologação no Raspberry Pi real.**
