# 0.1.51 — envio automático exclusivo para testes

- Autoriza envio apenas em modo testes, com perfil explícito e não excluído, claim válido e decisão local favorável.
- Bloqueia envio automático no modo all; mantém proteções de janela e idempotência.
- Adaptador n8n exige autorização explícita e resposta Gemini STOP. Homologação real pendente.

# 0.1.50 — alinhar testes HTTP à versão do pacote

- Atualiza as três asserções de versão em `tests/test_http.py` para 0.1.50. O build real 0.1.49 revelou que os testes de health e interface ainda esperavam 0.1.47.
- Alinha `APP_VERSION` e o manifesto para 0.1.50.
- Preserva a correção POST-only do proxy, os blocos NGINX com quebras de linha reais e a regressão do arquivo distribuído.
- Nenhuma alteração em dados, opções, credenciais, Meta, webhook, n8n ou política de atendimento.
- A build anterior 0.1.49 falhou no estágio de testes; a suíte da 0.1.50 precisa ser executada novamente no Supervisor.

# 0.1.49 — alinhar versão interna com o pacote

- Alinha `APP_VERSION` da aplicação com a versão do manifesto após a revisão da instalação revelar identificação interna ainda em 0.1.47.
- Preserva as correções de rota POST-only, o fragmento NGINX com blocos válidos e os testes adicionados na 0.1.48.
- Não altera opções, bancos, credenciais, Meta, n8n, webhook ou comportamento de atendimento.
- Build e homologação desta versão ainda dependem da atualização no Home Assistant.

# 0.1.48 — corrigir rota de salvamento da política no proxy

- Inclui encaminhamento POST-only para `/panel/automation/policy` e para a variante com prefixo de conta no proxy dedicado.
- Corrige as quebras de linha do fragmento NGINX distribuído; as duas locations agora são blocos NGINX reais, não sequências de escape literais.
- Acrescenta testes de regressão para a geração e o arquivo distribuído, incluindo a rejeição de escapes literais e o bloqueio de GET.
- Inclui o novo teste na suíte executada durante o build do add-on pelo Supervisor.
- Mantém sessão, CSRF, validação de IDs e política Testes com lista vazia; não ativa automação nem altera credenciais, dados ou configurações Meta.
- Nenhuma alteração foi aplicada ao proxy ativo. Build ARM64 e homologação funcional permanecem pendentes.

# 0.1.47 — corrigir marcação da caixa de entrada

- Corrige o fechamento do atributo `class` no contêiner da caixa de entrada; HTML passa a renderizar `class="content ui-inbox-page"` corretamente.
- Atualiza os testes do webhook e da caixa de entrada para validar a contagem compacta `1 mensagem`, em vez do rótulo redundante antigo `Mensagens armazenadas`; a ausência do rótulo é verificada no conteúdo visível, não em mensagens de erro internas do JavaScript.
- Mantém as verificações de ausência de títulos redundantes, o layout compacto e o comportamento responsivo.
- Corrige a fixture de isolamento: usa uma mensagem sintética exclusiva e verifica que o conteúdo da mensagem aparece na caixa de entrada, mas não nas configurações. O ID do remetente não é usado como proxy de privacidade, pois pode aparecer legitimamente na lista de perfis de teste.
- Preserva as correções CSRF e Meta das versões anteriores.

# 0.1.46 — corrigir escopo das asserções do token Meta

- Move as asserções do `debug_token` para o teste de envio pela Send API, onde a consulta realmente ocorre.
- Remove referências indevidas ao resultado `debug` do teste de assinatura de webhook, que não consulta permissões.
- Mantém a verificação do Page Access Token como `input_token` e o app access token no cabeçalho de autorização.
- Mantém a correção CSRF da política de atendimento e o ajuste UX responsivo da caixa de entrada.

# 0.1.45 — corrigir sintaxe das regressões de versão

- Corrige três asserções de versão em `tests/test_http.py` que ficaram com aspas incompletas na atualização anterior.
- Preserva a correção funcional 0.1.44: ação `automation` permitida na allowlist CSRF.
- Mantém o teste explícito de geração e validação do token CSRF de automação.
- Incorpora também o ajuste responsivo da caixa de entrada já desenvolvido: título único, contagem compacta, conteúdo aproximado do cabeçalho e ausência de títulos redundantes; testes browser verificam hierarquia e espaçamento em larguras desktop e mobile.
- Nenhuma opção, credencial, banco ou dado de runtime foi alterado.

# 0.1.45 — hierarquia compacta da caixa de entrada e densidade editorial

- Remove a linha extensa de metadados do topo da caixa; a contagem passa a ser um indicador compacto ao lado do título único **Caixa de entrada**.
- Remove a redundância de títulos auxiliares e reduz o espaço entre cabeçalho global e início do conteúdo na caixa de entrada.
- Mantém a explicação da consulta manual à Meta sob demanda, sem esconder limitações operacionais.
- Compacta espaçamentos gerais de páginas e painéis do Editorial sem alterar campos, dados, rotas, fluxos de publicação ou ações.
- Acrescenta regressões para título único, ausência de rótulos repetidos e distância do conteúdo ao cabeçalho em larguras desktop e mobile.
- Nenhuma mudança em APIs, OAuth, Meta, webhook, recebimento, envio, n8n, Drive ou persistência.

# 0.1.44 — corrigir CSRF da configuração de atendimento

- Inclui a ação `automation` na allowlist de ações administrativas para token CSRF, mantendo o escopo restrito à sessão do painel e à conta principal.
- Corrige os dois testes de gravação da política de atendimento que recebiam HTTP 403 por token CSRF vazio.
- Mantém o padrão Testes com lista vazia; nenhum perfil é autorizado automaticamente.
- Nenhuma credencial, opção de runtime, banco ou configuração Meta é alterada.

# 0.1.43 — validação da permissão no token efetivamente usado

- Corrige a verificação pré-envio para consultar o token de acesso da Página que será usado na Send API, em vez do token de usuário do sistema que o obteve.
- Acrescenta regressão que comprova que o token da Página é o `input_token` enviado ao `debug_token`, enquanto o app access token permanece somente no cabeçalho.
- Mantém o bloqueio por padrão, a lista de testes vazia, as permissões `pages_messaging` e `instagram_manage_messages`, a janela Meta de 24 horas e a idempotência.
- Esta correção ainda requer build/testes no Supervisor e homologação real; não ativa o workflow n8n.

# 0.1.41 — hotfix dos testes de navegação da 0.1.40

- Corrige a asserção do teste de grupos de navegação: rótulo “Gestão” passa a ser codificado explicitamente em UTF-8, evitando SyntaxError em literal bytes não ASCII durante o build ARM64 do Supervisor.
- Mantém integralmente a reorganização UX da 0.1.40; nenhuma alteração de regra de negócio, API, integração, dados ou opções.
- A 0.1.40 foi publicada, mas o build do Supervisor falhou antes da instalação; a 0.1.41 contém a correção e será reconstruída no host.

# 0.1.42 — controle de atendimento automático restrito

