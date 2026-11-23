## C3 — identidade reconciliada e publicação autorizada

O operador forneceu `/config/app/f6379561_artesaos_piloto/info`: slug completo
**f6379561_artesaos_piloto**, coerente com o manifesto e o pacote. O conflito
anterior foi resolvido, sem mudar identificadores. Autorização posterior: publicar
se não houver outros bloqueios. Publicação experimental permitida; atualização,
reinício, backup/restauração e homologação reais continuam sem autorização.
As limitações físicas conhecidas permanecem; QEMU não certifica o Raspberry Pi.

# C3 — atualização do Artesão Digital existente no Raspberry Pi 4

Alvo **0.2.0-dev.11**, pacote específico **aarch64**. Preparação/testes isolados,
**sem autorização para atualizar o HA real**. Ler fases A e B separadamente.

## A. Consulta permitida agora — somente leitura

Informado pelo operador: Raspberry Pi 4, aarch64, HAOS 18.3, Core 2026.9.3,
Supervisor 2026.09.3, SSD 480 GB; Artesão Digital — Testes **0.1.17**, em execução,
atualização automática desativada, hostname `f6379561-artesaos-piloto`.
Esses dados não foram inspecionados por conexão ao servidor nesta preparação.

1. Em **Configurações → Aplicativos/Add-ons → Artesão Digital — Testes → Informações**,
   copiar apenas nome/versão/estado e o identificador da URL do navegador:
   `/hassio/addon/IDENTIFICADOR_COMPLETO/info`. Não copiar tokens nem opções.
2. Na loja, consultar os **repositórios já configurados**, sem adicionar/remover ou
   mudar URL/branch. Identificar de qual repositório vem este aplicativo.
3. Se já houver Terminal/SSH e `ha`/`jq` disponíveis, alternativa só de consulta:

```sh
ha addons list --raw-json | jq '(.data.addons // .addons // []) | .[] | select(.name == "Artesão Digital — Testes") | {name,slug,version,repository,state}'
ha addons info IDENTIFICADOR_CONFIRMADO --raw-json | jq '(.data // .) | {name,slug,version,version_latest,repository,hostname,state,arch,boot,auto_update}'
```

Se o comando não existir nessa versão, usar a UI ou `ha addons info --help`; não
instalar/habilitar serviços para consultar. **Não enviar a saída sem filtro**:
`options` pode conter Google/SMTP. `repository` pode ser só o ID, não a URL.
4. Consultar na UI arquitetura/versões, memória disponível e espaço livre do SSD.
   480 GB é capacidade, não espaço livre. Não fazer teste de saúde/estresse do SSD.
5. Consultar backups já existentes: data, componentes, tamanho e localização da cópia
   externa/kit de recuperação, sem criar/restaurar backup ou parar aplicativo agora.
6. Registrar a URL/caminho atualmente usados e o hostname já usado no proxy, sem
   editar Nginx/DNS/Google. Não enviar senhas, cookies, tokens, backups ou dados.

### Identidade: evidência e limite

No código-fonte/clone de distribuição 0.1.17 foi confirmado `slug: artesaos_piloto`,
pasta `apps/artesaos-piloto`, origem declarada
`https://github.com/mmcromero/fabricacao-e-orcamentos-ha`.
O SHA-1 dessa URL começa com `f6379561`, coerente com o hostname informado.
**É evidência de uma origem candidata, não consulta ao Supervisor real.**

O caminho fornecido posteriormente pelo operador,
`/config/app/f6379561_artesaos_piloto/info`, confirma o identificador com underscore,
igual ao manifesto. Manter `f6379561_artesaos_piloto`; hostname não define identidade.
Mesmo nome de exibição não implica mesmo aplicativo/volume.

## Compatibilidade preparada

O pacote C3 conserva slug `artesaos_piloto`, nome, `/data`, porta interna 8099,
`PILOT_OPTIONS_FILE=/data/options.json`, prefixo `/artesaos-piloto/`, Google/admin e
schema comum (tenant 10/control 3/interest 2/support 2/legal 2). Só declara aarch64.
Usa Node 24.19.0 Bookworm ARM64 e runtime JS pré-compilado. O runtime fica em `runtime.tar.gz` (inclui dependências, sem depender de arquivos
node_modules ignorados pelo Git). O Dockerfile entregue extrai esse payload; **não compila Vite/TypeScript nem instala npm no Pi**. A imagem-base
é fixada por digest. Não contém contas, bancos ou opções reais.

