## dev.21 — consulta offline de Produtos

Preservar DATA_DIR inteiro, especialmente `.offline-key`, bancos e fotos. A nova
chave protege cópias locais e deve acompanhar a instalação ao recuperá-la; não é uma
credencial de API. Nenhum schema novo. Não limpar perfis/IndexedDB/caches na atualização.
Logout bloqueia sem apagar; mesma conta online recupera. Browser/SO podem limpar dados.
Usar kit Forja e add-on manual existentes; Nível1, sem requisito novo de certificação.
Rollback de código conserva volumes, mas dev.20 não oferece consulta offline e seu
worker antigo pode limpar assets públicos. Recuperação exige código/chave compatíveis;
não apagar dados nem restaurar banco automaticamente. Ver documentação OFF-01.

## dev.20 — fotos internas persistentes, IMG-PROD-001

Upload para produtos/consignados usa data/tenants/<tenant>/product-photos, incluindo
.owner (namespace persistente) e PNGs identificados pelo hash. Conservar a pasta
inteira junto ao banco do negócio: copiar só o SQLite não recupera as novas fotos.
Os mecanismos existentes que preservam/incluem todo o diretório data abrangem essa
estrutura; não excluir arquivos antigos nem .owner, não confundir com assets da imagem.
Nenhuma migração de schema ou download automático de URLs antigas é executado.
Arquivos criados/substituídos pelo usuário ficam fora da imagem, sob /data no HA e
no volume data do Forja. O nome/slug/portas/opções/credenciais dos adaptadores não mudam.

Usar atualizador Windows existente no Forja e atualização manual do mesmo add-on no
HA, após autorização de instalação. Nível1 mantido; backup recomendado sem requisito
novo de certificação. Publicar não instala. Após instalar, conferir versão/health,
login, envio/prévia/salvamento/substituição e reabertura das fotos nos dois ambientes.

Rollback pelo mecanismo existente preserva volumes/config/bancos/fotos. Sem schema
novo; contudo dev.19 não compreende referências api/product-photos/...: fotos internas
não serão exibidas e formulários antigos podem rejeitar a edição desses produtos.
Não apagar/converter referências ou arquivos para contornar isso. Coordenar o retorno
com a infraestrutura, reconhecendo essa limitação, ou corrigir no código compatível.
Nunca executar restauração de banco ou downgrade de dados automaticamente.

## dev.19 — feedback e navegação jurídica; somente Debian

Inclui exclusivamente UX-FEEDBACK-001/UX-LEGAL-001 sobre a dev.18. Sem schema novo,
migração ou alteração de autenticação/regras. Exige novo login pelo mecanismo de
versão existente. Antes de continuar, revisar/copiar campos não salvos conforme aviso.
Nível 1 preservado, backup recomendado sem certificação bloqueante.

Exportação somente Debian: usar o mesmo prepare-distributions.py com --debian-only.
A opção padrão continua exportando ambos os destinos. A opção restrita gera apenas
a árvore Debian e seu tar; nenhuma distribuição Home Assistant dev.19 é produzida.
ZIP/descriptor/índice públicos seguem prepare-forja-windows.py, sem executar SSH.
Publicação no GitHub não instala. Instalação futura: comandos Windows existentes,
plano/aceites/sudo, somente após autorização da infraestrutura/proprietário.
Rollback pelo procedimento existente de RECUPERACAO.md, preservando volumes,
configurações e registros; esta alteração de UI não exige restauração de bancos.
Homologar indicadores e os seis retornos jurídicos em desktop e Android/PWA real.

## dev.17 — primeira adoção de PWA-UPDATE-001

Antes da instalação autorizada: salvar/conferir informações e fechar/recarregar
manualmente abas antigas da dev.16, conforme aceite do proprietário único. A primeira
adoção não promete proteção retroativa. Da versão com mecanismo em diante, troca de
versão exige novo login e aviso conservador de alterações locais; Revisar mantém a
página para cópia, sem permitir novas gravações incompatíveis.

Homologação inicial: versão/commit, acesso/login, funcionamento básico, card de apoio
no final de Ajuda/Suporte e ausência de erros críticos aparentes. Ensaios extensos de
integridade/rascunhos/offline ficam em PWA-DATA-001, sem iniciar PWA-02 aqui.
Publicar/disponibilizar não instala. Nível 1 mantido; backup recomendado, não exige
certificação como nova condição. Usar os mesmos CMDs e procedimentos de retorno.