- Adiciona modo Testes/Produção por conta, lista de perfis autorizados e lista de exclusão com precedência absoluta; padrão seguro: Testes com lista vazia.
- Aplica a política no backend antes de expor/claimar mensagens para o n8n e novamente antes de qualquer envio. A janela de 24 horas usa o timestamp original do evento Meta; eventos sem timestamp, mensagens manuais, remetentes excluídos e conversas sob controle humano falham fechados.
- Adiciona aba Atendimento nas Configurações Meta, protegida por sessão e CSRF, com IDs técnicos estáveis dos perfis.
- Adiciona envio Meta somente com token de Página vinculado à conta Instagram, tarefa MESSAGING e permissões `pages_messaging` + `instagram_manage_messages`; tokens ficam no armazenamento criptografado local. Idempotência por mensagem e bloqueio de repetição em falhas incertas.
- Cria workflow n8n separado e inativo, com triagem local, Gemini restrito e envio exclusivamente pela Central. Não ativar até configurar a credencial própria `X-Instagram-Bridge-Secret`, cadastrar o perfil do proprietário e validar a conexão de mensagens Meta.
- Testes dirigidos de política, isolamento, CSRF, claim, exclusão, handoff, janela de mensagens e Send API incluídos no build do Supervisor. A execução local integral e a homologação real ainda precisam ser concluídas.

# 0.1.40 — reorganização global da navegação e experiência móvel

- Reorganiza a navegação em Editorial, Atendimento e Gestão; remove a identificação redundante da conta da sidebar e preserva o seletor global no cabeçalho.
- Cabeçalho compacto com breadcrumb curto (Central / área atual), hierarquia de títulos e espaçamentos ajustados.
- Navegação móvel em gaveta modal sobreposta, com altura natural da sidebar, shell de contas em uma coluna, sem quebra do cabeçalho em telas estreitas.
- Gaveta com foco inicial, ciclo de Tab/Shift+Tab, fechamento por Escape, clique externo ou seleção e retorno do foco ao controle.
- Preserva rotas, contexto de conta, autenticação, APIs, mensagens, Editorial, Meta, Drive e n8n; não altera regras de negócio nem dados persistidos.
- Inclui testes dirigidos de renderização, seletor global, grupos, rotas e navegação móvel. O build do Supervisor executará os testes Python de interface como parte da atualização.

# 0.1.39 — autorização editorial multi-conta e Drive privado

- Chaves cei2 emitidas pelo administrador com escopo escolhido; listagem dinâmica, autorização transacional, recibos próprios por conta e conexão. Preserva cei1. Sem publicação direta nas novas conexões.
- Pasta exclusiva por conexão e subpasta por conta, Google Auth somente leitura, hash, tamanho, MIME, validação sem armazenar e transferência idempotente. Credenciais reais ainda não provisionadas. Testes específicos incluídos no build.

## 0.1.38 (candidata)

- Identificação visual dos remetentes: foto circular de 48 px, nome e @username quando disponibilizados pela Meta. ID técnico preservado nos detalhes e como fallback.
- Consultas opcionais somente para remetentes das últimas 50 mensagens da conta selecionada, ao exibir os cartões. Cache com limite por conta, expiração e intervalo de nova tentativa. Foto normalizada localmente; nenhum URL da Meta ou token chega ao navegador. Sem consulta adicional no receptor de webhook.
- Mantém ingestão, deduplicação, fila, ações, importação manual, Editorial e conexão existentes. Não habilita respostas nem altera autorizações. O endpoint de perfil é documentado com token de Página; compatibilidade com o token Unified salvo e identidade real ainda precisam ser homologadas.
- Testes dirigidos de cache, isolamento e fallback incluídos. Estado de testes e publicação será registrado separadamente.

## 0.1.37

- Corrige o acesso por links do ChatGPT que acrescentam `?utm_source=chatgpt.com`: ignora parâmetros UTM conhecidos na navegação da interface, preservando login, sessão e configurações da conta. Não altera webhook, OAuth, fila, dados, layout ou publicação editorial.
- Mantém validação dos parâmetros funcionais e acrescenta testes de regressão de navegação e autenticação. Teste isolado de decisão de rota: 18/18 PASS; testes HTTP integrais pendentes. Publicação para homologação real autorizada pelo proprietário em 22/11/2026.

## 0.1.36

- Corrige o layout das mensagens preenchidas: a tabela tinha oito colunas, mas as larguras de sete já consumiam 100%, comprimindo a coluna de ações e quebrando os rótulos letra por letra. Substitui a tabela por cartões responsivos com texto, estado/origem e ações em áreas próprias.
- Ações legíveis e contidas no cartão, com alvos de toque de pelo menos 44 px; links longos, quebras de linha, emojis e rascunhos não provocam rolagem horizontal. Mantém rascunhos existentes visíveis e fila/metadados sob demanda.
- Exibe a data/hora recebida em Brasília, preservando o timestamp armazenado. Mantém formulários, destinos, CSRF, regras de atendimento, dados, busca manual e webhook. Este pacote altera apresentação; não confirma nem altera a entrega real de DMs por webhook.

## 0.1.35

- Corrige a interrupção de Atualizar mensagens quando uma conversa não inclui a lista de mensagens na resposta expandida. Usa a leitura direta /CONVERSATION_ID/messages somente para IDs retornados pela consulta da conta verificada. Até seis GETs por clique, espaçados e com orçamento de tempo, sem paginação ou consulta periódica.
- Continua a busca nas conversas disponíveis quando outra fica inacessível, informando Busca parcial. Se nenhuma lista puder ser lida, mantém o erro e a caixa existente. Token inválido interrompe a leitura sem gravar resultados parciais.
- Limita localmente a amostra a cinco conversas e dez mensagens de cada se a Meta devolver mais que o solicitado, em vez de rejeitar dados válidos. Mantém confirmação do destinatário, identidade, texto e data, deduplicação e origem manual fora da fila automática.
- Registra apenas contagens e categorias fixas da estrutura recebida e das falhas, sem textos, IDs privados, tokens ou resposta bruta. Preserva as interfaces Mobile First, fotos e exclusão da 0.1.34. A entrega real de webhooks continua em investigação.

## 0.1.34

- Acrescenta ao modal Excluir as opções Somente da Central Editorial e Da Central Editorial e do Instagram. A segunda exige confirmação explícita da conta/publicação, verifica permissão e propriedade e só limpa o registro local após sucesso confirmado pela Meta. Recusa e resultado incerto preservam dados; recibos persistentes impedem repetição automática e reimportação indevida do histórico. Carrosséis são excluídos por inteiro.
- Mostra fotos, nome e @ no seletor comum de contas, com cache local, iniciais de reserva e navegação acessível. Integra a branch feat/account-profile-avatars, preservando as correções da 0.1.33.
- Amplia o limite local de IDs opacos de mensagens de 160 para 1.024 caracteres na busca manual, webhook e processamento local. Distingue falhas de estrutura, identidade, ID e data na busca manual, sem exibir respostas privadas. A causa do erro real informado e a entrega de DMs reais por webhook continuam sem confirmação.
- Aplica a organização Mobile First aprovada: Conexão/Diagnósticos/Ferramentas, lista de contas separada do cadastro e Conteúdo/Prévia no celular. Cartões resumidos com detalhes e métricas sob demanda, contexto da conta preservado, proteção contra perda de alterações, retomada de composição e navegação de retorno. Cabeçalho sem repetição no celular, alvos de toque e estados consistentes.

## 0.1.33

