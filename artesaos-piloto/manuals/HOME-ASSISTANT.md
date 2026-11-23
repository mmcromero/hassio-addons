> **0.2.0-dev.25 — entrada e boas-vindas:** consulte [PRIMEIRO-ACESSO.md](PRIMEIRO-ACESSO.md). Atualização de interface sem mudanças de slug, volumes, autenticação ou schemas. Instalação continua manual. Notas antigas abaixo são históricas.

## dev.20 — fotos de produtos sob /data

IMG-PROD-001 preserva a identidade do add-on e não altera opções/portas/autenticação.
Novas fotos são PNGs privados em /data/tenants/<tenant>/product-photos; conservar
.owner e imagens junto aos bancos. Não ficam em runtime.tar.gz. Upload/substituição
não apagam versões anteriores. URLs externas antigas continuam dependentes da origem
externa; novas referências externas são recusadas. Ver ATUALIZACOES.md para limites
de retorno ao código dev.19. Não desinstalar/recriar o add-on para atualizar.

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

# Procedimento vigente — contingência manual Home Assistant

Forja 01/Debian é principal. HA é plano B temporário. O pacote acompanha as publicações autorizadas;
instalação, atualização no equipamento e sincronização não são automáticas. A preparação ocorre no
repositório/ambiente de desenvolvimento, sem acessar o Raspberry Pi pessoal.

## Proxy HA: 502 resolvido pelo proprietário — 03/11/2026

Evidências recebidas: log NGINX `host not found in upstream` apontando a
f6379561-artesaos-piloto em /share/nginx_proxy_default_artesaos.conf:6; consulta
Supervisor retornou slug f6379561_artesaos_piloto, hostname
f6379561-artesaos-piloto, state started, version 0.2.0-dev.14. O proprietário
reiniciou o NGINX e confirmou que o acesso passou a funcionar. Não relatou alteração
de proxy, dados, credenciais ou rede. Não houve acesso/intervenção desta sessão Codex.

Destino confirmado para esta instalação:
`proxy_pass http://f6379561-artesaos-piloto:8099;`
Preservar HTTPS, porta externa 8443 e prefixo /artesaos-piloto/; não expor 8099.
O nome já estava correto. O resultado é compatível com indisponibilidade do nome
na inicialização do NGINX, mas não comprova a causa exata ou um problema de cache DNS.
Não foi necessário corrigir código da aplicação. Acesso restabelecido não representa
homologação completa de login, módulos, persistência ou recuperação no HA.

Para recorrências, sem alterar configuração por suposição:
1. Consultar Supervisor com nomenclatura atual:
   `ha apps info f6379561_artesaos_piloto --raw-json | jq '(.data // .) | {slug,hostname,state,version}'`.
   Não compartilhar options/credenciais. Identidade acima é desta instalação;
   instalações locais/de outra origem exigem consultar seu próprio hostname.
2. Comparar hostname com proxy_pass e conferir logs atuais/horários. Antes de
   iniciar o proxy, confirmar que a aplicação está iniciada. Não renomear por hipótese.
3. Se houver falha persistente, verificar resolução e HTTP a partir do contêiner
   NGINX por acesso já autorizado; teste no core-ssh não prova a rede do proxy.
   Ex.: getent hosts HOSTNAME ou nslookup HOSTNAME, se já disponíveis, e uma consulta
   sem credenciais a http://HOSTNAME:8099/artesaos-piloto/login. Não instalar ferramentas,
   alterar DNS, abrir portas ou publicar IP numérico para contornar o problema.
4. Após confirmar destino/aplicação disponíveis, considerar reinício somente do
   NGINX com autorização: pode interromper temporariamente outros serviços que ele
   atende. Não reiniciar o Home Assistant inteiro. Conferir configuração com nginx -t
   no contexto apropriado antes de aplicar qualquer edição. Nesta ocorrência o
   proprietário executou o reinício e confirmou recuperação; não repetir agora.
5. Validar URL HTTPS habitual com 8443 e registrar o resultado. Se o hostname já
   corresponder, não reescrever o arquivo apenas porque houve um erro de DNS anterior.

Não automatizar reinícios nem alterar configurações globais de DNS/segurança nesta
rotina. Impacto na Central de Pendências: nenhum, diagnóstico operacional.

## Identidade visual da loja (não altera o aplicativo)

