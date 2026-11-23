# 0.2.0-dev.33 — recuperação integrada do PDV (22/11/2026)

- Reintegra a evolução visual do PDV: cabeçalho contextual compartilhado, contexto da sessão, painel de catálogo/carrinho/pagamento em desktop e etapas operacionais no mobile.
- Preserva a navegação geral, a identidade oficial do Artesão Digital quando não há logo do negócio, o catálogo de venda separado do cadastro de Produtos e o rodapé no fluxo.
- Atualiza o roteiro de verificação visual para desktop e mobile, incluindo identidade, geometria, painéis, carrinho e navegação.
- Sem alteração intencional de schema, dependências, API, autenticação, contratos de venda ou dados. Testes automatizados, build no Supervisor e homologação visual/funcional permanecem pendentes.

# 0.2.0-dev.32 — recuperação de UX de 13/11 (22/11/2026)

- PDV e Produtos compartilham cabeçalho e menu geral; largura normal no desktop, catálogo interno separado, sem barra inferior na entrada do PDV e rodapé fluido.
- Preservados motor de venda, ficha técnica, materiais, schema, identidade da loja, dados e Forja.
- Autorização excepcional do proprietário via modo pair: publicação de candidata para validação no HA antes do teste automatizado de navegador; build e homologação pendentes.

# 0.2.0-dev.31 — recuperação PDV (22/11/2026)

- Restaura o último código preservado do PR #82; configurações gerais mantêm navegação UX e controle de cor do PDV.
- Produtos: ações em lote acima do catálogo, controles Filtros e Ações em lote lado a lado em celular, consulta offline recolhível; preserva filtros e API.
- Preserva ProductForm, ficha técnica, alterações UX-STD-001, contratos de venda, schema, dados, identidade da loja e Forja. Build e homologação real pendentes.

# 0.2.0-dev.30 — identidade da loja HA (22/11/2026)

- Nome de apresentação Fábrica de Softwares - Artesão Digital e PNGs oficiais do catálogo (icon.png e logo.png).
- Preservados slug, pasta, origem, dados, identidade interna, código UX da dev.29 e Forja. Build Supervisor/homologação pendentes.

# 0.2.0-dev.29 — candidata de UX (22/11/2026)

- Organização mobile-first em categorias e abas; fichas de produto e fabricação, orçamento, estoque, pedidos, financeiro, clientes, ajuda, suporte e administração.
- Sem alterações diretas do PDV, schemas, dependências, opções ou slug. Preservar dados e a Forja 01.
- Candidata HA por fonte, AD-ESTEIRA-RAPIDA-001; build e homologação no Supervisor pendentes. Não representa versão estável nem atualização da Forja.

## 0.2.0-dev.26 — candidata local, não publicada

- Revisão contextual: Novo/Editar cliente dentro do PDV, sem liberar Clientes completo.
- Cadastros e recebimentos de consignados no PDV; referências de materiais separadas de operações físicas gerais.
- Correções da Central vinculadas à ocorrência/tenant, com operações originais, auditoria e idempotência; inclui pagamentos já agendados.
- Build/navegador aprovados; regressão Windows 255/265, dez limitações de plataforma; Linux integral e homologação real pendentes.

- Liberação manual de módulos por usuário na administração, com revisão e auditoria.
- Navegação e APIs verificam disponibilidade; serviços internos de PDV/fabricação preservados.
- Migração aditiva control 5 preserva contas existentes; novas contas iniciam com Essencial.
- Sem instalação, restrições comerciais ou redesenho do Pacote A. Ver docs/AD_CAIXA_FERRAMENTAS_001.md.

## 0.2.0-dev.25 — UX-PRIMEIRO-ACESSO-002

- Inscrição, login e convite em estados separados, com logotipo oficial e apresentação responsiva.
- Boas-vindas com nome/telefone obrigatórios, e-mail/Pix opcionais e logo opcional.
- Cadastro salvo antes dos cards Produtos/Precificação; Produtos sem custos prévios; onboarding concluído não se repete.
- Autenticação Google, convites, consentimentos, dados, slug e schemas preservados.
- Publicação conjunta HA ARM64/Forja AMD64 autorizada pelo proprietário; instalação sempre manual.
- Guia de entrada incluído nos dois pacotes em manuals/PRIMEIRO-ACESSO.md.