- Atualizar mensagens passa a buscar textos recentes na Meta por conta e gravar/exibir na caixa: até 5 conversas × 10 mensagens, em um GET explícito. Sem polling ou resposta automática. Espera, trava de duplicação, resultado/erro acessível e preservação da caixa.
- Identifica origem manual/webhook e deduplica pelos IDs existentes. Importação manual não entra na fila automática nem comprova recepção de webhook; webhook válido posterior promove o mesmo registro uma vez. Migração aditiva preserva dados existentes.
- Corrige a primeira conexão de contas novas: destaca Conectar Instagram pela Meta, explica cadastro/autorização, desabilita Verificar acesso Meta sem credencial e mantém consulta para credencial salva. Erros de autorização, token, consulta ou assinatura retornam à configuração da mesma conta com feedback fixo, sem JSON genérico ou nova autorização automática.
- Separa autorização da conta dos indicadores/configuração de webhook. Preserva credenciais por conta, sessões, CSRF e fluxo de publicação/integração genérica.
- Torna explícita a exclusão somente local no botão, modal e confirmação do Editorial. Exclusão remota não habilitada: o suporte ao BISU/Unified Login e a permissão específica ainda não foram confirmados. Nenhuma postagem real apagada.

## 0.1.32

- Consulta manual de controle e atividade em Configurações Meta, por conta, com uma única leitura de até cinco conversas usando `id,is_owner,updated_time`. Descarta IDs e não pede conteúdo nem participantes.
- Apresenta contagens de controle próprio/outro/não informado e atividade mais recente da amostra em Brasília. Ausência de `is_owner` e recusas da API permanecem inconclusivas; não comprovam falha de roteamento nem entrega da DM.
- Usa token salvo e sessão/CSRF por ação e conta, sem renovar credencial, assinar eventos, enviar mensagens ou alterar encaminhamento. Não grava o resultado nem consulta automaticamente ao abrir/recarregar.
- Botão com espera e bloqueio de repetição; falhas preservam o último resultado exibido. Mantém integração genérica, menu, Editorial, abertura externa, proxy e receptor da 0.1.31. Não declara corrigido o recebimento de DMs reais.

## 0.1.31

- Chaves por conta/ferramenta, com prazo de 90 dias, revogação e permissão opcional de publicação direta. Gerenciamento usa sessão administrativa e CSRF por ação/conta.
- Entrada JPEG/PNG/MP4 em estágio privado, commit atômico para revisão, recibos persistentes e proteção contra duplicação. Sem envio de versões não autorizadas. Cotas somam mídias temporárias e biblioteca.
- Publicação direta passa pelo executor da Central: autorização por conta/revisão, separada da transferência, sem novo envio na repetição do mesmo pedido. Falha de pré-requisitos mantém o conteúdo sem autorização de publicação.
- OpenAPI 3.1 e cliente Python genérico, sem dependência do ChatGPT. Prévia local sem rede por padrão; envio e publicação exigem opções explícitas.
- Menu aprovado em Editorial, Mensagens, Contas e Conexão Meta, sempre disponível; cabeçalho/seletor comuns, contexto por URL, Calendário e Histórico separados.
- Administração das conexões em Configurações Meta; preserva navegação e abertura externa da 0.1.30. Publicação direta recusa conteúdo editado após a transferência. Sem alteração do proxy ou credenciais Meta; instalação no HA é etapa posterior.

## 0.1.30

- Separa Mensagens e Configurações Meta em páginas por conta. Centraliza conexão, diagnóstico de recebimento e verificação de publicação nas configurações, com retorno das ações Meta/cadastro/OAuth para essa área. Mantém rotas existentes do proxy e sessão/CSRF por conta/ação.
- Retira do Editorial os avisos fixos de verificação e de funcionamento da agenda. Verificação manual de publicação mostra carregamento, bloqueia repetição, informa conclusão e preserva o resultado anterior em falhas. O executor continua verificando o acesso quando necessário; não exige consulta manual antes de cada publicação.
- Substitui Ingress pelo botão externo nativo do Home Assistant com template webui válido e remove o atalho lateral Ingress. Usa o HTTPS 8443 e GET já existentes para redirecionar à origem pública configurada; não expõe 8099, não cria mapeamento de portas nem exige alteração de proxy. Acesso ao HA pelo domínio habitual é necessário para o certificado HTTPS.
- Registra histórico carregado e algumas métricas reais confirmadas pelo proprietário na 0.1.29. Não altera receptor de DMs, publicação, histórico, mídias ou agenda. A reorganização geral do menu fica para discussão posterior.

## 0.1.29

- Importa histórico do Instagram por conta, paginado e em segundo plano, com progresso, cancelamento, persistência/reinício e deduplicação por ID remoto. Apenas consultas GET; não cria envios nem transforma histórico em rascunho.
- Inclui Histórico com filtros, ordenação por contagens/interações conhecidas e cobertura dos dados, além de publicações realizadas no Calendário com data original e seletor de mês.
- Baixa cópias de mídias para a biblioteca dentro das cotas, usando HTTPS/CDNs restritos, sem bearer no CDN ou redirecionamento. Valida/regrava como uploads, preserva metadados quando arquivos falham e identifica miniatura substituta de vídeo. Sincronização repetida reutiliza arquivos/IDs existentes.
- Acrescenta compartilhamentos/salvamentos quando a API permitir, com fallback para dados básicos e horários separados. Campo ausente não vira zero; interações conhecidas não são taxa de engajamento.
- Preserva autoria/local original, versões, sessões/CSRF por ação/conta, revisão e agendas existentes. Mostra texto alternativo retornado em detalhes de acessibilidade sem tratá-lo como legenda visível individual.
- Mantém exclusão local e proteção de registros durante sincronização, mesmos proxy/login/credenciais e build de sintaxe no HA. Stories antigos/arquivo privado e DMs continuam fora desta entrega; importação real ainda não homologada no HA.

## 0.1.28

- Acrescenta consulta manual de curtidas e quantidade de comentários por publicação e conta, usando somente GET na Meta e os campos id,like_count,comments_count. Não exige verificar a permissão de publicação para ler contagens e não envia conteúdo.
- Persiste contagens e horários separadamente da revisão editorial. Distingue zero de campo não retornado, preserva o último resultado em falhas e não presume que um erro de acesso prova exclusão no Instagram. Protege sessão/CSRF, conta, ID remoto, versão, consultas concorrentes e exclusão durante a leitura.
- Indica o link de Story como temporário e o retira após 24 horas da confirmação registrada, preservando histórico/prévia local. Não oferece link ao arquivo privado. Links de perfil deixam de ser apresentados como se fossem permalink de uma publicação.
- Confirmação operacional recebida: uma publicação e um Story reais funcionaram na 0.1.27. Carrossel, multicontas, DMs e as novas contagens reais continuam pendentes de confirmação.
- Mantém login Unified, tokens, permissões, proxy, isolamento, dados existentes, publicação e esteira rápida. Excluir continua sendo exclusão local; edição remota de legenda e republicação não foram incluídas neste lote.

## 0.1.27

- Corrige a sequência Meta 100 → indisponibilidade: o cache negativo guarda identidade e validade, preserva a causa específica, expira em 30 segundos e pode ser renovado pelo botão. Troca de credencial/conta invalida o resultado anterior.
- Retira account_type da consulta IGUser do Facebook Login; usa id,username. Elegibilidade desconhecida de Stories não é tratada como inelegibilidade confirmada; a Meta valida a operação. Recusas identificam a etapa sem revelar respostas privadas.
- Criar publicação inicia sempre uma composição vazia; edição só ocorre por Editar. Verificação mostra progresso, trava repetição e informa conclusão mesmo com resultado igual.
- Acrescenta exclusão local de publicações e de mídias, com confirmação, controle de versão, CSRF específico e isolamento por conta. Mídias compartilhadas são preservadas, agendamento pendente é cancelado e envios em andamento ou incertos ficam protegidos. Não remove posts no Instagram.
- Registra limpeza de arquivos em fila durável, retoma interrupções e contabiliza bytes pendentes na cota; informa espaço liberado e pendências.
- Unifica o menu em Contas, Conteúdo, Atendimento e Configuração. Acrescenta skeleton, carregamento de mídias por visibilidade, progresso real de upload, estados ocupados e transições curtas com suporte a teclado/movimento reduzido, usando Design Motion Principles.
- Preserva portas, proxy, credenciais, dados existentes, receptor de DMs e esteira rápida de sintaxe no build do HA. Publicação real segue aguardando confirmação do operador.