**P0 — Identidade da loja Home Assistant (22/11/2026):** antes de fechar qualquer candidata, conferir o padrão vigente no [README do hassio-addons](https://github.com/mmcromero/hassio-addons/blob/main/README.md) e os arquivos oficiais do catálogo. Para Artesão Digital, `name: "Fábrica de Softwares - Artesão Digital"`, `icon.png` e `logo.png` na raiz do add-on. Blobs oficiais registrados no catálogo em `8666d9ab6c2967985e5160afc4aaeedf145dba71`: icon.png `a0fdd10938db1b6a65aa60469e83ed1c7c9bd33a`, logo.png `7e500016222b0a5bf395be8ed17447edeb3e2af9`. Conferir no freeze e após publicar, inclusive SHA256SUMS. Atualizar a referência somente com mudança oficial comprovada. Fonte dos PNGs: `apps/umdoislab/pilot/store/`; não usar as imagens internas de `branding/` para a loja. Preservar estritamente `slug: artesaos_piloto`, pasta `apps/artesaos-piloto/`, origem `mmcromero/fabricacao-e-orcamentos-ha`, opções, /data, arquitetura e identidade interna. Não migrar catálogo, desinstalar, reinstalar ou alterar Forja. Uma correção de apresentação não exige repetir testes funcionais válidos, mas requer verificação do manifesto, dos assets e da exportação. A dev.29 não conforme permanece histórica; corrigir em nova versão, nunca sobrescrever a mesma versão.

## Preparar candidata HA por fonte — 22/11/2026

Para alterações elegíveis (UX sem mudança de schema, dependências ou contrato operacional), usar a norma AD-ESTEIRA-RAPIDA-001 no repositório fonte, caminho docs/operacao/AD_ESTEIRA_RAPIDA_001.md. O exportador scripts/prepare-ha-source.py verifica os SHAs congelados, versão, identidade e hashes, e prepara o Dockerfile que fará npm ci/build e verificará schemas no Supervisor. Não exige build ARM64 externo, QEMU ou Actions por rotina. O pacote permanece candidato, sem homologação. Testes dirigidos e segurança proporcional antes de publicação; homologação real após atualização manual. Não modificar Forja, dados, slug ou opções.

## Preparar pacote ARM64 pré-compilado — trilha alternativa

1. Ler AGENTS.md, nível de segurança aprovado e docs/operacao/DISTRIBUICOES.json.
2. Em commit limpo, gerar recibo pelo release-evidence.py e exportar pelo
   prepare-distributions.py com --validation. A pasta artesaos_piloto é fonte HA;
   não confundir seu tar com o complemento ARM64 pré-compilado.
3. Construir imagem com Dockerfile dessa fonte e --platform linux/arm64. O estágio
   de compilação usa BUILDPLATFORM; metadados/labels devem apontar à mesma fonte.
4. `python3 scripts/prepare-ha-aarch64.py --source /FONTE/artesaos_piloto --image
   IMAGEM-ARM64 --output /SAIDA-NOVA` gera apps/artesaos-piloto, runtime.tar.gz,
   manifesto aarch64, manuais e checksums. Rejeita imagem AMD64 ou origem divergente.
5. Conferir SHA256SUMS, versão/commit/data, schema, labels e arquitetura. Build ARM64
   não comprova execução ARM64; testes Debian não certificam Supervisor/Pi. Informar
   separadamente build, emulação, hardware e validação de Google/proxy.
6. Se surgirem adaptações/testes HA acima do esforço rotineiro, parar antes do
   trabalho adicional e pedir decisão conforme AGENTS.md. Não mascarar ausência de
   homologação. Não publicar no repositório de add-ons sem autorização aplicável.

## Publicar no repositório existente — sem acessar o equipamento

Destino: https://github.com/mmcromero/fabricacao-e-orcamentos-ha, branch main,
apenas apps/artesaos-piloto. Autenticação Git do ambiente deve autorizar escrita
nesse repositório; usar o gerenciador de credenciais/secret seguro já configurado,
nunca gravar tokens na URL, no pacote ou no Git. Não depende do acesso SSH ao Forja.

1. Conferir remote, branch, árvore limpa e fetch origin main; não sobrescrever
   alterações remotas. Exigir avanço normal, sem force push.
2. Usar prepare-ha-source.py pela receita rápida quando elegível; caso de risco específico, reutilizar a trilha pré-compilada acima. Conferir versão superior, autorização e SHA remoto.
3. Promover somente o conteúdo validado apps/artesaos-piloto, preservando exatamente
   repository.yaml e apps/umdoislab legado. Incluir nota PUBLICACAO-VERSAO.md com
   origem/testes/limitações; recalcular SHA256SUMS após acrescentar a nota.
4. Verificar checksums e concordância config.yaml/release.json/Dockerfile/labels. Conferir runtime.tar.gz apenas quando a trilha pré-compilada o gerar.
   Revisar git diff --stat e arquivos, commit e git push origin HEAD:main.
5. Comparar git rev-parse HEAD com git ls-remote origin refs/heads/main. Em um clone
   novo do commit remoto, repetir checksums e conferência de versão/runtime. Registrar
   o hash remoto em docs/operacao/DISTRIBUICOES.json no repositório funcional.

Disponibilidade no Git confirmada não certifica descoberta da atualização por um
Supervisor real. O proprietário recarrega/verifica atualizações da loja de add-ons
na origem existente e escolhe Atualizar manualmente (Nível 1: backup recomendado).
Não desinstalar/reinstalar para atualizar, não mudar slug/origem nem /data. Se o
add-on estiver ausente, instalar manualmente da mesma origem somente quando necessário.
Depois conferir versão/logs/healthcheck/login. Retorno é manual, preservando dados e
compatibilidade conforme RECUPERACAO.md; nunca fazer downgrade de schema por suposição.

## Instalar/ativar manualmente — somente em emergência autorizada

Preferir mesma origem https://github.com/mmcromero/fabricacao-e-orcamentos-ha e slug
artesaos_piloto quando houver instalação existente a preservar. A loja só oferece
os arquivos publicados naquele repositório; a branch funcional não atualiza o Pi.

Para instalação LOCAL NOVA a partir do pacote, com autorização operacional: verificar
checksums e extrair em preparação, copiar o conteúdo de apps/artesaos-piloto para
/addons/artesaos_piloto por mecanismo autorizado do Supervisor, recarregar a loja e
instalar o add-on local correspondente. Esse caminho cria identidade local distinta
da origem GitHub; não é atualização nem recuperação automática da instalação antiga.
Se existir pasta/add-on/dados, não sobrescrever ou desinstalar por suposição.

Antes de iniciar: verificar capacidade disponível sem afetar serviços domésticos;
configurar opções HTTPS/Google e allowlist administrativa locais, mantendo 8099 sem
exposição pública e o prefixo /artesaos-piloto/. Usar hostname real exibido pelo HA.
Proxy/rede exigem autorização separada; não aplicar alterações residenciais nesta
preparação. Não reutilizar automaticamente credenciais/volumes Debian.

Iniciar manualmente e conferir logs sanitizados, versão/commit/data/arquitetura,
login administrativo Google, login comum/convites e operações sintéticas. Não aplicar
Primeiro Acesso/senha Debian no HA. Registrar nível aplicado, riscos e resultado.
No Nível 1, backup recomendado sem certificação bloqueante; no Nível 2 aplicar as
condições aprovadas antes de alterações sobre dados existentes. Nenhum nível autoriza
exclusões ou restauração destrutiva por consequência.

## Dados da contingência — pendências separadas

- Recuperar dados Debian no HA: não implementado; bindDistribution bloqueia volumes
  de outro adaptador. Instalação emergencial pode começar vazia conforme decisão.
- Operar temporariamente: mesma base de negócio, configuração/autenticação próprias;
  capacidade e instalação física precisam de validação quando ativadas.
- Retornar dados HA ao Forja: mecanismo de transferência controlada pendente.
- Evitar duplicações/conflitos na transição: procedimento pendente; não mesclar bancos.
- PWA: sincroniza apenas com Forja; não há troca automática de destino para HA.

---

## Histórico de versões e instruções anteriores

Trechos abaixo documentam versões antigas. As prioridades e o procedimento vigente
acima prevalecem sobre afirmações antigas de HA como ambiente principal. Nenhuma
instrução histórica concede autorização operacional atual.

> Versão corrente: **0.2.0-dev.13**. Ver [estabilização e convites](ESTABILIZACAO-CONVITES.md).
> Pix aceita telefone BR com DDD; confirmação/erro aparece junto ao formulário.
> Migração incremental control4; demais schemas preservados. Manuais/evidências
> de versões anteriores abaixo são históricos. Não atualizar instalações reais
> sem autorização específica e backup consistente.

> Versão corrente: **0.2.0-dev.12**. Ver [administração dinâmica](ADMINISTRACAO-DINAMICA.md).
> Migrações tenant 11/legal 3, demais schemas preservados. Backup integral inclui
> documentos, aceites e PDFs em pilot-legal.sqlite. Não fazer downgrade sobre banco
> migrado. Instruções/evidências de versões anteriores abaixo são históricas.

## C3 — identidade reconciliada e publicação autorizada

O operador forneceu `/config/app/f6379561_artesaos_piloto/info`: slug completo
**f6379561_artesaos_piloto**, coerente com o manifesto e o pacote. O conflito
anterior foi resolvido, sem mudar identificadores. Autorização posterior: publicar
se não houver outros bloqueios. Publicação experimental permitida; atualização,
reinício, backup/restauração e homologação reais continuam sem autorização.
As limitações físicas conhecidas permanecem; QEMU não certifica o Raspberry Pi.

# Home Assistant — instalação, atualização e homologação

Versão de referência: **0.2.0-dev.11**. Para o Raspberry Pi 4 já instalado em 0.1.17, seguir [C3 atualização](C3-RASPBERRY-PI-ATUALIZACAO.md) e [backup específico](C3-RASPBERRY-BACKUP.md). Ambiente principal de instalação/testes/homologação.
Este manual acompanha os pacotes futuros. C1/C2 não autorizam executar estes passos
na instalação real: aguardar autorização específica para a primeira homologação.

## Pacote e requisitos

O artefato atual para o Pi é
`artesao-digital-home-assistant-aarch64-0.2.0-dev.11.tar.gz`, contendo
`apps/artesaos-piloto`, manifesto, Dockerfile e runtime pré-compilado em
`runtime.tar.gz`. Não contém bancos, credenciais ou dados reais; não é um backup
importável na UI. Destina-se à promoção revisada na mesma origem, e não a substituir
a instalação existente por um add-on local. A identidade foi reconciliada pelo caminho da interface informado pelo operador. SHA-256 e fontes em `docs/ARTEFATOS_C3.json`.

Base ARM64 Node 24.19.0 Bookworm fixada por digest; o Supervisor constrói a imagem
com o runtime já compilado, sem instalar npm/compilar frontend no Pi. QEMU é evidência
isolada; Supervisor/Pi físicos permanecem pendentes. É necessário HA com Supervisor;
Home Assistant Container/Core isolado não instala esse formato de complemento.
As instruções de instalação nova abaixo são genéricas e não se aplicam como
substituição da instalação 0.1.17 existente.

Antes de qualquer alteração real, registrar versão do HA/Supervisor, arquitetura,
origem/slug do add-on instalado, URL, hostname interno e configurações do proxy;
verificar espaço livre por inspeção não destrutiva e fazer backup completo protegido.
Não formatar nem testar estresse de disco. Não mudar o aplicativo principal de
Fabricação e Orçamentos; Artesão Digital mantém seus próprios dados.

## Integridade e instalação nova autorizada

1. Guardar o pacote e seu SHA256SUMS em local confiável. Na pasta do download:
   `sha256sum --ignore-missing -c SHA256SUMS`. Extrair em pasta de preparação; conferir
   a lista com `tar -tzf artesao-digital-home-assistant-0.2.0-dev.11.tar.gz`.
2. Copiar a pasta `artesaos_piloto` para `/addons/artesaos_piloto` da instalação HA,
   somente quando autorizada e se não houver instalação/pasta a preservar. Se já
   existir, seguir atualização abaixo; não substituir diretório/dados por suposição.
3. Loja de aplicativos → verificar atualizações/recarregar → aplicativos locais →
   **Artesão Digital — Testes** → instalar. Não iniciar antes de preencher opções.
4. Informar `public_url` HTTPS terminando exatamente em `/artesaos-piloto/`,
   `google_client_id`, `google_client_secret` e `admin_emails` com os administradores
   Google autorizados. SMTP é opcional e independente. Não publicar esses valores
   no Git ou logs. Não configurar o modo Debian nem Primeiro Acesso no HA.
5. Deixar a porta do host 8099 desabilitada. Usar o hostname interno real do add-on
   mostrado pelo HA para o proxy HTTPS existente. Não usar IP interno numérico que
   pode mudar ao reiniciar. Não expor SQLite, /data ou portas de diagnóstico.
6. Preservar a configuração Nginx atual. `generate-nginx.py --upstream-host HOSTNAME
   --output ARQUIVO-NOVO.conf` gera uma proposta sem sobrescrever: revisar e validar
   `nginx -t` antes de aplicar em etapa real autorizada. Não alterar rede/proxy agora.
7. Iniciar e conferir logs sem segredos, login comum, administração e rodapé da versão.
   Habilitar início automático no HA somente após a homologação autorizada.

## Google, administração e permissões

Callback exato: `https://SEU-ENDERECO/artesaos-piloto/auth/google/callback`.
Manter as URLs/credenciais atuais do HA na atualização. Conta administrativa continua
Google + allowlist `admin_emails`; usuários comuns continuam Google + convite e tenant
próprio. `/artesaos-piloto/admin/login` é o acesso administrativo. Não existe senha
padrão nem setup local no HA. Convites são geridos pela administração, não nas opções.
Termos/onboarding continuam conforme a configuração existente. Restrições de público
em teste do Google são independentes dos convites do aplicativo.

## Atualização de instalação existente

1. Confirmar **mesma origem/repositório/pasta e slug**. Instalar como outra origem
   pode criar outro identificador e volume: não equivale a atualizar. Não desinstalar
   para atualizar nem converter automaticamente add-on de repositório em add-on local.
   Se a origem real diferir, registrar e definir a rota de atualização antes de agir.
2. Fazer backup frio nativo do HA incluindo o Artesão Digital e suas opções; guardar
   pacote anterior, identificador, versão e acesso de recuperação local. Não depender
   apenas de acesso remoto para uma alteração do proxy. Conferir cópia protegida.
3. Atualizar somente os arquivos do pacote na **mesma origem**, sem tocar em /data,
   opções, bancos, chaves ou demais add-ons. Usar Atualizar/Recompilar do Supervisor,
   de acordo com a origem; não forçar instalação limpa.
4. Migrations executam no primeiro acesso/início dos bancos correspondentes, por
   tenant e scope. Bancos de tenants não abertos podem migrar sob demanda. Não editar
   SQLite. Se schema/checksum incompatível, inicialização é recusada; parar e investigar.
5. Validar os critérios abaixo e manter backup anterior até aprovação. Erro de
   atualização não autoriza apagar dados ou reinstalar. Ver RECUPERACAO.md.

## Backup, restauração e falhas

`backup: cold` no manifesto permite backup nativo com parada do add-on. Usar o fluxo
oficial do HA, incluindo opções e dados completos; proteger backup por conter segredos.
Também guardar pacote-fonte anterior. Não copiar somente validation.sqlite de um
usuário: controle, sessões, contatos cifrados, chave de cifra, anexos/logo, legal,
suporte, interesses e tenants são necessários. Não fazer cópia quente parcial.

Restauração em instalação real exige nova autorização, versão compatível e backup
verificado. Usar restauração nativa do HA na origem correta; nunca restaurar volume
HA no Debian. Não executar downgrade sobre schema já atualizado. Um backup anterior
não contém operações feitas depois dele. Testar restauração isoladamente antes.

Após falha/reinício: conservar dados e logs sanitizados; verificar status, versão,
espaço livre e hostname. Mensagem “Acesso permitido somente pelo Ingress” pode indicar
proxy apontando ao processo errado; não remover proteção. Conferir destino/hostname.
Reinício do proxy, quando necessário, pertence a uma intervenção real autorizada.

## Checklist para primeira homologação real — ainda pendente

- Arquitetura/Supervisor, instalação pela origem correta e preservação das opções.
- HTTPS/cookies e Google reais; admin permitido e bloqueio de não administrador.
- Primeiro e segundo login comum, isolamento de duas contas, sessões/logout.
- Produto/material/compra/fabricação, orçamento/PDF/pedido, reserva/entrega, pagamentos,
  venda/sessão/consignação, Central e embalagem/preparo (usar dados de homologação).
- Desktop e celular, backup frio/restauração, reinício do HA e recuperação do proxy.

C2 testa processos/contêineres e identidades controladas; não simula o Supervisor
inteiro nem certifica a instalação física. Debian não precisa estar pronto para
aprovar correções ou novas versões no HA.