## 0.2.0-dev.23 — BR CODE-01 + RETORNO
## 0.2.0-dev.22 — BR CODE-01
## 0.2.0-dev.21 — OFF-01

- Preparação completa e verificável de Produtos/fotos internas para consulta offline.
- Reabertura da PWA sem rede, lista/busca/paginação existentes, alterações desativadas.
- IndexedDB cifrado por conta/negócio, confirmação atômica, cópia anterior conservada.
- Logout bloqueia acesso sem apagar cópias; mesma conta pode recuperá-las online.
- Worker preserva gerações e caches externos; sem escrita/vendas/sync offline.
- Nível1, sem schema novo, sem instalação nesta entrega. Ver docs/OFF-01.md.

## 0.2.0-dev.20 — IMG-PROD-001

- Fotos de produtos e consignados por arquivo, com prévia e substituição; sem novo
  campo de URL externa. PNG/JPEG/WebP preparados no navegador, PNG validado no servidor.
- Otimização até1024px/lado e500KB; arquivos persistentes privados por negócio em
  data/tenants/<tenant>/product-photos; referências imutáveis com hash, sem schema novo.
- Novas URLs externas recusadas nas APIs; valores antigos do próprio registro
  preservados sem download/conversão. Nenhuma foto anterior apagada automaticamente.
- Preparação para offline por identificador/hash; sem cache comercial ou sincronização.
- Publicação nos dois ambientes autorizada; instalação/homologação física separadas.
- Rollback para dev.19 preserva dados, mas essa versão não exibe e pode recusar edição
  de produtos com novas referências internas. Não apagar/converter fotos para retornar.

## 0.2.0-dev.19 — UX-FEEDBACK-001 + UX-LEGAL-001

- Distribuição exclusivamente Debian/Forja das duas melhorias já implementadas.
- Feedback por ação, prevenção de repetição, mensagens e retorno jurídico contextual.
- Sem mudanças de autenticação, schemas, dados ou regras comerciais.
- Home Assistant não empacotado/publicado nesta entrega; fonte comum mantém versão
  coerente para build. Publicação não instala nem homologa o servidor.

## UX-FEEDBACK-001 + UX-LEGAL-001 — implementação local, sem distribuição

- Feedback de processamento por ação/formulário, bloqueio de repetição e liberação
  após resposta/erro; reutiliza UX-Loading-01, sem bloqueio global novo.
- Mensagens específicas preservadas; falhas não tratadas recebem aviso seguro.
  Confirmações de categoria/arquivamento somente após resposta confirmada.
- Política de Privacidade padronizada nos links; botão Voltar contextual com sessão
  validada no servidor, origem permitida e continuidade login/landing na mesma aba.
- Conteúdo jurídico, histórico, autenticação, regras, schemas e distribuição intactos.
- Versão declarada dev.18 mantida. Próxima distribuição proposta dev.19, sujeita a
  nova conferência do Git e autorização; nenhum pacote ou servidor atualizado.
- Evidências e homologação: docs/UX-FEEDBACK-001-UX-LEGAL-001.md.

## 0.2.0-dev.18 — domínio público único

- Origem oficial Forja: https://artesaodigital.com.br/artesaos-piloto/; Tailscale
  destinado à administração privada SSH/pacotes/atualizações, sem segundo login web.
- Retirada a proposta de múltiplas origens; Host/Origin/CSRF/sessões preservados.
- Callback Google validado explicitamente contra a origem/caminho configurados;
  PKCE, nonce, estado, cookies e fluxo de autenticação existentes mantidos.
- Testes de origem oficial, callbacks negativos, sessões/CSRF, PWA e Chromium local.
- Ativação, transição de PWA e rollback documentados em DOMINIO-PUBLICO.md; sem
  migração, offline, alterações comerciais ou instalação de servidores.

## 0.2.0-dev.17 — R1.4