## Distribuição dev.16 — UPD-CMD-01 e link obrigatório

Kit Windows: Baixar-Pacote.cmd → Verificar-Download.cmd (opcional) →
Atualizar-Forja-01.cmd (somente com autorização). Download/diagnóstico não instalam.
Preservar configuração, credenciais e atalho; atualizar apenas Forja01.ps1 e acrescentar
Baixar-Pacote.cmd quando a ferramenta anterior não tiver o downloader.

Em toda publicação Debian/Windows entregar versão, nome real do ZIP, URL HTTPS
direta clicável e verificada, SHA-256 e disponibilidade pública confirmada, conforme
AGENTS.md. Publicar/conferir manifesto por versão e arquivos antes de promover
publicacao-atual.json na origem existente. Regras operacionais N1/N2 não mudam.

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

> Segurança vigente por fase: consultar docs/operacao/SEGURANCA_POR_FASE.md no
> repositório e operation-policy.json no pacote. Nível 1 explicitamente aprovado:
> backup recomendado, sem bloqueio por ausência de certificação/cópia externa.
> Nível 2 exige as evidências e parâmetros aprovados. Esta regra substitui a
> exigência indistinta de backup nas instruções históricas abaixo.

> Versão corrente: **0.2.0-dev.13**. Ver [estabilização e convites](ESTABILIZACAO-CONVITES.md).
> Pix aceita telefone BR com DDD; confirmação/erro aparece junto ao formulário.
> Migração incremental control4; demais schemas preservados. Manuais/evidências
> de versões anteriores abaixo são históricos. Não atualizar instalações reais
> sem autorização específica e backup consistente.

> Versão corrente: **0.2.0-dev.12**. Ver [administração dinâmica](ADMINISTRACAO-DINAMICA.md).
> Migrações tenant 11/legal 3, demais schemas preservados. Backup integral inclui
> documentos, aceites e PDFs em pilot-legal.sqlite. Não fazer downgrade sobre banco
> migrado. Instruções/evidências de versões anteriores abaixo são históricas.

# Atualizações futuras — contrato de distribuição e continuidade

Forja 01/Debian é principal para operação e homologação. Home Assistant é apenas
contingência manual; respeitar a regra de esforço adicional em AGENTS.md. Não
compartilhar volumes, credenciais ou contas entre instalações.

## Para desenvolvimento de cada versão

1. Ler AGENTS.md/continuidade, verificar branch/diffs/HEAD/remoto efetivo e autorização.
2. Preservar regras comerciais e autenticação de cada adaptador. Alterações de schema
   são comuns, aditivas/migradas e testadas; não editar migrações históricas/checksums.
3. Atualizar artesao-release.json e pilot/config.yaml para a mesma versão. Base principal
   só muda por incorporação autorizada, preservando core-base.json e rastreabilidade.
4. Atualizar estes quatro manuais, limitações, relatório e critérios de compatibilidade.
5. Testar código, produzir ambos os pacotes de um commit limpo usando
   `python3 scripts/prepare-distributions.py --output DIRETORIO-NOVO --validation /CAMINHO/recibo.json`.
   Gerar o recibo antes com `python3 -B scripts/release-evidence.py --output /CAMINHO/recibo.json`
   sobre commit limpo. Não editar o recibo para simular aprovação.
   Opcional `--image-archive CAMINHO/image.tar` inclui imagem Docker amd64 previamente
   construída/tagueada da mesma fonte. O exportador não constrói nem instala serviços.
6. Validar SHA256SUMS, manifestos, hash do código comum, instalação/upgrade/backup/restore,
   login/permissões, integridade, reinício e UI nos pacotes. Informar simulado versus
   real; não usar compatibilidade física não testada como alegação de sucesso.
7. Commit/checkpoint/push na branch autorizada, comparar `git ls-remote` com HEAD;
   publicar artefatos revisáveis com versão/commit/checksums. Push não é implantação.

## Operador HA

Seguir HOME-ASSISTANT.md: mesma origem/slug, backup frio protegido, conservar pacote
anterior, atualizar sem desinstalar/zerar dados, validar Google/tenant e operações.
Supervisor real e proxy exigem autorização específica. Não fazer merge na principal
como parte de teste experimental nem transferir credenciais de outro aplicativo.