## 0.1.26

- Implementa publicação editorial por conta: imagem no feed, carrossel de imagens, Reel e Story, com confirmação imediata ou agendamento persistente no horário de São Paulo.
- Usa credencial e armazenamento da conta selecionada, confere instagram_content_publish e mantém sessão/CSRF por ação e conta. Cadastro e retorno OAuth incluem acesso direto ao Editorial correto.
- Acrescenta executor com reserva transacional, contêiner/progresso persistidos e consulta de resultado após perda de resposta. Uma tentativa ambígua não é repetida automaticamente; o painel permite verificar, corrigir ou autorizar nova tentativa com o mesmo contêiner.
- Entrega somente a mídia do post autorizado por link temporário de uma hora, vinculado a conta, revisão e execução. Reutiliza o GET público do callback existente; não abre a biblioteca nem requer nova rota no proxy. Converte imagens para JPEG, com fundo branco na transparência; suporta HEAD e faixas de bytes.
- Preserva rascunhos/mídias/agendas anteriores. Agendamentos criados sem executor não passam a publicar após atualizar: exigem confirmação. Edição/cancelamento revogam autorização. Falha de conexão de uma conta não publica pela credencial de outra.
- Exibe acesso de publicação, andamento, sucesso/link quando disponível e erros saneados com códigos numéricos. Mantém os limites de upload/biblioteca, o build de sintaxe no HA e o receptor IPv4/IPv6. DMs reais e recebimento de secundárias continuam pendentes; não foram alterados nesta entrega.

## 0.1.25

- Corrige incompatibilidade entre o proxy interno com destino IPv6 e o receptor que aceitava somente IPv4: uma única porta interna passa a aceitar IPv4/IPv6 quando o sistema oferece dual stack, mantendo IPv4 em sistemas sem esse suporte.
- Registra prontidão somente após abrir a porta, incluindo transporte ipv4_ipv6 ou ipv4. Mantém porta 8099, proxy, URLs, opções, dados, validação HMAC e isolamento por conta.
- Não declara que a entrega da DM foi resolvida: as recusas IPv6 foram confirmadas, mas não foi possível correlacioná-las à DM real. Build leve da 0.1.24 preservado.

## 0.1.24

- Mostra Verificando… ou Solicitando assinatura… imediatamente ao enviar uma ação Meta, com aviso de espera acessível e bloqueio de novos envios na mesma tela enquanto a navegação está pendente.
- Preserva POST/CSRF e retorno normal do servidor; restaura controles ao voltar pelo histórico em cache. Script fixo autorizado por hash CSP, sem liberar scripts inline arbitrários.
- Registra a chegada de POST ao caminho do webhook antes de analisar tamanho, assinatura ou corpo, com categorias e booleanos fixos. Não inclui conteúdo, IP, URL/query, cookies ou assinatura; chegada não equivale a autenticidade.
- Reduz o build no HA à checagem de sintaxe dos módulos de execução. Testes de comportamento são feitos no desenvolvimento conforme a alteração; a suíte completa deixa de rodar a cada atualização do dispositivo.

## 0.1.23

- Amplia Verificar acesso Meta com leitura do token já salvo: validade, app emissor e concessão das permissões de perfil/mensagens, sem expor token, segredos ou identificadores pessoais.
- Consulta metadados de assinatura do app: quando Instagram é retornado, mostra ativação, messages e destino público sem parâmetros/fragmentos. A ausência na API genérica é inconclusiva, não prova ausência no portal.
- Não infere Standard/Advanced Access nem bloqueio de produção a partir dos escopos. Mantém as consultas anteriores de assinatura da conta e acesso às conversas.
- Recusa redirecionamentos HTTP do Graph para evitar encaminhar credenciais a outro destino. Novas rotas Graph permitem somente GET com parâmetros fixos.
- Preserva opções, dados, URLs, proxy, manifesto e publicação do app. Sem envio de DM, novo OAuth, alteração de assinatura ou exigência de verificação empresarial nesta atualização.

## 0.1.22

- Documentação pública: política de privacidade com o escopo completo condicionado aos recursos ativados, termos de uso e instruções de exclusão pelo contato informado. Documentos publicados separadamente, sem alterar a versão ou exigir atualização do aplicativo instalado.
- Verificar acesso Meta consulta a assinatura efetiva do app/conta e acesso às conversas, usando o token cifrado já salvo e apenas GETs com campos limitados.
- Exibe diagnóstico com horário, estados independentes e erros fixos/códigos numéricos; não consulta conteúdo nem armazena IDs de conversas/respostas privadas.
- Mostra confirmação das ações; falha de identidade não renova a verificação anterior. Assinar mensagens não é confundido com entrega real e invalida diagnóstico anterior.
- Preserva isolamento, sessão/CSRF, opções, dados, manifesto, proxy e URLs. Não ativa envios, automações ou publicação nem altera ManyChat/roteamento.

## 0.1.21

- Reconhece eventos de texto em entry[].changes[] / field=messages do login unificado; preserva entry[].messaging[] e deduplicação entre formatos.
- Mantém assinatura HMAC obrigatória e filtro pelo destinatário, sem fallback para a principal nem ativação de secundárias/comentários/envios.
- Acrescenta logs de webhook com motivos fixos/contagens, sem conteúdo, IDs ou credenciais, para distinguir entrega/rejeição/reconhecimento/gravação.
- Mantém manifesto válido da 0.1.20, dados, opções, proxy e URLs; não requer reconectar a conta.

## 0.1.20

- Corrige a exclusão da Central da loja pelo Supervisor: removido `webui` com hostname/porta fixos, que viola o formato exigido `[HOST]:[PORT:...]`.
- Restaura a configuração Ingress e o ícone de painel da 0.1.18; mantém slug, opções, dados, credenciais, multicontas e ícones oficiais.
- Acrescenta regressão do contrato `webui` do Supervisor. Acesso externo dedicado continua pela URL própria; abertura externa automática pelo botão do HA não está disponível nesta correção.
- Nenhuma mudança no proxy, certificado, rede, OAuth, webhook ou recebimento/envio de mensagens.

## 0.1.19 — multicontas operacional e abertura externa direta — 21/11/2026

- Adiciona tela Contas com cadastro por nome/usuário, seleção e painéis isolados, usando o mesmo administrador. ID oficial é confirmado no OAuth, sem copiar token ou segredo por conta.
- OAuth resolve o contexto do retorno pelo state armazenado, valida a conta pretendida e guarda credenciais em diretório próprio. Abas de contas diferentes não compartilham seleção; descoberta de ativos paginada e limitada.
- Isola mensagens/handoff, mídia/rascunhos/agenda e CSRF por conta; credenciais não usam fallback. Preserva conta/token/chave/dados da principal, conectada pelo operador na 0.1.18. Registro recebe marcador operacional aditivo; cadastros internos antigos não são ativados.
- Compartilha somente campos necessários do mesmo app Meta nos cadastros explícitos do administrador; bridge/verify token/webhook da principal não são herdados pelas secundárias.
- Desativa Ingress e define webui HTTPS externa direta para a instalação Romeropi, sem nova porta. Adiciona rotas explícitas de Contas ao proxy e retorno correto de Verificar acesso Meta ao painel correspondente.
- Não ativa webhook, bridge secundária, envios, postagem ou automações. Atualização exige substituir somente o arquivo adicional Instagram do NGINX; callback/certificado/credenciais globais permanecem.
- Testes novos cobrem concorrência, identidade errada, callbacks paralelos, isolamento e preservação da principal; evidências completas no relatório/Issue #1. Casos de teste usam contas sintéticas, sem autorização real adicional.