- Distribuição de AD-UX-002: apoio voluntário aberto e após conteúdo de Ajuda/Suporte.
- Distribuição de PWA-UPDATE-001: detecção de versão, bloqueio preventivo de operações,
  logout/login controlados e aviso conservador antes de abandonar alterações locais.
- Primeira adoção aceita recarga manual de abas antigas; sem tratamento especial.
- PWA-DATA-001 registrada para futura homologação PWA-02, sem implementação.
- Mesmos schemas, identidade do add-on e contratos de distribuição. Nenhuma instalação
  autorizada por esta publicação. Homologação física posterior e limitada ao escopo.

## R1.3 — proteção de versão em desenvolvimento local, sem distribuição

- PWA-UPDATE-001: versão da página/servidor, marcador auxiliar de sessão, bloqueio
  preventivo de APIs e reautenticação controlada quando a versão muda.
- Aviso aprovado antes de abandonar estado local, com revisão/cópia sem logout.
- Sem offline, migrações, versão nova, push ou deploy. Primeira adoção exige recarga
  manual das abas antigas conforme aprovado. AD-UX-002 da R1.2 preservada.
- Evidências e limitações em docs/R1.3.md e R1.3-VALIDACAO.json.

## R1.2 — desenvolvimento local, sem nova versão de distribuição

- AD-UX-002: apoio voluntário aberto ao final de Ajuda/Suporte; conteúdo e ações preservados.
- PUSH-DOC-02: GOV-02 e DOC-UPD-01 enviados, remoto 3b2860a.
- PWA-UPDATE-001: não implementado; bloqueio da adoção em interfaces antigas e alternativa
  para aprovação em docs/R1.2.md. Não declarar proteção de atualização disponível.
- Sem pacote/deploy; versão declarada permanece dev.16. Testes locais não homologam dispositivos.

# 0.2.0-dev.16 — UX-Loading-01

Feedback discreto de espera em login local/Google, preparação do aplicativo,
navegação administrativa e requisições administrativas. Encerramento em resposta/
erro e restauração ao voltar à página. Autenticação, regras comerciais, schemas,
PWA e worker de rede preservados. Sem investigação de desempenho ou offline.
Implementação independente; não publicada nem instalada por esta entrega.

# 0.2.0-dev.15 — PWA-01 online e HA-UX-001

Manifest Android, escopo/prefixo próprios, identidade Artesão Digital com símbolo
existente e ícones 192/512. Janela standalone; autenticação/navegação preservadas.
Worker de rede sem cache mantido; sem offline comercial. Add-on apresentado como
Artesão Digital — Contingência, preservando slug, opções, /data e portas. Base 0.1.23
e schemas inalterados. Preparação local; sem publicação/instalação. iOS documentado,
não homologado fisicamente.

# 0.2.0-dev.14 — R1.1 e continuidade operacional

Inclui R1.1 (3471da1): cadastros consecutivos de interessados, alertas com conteúdo
e remoção do link redundante no login administrativo Debian. Feedback inicial,
Suporte e atalho financeiro existentes preservados. Inclui rastreabilidade,
procedimentos operacionais e segurança por fase até 79679b9. Versão incrementada
para o Supervisor identificar a atualização; base 0.1.23 e schemas inalterados.
Publicação GitHub não significa instalação no Forja ou homologação no Raspberry Pi.

# 0.2.0-dev.13 — estabilização e convites

- Pix: telefone BR, persistência/recarga, confirmação/erro junto ao botão, espera
  independente e proteção contra sobrescrita pela leitura inicial atrasada.
- Rodapé: links primeiro, versão própria automática centralizada na última linha;
  referência visual à base removida, metadados internos preservados.
- Interessados: geração/reutilização de convite com vínculo histórico e sem duplicar;
  mensagem/código/link prontos, cópia, WhatsApp e SMTP existente com estados reais.
- Migração incremental control4, sem datas retroativas e sem alteração de instalações.

# 0.2.0-dev.12 — suporte, documentos dinâmicos e sessões

