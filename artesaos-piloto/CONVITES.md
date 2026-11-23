# Convites — pacote experimental 0.1.17

O responsável autorizou fechar e publicar este pacote experimental após a preparação. A instalação continua manual; a publicação não configura credenciais nem envia mensagens reais.

## Formulário e lista

Na administração, Convites fica depois das abas Interessados no piloto, Chamados de suporte e Usuários cadastrados.

- Campos: nome da pessoa, e-mail de contato, WhatsApp com DDI/DDD e canal escolhido (e-mail ou WhatsApp).
- Nome e contato do canal escolhido são obrigatórios. Pode preencher os dois contatos. No canal WhatsApp, não é necessário e-mail.
- O botão é **Salvar**. Ele registra a pessoa e gera um código aleatório automaticamente, incluído na mensagem pronta. Não há campo para inventar o código, status Enviado ou confirmação manual de envio.
- Código individual, de uso único, sem vencimento. Os convites ativos existentes passam a não vencer; expirados/revogados permanecem inativos. Repetir a mesma solicitação não cria outro registro.
- A lista padrão contém somente convites ainda não aceitos. Convites expirados anteriores/revogados continuam identificados pela situação; não oferecem link de novo envio com código vencido.
- Quando um convite é aceito, ele sai da lista e a conta aparece em **Usuários cadastrados**. Na tela aberta, a lista atualiza ao receber foco ou a cada 15 segundos enquanto visível e sem formulário em edição; também existe Atualizar convites.
- Os dados históricos não são apagados ao esconder o convite aceito. Isso permite auditar o vínculo e preservar os contatos em Exibir dados do usuário ativado. Ainda é necessário definir retenção/descarte no pacote jurídico.

## Contato e conta Google

Por decisão expressa do usuário, **os novos convites são autorizados pelo código e ficam vinculados à primeira conta Google verificada que o usar**. O contato pode ser um e-mail não Google ou apenas telefone. Não é necessário conhecer previamente o e-mail da conta Google da pessoa.

A ativação é atômica: somente uma conta pode consumir o código. O sistema registra qual conta o aceitou e cria o banco individual da conta, mantendo o isolamento. A conta Google continua necessária para autenticar e para os próximos logins.

Convites anteriores à mudança, inclusive os das antigas opções/CLI, conservam sua regra de vinculação ao e-mail; não são convertidos para primeira conta. Seus códigos estavam armazenados somente como hash e não podem ser reconstruídos, nem são inventadas datas ou nomes históricos. A administração mostra essa ausência explicitamente.

## WhatsApp

Após Salvar, Exibir convite contém a mensagem e **Abrir no WhatsApp**, com link wa.me, telefone normalizado e texto contendo o código. O administrador abre a conversa e envia. Não há API WhatsApp Business, disparo automático, confirmação de entrega/leitura ou confirmação manual no sistema.

Não se abre uma conversa externa automaticamente após a resposta de Salvar; o botão explícito permite ao administrador revisar a mensagem e evita bloqueio de pop-up. A mensagem também pode ser copiada.

## E-mail

Sem SMTP configurado, Salvar prepara a mensagem e oferece **Abrir no meu e-mail** e Copiar mensagem. Registrar o contato não comprova entrega; o produto não acompanha esse estado, conforme solicitado.

Com SMTP configurado, Salvar no canal e-mail tenta enviar a mensagem automaticamente. Há proteção técnica interna contra repetição/concorrência, sem exibir estado de envio na lista. Se o provedor não confirmar a tentativa, o registro permanece salvo e a interface informa o problema; não existe repetição automática silenciosa. Aceitação pelo servidor SMTP não prova entrega ou leitura.

Configuração opcional nas opções do aplicativo ou em variáveis do servidor:

| Opção | Variável |
| --- | --- |
| smtp_host | PILOT_SMTP_HOST |
| smtp_port | PILOT_SMTP_PORT |
| smtp_user | PILOT_SMTP_USER |
| smtp_password | PILOT_SMTP_PASSWORD |
| smtp_from | PILOT_SMTP_FROM |

Todos vazios desativam SMTP. Ao habilitar, fornecer o conjunto completo; portas aceitas 465 (TLS direto) e 587 (STARTTLS obrigatório), com verificação de certificados ativa. O endereço remetente deve ser autorizado pelo provedor. Não colocar senhas em Git, chat, logs ou exemplos públicos.

Para o piloto pequeno, SMTP de uma conta existente é a opção inicial recomendada. Gmail depende de autenticação permitida pela conta, como senha de app quando disponível; não usa a permissão do login Google do aplicativo. Um provedor transacional pode oferecer SMTP e melhores ferramentas de entrega quando houver crescimento. Nenhum provedor, plano, custo, credencial ou endereço de servidor foi presumido/configurado nesta sessão.

## Dados, atualização e limites

Não existe mais teto fixo de cinco cadastros no modo de produção. O formulário de convites substitui os pares fixos nas opções; variáveis/opções antigas não criam convites e o comando CLI invite está desativado. Um contato não pode ter dois códigos ativos simultâneos. As listas são paginadas em 25 registros; busca de telefone completo usa índice derivado por HMAC, sem expor o telefone em claro no índice.

A atualização cria campos binding_mode e accepted_user_id no controle de convites e tabelas de metadados/controle técnico. Novos códigos, nome e telefone são cifrados com AES-256-GCM e chave local **pilot-invitations.key**. E-mails permanecem na tabela de controle existente. A chave no mesmo volume não protege contra comprometimento de ambos.

Backup protegido precisa incluir o volume completo, com banco e chaves. Chave ausente ou incorreta não gera outra por cima de dados existentes. A restauração completa deve ser testada antes da atualização real. **Não há rotina de backup da instalação pessoal configurada atualmente.** Esta documentação não a configura.

As rotas são exclusivas da administração, com sessão e contexto de aba; gravações exigem origem correta e CSRF. Código completo não é retornado na listagem nem nos dados do usuário, apenas na consulta explícita do convite por administrador. Não há acesso aos dados comerciais das contas no controle de convites.

## Limites da validação

Testes de código e navegador usam identidades, contatos e envios sintéticos. Nenhum e-mail/WhatsApp real foi enviado. SMTP real, o aplicativo nativo do WhatsApp no telefone, Google real, Home Assistant e hardware final permanecem dependentes da configuração e validação do responsável.


## Revogar e ativar novamente

Revogar bloqueia um código não usado. A operação é administrativa, exige origem/CSRF/contexto e não desativa uma conta já cadastrada. Ativar novamente gera um código diferente após confirmar o formulário; o anterior permanece revogado e seu vínculo de substituição fica preservado. A lista operacional mostra o registro atual, evitando duplicar a mesma pessoa com códigos substituídos. Uma repetição da mesma solicitação não gera múltiplos códigos.

A nova mensagem precisa ser enviada à pessoa. WhatsApp abre o texto/código atual; SMTP, se configurado, é tentado após Salvar. Não existe estado de envio do produto. Sem vencimento, um código vazado pode ser usado no futuro enquanto não tiver sido consumido/revogado; esse é o motivo para proteger mensagens e oferecer a revogação. Não há promessa de validade de códigos anteriormente expirados.

As limitações da audiência em modo Teste no Google continuam sendo do provedor. A remoção do teto do aplicativo não publica o OAuth nem adiciona testadores no console Google automaticamente. O hardware também continua limitando memória, concorrência e armazenamento; o cache de bancos e os limites temporários de frequência não são limite de usuários cadastrados.