## 0.1.18 — hostname exclusivo no proxy existente — 21/11/2026

- Substitui a recomendação 0.1.17 de abrir 9443: remove listener TLS da aplicação, mapeamento de porta pública, webui 9443 e montagem `/ssl`. A Central atende somente HTTP interno 8099 com Ingress preservado.
- Adiciona gerador/candidata NGINX para hostname exclusivo no listener HTTPS existente: rotas/métodos explícitos, Host/SNI, limite de login por IP, limites de corpo, sem bridge/health/Supervisor/webhook ou logs de URLs OAuth nesse host.
- Preserva login, dados, flags e vínculo de origem do OAuth; opções antigas certfile/keyfile são aceitas mas ignoradas pela aplicação. Nenhuma ativação Meta.
- Guia detalhado de certificado wildcard DuckDNS preservando o domínio atual, instalação de somente um arquivo adicional e rollback. Certificado informado cobre apenas o HA; novo host não deve ser ativado antes da emissão/cobertura correta.
- 201 testes Python PASS, Chromium PASS em hostname separado na mesma porta, build Docker amd64 com 198 testes PASS e validação NGINX real local PASS. Nenhuma instalação/alteração no HA ou roteador foi executada; não declara homologação.

## 0.1.17 — HTTPS independente da origem do HA — 21/11/2026

- Adiciona listener TLS 1.2+ em 9443 com certificado/chave de `/ssl` montado somente para leitura; ativado ao preencher `public_base_url`. Certificados são relidos em novas conexões. Falhas não abrem HTTP público e preservam o listener interno 8099.
- Declara porta HTTPS e webui; mantém Ingress opcional e acrescenta links para janela própria no login/painel. Reutiliza Handler, autenticação, sessão, CSRF e `/data`, sem migração de dados nem segunda conta.
- Reconhece TLS nativo sem depender de X-Forwarded-Proto, mantendo Secure/HttpOnly/SameSite=Strict na sessão e SameSite=Lax nos cookies OAuth.
- Bloqueia OAuth se `meta_oauth_redirect_uri` divergir da origem independente; recusa Host antigo antes de iniciar/consumir autorização ou trocar código. Não altera Meta, webhook, NGINX, service worker do HA ou outros aplicativos.
- Chromium inclui worker sintético ativo na origem antiga e acesso na nova porta sem bypass, login real local, probe e autorização simulada. Instruções de certificado, porta/NAT e callback no README. Infraestrutura/Meta reais não foram alteradas nem homologadas.

## 0.1.16 — não perder cookies em campos HTTP separados — 21/11/2026

- Corrige perda comprovada de cookies quando um intermediário envia múltiplos cabeçalhos Cookie: o servidor lia só o primeiro. Agora reúne todos os pares antes de sessão, CSRF, probe e callback OAuth.
- Rejeição de cookie de state duplicado é mantida, inclusive entre campos separados; não escolhe arbitrariamente primeiro/último valor do state.
- Acrescenta à tela flags de cookie OAuth presente e múltiplos campos; log inclui somente contagem limitada, sem valores/nomes/nonce/state/códigos.
- Testes: 189 Python PASS; Chromium com nove cenários de probe, incluindo fragmentação no proxy, e regressões de abas concorrentes/configuração PASS. Provedor e infraestrutura simulados, sem Meta/HA real.
- Sem mudança em dados, esquema, tokens, atributos/path/TTL do cookie, Ingress/NGINX, opções ou demais add-ons. O teste real da 0.1.15 não provou fragmentação no HA; esta versão corrige a falha de parser reproduzida e permite verificar se ela explica o caso do operador.

## 0.1.15 — diagnóstico seguro e vínculo da configuração OAuth — 21/11/2026

- Sincroniza na fonte privada o probe e os testes da distribuição 0.1.14, preservando cookies por tentativa e identificação de versão.
- Diferencia ausência de cabeçalho Cookie de nome esperado ausente; mostra resultado e versão na tela do probe. Logs de emissão/retorno contêm somente flags, atributos fixos e contagem limitada, sem cookies, nonce, state, códigos OAuth, tokens, URLs ou segredos.
- Separa falhas HTTP, TLS, DNS, timeout, rede e JSON em `exchange_code`; registra apenas status e códigos/subcódigos inteiros saneados, descartando mensagens/corpos/cabeçalhos remotos. Preserva `redirect_uri` idêntico e resposta pública genérica.
- Adiciona fingerprint de configuração pública em `meta_oauth_states.authorization_context`, migração aditiva. Tentativa emitida com outro app/redirect/versão/negócio/conta é recusada antes do exchange; estados antigos em voo são invalidados, sem alteração de tokens, contas ou dados existentes.
- Testes locais: 185 Python PASS; Chromium com 8 cenários de cookie, duas abas concorrentes e config drift PASS. Sem Meta real, Actions ou build/instalação no HA nesta execução.
- Publicação autorizada pelo proprietário pela esteira rápida P0, somente `instagram-central/`, preservando slug, opções, arquitetura, Ingress, ícones oficiais e demais add-ons. O Supervisor executará o build durante a atualização do operador.
- Não declara a causa do transporte no HA corrigida nem OAuth homologado. Primeiro teste do operador: **Testar navegador e proxy (sem Meta)** na versão 0.1.15; nenhuma ativação de Meta/webhook/DM/posts integra esta entrega.

## Evidência de homologação — probe 0.1.14 falhou no navegador — 21/11/2026

- O Home Assistant mostra a versão `0.1.14` em execução.
- O proprietário executou **Testar navegador e proxy (sem Meta)**. O navegador chegou a `/oauth/meta/callback?probe=...`, mas recebeu `Cookie não retornou corretamente. Verifique navegador e proxy antes da autorização Meta.`
- No código, essa resposta é emitida quando `check_cookie_probe()` lança `OAuthError`; ainda não distingue, na tela, cookie ausente, duplicado, divergente ou nonce inválido.
- O log registra a causa fixa (`OAuth cookie probe failed: ...`) e `host_ok`/`https_ok`, sem registrar nonce ou valor do cookie. A linha do log ainda não foi coletada.
- A falha mostra que o teste automatizado anterior não reproduziu o transporte real do navegador: o teste HTTP injeta manualmente o cabeçalho `Cookie`, em vez de validar que o navegador armazenou e devolveu o `Set-Cookie` após o redirecionamento 302.
- **Próxima ação:** coletar a linha `OAuth cookie probe failed` nos logs do add-on e corrigir o ponto comprovado. Não alterar NGINX/Ingress nem opções por tentativa. Não repetir OAuth real. Mensagens e Editorial permanecem preservados.
## 0.1.14 — probe usa o mesmo cookie de estado do OAuth — 21/11/2026