- Suporte abre a listagem; formulário somente por ação explícita, sem erros iniciais.
- Administração dinâmica de documentos/rascunhos/publicações/histórico e manual PDF.
- Termos obrigatórios por API e interface; auditoria de aceite/ciência/recusa imutável.
- Pix opcional administrável em Suporte e Ajuda.
- Visitantes manuais por sessão com eventos, idempotência, preferência e conversão estimada.
- Clientes: tipo informativo, origem e sessão de captação preservadas; novos contatos.
- Migrações tenant 11/legal 3; sem mudanças de preços históricos ou dados reais.
- [Instruções administrativas](../distribution/docs/ADMINISTRACAO-DINAMICA.md).

## 0.2.0-dev.11 — C3 preparação Raspberry Pi 4

- Build cruzado e guard de dependências produtivas portáveis; schema comum preservado.
- Add-on aarch64 com runtime pré-compilado rastreável, sem npm/Vite no Pi.
- 179 testes comuns, ARM64/QEMU Cortex-A72, upgrade 0.1.17, dados/sessões/chaves,
  backup/restauração e reinício/falha isolados validados. Não certifica Pi/Supervisor.
- Tutorial por identidade/origem e plano de recuperação; nenhuma promoção principal
  ou atualização real. Debian acompanha a mesma versão de forma independente.

## 0.2.0-dev.10 — C1/C2 distribuição

- Add-on HA e pacote Debian Compose da mesma fonte/schema, com SHA256SUMS e imagem amd64.
- Manuais permanentes de instalação/atualização e backup/recuperação; helper conservador.
- Healthcheck preserva Host; assets imutáveis legíveis sem root e volumes privados mantidos.
- 176 testes da fonte exportada + 8 do helper, runtimes/Compose/backup/restore/crash e
  navegadores desktop/mobile aprovados em isolamento. Homologação real ainda pendente.
- HA principal; Debian independente, sem bloquear novas versões pela falta do notebook.

## 0.2.0-dev.10 — B10

- Embalagem cadastrada ou custo manual na ficha; última compra e fabricação existentes.
- Sugestão geométrica conservadora com orientação/folga e estimativa de massa/custo.
- Preparo real integral por pedido: lotes, transação/idempotência, histórico e déficit.
- Cotação sem baixa ou novo financeiro; embalagem incluída e peso real preservados.
- Cinco grupos de Configurações com cadastros e serviços anteriores reutilizados.
- 176 testes, build, navegador B3–B10 1280/390 e regressão de UI incluindo 320 px;
  atualização/restauração sintéticas e paridade de cinco schemas aprovadas.
- Etapa C depende de autorização; nenhum pacote instalável/deploy/produção alterado.

## 0.2.0-dev.9 — B9 e fechamento B4–B9

- Central de Pendências no cabeçalho, contador, filtros, agrupamento e histórico.
- Correções por origem/local, resolução justificada e vencimentos sem duplicação.
- Históricos antigos por cursor e PDF com quebra pela largura real da fonte existente.
- 166 testes, build, navegador B3–B9, atualizações/restaurações sintéticas e paridade
  dos cinco schemas aprovados. Nenhum servidor ou banco real alterado.
- B10 e empacotamento/implantação final aguardam autorização conforme plano.

## 0.2.0-dev.8 — B8

- Sessões opcionais e conferência física independente do fechamento financeiro.
- Consignados de terceiros, repasses fixos, remessas/acordos de parceiros e acertos.
- Destinação explícita de excedentes privados e preferência de tela inicial.
- Áreas carregadas sob demanda; 155 testes, build e navegador integrados aprovados.

## 0.2.0-dev.7 — B7

- Venda imediata multi-item com pagamentos, descontos/cupons e comprovante não fiscal.
- Saldo insuficiente não bloqueia: saída e divergência persistem atomicamente.
- Troco correto, cupom só conta na confirmação e histórico preservado.
- 143 testes, build e navegador até venda/PDF aprovados em ambiente sintético.

## 0.2.0-dev.6 — B6

- Financeiro integrado a compras/pedidos, journal, contas e pagamentos divididos.
- Liquidação futura, crédito/reembolso explícitos e recorrências pendentes.
- Caixa separado de custos analíticos, sem dupla contagem; histórico preservado.
- 132 testes, build e navegador financeiro aprovados em ambiente sintético.