Build ARM64 e execução QEMU Cortex-A72 são evidências isoladas: não certificam o
Supervisor 2026.09.3, HAOS 18.3, kernel/SSD/memória/temperatura ou o Pi físico.
Core integra a UI/proxy; o aplicativo não troca o login HA por setup Debian.
Debian acompanha a versão, mas sua instalação física não bloqueia esta preparação.

## B. Após autorização específica — atualização pelo painel

1. Confirmar os itens da fase A. Se identificador/origem diferirem dos esperados,
   parar e reconciliar. Não desinstalar nem criar instalação local paralela.
2. Executar o plano **C3-RASPBERRY-BACKUP.md**: backup completo nativo protegido,
   cópia externa e possibilidade de restauração demonstrada, pacote anterior 0.1.17
   e acesso de recuperação local. Não avançar se backup/chaves/origem forem incertos.
3. O painel só oferece **Atualizar** se a versão 0.2.0-dev.11 estiver publicada na
   **mesma origem/repositório/branch já usada**, com slug inalterado. Esta preparação
   não publicou nem modificou a branch principal do repositório de distribuição.
   O arquivo tar.gz, sozinho, não faz aparecer o botão.
4. Em uma futura promoção autorizada, o responsável pela distribuição copia o conteúdo
   `apps/artesaos-piloto/` do pacote para **a mesma pasta da origem confirmada**,
   revisa e publica a versão. Não troca URL do repositório, não muda slug, não mexe
   nos outros aplicativos e não escreve em /data. Publicar na principal exige
   autorização separada; não está incluído na preparação C3.
5. Depois dessa publicação autorizada, na loja usar a ação de verificar atualizações;
   abrir o aplicativo existente e confirmar **0.1.17 → 0.2.0-dev.11**, aarch64.
   Usar **Atualizar**, preservando opções/dados. Não usar Desinstalar/Instalar como
   alternativa. Se o HA mostrar apenas Instalar, parar: pode ser outra origem.
6. Aguardar conclusão/reinício; conferir logs sanitizados e rodapé da versão. Bancos
   de tenants podem migrar na primeira abertura. Não editar SQLite nem regenerar chaves.
7. Testar Google administrador e usuário comum, sessão existente/novo login, duas
   contas isoladas, empresa/configurações/produtos/clientes/orçamentos/PDF e dados
   comerciais; depois compra/fabricação/pedido/reserva/pagamento/venda/sessão/Central/
   preparo com dados de homologação autorizados. Conferir desktop/celular.
8. Manter atualização automática desativada e backup anterior até homologação.
   Reinício completo do Pi, se desejado, só nessa intervenção autorizada.

### Se não houver atualização pelo painel

- **Origem Git:** a alternativa segura é promover a nova versão na origem existente,
  com permissão para essa publicação. Não há importador genérico de tar.gz de add-on
  na UI; não restaurar o pacote como backup nem criar origem `local` para contornar.
- **Origem local confirmada:** atualizar somente arquivos da pasta local já usada,
  conservando identidade/slug; recarregar a loja e atualizar/recompilar conforme a
  UI disponível. Não criar outra pasta/origem nem escrever nos dados.
- Origem/slug ainda não confirmados: o tutorial permanece condicional. Não manipular
  checkout interno do Supervisor, usar docker load no HA ou trocar imagem manualmente.

## Conferência do pacote no computador, antes de copiar

```sh
sha256sum --ignore-missing -c SHA256SUMS
tar -tzf artesao-digital-home-assistant-aarch64-0.2.0-dev.11.tar.gz
```

A raiz é `apps/artesaos-piloto/`. Em diretório de preparação novo, extrair e executar
`sha256sum -c SHA256SUMS` dentro dessa pasta. Conferir release.json, versão,
`arch: [aarch64]`, `slug: artesaos_piloto`, imagem-base e runtime. Não misturar arquivo
AMD64/Debian com o add-on ARM. A imagem Docker ARM de diagnóstico, se entregue à
parte, é para testes/reconstrução; não é arquivo de atualização/restauração da UI.
Hashes, origem e evidências dos artefatos finais ficam em `docs/ARTEFATOS_C3.json`.

## Condições para autorizar a atualização real

- Slug completo/origem confirmados; mesma instalação e diretório de dados.
- Fonte disponível na origem correta por publicação autorizada, sem mudar principal
  ou endereço de repositório por inferência.
- Backup nativo completo/cópia externa/chave de recuperação e pacote anterior.
- Integridade/restauração viáveis; espaço livre, memória e acesso de recuperação.
- Callback/URL/Google/allowlist/proxy atuais registrados com segurança e preservados.
- Janela de intervenção e critérios de interromper/recuperar definidos.

**Esta C3 termina antes de promover fonte na principal ou atualizar o Raspberry Pi.**