- **Incidente:** após a atualização relatada para 0.1.13, o callback real continuou falhando em `parse_callback` com `OAuth browser state mismatch`, embora `redirect_authority_match=True` e `forwarded_https=True`.
- **Falha de cobertura identificada:** o teste `probe=1` ainda usava cookie fixo `ig_oauth_probe`, diferente do cookie derivado de `state` usado pelo OAuth 0.1.13. Portanto, o PASS anterior validava host/HTTPS/escopo genérico, mas não validava o mecanismo de cookie que falhava no callback.
- **Correção de diagnóstico:** o probe passa a emitir e validar `ig_oauth_state_<hash>` com valor sintético de 256 bits, usando exatamente `_state_cookie_name` e o mesmo leitor de cookie do callback. Não grava estado OAuth no SQLite e não acessa a Meta.
- **Identificação da versão:** `/health` passa a retornar `version: 0.1.14`; a página de probe informa a versão em execução, para confirmar que o Supervisor carregou a candidata.
- **Testes:** acrescentada cobertura unitária e HTTP para nome/valor derivados do state, cookie de outra tentativa, valor divergente, atributos e marcador de versão.
- **Segurança e escopo:** mantém `Secure`, `HttpOnly`, `SameSite=Lax`, `Path=/oauth/meta/callback`; sem mudança de NGINX, Ingress, opções, credenciais, banco, webhook, Direct, respostas automáticas ou publicações.
- **Publicação:** PR #67 mesclado em `main` em 21/11/2026, commit `418ca163c7534273c5d4ed906c835ac424d47d8b`.
- **Instalação:** tela de informações do Home Assistant consultada em 21/11/2026 mostra `Versão atual: 0.1.14` e estado `Em execução`. O manifesto não declara imagem pré-compilada; o Supervisor constrói pelo Dockerfile, que executa `py_compile` e `unittest` antes do runtime. O serviço em execução confirma que o gate de build foi ultrapassado; os logs individuais dos testes não foram capturados nesta consulta.
- **Homologação restante:** executar no navegador autenticado **Testar navegador e proxy (sem Meta)**. Não repetir OAuth real.
- **Consulta Supervisor via n8n:** workflow de leitura recebeu HTTP 401 com as credenciais disponíveis; não foi usado para confirmar a instalação. A confirmação foi feita pela tela Info do add-on no Home Assistant.

## 0.1.13 — isolamento do cookie de estado OAuth por tentativa — 20/11/2026

- Cada início OAuth gera um cookie com nome próprio derivado do SHA-256 do `state`; a callback valida somente o cookie correspondente ao estado recebido.
- Evita que duas tentativas/abas simultâneas sobrescrevam o mesmo cookie global. O log real anterior comprova um cookie presente e divergente, mas não comprova que concorrência foi a causa.
- Mantém o `state` aleatório de 256 bits, expiração de 10 minutos, consumo único no SQLite, comparação constante e atributos `Secure`, `HttpOnly`, `SameSite=Lax` e `Path=/oauth/meta/callback`.
- Sem alteração de NGINX, Ingress, opções, banco, credenciais, slug, porta, interface Mensagens/Editorial ou outros add-ons.
- Testes do módulo OAuth: 18/18 passaram em execução offline isolada com os arquivos do SHA de origem. Build do Dockerfile pelo Supervisor e teste real no HA ainda pendentes.
- Não repetir autorização Meta nem habilitar webhook, assinatura, envio de Direct, respostas automáticas ou publicações nesta etapa.

## 0.1.12 — diagnóstico de cookie OAuth e contexto do proxy — 20/11/2026

- **Distribuição:** versão 0.1.12 publicada em `mmcromero/hassio-addons:main/instagram-central/` em 20/11/2026. O build do Supervisor, a suíte integral do Dockerfile, a instalação e a homologação real continuam pendentes. A publicação não altera o Raspberry, NGINX ativo, opções ou credenciais.
- Inclui as correções já publicadas em 0.1.11: `redirect_uri` na troca do código, armazenamento por `account_registry.credential_root`, tratamento de erro de verificação e testes de regressão.
- Distingue no callback três situações sem registrar valores: cookie `ig_oauth_state` ausente, duplicado ou divergente do `state`.
- Adiciona teste de navegador e proxy **sem Meta**: `/oauth/meta/start?probe=1` exige a mesma autenticação administrativa, emite cookie temporário (60 s) com o mesmo escopo do OAuth e redireciona à rota pública existente de callback. A callback confirma cookie, host e HTTPS sem criar estado OAuth, trocar token ou abrir o Facebook.
- Exibe **Testar navegador e proxy (sem Meta)** na Central, em nova aba; nenhuma rota pública nova nem alteração de NGINX exigida.
- Registra apenas indicadores booleanos `redirect_authority_match` e `forwarded_https` para separar origem/Host e encaminhamento HTTPS do NGINX.
- Mantém `Path=/oauth/meta/callback`, `Secure`, `HttpOnly` e `SameSite=Lax`; não amplia o escopo do cookie sem evidência.
- Não altera configuração ativa do NGINX, Ingress, opções do Home Assistant ou painel da Meta. Não habilita mensagens, webhook, envio ou publicação.
- Testes dirigidos adicionados; execução ainda não comprovada nesta etapa.

## 0.1.11 — correção da troca de código OAuth Meta (redirect_uri obrigatório) — 20/11/2026

- **Diagnóstico da causa raiz (P0):** a requisição de troca de código por token de acesso (`oauth_meta.exchange_code`) para a Meta Graph API (`https://graph.facebook.com/{version}/oauth/access_token`) omitia o parâmetro `redirect_uri`. Conforme a especificação OAuth 2.0 (RFC 6749 §4.1.3) e as regras da Meta Graph API, quando `redirect_uri` é informado na autorização inicial (`/dialog/oauth`), o mesmo valor idêntico é obrigatório na requisição de troca do código. A ausência causava rejeição pela Meta (HTTP 400), levantando `OAuthError("Meta authorization exchange failed")` na etapa `exchange_code` e retornando ao navegador `{"error":"OAuth refused or expired"}`.
- **Correção da troca de código:** inclusão explícita de `"redirect_uri": cfg["meta_oauth_redirect_uri"]` nos parâmetros de `oauth_meta.exchange_code`, alinhado à documentação e ao endpoint de autorização.
- **Isolamento de credenciais multi-contas:** padronização da gravação de tokens criptografados (`store_token`) em `server.py` utilizando `account_registry.credential_root(...)`, assegurando compatibilidade retroativa para a conta primária `umdoislab` (`/data`) e isolamento nativo para futuras contas secundárias (`/data/accounts/<business_id>`).
- **Diagnóstico ampliado de conexão:** tratamento específico de `instagram_connection.ConnectionError` no callback para registro seguro do motivo da rejeição da conta Instagram nos logs sem expor tokens ou segredos.
- **Testes de regressão:** adicionados testes em `test_oauth_meta.py` e `test_http.py` comprovando envio do `redirect_uri` correto na chamada Graph API e sucesso de autenticação no fluxo ponta a ponta.
- **Compatibilidade:** preservados slug (`umdoislab_instagram`), SQLite, dados em `/data`, Ingress, portas, Editorial, Mensagens e arquitetura multi-contas. Sem migrações destrutivas.

## 0.1.10 — diagnóstico seguro de retorno OAuth e nova aba — 20/11/2026