## Operador Debian — atualização controlada por imagem

A ferramenta nova `operations.py` complementa `manage.py`; não reinstala a aplicação.
Não é um serviço permanente. Produção exige autorização operacional separada.

1. Exportar e validar pacote de origem exata. Construir **fora da instalação ativa**:
   `docker build -t artesao-digital:REVISAO -f PACOTE/app/Dockerfile PACOTE/app`.
   Não usar o app/ antigo da instalação para reconstruir a versão nova. No cloud,
   usar CA/proxy BuildKit documentados, sem desativar TLS.
2. Executar `python3 operations.py --root /srv/artesao-digital-app collect` com helper
   disponibilizado em diretório de ferramentas aprovado. Saída sanitizada informa
   declaração, labels, ID real e metadados do runtime, divergências e healthcheck.
3. No Nível 2, exigir backup e recuperação; no Nível 1, recomendar sem tornar
   certificação condição bloqueante. Helper de backup: `python3 /PACOTE/manage.py --root
   /srv/artesao-digital-app backup --output /BACKUP-NOVO`; guardar cópia externa e imagem anterior.
   Testar recuperação isolada e registrar evidência, conforme RECUPERACAO.md.
4. Executar `python3 operations.py --root /srv/artesao-digital-app plan --package
   /PACOTE --policy /POLITICA-APROVADA.json`. No Nível 2 acrescentar
   `--archive /BACKUP --recovery-evidence /ATESTADO.json`; no Nível 1 são opcionais. Somente com zero
   bloqueios prosseguir. A ferramenta não instala dependências nem carrega imagem:
   carregamento/construção deve ser feito em etapa autorizada antes.
5. Com autorização e política aprovada, mesmo comando usando `apply` e acrescentando `--image IMAGEM
   --approve-update`. Instalação legada sem metadados exige ainda
   `--allow-legacy-current`, após revisão explícita da incerteza da origem.
6. O helper mantém a imagem anterior referenciada por contêiner parado; cria recibo
   privado em .operations/, seleciona a imagem por ID em compose.override.yaml e
   executa Compose sem build/pull. Compara configuração efetiva antes/depois: somente
   imagem/pull_policy podem mudar. Override existente sem proveniência ou modificado causa bloqueio para revisão.
7. Mantém app/, compose.yaml, data/, config/, private-codes/ e .env originais.
   .operations/active-release.json registra a declaração ativa, separada do pacote
   histórico. **Não reconstruir usando o app/ histórico.** A seleção normal do Compose
   passa a usar compose.override.yaml; não remover nem ignorar esse arquivo.
8. Verifica healthcheck, imagem, labels e runtime. `collect` diferencia concordância
   técnica de homologação funcional, que continua pendente. Não exporta logs brutos.
   Verificar logs localmente com sanitização e testar acesso/autenticação no endereço
   aprovado. A ferramenta não afirma que login real foi testado.

O atualizador recusa schemas diferentes e compara todas as migrações dos bancos do
backup ao catálogo da imagem de destino. Tenant ainda não migrado também bloqueia:
nenhuma autorização de migração é inferida. Não restaurar dados durante atualização.
Falha não apaga nem recria volumes e não inicia desenvolvimento corretivo automático.
Retorno por imagem exige aprovação, mesmo catálogo e fonte interrompida, conforme
RECUPERACAO.md. Sem Docker acessível, pacote e plano podem ser preparados, mas não
há prova de implantação. Novas atualizações aceitam apenas override criado pela ferramenta e com hash
inalterado; qualquer configuração externa exige revisão operacional.

## Pendências permanentes de homologação

- Instalação/atualização/backup nativo Supervisor, Google/TLS/cookies reais no HA.
- Samsung/Debian físico, arquitetura/recursos/espaço/desempenho e início no boot.
- DuckDNS/CGNAT/HTTPS/renovação, proxy/firewall e acesso de rede isolada/celular.
- ARM/aarch64 e dispositivos/compartilhamento reais, quando aplicável.

A autorização C1/C2 prepara e testa em isolamento. Ao concluir, parar e aguardar
permissão específica para a primeira instalação real no Home Assistant.

Para C3/Raspberry Pi 4, usar o roteiro específico C3-RASPBERRY-PI-ATUALIZACAO.md: confirmar identidade/origem, não converter instalação e não confundir imagem de diagnóstico com backup/importação da UI.