## 0.2.0-dev.5 — B5

- Pedidos diretos ou por aprovação de proposta, itens múltiplos e snapshots.
- Reservas centrais, fabricação própria/privada, edição, cancelamento e entrega.
- Orçamento aprovado preservado; Concluído somente após entrega do pedido.
- 122 testes, build e navegador com entrega integral aprovados.

## 0.2.0-dev.4 — B4

- Fabricação concluída transacional e idempotente com consumo físico de lotes.
- Estoque de produtos, ajustes e transferências sem duplicação de custos.
- Preços independentes, cópia automática somente no total físico exatamente zero,
  atualização opt-in por faixa e histórico preservado.
- 115 testes, build e fluxo de navegador em ambiente sintético aprovados.

## 0.2.0-dev.3 — B3, desenvolvimento sem publicação

- Consolidação versionada do schema legado, preservação/restauração verificadas em fixtures.
- Materiais no Estoque, classificações/acondicionamento, compras e unidades físicas.
- Última compra registrada define referência mesmo com data retroativa; sem custo médio.
- Consumo, ajustes, perdas e déficit auditados/idempotentes; obrigação financeira pendente única.
- Custos atuais sem regravar snapshots ou preços comerciais; logins HA/Debian preservados.
- Ver B3-MATERIAIS-COMPRAS.md; B4 não iniciada e nenhuma atualização real autorizada.

# 0.1.17 — gestão centralizada e convites sem vencimento (experimental)

- Remove os cinco pares e-mail/código das opções do Home Assistant e deixa de gerar convites por opções/variáveis antigas. Criação e gestão passam pela administração Web; contas, dados e convites persistidos são preservados.
- Remove o teto fixo de cinco contas/convites no modo de produção. Listas de usuários e convites usam paginação de 25 itens e busca. Consultas de telefone usam índice de identificação derivado por HMAC, sem decifrar todos os contatos.
- Novos convites não têm vencimento e continuam de uso único, vinculados à primeira conta Google verificada que usar o código. Convites existentes ainda ativos perdem o vencimento; expirados ou revogados não são reativados automaticamente. Os antigos mantêm sua regra de conta Google/e-mail.
- Acrescenta Revogar convite e Ativar novamente. A reativação gera outro código e nova mensagem; o código anterior permanece inválido. Contas já ativadas não são desativadas/reabertas por essas ações de convite.
- Preserva contatos, chave e histórico; mostra somente o código atual na lista operacional quando houver substituição. Reinício não reverte revogação nem a troca de código.
- Limita instâncias/bancos de contas abertos simultaneamente, reabrindo sob demanda e preservando os dados. Isso é controle temporário de recursos, não limite de cadastro.
- Mantém SMTP opcional, WhatsApp com mensagem pronta, base 0.1.23, aplicativo principal e textos jurídicos definitivos desativados. Entrega experimental; consulte VALIDACAO-0.1.17.md.

# 0.1.16 — administração e convites (experimental)

- Acrescenta Usuários cadastrados à administração: contas realmente ativadas, situação do acesso e Exibir dados cadastrais, com consulta restrita e leitura sem criar cadastros ausentes.
- Acrescenta Convites com nome, e-mail, WhatsApp e escolha do canal. Salvar gera automaticamente código de uso único e mensagem; sem estado nem confirmação de envio na lista.
- Novos convites vinculam à primeira conta Google verificada que usar o código válido. Contatos podem ser diferentes do login ou somente telefone. Convites antigos conservam o vínculo por e-mail.
- Convites aceitos saem da lista e aparecem em Usuários cadastrados; Exibir dados preserva os contatos informados no convite, separados dos dados da empresa.
- Prepara WhatsApp por link com mensagem e código preenchidos; e-mail manual ou SMTP opcional, desativado sem configuração. Nenhuma integração automática com a API WhatsApp Business.
- Cifra nome/telefone/código recuperável com chave própria, preserva o hash de autenticação, limite de contas, expiração e idempotência de registro. Protege consulta/gravação por administração, contexto, origem e CSRF.
- Documenta manutenção do principal independente e recuperação do acesso por reinício do Nginx após mudança de IP interno. Preserva base 0.1.23 e aplicativo principal.
- Aceite jurídico definitivo continua desativado. Não é primeiro release estável; consulte VALIDACAO-0.1.16.md.

