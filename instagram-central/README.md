# Central Instagram — 0.1.39 (multi-conta editorial e Drive privado)

**Links de navegação:** a Central aceita parâmetros de atribuição UTM conhecidos em `/` e `/panel`, inclusive `?utm_source=chatgpt.com`. Sem sessão, exibe login; com sessão, mantém a página solicitada. Não altera o webhook, OAuth ou a entrega de DMs reais. A validação na instalação depende de homologação.

A Central prioriza o uso no celular. Configurações tem três abas: **Conexão, Diagnósticos e Ferramentas**. Contas separa a lista do cadastro. No editor, **Conteúdo e Prévia** alternam no celular e aparecem juntos em telas amplas, sem perder campos ou mídias. Revisão e Histórico mostram cartões resumidos e detalhes sob demanda. A conta ativa tem foto/nome/@ no seletor; sem foto, aparecem as iniciais.

Há proteção contra perda de alterações e **Continuar composição** para retomar o que ainda não foi salvo. **Criar publicação** continua abrindo uma composição nova após confirmar o descarte quando necessário. O menu mantém as quatro seções aprovadas e o mesmo contexto da conta.

**Atualização:** preserve as opções e `/data` e atualize somente a Central. Não exige alterar NGINX, webhook, portas ou login. A nova exclusão no Instagram pode exigir uma permissão adicional, conforme abaixo. Testes locais incluem toque emulado, criação/revisão/agendamento, larguras 320/360/390, teclado e movimento reduzido. Uso em aparelho real e operações Meta reais precisam ser confirmados após instalar.

No novo modal **Excluir**, escolha **Somente da Central Editorial** ou, para publicações com ID remoto confirmado, **Da Central Editorial e do Instagram**. A opção remota pede confirmação da conta indicada e só remove o registro local após a Meta confirmar a exclusão. Pode exigir incluir `instagram_manage_contents` no aplicativo e na configuração do Login do Facebook para Empresas e usar **Conexão Meta → Atualizar permissões da conta → Renovar autorização da conta**. A permissão e o suporte da conexão são conferidos antes de enviar a exclusão; uma recusa preserva registro e arquivos. Carrosséis são excluídos inteiros, não uma imagem isolada. Em caso de resultado incerto, confira o Instagram antes de autorizar nova tentativa; a Central não repete a exclusão automaticamente. As mídias usadas por outras publicações continuam preservadas.

## Mensagens recebidas

A caixa mostra cartões com remetente, data/hora de Brasília, texto completo, controle e origem. Os botões **Assumir, Aguardar, Concluir e Voltar ao bot** mantêm as ações locais de atendimento, com rótulos legíveis e espaço próprio. Rascunhos existentes aparecem no cartão; **Fila e rascunho** reúne os detalhes adicionais. Os controles não enviam respostas ao Instagram.

O operador confirmou leitura/gravação/exibição de mensagens reais pela busca manual na 0.1.35. Isso não comprova entrega por webhook. Para testar uma DM nova, envie-a e recarregue somente a página (F5): esse GET lê o banco local. **Atualizar mensagens** consulta a Meta e não deve ser usado como prova de webhook.

## Busca manual de mensagens

Em **Mensagens → Caixa de entrada → Atualizar mensagens**, o botão agora consulta a Meta com a credencial da conta selecionada e grava os textos recebidos para exibir na caixa. Antes, ele apenas recarregava o banco local. A busca é feita **somente pelo clique**, sem consulta periódica ou resposta automática.

Uma busca consulta até **5 conversas recentes e 10 mensagens de cada**, sem seguir paginação. Se a listagem não incluir as mensagens, consulta diretamente a lista daquela conversa: no máximo seis GETs por clique, espaçados e com orçamento de tempo. Conversa indisponível não oculta as outras que puderem ser lidas; a tela informa **Busca parcial**. Se nenhuma lista puder ser lida, informa erro e preserva a caixa. Se a Meta entregar mais itens que o pedido, somente os primeiros cinco/dez da amostra são processados, com aviso de limite. Repetir a busca não duplica registros. Só importa textos de até 2.000 caracteres com remetente/destinatário identificados e destino igual à conta selecionada; saídas, outros destinatários e mídia sem texto não entram. Campo de identidade ausente ou recusa da Meta produz aviso, preservando a caixa existente. Não é importação de todo o histórico nem garante acesso a conteúdo que a Meta não disponibilizar.

A coluna **Origem** distingue **Consulta manual à Meta** de **Webhook**. As importações ficam fora da fila automática; se o mesmo ID de mensagem chegar depois pelo webhook válido, o registro passa a Webhook e fica elegível uma vez, respeitando o atendimento humano existente. Uma nova busca não reabre mensagem já processada. As contagens de recebimento nas configurações consideram somente webhook. Ver mensagens importadas manualmente **não comprova nem corrige a entrega dos webhooks**.

