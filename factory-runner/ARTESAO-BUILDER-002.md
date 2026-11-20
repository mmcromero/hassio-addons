# ARTESAO-BUILDER-002 — Executor externo e isolado de builds

**Estado:** código desenvolvido na branch isolada `feat/factory-runner-artesao-package-adapter`. **Não executado em VM real, não instalado e não publicado.** Rastreabilidade na Issue #2.

## Objetivo e limites

O `artesao_isolated_executor.py` prepara **artefatos locais de teste**, seguindo as mesmas receitas oficiais do Artesão Digital. Ele **não faz push, merge, release GitHub, instalação, update ou comunicação com servidores**. As duas arquiteturas são distintas:

| Trilha | Papel | Imagem/artefato |
| --- | --- | --- |
| Home Assistant | Contingência do Artesão Digital | Imagem `linux/arm64`, pacote `apps/artesaos-piloto/`, `runtime.tar.gz`, `SHA256SUMS` |
| Debian/Forja 01 | Principal, independente do HA | Imagem `linux/amd64`, pacote Debian/Compose, `image.tar`, `SHA256SUMS`; ZIP Windows somente se descriptor oficial da versão existir |

Não confundir com o Avisaqui nem instalar os pacotes na Forja 01 ou no Raspberry. A versão do **Factory Runner permanece RC9 no catálogo**; desenvolvimento do executor não a altera.

## Origem canônica (verificada no Git)

- `mmcromero/fabricacao_e_orcamentos:main`: `scripts/release-evidence.py`, `scripts/prepare-pilot-release.py`, `scripts/prepare-distributions.py`, `scripts/prepare-ha-aarch64.py`, `scripts/prepare-forja-windows.py`.
- Fluxos oficiais do produto: `.github/workflows/artesao-publicar-ha.yml` e `artesao-pacote-forja.yml` **lidos como documentação dos comandos**, **NÃO executados**.
- Fontes `apps/umdoislab/artesao-release.json` e `pilot/config.yaml`; distribuição `mmcromero/fabricacao-e-orcamentos-ha:main` com `apps/artesaos-piloto/release.json` e ponteiro `forja-01/publicacao-atual.json`.
- O recibo `release-evidence.py` requer build/testes + ferramentas/operações, checkout limpo e `schemaChecksums`; o empacotador oficial exige esse recibo do SHA fixo. As imagens Docker exigem labels com SHA, versão, distribuição e data.

## Etapas implementadas

1. **Plano somente leitura:** carregar perfil autorizado `artesao_package`, comparar SHA e versão das duas distribuições; barrar versão reutilizada, migração sem liberação, divergência de base ou mudança de scripts aprovados. Nenhum diretório de saída é criado.
2. **Execução externa (não acionada nesta entrega):** o argumento `--execute` exige Linux não-root, política local separada e fixada a **um SHA e uma versão**, caminhos absolutos, destino novo, checkout sem alterações **inclusive arquivos ignorados**, SHA do HEAD exato e cache npm offline preprovisionado.
3. **Validação oficial:** `npm ci --offline`, depois `scripts/release-evidence.py` no checkout do projeto. Conferir recibo real `passed`, quatro verificações, `schemaChecksums` e SHA exato. Nunca sintetizar recibo.
4. **HA:** `scripts/prepare-distributions.py` gera fonte; `docker buildx build --platform linux/arm64 --network=none --load`; `scripts/prepare-ha-aarch64.py` verifica imagem/labels e gera pacote; conferir SHA256SUMS e release.json.
5. **Debian:** exportar fonte `--debian-only`; `docker buildx build --platform linux/amd64 --network=none --load`; `docker save`; reexecutar o exportador com `--image-archive`. Conferir SHA256SUMS, SHA da imagem, release.json e schemas iguais aos do HA.
6. **Forja Windows:** opcional e bloqueado sem `docs/operacao/publicacoes/VERSAO.json` oficial da mesma fonte. Se existir, executar `scripts/prepare-forja-windows.py`, conferir hashes e gerar ZIP **somente em saída local nova**. Não criar descriptor presumido.
7. **Recibo final:** `FACTORY_ARTESAO_BUILD_REPORT.json` lista SHA, versão, hashes de arquivos, etapas verificadas, `published: false`, `installed: false`. Falha em qualquer etapa grava `INCOMPLETE-NOT-FOR-PUBLICATION`. Não existe chamada a GitHub Actions, Git push/merge, HA, SSH ou Docker remoto.