# 0.1.15 — pacote experimental de testes

- Acrescenta logo opcional por conta, com prévia, otimização, substituição e remoção sem histórico de imagens no aplicativo.
- Gera PDF selecionável em memória, com empresa, cliente, produtos/preços escolhidos, quantidades, embalagem, frete, total e observações. Sem custos internos, margens ou multiplicadores.
- Preserva dados textuais e valores por edição finalizada, usa logo atual ao gerar novamente e oferece visualizar/baixar/compartilhar quando suportado. Compartilhar não marca como enviado.
- Prepara documentos públicos e aceite versionado antes das boas-vindas, com bloqueio no servidor quando ativado. Desativado por padrão; nenhuma minuta definitiva incluída.
- Reconstrói minutas e pendências operacionais com hospedagem pessoal no Brasil e ausência atual de backup. Mantém base 0.1.23 e aplicação principal.
- Entrega experimental, não primeiro release estável. Consultar DOCS e VALIDACAO-0.1.15.md para evidências e limites.

# 0.1.14

- Acrescenta link fixo de Suporte técnico no rodapé autenticado, com formulário de abertura de chamado para dúvida de uso ou relato de erro. O suporte também fica disponível durante as boas-vindas.
- Inclui a aba Meus chamados nas configurações, com histórico da própria conta, filtros, paginação, mensagens e acompanhamento de status.
- Acrescenta Central de suporte na administração, com consulta de todas as contas, resposta e mudança de status: Em aberto, Em análise, Respondido, Aguardando resposta do cliente e Finalizado.
- Mantém o histórico das mensagens e mudanças de status; a resposta do usuário retorna o chamado a Em aberto e permite reabrir um chamado finalizado.
- Protege acesso por conta e permissão administrativa, sessão, contexto da aba e CSRF. Inclui revisão para alterações concorrentes, limites de envio e chaves de reenvio para evitar duplicações em falhas de rede.
- Armazena chamados no volume do piloto, sem envio automático de e-mail nem coleta automática de arquivos ou registros comerciais. Preserva a base 0.1.23.

# 0.1.13

- Oculta a opção de catálogo para produtos de cliente, limpa a marcação ao mudar a origem e corrige os registros antigos. O servidor também impede a inclusão por edição, importação ou ação em lote.
- Mantém custos e precificação sempre expostos nas configurações gerais. Multiplicadores vazios, inválidos ou abaixo do mínimo são corrigidos e persistidos: atacado 1,5; loja de fábrica 2,0; varejo 3,0. Valores acima do máximo continuam exigindo revisão explícita.
- Acrescenta boas-vindas obrigatórias, com checklist e retomada em próximos logins até a conclusão. Exige empresa/responsável/telefone/e-mail, ao menos um material válido, uma tarifa horária positiva, horas produtivas mensais positivas e uma despesa operacional positiva. Tarifas horárias não utilizadas recebem zero.
- Bloqueia operações comerciais no servidor enquanto a configuração inicial não estiver concluída, preservando acesso aos cadastros necessários e à saída da sessão. A conclusão fica registrada no banco individual de cada conta.
- Rateia despesas pelo tempo humano quando o tempo de máquina da etapa é zero, conforme solicitado. Quando há máquina, utiliza somente esse tempo para o rateio; tarifas de trabalho humano continuam somadas normalmente. Preços comerciais e orçamentos anteriores não são substituídos automaticamente.
- Preserva a base 0.1.23 e o comportamento do aplicativo principal.

# 0.1.12