- **Correção de experiência:** o link `Conectar Instagram pela Meta` abre em nova aba com `target="_blank"` e `rel="noopener noreferrer"`, evitando que a interface incorporada do Home Assistant tente abrir a autorização Meta dentro de iframe.
- **Diagnóstico de falha real:** a Meta retornou a `/oauth/meta/callback`, mas a Central exibiu `OAuth refused or expired`; a conta permaneceu não verificada. O callback agora registra **somente a etapa interna** de falha (`parse_callback`, `consume_state`, `exchange_code`, `verify_instagram_account` ou `store_credential`) e uma razão interna segura. A resposta pública continua genérica e não expõe credenciais.
- **Teste de regressão adicionado:** valida presença de nova aba e mensagem de etapa `exchange_code` sem imprimir state ou código OAuth. O teste foi incluído na suíte de build do Supervisor, mas sua execução ainda precisa ser comprovada no hardware alvo.
- **Compatibilidade:** preservar slug, nome da loja, `ingress`, portas, opções, chaves, credenciais, bancos, mídias, Mensagens, Editorial e demais add-ons. Sem migração destrutiva. Não habilita publicações externas nem respostas automáticas.
- **Esteira:** procedimento `hassio-addons/CONTRIBUTING.md` P0. Sem Actions. Publicação no catálogo e instalação no Supervisor são fases separadas.

## 0.1.9 — correção de falha de compilação no Supervisor (hotfix) — 20/11/2026

- **Erro real confirmado:** a atualização 0.1.8 falhou no passo Dockerfile `python3 -m py_compile`, em `tests/test_http.py:224`: `SyntaxError: bytes can only contain ASCII literal characters`. Nenhum teste da 0.1.8 foi executado pelo Supervisor após essa falha.
- **Correção restrita:** troca `b'aria-label="Módulos"'` por `'aria-label="Módulos"'.encode("utf-8")`, mantendo a verificação exata do cabeçalho. A origem foi inspecionada nos 22 arquivos Python da candidata; não foram encontrados outros literais bytes com caracteres não ASCII pelo verificador textual (não equivale ao `py_compile` integral).
- **Identidade e compatibilidade:** incremento de versão 0.1.8 → 0.1.9; sem alteração nos módulos de execução, Dockerfile, login, bancos, dados persistidos, SVG/PNG, slug, arquitetura, opções ou Meta.
- **Esteira:** seguir `hassio-addons/CONTRIBUTING.md` P0; sem GitHub Actions ou build ARM64 externo obrigatório. A prova final será o build e suíte no Supervisor durante a atualização autorizada.

## 0.1.8 — patch privado de UX e legendas locais (NÃO PUBLICADO/INSTALADO) — 20/11/2026

- **Publicação no feed:** uma única opção visível; 1 foto gera `feed`, 2 a 20 fotos geram `carousel` automaticamente. O formato interno e rascunhos anteriores continuam compatíveis.
- **Legendas:** escolha de uma legenda geral ou texto separado para cada imagem de carrossel. Persistência local aditiva no SQLite e na API privada (`captionMode`, `slideCaptions`); rascunhos 0.1.7 são preservados com modo geral por padrão. Nenhuma legenda individual é enviada à API Meta; publicação externa segue desativada.
- **Prévia de celular:** navegação anterior/próxima e indicador de posição em carrossel, incluindo texto da imagem selecionada.
- **Aprovações:** miniatura da primeira mídia, título derivado do início da legenda, resumo curto, tipo e estado nessa ordem. Clique na miniatura ou descrição abre modal central com celular grande, prévia completa e navegação apenas para leitura. Botões Editar/Aprovar/Agendar/Cancelar agenda preservados.
- **H11 — falha intermitente de mídia após sessão longa:** H11 passou por relato do proprietário depois de F5 (Story com MP4 já existente, prévia, reprodução, salvamento e aprovação), mas antes de recarregar a aba o MP4 não carregou e operações de upload/salvar produziram erro técnico de JSON. O patch passa a destacar mídia não carregada diretamente na miniatura/prévia, apresentar erro persistente junto ao formulário/Biblioteca quando uma operação falha e explicar resultados HTTP não confirmados sem afirmar que algo foi gravado ou descartado. **Causa HTTP exata ainda não identificada; não houve logs do HA.**
- **H10 — agendamento contextual:** janela de agendamento mostra a **primeira mídia**, um título derivado do início da legenda, um resumo da legenda e o tipo da publicação, sem alterar o esquema de dados. Data anterior à atual (horário de São Paulo) é recusada com mensagem clara dentro do modal, imediatamente acima de **Confirmar agenda**. Em falhas HTTP/servidor, a janela e o horário digitado permanecem, o erro fica visível e o sistema não exibe texto técnico de parsing JSON. Backend continua validando e recusando datas vencidas.
- **H09 — aviso persistente de conflito:** a API já rejeita versão antiga com HTTP 409, preservando a edição mais recente. O feedback antigo usava toast temporário, na mesma aparência de sucesso, e o proprietário não percebeu uma recusa. A candidata mostra agora **erro destacado e permanente junto ao formulário**, mantém o texto não salvo no campo, e orienta reabrir a publicação antes de tentar novamente. Os toasts de outros erros passam a ter apresentação distinta dos sucessos; contrato de versionamento e dados não foi alterado.
- **Visual unificado da Central:** Mensagens usa o tema escuro aprovado do Editorial (paleta, marca, menu lateral, topo conciso, painéis de conexão e tabela responsiva), sem trocar HTML do login nem ações internas de handoff/Meta. Ambos os módulos agora exibem botão **Sair** no cabeçalho, usando o mesmo `POST /auth/logout` existente; sem autenticação adicional.
- **Calendário após edição:** reserva anterior de data/hora é preservada em campo não executável; a publicação aparece no calendário com destaque **Aguardando nova aprovação** e botão **Aprovar** direto na lista. Reaprovação restaura automaticamente o horário se ainda futuro; se passou, mostra horário expirado e permite reagendar. Cancelar agenda continua limpando a reserva.
- **Persistência e segurança:** migração sem exclusão de dados, CSRF e mesma sessão administrativa, arquivos de mídia privados, nenhuma porta ou serviço novo. Limite de JSON de rascunho de 256 KiB para até 20 legendas de 2.200 caracteres; demais ações permanecem limitadas a 16 KiB.
- **Testes direcionados adicionados:** migração de base anterior, rascunhos persistentes, validação de payloads/limites, fluxo HTTP e roteiro Chromium de carrossel/modal. **Ainda não executados nesta conversa:** não declarar PASS, build de imagem ou homologação 0.1.8.
- **Situação:** desenvolvimento em branch privada `feat/instagram-editorial-ux-patch-001`, sem merge, publicação, atualização Home Assistant, ativação Meta ou GitHub Actions. A 0.1.7 foi publicada no catálogo (commit `b39f9edf2772f295d13180b456ff040271071329`), instalada e teve abertura visual e H01 aprovados **por relato do proprietário**; H02 passou por relato, com falha de preservação da agenda registrada.
- **Navegação após F5 no Ingress:** o retorno à tela de Mensagens foi relatado como não bloqueante. Não foi identificado mecanismo do wrapper HA que explique a troca; nenhuma mudança especulativa de roteamento/Ingress foi feita neste patch.

## 0.1.7 — Central Instagram unificada: Mensagens + Editorial (CANDIDATA PRIVADA, NÃO PUBLICADA/INSTALADA) — 20/11/2026

