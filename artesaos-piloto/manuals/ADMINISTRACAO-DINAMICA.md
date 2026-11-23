> Versão corrente: **0.2.0-dev.13**. Ver [estabilização e convites](ESTABILIZACAO-CONVITES.md).
> Pix aceita telefone BR com DDD; confirmação/erro aparece junto ao formulário.
> Migração incremental control4; demais schemas preservados. Manuais/evidências
> de versões anteriores abaixo são históricos. Não atualizar instalações reais
> sem autorização específica e backup consistente.

# Administração — documentos, Pix e manual (0.2.0-dev.12)

## Acesso e publicação

Entrar pela administração já existente: Google autorizado no Home Assistant;
primeiro acesso/senha e recuperação por console no Debian. Abrir a aba
**Documentos e contribuição**. Login comum não concede permissão de publicação.
Nenhuma alteração nestas configurações exige build ou atualização do aplicativo.

## Termos, Privacidade e Cookies

1. Escolher o tipo; informar uma versão nova e única (até 100 caracteres).
2. Preencher texto simples ou selecionar TXT/MD. O conteúdo é apresentado como texto,
   não executado como HTML. Limite de 100 mil caracteres.
3. Para Termos, avaliar se a atualização exige novo aceite. A dispensa deve ser
   juridicamente adequada; não remove a obrigação de usuários sem aceite válido.
4. Salvar rascunho. Conferir o conteúdo integral no histórico e clicar **Publicar esta
   versão**. Publicação grava data/hora do servidor e responsável autenticado.
5. Versões publicadas são imutáveis; correções usam outra versão. Histórico integral
   e auditoria permanecem disponíveis. Auditoria tem consulta por conta e páginas de
   500 eventos, incluindo referência da versão do manual publicada na ocasião.

Na primeira execução desta versão são publicados textos iniciais beta da Tudoe3d,
sujeitos a revisão jurídica. Usuários novos e existentes sem evento de aceite válido
precisam confirmar os Termos antes das funções protegidas. Não são fabricados eventos
retroativos a partir de sessões ou da tabela antiga de aceites. O histórico antigo é
preservado; documentos legados são consultáveis na administração, sem metadados
retroativos inventados, e aceites antigos são consultáveis na seção legada da administração e preservados no banco/backup; novos eventos têm referência integral imutável.
A escolha **Recusar e sair** registra a recusa e encerra a conta. APIs verificam a
exigência a cada operação, inclusive em sessões abertas. Administração continua
acessível para gerenciar documentos e recuperar acesso.

Privacidade pode receber ciência na Ajuda; isso não é consentimento genérico a todo
tratamento. A inspeção identificou cookies técnicos de sessão/CSRF/autenticação,
service worker de preparação e preferências/fila técnica local do navegador.
Não foram identificados mecanismos próprios opcionais de publicidade/analytics.
Por isso, não existe banner de consentimento fictício. Não adicionar mecanismos
opcionais sem escolha real e prévia. A auditoria abrangente LGPD está no backlog alto.

## Manual PDF

Escolher **Manual PDF**, informar versão e enviar PDF de até 5 MiB. Salvar rascunho,
consultar/baixar a versão para revisão e publicar. O servidor verifica leitura pelo
parser PDF, limites e indicadores de conteúdo ativo; não promete varredura antivírus.
Arquivos ficam como BLOB imutável em `/data/pilot-legal.sqlite`, incluído no backup
integral. Publicar outra versão muda apenas a versão ativa; as anteriores permanecem.
Ajuda mostra versão/data e link para abrir/baixar, com histórico. Na ausência de manual,
mostra mensagem adequada. Não há conteúdo definitivo nem editor por capítulos nesta
entrega. O identificador/versionamento permite futura estrutura por capítulos.

## Contribuição voluntária

Informar chave Pix, beneficiário e mensagem; marcar **Ativar** e salvar. São aceitos
formatos CPF/CNPJ com dígitos verificadores, telefone +DDI, e-mail ou chave aleatória.
Verificar titularidade e recebimento no banco: validação de formato não comprova
propriedade/funcionamento. Desativação oculta a contribuição sem nova publicação.
Suporte e Ajuda exibem convite discreto para copiar a chave. Não há valor mínimo,
comprovante, licença, bloqueio ou prioridade de atendimento vinculada à contribuição.

## Visitantes e novos contatos

Na sessão em Vendas, **Visitantes** começa minimizado e zero. Expandir libera +1/−1;
minimizar conserva o total. Preferência fica no banco por contexto da conta/sessão.
Incrementos são eventos com chave idempotente/data do servidor, transação SQLite e
saldo nunca negativo. Cliques rápidos entram numa fila técnica local. Em resposta
perdida, a mesma chave é reenviada após retorno; não duplica. Se houver operações
pendentes, mantenha o armazenamento local até confirmar. Apagar dados do navegador
antes do envio pode eliminar operações ainda não recebidas pelo servidor.
Sessões encerradas mantêm histórico e admitem correção manual da contagem.
Conversão é estimativa vendas/visitantes, sem porcentagem com zero e sem teto de 100%.

Novo cliente em Orçamentos pré-seleciona Atacado; em Vendas/cadastro direto, Varejo.
O tipo é editável e nunca altera preços, descontos ou snapshots. Registros antigos
ficam Não definido. Origem, criação e sessão de captação são imutáveis no servidor;
cliente existente que compra não vira novo contato. Sessão mostra a quantidade/lista
com links aos cadastros, inclusive após encerramento. O local vinculado à sessão é
preservado por chave, sem depender de nome livre de feira/evento.

## Atualização e retorno

Preservar slug `artesaos_piloto`, ID `f6379561_artesaos_piloto`, origem, /data, opções,
Google, sessões e chaves. Migrações incrementais: tenant 10→11, legal 2→3; demais
schemas inalterados. Não sobrescrever tabelas antigas nem aceites anteriores.
Antes de atualizar instalação real: autorização específica e backup completo validado,
com todos os bancos/arquivos/chaves/opções. Não executar dev.11/0.1.17 sobre banco
migrado dev.12; restaurar aplicação e dados pré-upgrade coerentes para retorno.
Debian tem o mesmo schema e negócio, com dados/credenciais independentes.
Este manual não é instalação do servidor Forja 01 e não modifica infraestrutura.