- Reorganiza o menu em Produtos, Clientes, Orçamentos e Configurações, com ícones. A faixa de navegação ocupa a largura abaixo do cabeçalho verde e usa botão hambúrguer para abrir/fechar os itens no celular, com suporte a Escape e teclado.
- Define Produtos como entrada após primeiro login, novo login e acesso à raiz. A antiga página de Fabricação deixa de existir no piloto; links antigos abrem Produtos, cujo formulário mantém os dados de fabricação e preços calculados.
- Reúne configurações em uma página: dados da empresa e parâmetros comuns nas configurações gerais, fora das abas Produtos, Clientes e Orçamentos. As abas preservam o preenchimento ao alternar e aceitam navegação por teclado.
- Acrescenta cadastro opcional de empresa, responsável, telefone e e-mail por conta, com validação, persistência e proteção contra sobrescrita por outra janela. Não inclui estes dados na tela nem em arquivos de orçamento.
- Registra o uso futuro dos dados da empresa somente no documento final do orçamento em Ideias Futuras, sem execução automática.
- Mantém a base 0.1.23 e os dados existentes. O novo cadastro cria apenas uma tabela adicional no banco individual do piloto.

# 0.1.11

- Atualiza o aviso no login para orientar a manter uma cópia das informações e informar que o ambiente está em construção e pode apresentar instabilidades.

# 0.1.10

- Prioriza a apresentação do piloto gratuito por convite e o formulário de interesse na entrada; separa o login em uma seção própria abaixo, acessível pelo link “já tenho um convite/login”.
- Integra a navegação das áreas ao cabeçalho fixo, em uma única linha. Em telas estreitas, o menu tem rolagem horizontal e mantém o item atual acessível; o e-mail fica oculto para reservar espaço à navegação e ao botão Sair.
- Ajusta o espaço do conteúdo à altura real do cabeçalho e preserva autenticação, isolamento e a base 0.1.23.

# 0.1.9

- Aplica a identidade visual em todas as áreas do piloto, incluindo login, conclusão de acesso, administração, formulários e diálogos: Georgia nos títulos, Arial no conteúdo, fundo Linho e Verde Mata nos elementos principais.
- Usa a logo principal colorida nas telas de acesso e a horizontal negativa nos cabeçalhos autenticados, com proporção, espaço livre, contraste e alternativa textual preservados.
- Inclui as variantes e guias na exportação e prepara as duas logos no build. Preserva a base 0.1.23, autenticação e dados por usuário.
- Validação: compilação, 41 testes automatizados e navegador com provedor controlado, contas isoladas e telas estreitas. Google e instalação reais continuam dependentes de validação no ambiente final.

# 0.1.8

- Incorpora a base Fabricação e Orçamentos 0.1.23, preservando adaptações do Artesão Digital e atualizando versão/commit-base dos metadados.

- Alinha a logo do cabeçalho das áreas de usuário à margem do conteúdo e posiciona o e-mail à direita, antes de Sair.

- Centraliza a logo na tela de login sem alterar o alinhamento dos campos ou a posição da marca no cabeçalho autenticado.
- Preserva imagem original, proporção e alternativa textual quando a logo não carrega.

# 0.1.7

- Acrescenta aviso de piloto por convite e formulário de interesse com nome/e-mail obrigatórios e WhatsApp opcional; registrar não cria conta nem libera acesso.
- Adiciona login administrativo separado pelo Google e lista explícita `admin_emails`, negando acesso por padrão. Sessões administrativas são separadas e não consomem vagas de usuário.
- Inclui consulta restrita e paginada de interessados, responsiva, com validação de autorização no servidor e proteção contra sessão de outra conta.
- Protege o formulário com validação, origem, token de uso único, limites de tentativas e deduplicação sem revelar contatos existentes.
- Cifra o conteúdo dos contatos novos por AES-256-GCM, com arquivo de chave restrito e retenção de noventa dias. A chave no mesmo volume não protege contra comprometimento de banco e chave juntos; backups e demais bancos ainda exigem proteção própria.
- Inclui a logo original fornecida pelo usuário no cabeçalho, com alternativa textual em caso de ausência/falha e acessibilidade; não implementa upload ou gestão completa de usuários.

# 0.1.6