- Entrega a Central Editorial **dentro do mesmo add-on, painel e sessão administrativa** já usados por Mensagens, sem segundo aplicativo, login ou autenticador Meta.
- Integra a interface Editorial privada (biblioteca, upload, rascunhos, revisão, aprovação, agendamento, edição e cancelamento) ao backend HTTP e SQLite persistente. **Agenda não publica posts**; não existe executor de publicação Meta nesta candidata.
- Armazena o Editorial Umdoislab em `/data/editorial/editorial.sqlite3` e mídia em `/data/editorial/media/`. Preserva Mensagens em `/data/instagram.sqlite3`, dados existentes, sessão, chaves e credenciais legadas.
- Adiciona base multicontas com `business_id` interno separado do identificador Instagram. As rotas administrativas e de Mensagens desta entrega continuam limitadas à Umdoislab; **não ativa segunda conta real** nem herda segredos entre negócios.
- Reforça sessão e autorização, CSRF por ação/negócio, validação de upload, CSP, mídia privada, limites, versionamento transacional e bloqueio de reenvio após resultado ambíguo.
- Mantém `slug: umdoislab_instagram`, `arch: [aarch64]`, Ingress/porta interna 8099, padrão `backup: cold` e as opções `ingress_enabled:false`, `drafts_enabled:false`, `meta_oauth_enabled:false`. Não altera a Central WhatsApp, n8n, Gemini ou o NGINX.
- Atualiza Dockerfile com os módulos, interface, Pillow/tzdata e testes do add-on embutidos no build. Preserva a marca pública existente (mesmos `icon.png`/`logo.png` do catálogo).
- **Evidência de código já existente, sem repetição após alteração só documental/versionamento:** Python offline **152/152 PASS**, Chromium E2E PASS; build complementar Alpine **linux/amd64** **149/149 PASS** com CA TLS temporária do executor. O build original no executor falhou por confiança TLS, exit 1; o teste não foi feito em ambiente Codex integralmente independente. Ver [IG-PR7-GATE-001](https://github.com/mmcromero/instagram-automacoes/blob/d4a885460635d5930b8c8a1e4875e94918816dae/docs/evidence/IG-PR7-GATE-001-20261120/RELATORIO.md) e [parecer Issue #1](https://github.com/mmcromero/instagram-automacoes/issues/1#issuecomment-7040960917).
- **Status:** apenas branch privada de candidata 0.1.7, não distribuída, sem merge, Actions, publicação, instalação, ativação OAuth/webhook Meta, recebimento de DM real, envio Direct ou publicação de post. A 0.1.6 do catálogo é o pacote anterior e não inclui Editorial integrado.

## 0.1.6 — Lote 1: conexão oficial Meta e primeira DM (candidata experimental; NÃO ATIVADA) — 20/11/2026
- Corrige troca de código do Login Unificado para o contrato GET da Meta. Valida identidade da conta `@umdoislab` (ID exato) e portfólio antes de armazenar token.
- Adiciona diagnóstico visual de conexão no painel autenticado: configurações faltantes, conta verificada, webhook habilitado, assinatura solicitada, mensagens armazenadas e última entrada.
- Ações administrativas reais `Verificar acesso Meta` e `Assinar mensagens na Meta`; assinatura opt-in só do campo `messages`, nunca envia Direct. Protegidas por sessão e CSRF.
- Integra os testes de contrato Graph, OAuth e HTTP ao Dockerfile. Não altera o esquema existente nem apaga histórico do SQLite.
- Prepara fragmento HTTPS de três rotas exatas no NGINX existente, arquivado somente no repositório privado; **nenhuma alteração aplicada no Raspberry nesta branch**.
- Graph API padrão documentado `v27.0`; entradas OAuth e webhook continuam **false** por padrão. Mantém HTML login, Chrome, senha, marca e slug da 0.1.5.
- Testes locais comprovados: 9/9 Graph, 12/12 OAuth, 9/9 sessão-CSRF; hashes dos arquivos exatos conferidos. Sintaxe NGINX equivalente aprovada isoladamente. Suíte HTTP inteira e execução no Supervisor **pendentes**, sem alegar primeira DM real.
- Requer HTTPS público validado, autorização Meta, assinatura do campo messages e teste com outra conta, com segurança e revogação documentadas em `docs/IG-LOT1-REAL-001.md`.

## Em desenvolvimento — login HTML para Chrome (NÃO PUBLICADO) — 20/11/2026
- Troca a janela HTTP Basic do painel por um formulário HTML com campos `autocomplete=username` e `autocomplete=current-password`.
- Reutiliza `admin` e `panel_password` existentes; não grava nem expõe senha no código.
- Armazena apenas digest HMAC do token aleatório da sessão em SQLite; sessão expira em 12 horas e pode ser encerrada por **Sair**. Alterar senha invalida sessões antigas.
- Limite de tentativas incorretas e testes de login/logout, cookies, segurança e fluxo HTTP adicionados ao build do Supervisor.
- Mantém OAuth Meta, webhook, rascunhos e mensagens automáticas desativados; sem alteração no WhatsApp ou n8n.
- **Ainda não é uma versão de catálogo nem está instalada no Home Assistant**. Depende de revisão e autorização específica antes de publicar ou atualizar o Raspberry.

## 0.1.2 — OAuth Meta unificado (experimental, desativado por padrão) — 20/11/2026
- Adiciona login unificado Meta com `config_id`, `state` descartável, callback HTTPS e troca de código no servidor.
- Armazena credenciais cifradas no volume local do aplicativo; mantém os tokens fora da interface e dos logs.
- Todos os novos campos opcionais ficam vazios ou desativados por padrão; sem mensagens automáticas e sem ações no WhatsApp.
- Preserva painel Ingress, banco SQLite, slug e credenciais da versão 0.1.1; não muda a porta do aplicativo.
- Adiciona o pacote `py3-cryptography` e integra 4 testes de smoke + 11 testes OAuth no build local do Supervisor.
- **A publicação não configura o NGINX nem habilita o OAuth.** Instalação e homologação exigem autorizações próprias.

# Histórico — Central Instagram

## 0.1.1 — padronização da distribuição Home Assistant

- Nome público: `Fábrica de Softwares - Central Instagram`.
- `icon.png` e `logo.png` oficiais do catálogo compartilhado (mesmos blobs Git de Kanban e dos outros add-ons), inseridos na distribuição pública.
- Mantidos `slug: umdoislab_instagram`, dados SQLite, `panel_icon` interno, integração desativada e versão anterior imutável.
- Correção exclusiva de marca e versão; não instalada, nem homologada.

## 0.1.0 — primeira candidata de teste para Home Assistant (não instalada)

- Add-on experimental aarch64 com Dockerfile e Ingress.
- SQLite independente, deduplicação, fila de mensagens com reserva/ACK e handoff.
- Painel HTML autenticado, CSRF, auditoria e visualização de rascunhos.
- API interna de classificação; decisões sem envio e sem Gemini.
- Webhook Meta com HMAC-SHA256 desativado por padrão.
- Quatro verificações dirigidas sem rede executadas **durante futuro build do Supervisor**.
- Nenhum workflow n8n ou integração WhatsApp incluído na distribuição.
- Estado: preparação de candidata; sem instalação e sem homologação.


## Histórico do desenvolvimento — OAuth Meta Unified Login

- Endpoints internos de início e callback OAuth, com `state` de 10 minutos e cookie HTTPS seguro.
- Troca de código por Graph API (inativa até autorização), e token cifrado em arquivo restrito no volume `/data`.
- Metadados `meta_app_id`, `meta_login_config_id` e URL de retorno configuráveis; `meta_oauth_enabled:false` por padrão.
- 11 testes OAuth offline dirigidos, além dos testes HTTP criados para o callback; não ativa webhooks ou mensagens automáticas.
- **Não foi publicado/instalado na versão 0.1.1**. Nenhum arquivo do catálogo público modificado.