## Isolamento obrigatório — NÃO habilitar nos servidores atuais

O executor é um **programa para uma VM descartável dedicada**, gerenciada fora do Raspberry/Home Assistant e fora da Forja 01. **O arquivo de política não prova isolamento físico nem bloqueio de rede.** Antes de uma execução real, a Infra deve comprovar, em máquina dedicada: ausência de acesso à rede de produção e a serviços externos, firewall restritivo, nenhum volume de dados comerciais, credencial pessoal, SSH agent ou token de produção, Docker **local da VM**, caches npm/BuildKit offline preprovisionados e logs/recibos sanitizados. A própria política inclui `network_policy: blocked_external`, mas essa declaração **não substitui o teste real da rede/VM**. Falhas de dependências offline são **bloqueio legítimo**; não abrir rede, mapear socket da Forja ou desativar segurança para resolvê-las sem novo projeto/autorização.

O código nega executar com UID 0, tokens `SUPERVISOR_TOKEN`/`GITHUB_TOKEN` etc no ambiente, marca HA de supervisão, `DOCKER_HOST` remoto, caminhos relativos, saída existente, checkout sujo, HEAD divergente, tag de imagem Docker já existente e política diferente do SHA/versão. O Docker CLI é explicitamente fixado ao socket local `unix:///var/run/docker.sock`. O próprio acesso Docker dá poder elevado **dentro da VM**; por isso a VM deve ser descartável, segregada e pré-aprovada. Não é seguro executar este código no servidor de produção ou compartilhar o socket do HA.

### Contrato de política para futura VM isolada

A política deve ficar **fora** dos repositórios, no sistema de build independente, com conteúdo da forma:

```json
{
  "kind": "factory-runner-disposable-builder-v1",
  "host_role": "dedicated_disposable_vm",
  "network_policy": "blocked_external",
  "production_access": false,
  "docker_endpoint": "unix:///var/run/docker.sock",
  "source_repository": "mmcromero/fabricacao_e_orcamentos",
  "expected_source_sha": "SHA_EXATO_DE_40_CARACTERES",
  "expected_version": "VERSAO_NOVA_JA_VALIDADA",
  "npm_cache": "/var/cache/factory-runner/npm"
}
```

Os dois valores de exemplo acima **não são executáveis**; devem ser substituídos apenas pelo commit/versão de uma candidata nova realmente aprovada. O cache offline deve existir. `Docker buildx` também requer imagens-base/caches previamente disponíveis sem buscar repositórios pela internet.

### CLI futuro, somente no builder segregado

```sh
python3 artesao_isolated_executor.py --source /builder/source --distribution /builder/public --profile /builder/config/artesao_digital.json --expected-source-sha SHA_EXATO --output /builder/saidas/novo-lote
```

Este modo **não executa builds**; apenas apresenta o plano. O modo de execução é o mesmo comando acrescido de `--builder-policy /builder/private/builder-policy.json --execute`. **Não executar** esse modo em Raspberry, Home Assistant ou Forja 01. A ativação real depende de provisionar e validar a VM de build externa.

## Estado e testes

`tests/test_factory_runner_artesao_isolated_executor.py` contém **15 testes offline** para SHA/checksum, traversal e symlinks, validação de recibo, arquiteturas, bloqueios de política, plano sem execução, checkout limpo e falha inicial sem publicar. O Dockerfile do Factory Runner copia o executor **somente para o estágio de validação de testes**; não o inclui na imagem final do add-on. Nenhum direito de execução/Docker é acrescentado ao HA.

**Status de execução da suíte no projeto: ainda pendente.** Os testes foram escritos na branch mas o ambiente deste chat não dispõe de checkout completo privado com runtime Docker; não afirmar PASS. O código do executor é uma implementação verificável, não comprova imagens ARM64/AMD64 construídas. Na fotografia do Git, a fonte e o HA público têm `0.2.0-dev.28` de SHAs diferentes; **esse caso é bloqueado antes de iniciar o executor**. Um futuro build exige versão superior e fonte fixada, sem alterar a versão atual por conveniência.