- Amplia as opções do Home Assistant para cinco pares de e-mail e convite inicial, mantendo compatibilidade com os dois existentes e o limite de cinco contas.
- Carrega os campos 3, 4 e 5 tanto do arquivo de opções quanto das variáveis de ambiente da execução independente.
- Preserva a vinculação por e-mail, uso único, validade, revogação e isolamento dos convites; pares inteiramente vazios são ignorados.
- Orienta a escolha entre OAuth em Teste com e-mails autorizados e publicação no Google antes de liberar os primeiros participantes.

# 0.1.5

- Corrige Sair após expiração ou ausência de sessão: encerra o fluxo e limpa os cookies restantes, sem exigir uma sessão ainda ativa.
- Mantém validação de origem em todas as saídas e exige CSRF/contexto da aba quando a sessão ainda é válida. Uma aba antiga não pode encerrar outra sessão ativa.
- Exibe aviso ao falhar a conexão/saída e permite tentar novamente, sem deixar o botão sem resposta.
- Inclui a correção de cache da 0.1.4 para instalações que ainda estão na 0.1.3. Mantém a base em 0.1.19.
- Confere login, recarga comum, troca de contas, saída com cookies expirados e falha de rede no navegador com Nginx/cache HA simulados. Validação real continua manual.

# 0.1.4

- Corrige tela sem conteúdo após login quando o cache do Home Assistant interfere no carregamento dos módulos da interface.
- Isola o carregamento no caminho do Artesão Digital com um service worker sem cache, sem remover o worker ou os arquivos de cache do Home Assistant. Remove somente entradas antigas do caminho do piloto.
- Aguarda a preparação do navegador antes de entrar com Google e carregar a interface; apresenta mensagem se essa preparação falhar.
- Valida primeiro acesso, novo login, troca de contas no mesmo navegador e preservação do cache externo pelo proxy Nginx. Google real e instalação continuam sujeitos à conferência manual.

# Histórico do Artesão Digital — Testes

## 0.1.3

- Serve os arquivos compilados públicos da interface sem depender do cookie de sessão, evitando redirecionamento de JavaScript para HTML de login e tela vazia.
- Mantém documentos com contexto de usuário e todas as APIs de dados protegidos por sessão; origem, CSRF e isolamento não mudam.
- Acrescenta regressão para JavaScript sem cookie com MIME correto e navegação pelo Nginx com recursos carregados anonimamente.

## 0.1.2

- Adota Artesão Digital como nome visível no aplicativo, telas de login e instalação de testes.
- Abre Orçamentos automaticamente após login e ao acessar o login com sessão válida.
- Mantém as duas versões em rodapé fixo visível, com espaço reservado para não cobrir controles.
- Usa faixa verde fixa no topo, com nome à esquerda, e-mail centralizado e Sair à direita, adaptada a telas estreitas.
- Preserva slug, volume, contas, convites e URL de retorno Google existentes.
- Inclui Abrir interface Web na página do aplicativo do HA, apontando ao login HTTPS pela porta já existente8443.
- Acrescenta testes de rodapé dentro do viewport e marca da implantação nas áreas principais.

## 0.1.1

- Exibe no rodapé a versão do piloto e a versão-base do Fabricação e Orçamentos, obtidas dos metadados de compilação.

- Conclui o login em uma página própria, remove parâmetros OAuth do histórico e confirma a sessão antes de abrir Produtos automaticamente.
- Usa a mesma entrada para primeiro acesso e novo login sem convite, mantendo os dados e as contas já ativadas.
- Mostra orientação explícita quando a sessão não pode ser reconhecida, sem retornar silenciosamente à tela de convite.
- Testa Produtos efetivamente renderizado após login, além da barra da conta, sem abrir links manuais.
- Exercita duas contas, logout/novo login, sessão inicialmente indisponível e sessão ausente através de Nginx HTTPS com backend HTTP, usando provedor controlado.
- Preserva porta externa na rota sem barra final no gerador Nginx.

## 0.1.0

- Primeira versão experimental com Google OpenID Connect, convites individuais, sessões protegidas e banco separado por conta.
- Instalação separada no Home Assistant; uso somente com dados fictícios enquanto a validação e as proteções pendentes não forem concluídas.