**Contas novas:** cadastrar nome/@ cria o cadastro local. Em **Configurações Meta**, a próxima ação destacada é **Conectar Instagram pela Meta**; **Verificar acesso Meta** fica desabilitado até existir credencial salva. Credencial já salva pode ser verificada mesmo sem identidade confirmada. Falta de autorização, credencial recusada/expirada, acesso negado e falha de consulta/assinatura mostram mensagens distintas nas configurações da mesma conta. A consulta não inicia OAuth nem assina eventos automaticamente. Autorização da conta e indicadores de webhook aparecem separados. Correção do [relato registrado](https://github.com/mmcromero/instagram-automacoes/issues/1#issuecomment-7077224670).

**Exclusão:** o botão e o modal dizem **Excluir da Central / Excluir somente da Central**. A confirmação deixa explícito que a publicação continua no Instagram; a seleção de mídias remove só arquivos locais sem uso em outros posts. **Excluir da Central e do Instagram não está implementado nem habilitado nesta conexão.** A documentação de [exclusão IG Media](https://developers.facebook.com/documentation/instagram-platform/reference/instagram-media#delete) restringe essa operação ao Facebook Login com token de usuário e `instagram_manage_contents`; não confirma suporte ao BISU do Unified Login usado aqui. Existe relato externo de funcionamento com Unified e essa permissão, mas não é uma capacidade confirmada para nosso token. Nenhuma postagem real foi apagada e não foram alterados login ou permissões.

**Atualização 0.1.33:** atualize somente a Central, preservando opções e `/data`. Uma coluna de origem é adicionada ao SQLite; registros anteriores continuam como Webhook. Não exige mudança de proxy, token, URL ou login. Depois escolha uma conta já conectada, abra a caixa e clique uma vez em Atualizar mensagens. A busca e a correção de conexão passaram nos testes locais com Meta simulada; leitura real dos textos no HA ainda aguarda o operador. O webhook continua como objetivo do recebimento imediato, processamento e resposta; este pacote não o substitui por consultas periódicas.

## Controle e atividade das conversas (0.1.32, preservados)

Em **Conexão Meta → Configurações Meta → Controle e atividade das conversas**, clique em **Consultar controle e atividade** para uma leitura específica com o token já salvo da conta selecionada. Uma única consulta GET examina até cinco conversas e mostra quantas estão sob controle do aplicativo, fora desse controle ou sem essa informação, além do horário de atividade mais recente da amostra em Brasília. Não consulta textos nem participantes; os IDs recebidos são descartados, sem armazenamento ou exibição. O resultado fica somente na página e não é renovado automaticamente.

`is_owner` depende do que a Meta disponibiliza para esse acesso/encaminhamento. Campo ausente é **não informado**, nunca interpretado como controle de outro aplicativo. Recusa da consulta mostra erro/códigos numéricos sem inventar contagens; falha preserva o resultado anterior. A amostra não identifica o aplicativo padrão nem prova recebimento da DM enviada ou entrega de webhook. O botão mostra carregamento e impede cliques repetidos enquanto aguarda.

**Atualização 0.1.32:** somente a Central, preservando opções e `/data`. Usa a sessão, a credencial de cada conta e a rota de diagnóstico existentes, sem novo OAuth ou configuração de proxy. O operador confirmou a 0.1.31 instalada; amostras da Meta chegaram e foram aceitas, mas a DM real não apresentou novo marcador de chegada. Alterar somente a assinatura de `messages` de v27 para v26 não trouxe melhora observada; retornar esse campo à v27 é uma ação manual pendente, sem mudar a versão Graph da Central. A 0.1.32 acrescenta evidência para investigar, sem declarar o recebimento corrigido. Instalação e consulta real desta versão ainda dependem do operador.

## Integração de ferramentas e menu unificado (0.1.31, preservados)

A 0.1.31 incorpora o PR #13, preservando as configurações e a abertura externa da 0.1.30. O menu mantém **Editorial, Mensagens, Contas e Conexão Meta** em todas as páginas. Contas usa o mesmo cabeçalho e estilo; o seletor de conta permanece no topo e a navegação preserva a seleção por URL, sem alterar a conta de outra aba. **Calendário** e **Histórico** continuam separados. Criar publicação abre uma composição nova.

Em **Conexão Meta → Configurações Meta → Conectar ferramentas de criação**, crie uma chave por ferramenta e conta. Ela aparece uma vez, vence em 90 dias e pode ser revogada. Por padrão permite somente transferir para revisão. **Permitir publicação direta quando eu autorizar** concede o acesso adicional; cada publicação ainda exige autorização específica para aquele conteúdo/versão e conta. Criar uma chave não autoriza transferências futuras ou automáticas.

“Manda/sobe para a Central” autoriza transferir a versão escolhida para revisão. “Publica agora”, “publicação direta” ou autorização equivalente autoriza transferir pela Central e liberar aquele conteúdo. A interpretação pertence ao agente/ferramenta; a API exige indicadores separados e não depende de palavras-chave exatas. Conteúdo editado após a transferência não pode usar a autorização original da integração: revise/publique na Central ou faça nova transferência autorizada.

A API recebe JPEG/PNG/MP4 em estágio privado e finaliza todas as mídias de um post em um commit. Recibos persistentes e requestId evitam recriação ou novo envio quando o pedido é repetido. Chaves não concedem administração, leitura de outras conexões/contas ou acesso ao token Meta. Cotas incluem temporários e biblioteca. [OpenAPI 3.1](tools/editorial-openapi.json) · [Cliente Python genérico](tools/editorial_client.py) (sem rede por padrão) · [Guia completo](https://github.com/mmcromero/instagram-automacoes/blob/feat/instagram-multicontas-operacional-001/docs/IG-EDITORIAL-INTEGRATION-001.md).

**Atualização/ativação:** atualize somente a Central para 0.1.31, preservando opções e /data. Não altere proxy, certificados ou credenciais Meta. Depois escolha a conta, crie a conexão nas configurações e guarde a chave no cofre/configuração privada da ferramenta. Configure `CENTRAL_EDITORIAL_URL` com a origem HTTPS da Central e `CENTRAL_EDITORIAL_TOKEN` com essa chave. Não envie o valor no chat, Git ou URLs. O pacote não cria chaves reais nem configura automaticamente serviços externos. Instalação, conexão privada da ferramenta e homologação no HA são etapas posteriores do operador.

## Configurações e abertura externa (0.1.30, preservadas)

**Configurações Meta** é uma página própria da conta selecionada. Reúne conexão, configuração necessária, diagnóstico de recebimento, **Verificar acesso Meta**, assinatura de mensagens e **Verificar publicação**. Mensagens fica dedicada ao atendimento. O Editorial deixa de mostrar os dois avisos fixos de diagnóstico/publicação e funcionamento da agenda.

**Verificar publicação** é uma consulta manual para investigar erros ou conferir uma conexão alterada; não é uma etapa obrigatória antes de cada envio. O executor continua conferindo o acesso automaticamente quando necessário. A consulta manual mostra carregamento, impede repetição enquanto aguarda, informa conclusão mesmo com resultado igual e preserva o diagnóstico anterior se a consulta falhar. Abrir/recarregar Configurações não consulta a Meta automaticamente.

**Abrir página no Home Assistant:** o botão passa a abrir a Central em outra aba, sem Ingress ou clique intermediário. O atalho Ingress da barra lateral do HA foi retirado. O manifesto usa o template suportado `https://[HOST]:[PORT:8443]/webhook/instagram?open=central`; o GET reaproveita a rota já existente no proxy e redireciona para o `public_base_url` HTTPS configurado, mantendo a autenticação da Central. Não publica a porta interna 8099 nem ocupa uma nova porta 8443. Para esse botão, acesse o HA pelo domínio HTTPS habitual **romeropi.duckdns.org:8443**: `[HOST]` acompanha o endereço usado no navegador; acesso por IP/hostname local não fornece o certificado do domínio. A URL direta da Central continua **https://instagram.romeropi.duckdns.org:8443/panel**.

**Atualização:** somente a Central para 0.1.30, preservando opções e `/data`. Não é necessário alterar proxy, token, login ou configurações Meta. A abertura real do botão no HA aguarda confirmação após atualizar; manifesto/expansão de URL, redirecionamento e nova aba foram conferidos em ambiente local. A organização geral do menu foi aprovada e incorporada à 0.1.31.

**Resultado real informado pelo proprietário:** o histórico da 0.1.29 carregou e algumas métricas apareceram. Uma publicação e um Story já funcionaram na 0.1.27. DMs, carrossel e multicontas reais continuam pendentes; esta versão não altera o receptor de mensagens.

## Histórico e importação de mídias (0.1.29)


Em **Histórico**, clique em **Sincronizar histórico** para trazer as publicações que a Meta disponibilizar da conta selecionada, inclusive anteriores à Central. A opção de baixar mídias vem marcada. A sincronização percorre as páginas em segundo plano, mostra progresso e permite cancelar; registros já importados permanecem. Executar novamente atualiza registros pelo ID do Instagram sem duplicar nem publicar novamente. A conexão existente é usada por conta, com a mesma sessão e sem trocar proxy/login.

O histórico reúne publicações importadas e envios da Central, com data original, legenda retornada, link, curtidas e comentários. Compartilhamentos/salvamentos são consultados separadamente quando disponíveis; recusa desses campos não impede importar o restante. Há filtro por formato e ordenação para comparação. **Interações conhecidas** somam as contagens disponíveis e mostram cobertura; não são uma taxa de engajamento nem reconstrução das contagens em datas passadas. Zero continua distinto de dado ausente. A data da consulta é exibida.

O **Calendário** inclui publicações realizadas na data original e mantém as agendas. Use o seletor de mês ou **No calendário** em uma publicação para abrir seu mês. Registros importados são histórico publicado; não entram como rascunho ou fila de envio. A Central mantém o original local de posts que ela própria criou e apresenta os dados consultados separadamente. Não se presume exclusão remota quando uma publicação deixa de aparecer ou uma consulta falha.

As cópias de mídia entram na **Biblioteca** com autenticação, conforme limites existentes: 25 MiB por arquivo, até 500 arquivos/1 GiB e até 1000 publicações locais. Imagens passam pela mesma validação/regravação dos uploads. Downloads aceitam somente HTTPS nos CDNs permitidos, sem seguir redirecionamentos nem enviar o token Meta ao CDN. Arquivo grande/indisponível ou biblioteca cheia não apaga o registro histórico. Se um vídeo não puder ser baixado, pode ser importada sua miniatura, com aviso explícito no registro; ela não é o vídeo original. A cópia depende da mídia fornecida pela API e não garante o arquivo original da câmera.

Exclusão continua **local**. Ao apagar um registro importado, é possível remover suas mídias sem uso em outros posts; uma nova sincronização poderá trazê-lo novamente se existir no Instagram. Durante uma sincronização ativa, cancele ou aguarde antes de apagar um registro importado. Não recupera Stories antigos nem o arquivo privado do Instagram. Na prévia, Descrição de acessibilidade mostra o alt_text retornado, sem convertê-lo em legenda individual visível ou afirmar que são campos equivalentes.

**Atualização:** apenas a Central para 0.1.29, preservando opções e /data. Sem nova configuração do proxy, token ou login. O importador não inicia sozinho após atualizar; você escolhe quando sincronizar cada conta. A importação real dos seus registros e as contagens efetivas ainda aguardam execução no HA pelo operador. Testes locais usaram 69 publicações sintéticas e duas contas simuladas. Recebimento de DMs continua pendente.

## Curtidas, comentários e duração dos Stories (0.1.28)

**Resultado real informado pelo operador:** uma publicação e um Story foram enviados com sucesso na 0.1.27. Carrossel, multicontas e DMs ainda não foram confirmados. A leitura real das contagens da 0.1.28 aguarda uso pelo operador.

Em **Revisão e envios**, publicações enviadas com ID confirmado mostram curtidas e quantidade de comentários. Clique em **Atualizar métricas** para consultar os números daquela publicação, usando a conexão da conta selecionada. Não há consultas contínuas nem acesso ao conteúdo dos comentários. Os números e a data da última consulta ficam salvos. Zero aparece como zero; campo ausente aparece como não informado. Falha de acesso preserva os últimos valores e não é tratada como prova de exclusão. Contagens dependem do que a Meta disponibiliza, inclusive conforme formato, privacidade e superfície; não são uma promessa de totais de anúncios.

Stories têm link explicitamente temporário. Após 24 horas da confirmação de envio registrada localmente, o botão de abrir o Story é retirado; o histórico e a prévia local permanecem enquanto seus arquivos forem mantidos. A Central orienta consultar o arquivo no aplicativo Instagram, sem prometer acesso ao arquivo privado pela API. Publicações anteriores usam o horário já registrado na auditoria; não se inventa horário quando ele estiver ausente.

**Limites após publicar:** Excluir continua apagando somente o registro/arquivos locais escolhidos. Edição posterior de legenda na Meta e cópia/republicação não estão implementadas. A referência IG Media documenta atualização de comentários, sem edição da legenda. A exclusão remota é documentada para Facebook Login com instagram_manage_contents; a tabela dessa operação não confirma Unified Login/BISU, utilizado pela Central. Não se trocou login nem foram solicitadas permissões adicionais neste lote. [Referência oficial](https://developers.facebook.com/documentation/instagram-platform/reference/instagram-media).

**Atualização:** somente a Central, preservando opções e /data. Mesmos proxy, login e credenciais. As consultas novas usam as rotas já permitidas e CSRF próprio por ação/conta. Sem suíte integral no build do HA.

## Correções de publicação, navegação e exclusão (0.1.27)

A 0.1.27 corrige o erro interno que transformava uma primeira recusa da Meta em “Editorial temporariamente indisponível” nas tentativas seguintes. A verificação não pede mais `account_type`, campo não documentado para o IGUser do Facebook Login. Consulta somente `id,username`; a Meta continua responsável pela elegibilidade de Stories. Uma recusa agora identifica a etapa com um rótulo fixo e código numérico, sem expor resposta privada ou credenciais. O primeiro erro 100 observado é compatível com a consulta removida, mas sua causa exata não foi comprovada por uma resposta real detalhada.

**Criar publicação sempre inicia um formulário vazio.** Para continuar uma publicação salva, abra **Revisão e envios → Editar**. O menu agrupa Contas, Conteúdo, Atendimento e Configuração; mantém o contexto da conta em todas as páginas. Verificar publicação mostra andamento, bloqueia repetição e confirma a conclusão mesmo quando o resultado permanece igual.

Há skeleton no carregamento dos dados e das mídias, carregamento de mídia conforme visibilidade, progresso real de upload seguido da etapa de validação, e transições curtas de entrada/saída. Teclado e preferência de movimento reduzido têm resposta imediata; indicadores preservam o texto da operação. Aplicação da skill [Design Motion Principles](https://github.com/kylezantos/design-motion-principles).

**Excluir:** em Revisão e envios, use Excluir e confirme. É possível preservar as mídias ou remover somente as que não são usadas em outra publicação. Na Biblioteca, Excluir mídia apaga arquivos sem vínculo; arquivos em uso mostram a quantidade de publicações e ficam protegidos. Excluir um agendamento pendente cancela seu envio; conteúdos em processamento ou com resultado remoto incerto não podem ser apagados. Excluir um registro publicado remove apenas o histórico local, mantendo o conteúdo no Instagram. A confirmação informa o espaço liberado e eventual limpeza pendente. A limpeza de arquivos interrompida é retomada ao abrir a conta; bytes pendentes continuam contando na cota.

**Atualização da 0.1.26:** atualize somente a Central, preservando opções e `/data`. Não exige reconexão, troca de token ou alteração no proxy. O aceite real de uma publicação e um Story foi informado posteriormente pelo operador; testes automatizados continuam usando contas e Meta simuladas. O 504 identificado no acompanhamento `logs/follow` é do caminho de logs HA/NGINX, sem evidência de relação com a publicação.

## Publicação editorial em múltiplas contas (introduzida na 0.1.26)

[Política de privacidade](PRIVACY.md) · [Termos de uso](TERMS.md) · [Solicitar exclusão de dados](DATA_DELETION.md)

A **0.1.26** implementa o envio do Editorial ao Instagram para a conta selecionada: imagem no feed, carrossel de 2–20 imagens, Reel e Story. O mesmo executor atende as contas, com token, mídias, posts e agenda separados. Publicar não depende de receber DMs. Mensagens recebidas continuam em investigação; esta entrega não habilita o receptor das contas secundárias.

**Atualização:** faça backup e atualize somente a Central, preservando opções e `/data`. Não substitua o proxy, certificados ou tokens por rotina. O build do HA continua limitado à sintaxe. Os testes de publicação usam Meta simulada; a primeira publicação real e a execução no seu HA precisam ser confirmadas pelo operador.

### Usar o Editorial

1. Abra **https://instagram.romeropi.duckdns.org:8443/accounts** e escolha a conta. Para adicionar outra, informe seu nome/usuário e conclua **Conectar com a Meta** no painel correspondente. A conta precisa ser profissional e estar disponível na autorização Meta; estar na mesma Central de Contas não substitui essa autorização. A principal não é desconectada.
2. Entre no **Editorial** da conta. O acesso de publicação é conferido automaticamente quando necessário. Se precisar investigar um erro, use **Configurações Meta → Verificar publicação**: a Central lê validade/app/permissões do token, identidade e configuração de entrega de mídia. Se faltar `instagram_content_publish`, inclua essa permissão na configuração de login do app Meta e reconecte somente a conta afetada. Não substitua App Secret ou verify token por um token de acesso. A confirmação de pré-requisitos não equivale a App Review aprovado nem à publicação real concluída.
3. Na **Biblioteca**, carregue a mídia; em **Criar publicação**, prepare conteúdo e legenda. Em **Revisão e envios**, revise e aprove. Escolha **Publicar agora** e confira a conta exibida antes de confirmar, ou **Agendar** e confirme um horário futuro de São Paulo.
4. Acompanhe **Publicando**, **Publicada** ou o motivo da interrupção em Aprovações. O resultado atualiza enquanto a página está visível. **Ver no Instagram** abre o post quando a Meta fornece o link; caso contrário, abre o perfil da conta. A Central deve permanecer ligada para executar a agenda; envios autorizados vencidos são retomados quando ela volta.

Agendamentos de versões anteriores ficam aguardando **Confirmar envio agendado**. Aprovar/editar conteúdo não libera silenciosamente uma agenda antiga; edição e cancelamento revogam a autorização. Um envio possivelmente aceito sem resposta entra em verificação, sem novo POST automático. Use **Verificar resultado**; somente libere nova tentativa após conferir que não foi publicado. A tentativa usa o mesmo contêiner da Meta. Falhas anteriores ao envio podem voltar ao rascunho para correção.

### Mídias e permissões

- Imagens são enviadas em JPEG, até 8 MB. PNG recebe fundo branco nas áreas transparentes. Feed/carrossel exigem proporção entre 4:5 e 1,91:1; a Central recusa proporções incompatíveis sem cortar a imagem silenciosamente.
- Carrosséis usam uma legenda geral. Anotações por imagem são preservadas localmente, mas precisam ser convertidas para legenda geral para publicar, conforme a capacidade da API.
- Reels aceitam MP4; Stories aceitam uma imagem ou MP4 e exigem conta Empresa. O texto de um Story precisa fazer parte da própria mídia. A API valida codecs/duração; referência atual: Reel de 3 segundos a 15 minutos, Story em vídeo de 3 a 60 segundos. A Central mantém upload máximo de 25 MiB e não faz transcodificação de vídeo.
- O acesso à biblioteca continua autenticado. Somente mídias de um post autorizado recebem links temporários de uma hora, restritos à conta/revisão/execução. Cancelamento, edição, falha ou conclusão interrompem seu acesso; links antigos não voltam a funcionar numa nova execução. Não compartilhe esses links.
- A Meta precisa conseguir buscar a mídia pela URL HTTPS do callback cadastrado. A Central reutiliza essa rota existente para entrega temporária, sem depender da chegada de eventos de mensagens e sem alteração dos arquivos NGINX. Tokens OAuth não são enviados nessa URL.

As seções seguintes registram versões e etapas anteriores. O funcionamento da 0.1.27 descrito acima prevalece sobre limitações históricas de publicação local.

## Histórico 0.1.25 — conexão interna

A **0.1.25** corrige a incompatibilidade identificada nos logs reais: o NGINX tentou alcançar a porta 8099 por IPv6, enquanto o receptor aceitava somente IPv4. A Central usa uma única porta com IPv4/IPv6 quando o sistema permite dual stack; mantém IPv4 em sistemas sem esse suporte. O comportamento HTTP, assinatura e armazenamento são os mesmos nos dois protocolos.

**Para atualizar da 0.1.24:** faça backup e atualize somente a Central, preservando opções e `/data`. Não substitua arquivos nem reinicie o proxy. A linha de inicialização deve mostrar `version=0.1.25 transport=ipv4_ipv6` no ambiente com dual stack. Isso confirma a abertura do receptor, ainda não a entrega de DM. As consultas Meta já aprovadas não precisam ser repetidas.

As recusas IPv6 são comprovadas, mas não foram correlacionadas à DM real: uma coincide com o pedido técnico que acabou respondendo 403. O HTML 504 antigo também não teve origem/horário correlacionados. Esta correção remove a incompatibilidade demonstrada sem atribuir toda a falha a ela.

## Registro e interface anteriores 0.1.24

A **0.1.24** mostra **Verificando…** ou **Solicitando assinatura…** imediatamente após o clique, com aviso de espera e botões Meta desabilitados enquanto a navegação está pendente. A trava vale para a mesma tela; ao voltar pelo histórico em cache, os controles são restaurados.

O receptor passa a registrar **Meta webhook request** na entrada de POSTs para `/webhook/instagram`, inclusive antes das recusas por tamanho ou assinatura. A linha contém somente versão, categorias e booleanos: não inclui conteúdo, IP, parâmetros, cookies ou valor da assinatura. Chegada não prova autenticidade; a validação HMAC posterior continua obrigatória. Ausência dessa linha, sozinha, não distingue falha da Meta, rede ou proxy.

**Para atualizar da 0.1.23:** faça backup e atualize somente a Central, preservando opções e `/data`. Não altere proxy, certificado, credenciais ou modo publicado do app. Confirme a versão na inicialização antes de outro teste de recebimento. As quatro consultas Meta já confirmadas não precisam ser repetidas por rotina. Esta versão melhora a observação da falha; não declara entrega real corrigida.

O build no HA executa somente uma checagem rápida de sintaxe dos módulos de execução, sem repetir a suíte completa no dispositivo. Testes de comportamento são realizados no desenvolvimento conforme a mudança. Publicação não comprova instalação ou funcionamento no Raspberry.

## Auditoria anterior 0.1.23

A **0.1.23** amplia **Verificar acesso Meta** com leituras de metadados do token salvo e da configuração de webhook do aplicativo, quando exposta pela API. O painel mostra validade do token, vínculo com o App ID e concessão de `instagram_basic`/`instagram_manage_messages`. Esses dados não informam o nível Standard/Advanced Access nem comprovam elegibilidade de produção ou entrega de DM.

Se a Meta retornar o objeto Instagram na consulta do app, o diagnóstico mostra ativação, campo `messages`, HTTPS, correspondência do caminho `/webhook/instagram` e somente o domínio/porta de destino. Valores de parâmetros, fragmentos, identificadores de pessoas e respostas privadas são descartados. A consulta genérica pode não expor Instagram: nesse caso aparece **não confirmado**, sem concluir que a assinatura esteja ausente do portal.

**Resultado real informado pelo operador na 0.1.23:** assinatura da conta com `messages`, acesso às conversas aceito, token válido/do app configurado/com as duas permissões, e webhook do aplicativo Instagram ativo com `messages`, HTTPS, caminho e destino esperados. As consultas não comprovam entrega real nem nível Standard/Advanced Access.

As consultas são GET, com host fixo, timeout e tamanho de resposta limitados. A credencial do aplicativo é formada somente em memória no servidor, sem gerar ou substituir o token OAuth. Redirecionamentos de Graph são recusados para não encaminhar credenciais a outro destino. Nenhum segredo precisa ser copiado para o navegador ou enviado no chat. Nenhuma verificação empresarial, App Review ou assinatura adicional é executada por Verificar acesso Meta.

## Diagnóstico anterior 0.1.22

A **0.1.22** mostra o resultado de **Verificar acesso Meta** no próprio painel. Além de verificar a identidade, consulta, sem alterar a Meta, se o aplicativo configurado consta na assinatura da conta com o campo `messages` e se o token salvo permite consultar uma amostra de conversas. A amostra pede somente um ID, que é descartado; não consulta textos, participantes ou histórico. Falha de identidade não renova a verificação anterior e aparece explicitamente. Falhas de consulta aparecem separadas, com categorias fixas e códigos numéricos, sem a resposta privada da Meta.

**Atualização da 0.1.21:** faça backup e atualize somente a Central, preservando opções e `/data`. Não substitua o proxy nem refaça OAuth por rotina. Abra **https://instagram.romeropi.duckdns.org:8443/panel**, clique uma vez em **Verificar acesso Meta** e leia **Diagnóstico de recebimento**. É possível compartilhar somente as linhas **Assinatura consultada na Meta** e **Acesso às conversas**. Nenhum token precisa ser copiado. Recarregar a página apenas exibe o último diagnóstico, com horário; não consulta novamente a Meta. Um acesso aceito com amostra vazia não comprova recebimento de DM.

O botão **Assinar mensagens na Meta** também passa a mostrar confirmação quando a Meta aceita o pedido; isso ainda não comprova a chegada de eventos reais. Uma nova assinatura invalida o diagnóstico anterior; use Verificar acesso Meta para uma nova leitura quando necessário. Não há assinatura automática, envio, mudança no ManyChat ou roteamento de conversas nesta atualização.

### Credenciais: funções diferentes

| Campo | Origem e finalidade |
|---|---|
| `meta_app_id` | ID do aplicativo `auto_reply` nas configurações básicas da Meta; identifica o app. |
| `meta_app_secret` | Chave secreta desse mesmo app; usada no OAuth e na validação de assinatura dos eventos. Não é um token de acesso. |
| `meta_verify_token` | Segredo de verificação escolhido na instalação; deve coincidir com **Verificar token** do webhook na Meta. Não é emitido pelo login. |
| Token de acesso OAuth | Emitido pela Meta após autorização e guardado cifrado pela Central, por conta. Não deve ser colado no App Secret ou no verify token. |
| `bridge_secret` e senha do painel | Segredos locais com finalidades próprias; não são credenciais a cadastrar no webhook da Meta. |

O valor antigo encontrado por engano em App Secret tem origem desconhecida. Não o mover para outro campo por suposição. OAuth autorizado e evento de teste com assinatura aceita são evidências desses passos nas respectivas tentativas; não comprovam toda a configuração de mensagens ou todas as funcionalidades futuras. A primeira DM real segue pendente. As consultas desta versão ajudam a localizar a falha sem presumir que todo o código/configuração já esteja correto.

## Correção anterior 0.1.21

A **0.1.21** corrige o reconhecimento de mensagens recebidas no envelope `entry[].changes[]` com `field=messages`, usado no login unificado, além de preservar `entry[].messaging[]`. Antes, um evento unificado válido podia receber HTTP 200 sem que sua mensagem fosse gravada. Assinatura HMAC, conta destinatária, deduplicação e isolamento permanecem obrigatórios. Outros campos, como comments, continuam sem processamento/resposta automática.

**Atualização da 0.1.20:** preservar opções e /data e atualizar somente a Central. Nenhuma alteração de proxy, certificado, URL de webhook, callback, senha ou consentimento OAuth é necessária por causa deste hotfix. O webhook real continua na URL que o operador verificou na Meta: `https://romeropi.duckdns.org:8443/webhook/instagram`; a URL do painel/OAuth permanece no subdomínio dedicado. Esses endereços têm finalidades distintas. A 0.1.20 já restaurou o manifesto aceito pelo catálogo; esse formato foi mantido.

Para testar: envie uma nova mensagem de texto após a atualização e atualize o painel. Em caso de falha, os logs agora registram somente `Meta webhook accepted` com versão e contagens `legacy_events`, `unified_events`, `recipient_match`, `matched_text`, `stored`, ou `Meta webhook rejected` com motivo fixo. Nunca incluem conteúdo, IDs de pessoas/contas, assinatura, token, segredo ou URL. Um evento fictício do botão Teste pode ser aceito com recipient_match=0/stored=0, pois não corresponde à conta real; isso não autoriza armazená-lo na principal.

A entrega do evento fictício pela Meta passou, segundo a captura do operador; o recebimento da primeira DM real ainda aguarda aceite na 0.1.21. Não concluir que o estado Não publicado é sozinho a causa: Standard Access permite testes com pessoas com função no app; a elegibilidade de entrega real depende das regras da API e não é comprovada por um toast do teste. O executor não mudou modo do app, permissões, assinaturas ou funções na Meta.

**Primeira conta real:** o proprietário confirmou `@umdoislab` verificada e autorizada na 0.1.18. A 0.1.19 preserva essa credencial, chave, mensagens e Editorial. As contas adicionais deste lote foram testadas com dados/provedor sintéticos; não representam autorizações reais de outras contas.

A 0.1.20 corrige o manifesto inválido da 0.1.19: o campo `webui` não aceita uma URL com hostname/porta fixos. O Supervisor exige os marcadores `[HOST]:[PORT:...]`; a URL fixa fazia a Central deixar de ser listada na loja. Removido esse campo e restaurados o Ingress interno 8099 e o ícone de painel da 0.1.18. Os arquivos oficiais icon.png/logo.png continuam preservados. O cadastro/conexão de contas e os painéis isolados da 0.1.19 permanecem. **Nenhuma nova porta no roteador, volume SSL ou chave privada na Central.**

**Abertura da interface:** o botão do HA continua entrando pelo Ingress. Para operar ou conectar contas, abra o endereço HTTPS dedicado indicado abaixo em uma aba própria. Não foi implementada abertura externa automática pelo botão do Supervisor; a promessa correspondente da 0.1.19 estava incorreta.

Fonte privada: `mmcromero/instagram-automacoes`, branch `feat/instagram-multicontas-operacional-001`, baseada no PR #11. Commits, PR, relatório e publicação auditada na [Issue #1](https://github.com/mmcromero/instagram-automacoes/issues/1). Nome/slug `umdoislab_instagram`, arquitetura declarada `aarch64`, backup cold e ícones oficiais preservados. Fonte main privada e outros aplicativos não são alterados.

## Atualização da 0.1.18

1. Faça backup do aplicativo com seus dados e preserve todas as opções, especialmente senha, App ID e App Secret já corrigidos. Não desinstale nem apague `/data`.
2. Atualize a Central para **0.1.20**. Não é necessário reconectar `@umdoislab` nem copiar token. As duas URLs públicas permanecem as mesmas:
   ```yaml
   public_base_url: "https://instagram.romeropi.duckdns.org:8443"
   meta_oauth_redirect_uri: "https://instagram.romeropi.duckdns.org:8443/oauth/meta/callback"
   ```
3. Atualize **somente** `/share/nginx_proxy/instagram.conf` com [a candidata desta versão](proxy/instagram.conf), mantendo cópia anterior fora do padrão `*.conf`. As rotas novas `/accounts` precisam deste arquivo; o proxy 0.1.18 ainda atende o painel principal, mas retorna 404 para Contas.
4. Reinicie somente o NGINX SSL proxy pelo HA, com acesso local disponível para recuperação. Não altere certificado, roteador, domínio principal, fragmentos Avisaqui/Artesão ou o webhook antigo. [Guia e rollback](proxy/GUIA-OPERADOR.md).
5. Abra **https://instagram.romeropi.duckdns.org:8443/panel**. Use essa URL externa para os testes. O botão do aplicativo continua usando Ingress; não inicie OAuth dentro dele. A conta Umdoislab deve continuar conectada. Se aparecer pendente, preserve os dados e diagnostique antes de iniciar outro consentimento.

`certfile`/`keyfile` antigos permanecem aceitos, mas são ignorados pela aplicação. O NGINX continua lendo `/ssl`. O certificado wildcard já foi emitido pelo operador para esta instalação; não emitir outro por causa desta atualização.

## Como adicionar e usar outra conta

1. Faça login com o mesmo administrador da Central e abra **Contas**.
2. Informe um nome de exibição e o **usuário exato do Instagram**, por exemplo `@minhaconta`. Clique em **Adicionar conta**. Isso cria somente um cadastro pendente; não chama a Meta ou ativa mensagens.
3. No painel dessa conta, clique em **Conectar Instagram pela Meta**. Confira os ativos/permissões e selecione a conta pretendida. A Central descobre o ID oficial pelo usuário informado; não é preciso colar ID/token ou outro segredo no cadastro.
4. Após autorização, use **Voltar ao painel da conta**. Em Contas, abra o painel correspondente. Mensagens, handoff, credencial e Editorial ficam no contexto escolhido. Abas de contas diferentes podem permanecer abertas sem trocar a seleção uma da outra.
5. Contas de teste precisam estar aptas no mesmo app Meta (conta profissional, portfólio/convite/função aplicáveis). Clientes externos podem exigir Advanced Access/App Review da Meta; isso não é contornado pela Central.

O mesmo administrador tem acesso a todas as contas cadastradas. Não há login individual por cliente nem RBAC neste lote. Uma conta/ID já vinculada não é remapeada silenciosamente; duplicatas de usuário/ID são recusadas. Até 100 registros por instalação. Contas internas antigas não se tornam operacionais automaticamente.

## Isolamento e limites

- A conta principal conserva `/data/meta-oauth-token.enc`, sua chave e `/data/editorial/`. Novas contas usam diretórios próprios em `/data/accounts/{id-interno}/` e `/data/editorial/accounts/{id-interno}/`. Migração aditiva acrescenta somente o marcador de cadastro operacional ao registro de contas.
- Um único app Meta é reutilizado por cadastros explicitamente feitos pelo administrador. Campos necessários do app/login são compartilhados por uma lista explícita; segredo da bridge, verify token e ativação de webhook da principal não são herdados pelas secundárias.
- OAuth mantém callback único no mesmo hostname. State/cookie vinculam o retorno à conta que iniciou a autorização, sem depender de qual painel está aberto. Cookie por tentativa, expiração, consumo único, vínculo de configuração e validação de ID/usuário continuam obrigatórios. A descoberta usa paginação limitada e não segue URLs arbitrárias devolvidas pelo provedor.
- Cadastro e mutações exigem sessão/CSRF. Tokens CSRF de Editorial/ações Meta são vinculados à conta; IDs de mídia e destinatário não selecionam implicitamente outro armazenamento. Credenciais não fazem fallback para a principal.
- O token emitido pela Meta pode abranger mais de um ativo do portfólio compartilhado; a aplicação restringe suas rotas ao contexto validado. Separação local não altera a granularidade da autorização concedida na Meta.
- **Histórico 0.1.19:** não havia nova assinatura, envio de Direct ou executor de postagem naquele lote. Desde 0.1.26, a publicação editorial por conta depende da confirmação descrita no início deste manual. A bridge e o receptor de DMs continuam restritos à principal; a recepção nas secundárias segue pendente.
- O indicador de conexão usa a última identidade verificada/credencial armazenada; não comprova entrega de mensagens nem validade eterna do token. **Verificar acesso Meta** faz a leitura de verificação no contexto correto quando acionado pelo administrador.

## Validação e distribuição

Testes locais incluem preservação byte a byte da credencial/chave principal, migração de registro antigo, cadastro concorrente sem duplicação, recusa de caminhos/identidades inválidos, OAuth de contas diferentes com callbacks em ordem inversa, mídia/CSRF/handoff isolados e descoberta paginada. Chromium cobre cadastro, OAuth simulado, bibliotecas separadas e regressão Editorial completa; NGINX real local verifica as novas rotas, autenticação, TLS, probe e limites.

Resultados/SHAs finais e evidências estão na Issue #1 e no relatório privado do lote. Build local não é homologação ARM64/Supervisor. Nenhuma conta real adicional foi autorizada pelo executor, nem instalação/reinício de HA ou proxy foi executado por ele. Publicação do pacote e teste real pelo operador são etapas distintas.

## Histórico das correções anteriores

## Correção 0.1.16 — leitura de todos os cabeçalhos Cookie

- Após o teste real da 0.1.15, chegaram logs com cabeçalho Cookie presente, mas nenhum cookie OAuth no trecho lido. Localmente foi comprovado que `HTTPMessage.get('Cookie')` retorna somente o primeiro campo; se um intermediário encaminha o cookie esperado em um segundo campo, a aplicação o ignora.
- A 0.1.16 reúne todos os campos Cookie em ordem antes de sessão/CSRF/OAuth/probe. Não descarta pares nem escolhe um dos duplicados: dois cookies com o nome de state esperado continuam sendo rejeitados.
- A tela de falha também mostra se algum cookie de estado chegou e se havia vários campos Cookie. O log registra a contagem limitada de campos recebidos, nunca seus nomes/valores.
- Evidência: **189 testes Python PASS** e **Chromium PASS** em nove cenários, incluindo proxy que fragmenta Cookie, mais abas concorrentes/config drift. Antes da correção, cookie esperado no segundo campo retornou 400; reunido num campo ou no primeiro, 200. Após a correção, o segundo campo passa; duplicação continua 400.
- A reprodução comprova uma falha de leitura do servidor, **não comprova que o HA encaminhou cabeçalhos separados**. Se o teste real ainda falhar, a tela/log 0.1.16 permitirá verificar essa condição sem expor dados.
- Sem nova migração, alteração de credenciais, esquema, banco, atributos de cookie, opções ou proxy. Instalação/Meta continuam fora da execução do Codex.

## Mudanças 0.1.15

- Logs de emissão indicam somente modo/versão e atributos fixos; logs de retorno usam flags e contagem limitada, nunca nomes/valores de cookies.
- Falhas de troca são classificadas como HTTP, TLS, DNS, timeout, rede ou JSON; status HTTP e códigos/subcódigos numéricos seguros podem aparecer no log, sem corpo, mensagem remota, URL ou cabeçalhos. A resposta pública permanece genérica.
- `meta_oauth_states.authorization_context` é uma coluna aditiva com fingerprint de campos públicos da configuração. Mudança de app/configuração/redirect/versão/conta entre start e callback é recusada antes da troca. Estados em voo emitidos antes desta atualização não são reutilizados; credenciais existentes não são alteradas.
- Mantém cookies individuais por tentativa, `Secure`, `HttpOnly`, `SameSite=Lax`, `Path=/oauth/meta/callback`, TTL e consumo único, contas/tokens isolados, mesma aplicação Meta, mesmo login, Mensagens e Editorial.
- Evidência local: **185 testes Python PASS**, **8 cenários Chromium de probe PASS**, duas abas com autorizações sintéticas independentes e rejeição de mudança de configuração antes do exchange. Rede de testes limitada a loopback/stubs; nenhuma chamada Meta ou operação HA real.
- Esteira rápida P0: teste do diff, inspeção de sintaxe/configuração/segredos, exportação auditada uma vez e publicação somente da pasta autorizada com `[skip ci]`. Sem Actions ou exigência genérica de build ARM64 externo. Build/instalação/homologação no HA são etapas distintas.

## Histórico anterior


## Candidata 0.1.14 — probe do mesmo cookie state usado pelo OAuth

- O teste anterior `probe=1` usava `ig_oauth_probe`, diferente do cookie `ig_oauth_state_<hash>` do fluxo real. O teste de transporte aprovado não cobria o cookie novo.
- A 0.1.14 passa a emitir um nonce sintético e um cookie com o mesmo nome derivado do state e o mesmo leitor de cookie usados pelo callback OAuth. A callback de probe valida o cookie sem criar state no SQLite nem chamar a Meta.
- `/health` informa a versão carregada; a página de probe também mostra a versão. Isso permite confirmar se o Supervisor está executando a versão publicada.
- Testes unitários e HTTP adicionados para validar nome e valor do cookie, cookie de outra tentativa, valor divergente e versão.
- Situação: código em branch privada; testes pendentes; sem merge/publicação/instalação. Nenhuma tentativa OAuth real necessária.

## Candidata 0.1.13 — isolamento do cookie de estado OAuth por tentativa

- Cada autorização usa um nome de cookie próprio, derivado do SHA-256 do `state`; o callback valida somente o cookie correspondente ao `state` recebido.
- Evita colisão/sobrescrita entre tentativas simultâneas no mesmo navegador. A evidência anterior confirma cookie presente e divergente, mas não prova que concorrência foi a causa original.
- Preserva `state` aleatório de 256 bits, expiração de 10 minutos, consumo único no SQLite e atributos `Secure`, `HttpOnly`, `SameSite=Lax` e `Path=/oauth/meta/callback`.
- Não altera NGINX, Ingress, rotas, banco, dados, credenciais, opções do HA, webhook, Direct ou publicação de posts/stories.
- Testes offline do módulo OAuth: 18/18 passaram em harness isolado com o arquivo `oauth_meta.py` e `test_oauth_meta.py` do SHA de origem. Isso não substitui o build do Supervisor nem a homologação no HA.
- Estado desta candidata: proposta em PR de distribuição; não instalada nem homologada. A única tentativa real anterior de OAuth foi consumida e não deve ser repetida sem autorização específica.

## Versão 0.1.12 — diagnóstico de cookie, origem e proxy

- Reúne as alterações funcionais de 0.1.11 já publicadas: `redirect_uri` idêntico na troca de código e gravação de credenciais no diretório correto por negócio.
- Separa falhas de cookie ausente, duplicado e divergente. O log não imprime cookie, `state`, código OAuth ou segredo.
- Botão **Testar navegador e proxy (sem Meta)** verifica, em nova aba, se o navegador aceita e devolve um cookie temporário pelo HTTPS público; testa o mesmo caminho de callback e não contata a Meta. Reutiliza as rotas existentes `/oauth/meta/start` e `/oauth/meta/callback`; não altera o OAuth real.
- Acrescenta indicadores booleanos de correspondência entre Host público e autoridade do callback configurado, e de `X-Forwarded-Proto=https`.
- Mantém o cookie restrito a `Path=/oauth/meta/callback`; esse caminho corresponde ao callback. Não amplia para `/`.
- Não altera NGINX ativo, Ingress, Meta, credenciais, banco, mídias ou opções do HA.
- **Distribuição histórica 0.1.11:** publicada na `main` do catálogo, somente na pasta `instagram-central/`. Naquele pacote o Dockerfile incluía a suíte integral; desde 0.1.24, o build do Supervisor verifica somente sintaxe. Publicação não altera o Raspberry, NGINX ativo, opções, credenciais ou painel Meta.

## Versão 0.1.11 — correção de redirect_uri e isolamento de credenciais

- Inclui `redirect_uri` na troca do código OAuth.
- Usa `account_registry.credential_root(...)` ao armazenar token no callback e na assinatura.
- Adiciona testes de regressão unitário e HTTP.
- Publicação no catálogo público: PR #64, commit `fe90bd3ee77e03a15a40d9320d034616a3c72656`. O erro de `parse_callback` persistiu após a atualização relatada pelo proprietário.

## Candidata 0.1.10 — retorno OAuth e nova aba

- Link externo da Meta usa nova aba e `rel="noopener noreferrer"` para não abrir login dentro do iframe do Home Assistant.
- Logs locais do callback identificam a **etapa** da falha sem exibir URL com `code`, `state`, cookies, credenciais ou dados retornados pela Meta.
- Inclui teste de regressão dirigido; naquele pacote o Dockerfile verificava a suíte integral. Desde 0.1.24, o build no Supervisor verifica somente sintaxe. Nenhum PASS do Supervisor é declarado antes da atualização real.
- Sem alterações nos bancos, rascunhos, credenciais existentes ou nas rotas de publicação; não habilita envio ou publicação Meta.

## Funcionalidades incluídas no código 0.1.7

**Mensagens:** interface administrativa com formulário HTML e sessão única, visão de mensagens, indicador de estado de conexão, handoff e auditoria, deduplicação e filas locais com claim/ACK, políticas offline e OAuth Meta preparado mas desligado. O painel usa a senha própria `panel_password` e não envia Direct.

**Editorial:** a navegação abre `/editorial/` no mesmo servidor e sessão de Mensagens. Biblioteca de mídia, upload JPG/PNG/MP4 com validação de tipos/limites, rascunhos, edição, aprovação, agenda no fuso `America/Sao_Paulo`, cancelamento e recarga persistente via HTTP+SQLite. Edição invalida aprovação/agenda anterior; operações obsoletas recebem conflito de versão. **A agenda é local, não realiza postagem.** Não há segundo login nem serviço Editorial separado.

**Estrutura multicontas:** cadastro interno de negócios, separação entre `business_id` e ID da conta oficial Meta e isolamento de tokens/mídias. Nesta candidata, **somente Umdoislab** tem rotas administrativas operacionais. Outras contas são apenas sintéticas em testes; nenhuma ativação real.

## Patch 0.1.8 — interface Editorial (não publicado)

- **Feed automático:** a opção Publicação no feed aceita 1–20 imagens; uma imagem mantém `feed`, várias imagens são gravadas como `carousel`. Story e Reel continuam separados. Rascunhos anteriores mantêm o tipo.
- **Legendas locais por imagem:** quando o carrossel tem 2 ou mais imagens, escolher *Uma legenda para todas as imagens* ou *Legenda individual por imagem*. O SQLite mantém `caption_mode` na publicação e `slide_caption` em cada anexo, com migração **aditiva**. A API aceita `captionMode` e `slideCaptions` opcionais, mantendo chamadas antigas válidas. **A API Meta não está habilitada para publicar essas legendas**; não há conversão ou descarte silencioso.
- **Prévia no Editor e em Aprovações:** setas para percorrer carrossel, contador posição/total; miniatura de capa e bloco de texto clicáveis no cartão de Aprovações. O modal grande abre **somente leitura**, sem formulário/edição/aprovação. Editar, Aprovar, Agendar e Cancelar mantêm as ações anteriores.
- **Título do cartão:** sem novo campo obrigatório. A interface utiliza o início da legenda geral (ou primeira legenda individual) como título curto, seguido de resumo visual; depois mostra tipo e status. Preserva os rascunhos existentes.
- **Mídia indisponível em aba antiga (H11):** se foto/vídeo apresentar erro de carregamento, Biblioteca e prévia mostram aviso junto à própria mídia orientando atualizar a página. Falhas de upload/salvar exibem alerta persistente perto do componente afetado, com tratamento de sessão inválida e resposta não JSON. O app não reinicia a sessão automaticamente, não repete gravações sem confirmação e não assume que a falha é expiração de login. A sessão do painel já existente expira em 12 horas; tokens CSRF de ação são obtidos no momento da ação. A causa do H11 ainda depende de evidência de status HTTP/log para ser identificada.
- **Agendar com contexto (H10):** o modal mostra miniatura da primeira mídia (ou frame de vídeo), título derivado da legenda e trecho da legenda para confirmar a publicação correta. Erros de data passada são mostrados dentro da janela, junto ao botão **Confirmar agenda**, sem fechar o modal nem apagar a entrada. Horário civil é comparado em `America/Sao_Paulo`, **além** da validação obrigatória no servidor. Respostas inesperadas do servidor deixam de expor mensagens técnicas `JSON.parse` ao operador; um retorno não JSON não será tratado como gravação confirmada. Nenhuma mudança no backend de publicação Meta.
- **Edições simultâneas (H09):** o backend mantém bloqueio por versão (HTTP 409). Em caso de conflito, o formulário mostra alerta de erro persistente **“Não foi salvo”**, preserva a digitação local e não trata a ação como sucesso. A mensagem explica que outra aba alterou a publicação e orienta recuperar a versão atual. Não é feito merge automático das duas edições nem sobrescrita da versão mais recente.
- **Padrão visual e logout único:** painel Mensagens passa a usar o mesmo tema escuro, hierarquia, menu lateral e cabeçalho do Editorial; os formulários `Assumir`, `Aguardar`, `Concluir`, `Voltar ao bot` e os controles Meta são preservados. O cabeçalho de ambos mostra conta e botão **Sair**. No Editorial, usa `action="../auth/logout"`, no painel Mensagens `action="auth/logout"`; ambas resolvem para **a rota administrativa existente** `POST /auth/logout`. Não há nova senha, cookie, rota de logout ou envio externo.
- **Calendário com reserva e revisão:** ao editar uma publicação já agendada, a data e a hora continuam registradas em `pending_schedule_at` e a execução fica bloqueada até nova aprovação. A publicação aparece no calendário com destaque visual e botão **Aprovar** diretamente na lista. Ao aprovar, o horário original volta se futuro; se vencido, permanece visível como expirado e solicita reagendamento. O botão **Cancelar agenda** segue limpando a reserva ativa.
- **Teste de F5 do Ingress:** retorno ocasional à página Mensagens relatado; sem causa confirmada, o patch não altera o roteamento do Home Assistant.
- **Evidência:** novos testes Python de migração, validação e persistência e roteiro de Chromium incorporados aos testes de desenvolvimento. **Não estão executados nesta conversa**; não confundir revisão de fonte com PASS de homologação.

## Dados e compatibilidade

- Mensagens, fila, estados, sessões e registro de contas: `/data/instagram.sqlite3` (SQLite WAL).
- Editorial da Umdoislab: `/data/editorial/editorial.sqlite3` e `/data/editorial/media/`.
- Chaves e token cifrado Meta, **se existirem**: permanecem na raiz `/data`, sem migração destrutiva; `/data/options.json` contém opções operacionais privadas no ambiente do add-on. Nunca copiar dados, tokens, opções ou chaves reais para o pacote ou para o Git.
- Migrações são aditivas; preservar diretórios, credenciais, mídias, chaves e os dois bancos durante qualquer atualização futura autorizada. Histórico `IndexedDB` do protótipo não é apagado nem importado automaticamente. Um backup consistente, inclusive WAL e mídia, deve ser avaliado no portão da instalação; não bloqueia a preparação privada deste pacote.

## Estado seguro por padrão

`ingress_enabled: false`, `drafts_enabled: false`, `meta_oauth_enabled: false`. São opções de integração específicas, **não** o campo `ingress: true` que apresenta o painel pelo Home Assistant. Senhas/segredos começam vazios no manifesto e nunca devem aparecer no Git.

A Central publica somente posts aprovados e explicitamente autorizados na conta selecionada. Agendamentos antigos permanecem sem autorização até sua confirmação; atualizações não criam envios. Não envia Direct, não liga robô Gemini, não chama WooCommerce/n8n ou WhatsApp, não configura NGINX nem expõe a porta 8099 diretamente. O estado de publicação da API reflete os pré-requisitos conferidos para cada conta, sem comprovar uma publicação real antes de executá-la.

Acesso administrativo deve usar a origem HTTPS própria da Central com credenciais reais; o Ingress foi retirado na 0.1.30. A sessão do painel e as rotas Editorial exigem autenticação; mutações exigem CSRF por ação, e a mídia é privada. MP4 passa por verificação **estrutural**; não há transcodificação nem antivírus. Limites atuais: 25 MiB por upload, 20 MP para imagens, biblioteca até 500 arquivos/1 GiB e até 1000 publicações locais. Não há rotina automática de limpeza.

## Testes de desenvolvimento — evidências já aceitas com ressalvas

No corte base do PR #7, anterior às alterações OAuth 0.1.11 e 0.1.12:
- `python3 scripts/validate_offline.py`: **152/152 PASS**.
- `node instagram-central/tests/editorial_browser.cjs`: **PASS** em navegador Chromium com dados sintéticos.
- Build complementar no Linux/amd64, montando CA temporária do executor como segredo BuildKit: **149/149 testes do add-on PASS**. O Dockerfile original falhou por confiança TLS ao buscar índices Alpine naquele ambiente (exit 1); a execução não ocorreu em novo ambiente Codex independente.

Essas evidências **não comprovam** build `aarch64` ou execução no Home Assistant, e não devem ser repetidas por rotina quando só versão/documentação mudou. O Supervisor poderá construir no hardware alvo **apenas durante uma instalação autorizada**. Norma: [P0 do catálogo Home Assistant](https://github.com/mmcromero/hassio-addons/blob/main/CONTRIBUTING.md).

## Distribuição Home Assistant — hotfix 0.1.9 para corrigir build ARM64

A versão 0.1.8 foi publicada no catálogo, mas **não passou na compilação dos testes dentro do Dockerfile no HA**, conforme o log do proprietário. O erro ocorreu antes da execução dos testes e da inicialização da nova versão. A 0.1.9 corrige a expressão Python inválida, usando `.encode("utf-8")` na asserção do `aria-label`. Nenhum módulo de execução, dado `/data`, token, opção de autenticação, ícone ou slug é alterado. A fonte do pacote novo está nesta branch; a publicação é feita pela P0 do catálogo apenas após conferência do diff e dos testes dirigidos. O Supervisor validará `py_compile` e a suíte no próximo build de atualização autorizada. O estado instalado atual deve ser confirmado no HA, não inferido do GitHub.

Documentação técnica: [contrato Mensagens + Editorial](https://github.com/mmcromero/instagram-automacoes/blob/f6ad64bc55bb3d8299c1e3cd71d40f5e63897082/docs/IG-MULTICONTAS-001.md), [relatório Codex](https://github.com/mmcromero/instagram-automacoes/blob/f6ad64bc55bb3d8299c1e3cd71d40f5e63897082/docs/IG-MULTICONTAS-001-RELATORIO-CODEX.md), [plano de homologação](https://github.com/mmcromero/instagram-automacoes/blob/6a6b4766c013d856b40856c06b47f53bef4a2d69/docs/IG-PR7-HOM-001-PLANO-CANDIDATA-HOMOLOGACAO.md). Consulte `CHANGELOG.md` para o histórico de versões anteriores.
