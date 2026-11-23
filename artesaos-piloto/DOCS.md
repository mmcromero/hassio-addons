# Artesão Digital — Testes

Manual permanente de distribuição C1/C2: [Home Assistant](manuals/HOME-ASSISTANT.md),
[Debian](manuals/DEBIAN.md), [recuperação](manuals/RECUPERACAO.md) e
[atualizações](manuals/ATUALIZACOES.md) no pacote exportado. No repositório, esses
arquivos estão em `distribution/docs/`. HA é o ambiente principal de homologação;
Debian permanece alternativa independente. Instalação real exige autorização.

Aplicativo experimental independente, baseado no núcleo Fabricação e Orçamentos 0.1.23. Não substitui, atualiza ou compartilha o volume do aplicativo principal. A imagem desta rodada foi construída/testada em amd64; aarch64 ainda depende da instalação real. Primeiro teste restrito ao responsável com duas contas Google próprias e dados fictícios; não convidar terceiros ainda.

## Manutenção e independência do principal

O Artesão Digital funciona com o aplicativo principal parado. Consulte [MANUTENCAO.md](MANUTENCAO.md) para parada, futura desinstalação com preservação de dados e recuperação de acesso após mudanças de IP interno no proxy.

## O que está implementado

Login Google OpenID Connect com Authorization Code, PKCE S256, state e nonce; verificação de assinatura, emissor, audiência, validade e e-mail verificado. Na versão atual, convites são gerenciados pela administração Web, sem teto fixo de cinco contas. Novos códigos são de uso único, sem vencimento e vinculam-se à primeira conta Google verificada que os usar; convites antigos mantêm sua regra de vínculo. Há revogação e reativação com novo código. Sessões com token aleatório de 256 bits armazenado como hash, cookies Secure/HttpOnly/SameSite, oito horas absolutas e trinta minutos de inatividade. Alterações exigem origem exata e token CSRF; a página fica vinculada à conta para bloquear abas antigas após troca de usuário. Logout invalida a sessão no servidor; revogação invalida sessões e convites.

Cada usuário recebe um banco SQLite separado. O servidor escolhe esse banco pela sessão autenticada, nunca por um identificador de conta enviado pelo navegador. As APIs comuns, categorias, parâmetros, importação, exportação e arquivamento usam a mesma separação. O login do Home Assistant não autentica o piloto.

## Limites desta entrega

Testes automatizados com identidades/servidor OIDC controlados não comprovam login real no Google ou funcionamento no seu Home Assistant. Ainda exigem validação o Google real, a configuração do proxy, cookies no navegador real, Supervisor e imagem ARM. Não é uma certificação de segurança nem revisão independente.

HTTPS protege o trajeto navegador–Nginx. A rede interna Nginx–aplicativo usa HTTP, como o proxy atual do Home Assistant. SQLite e opções do aplicativo NÃO são criptografados em disco por esta versão. Permissões restritas não equivalem a criptografia. Backups padrão do HA podem incluir opções/credenciais; use a proteção de backups da instalação e armazenamento protegido. Criptografia em repouso e avaliação independente permanecem requisitos antes de usar dados sensíveis ou liberar artesãos. Não copie bancos, clientes ou credenciais da aplicação principal.

## Instalação manual separada

1. Na loja do HA, atualize o catálogo e instale **Artesão Digital — Testes**. Não desinstale Fabricação e Orçamentos.
2. Mantenha a porta do host desabilitada. O Nginx acessará a porta interna 8099 pelo hostname mostrado na informação do novo aplicativo.
3. Não inicie sem configurar as opções abaixo. Ausência de Google ou URL válida faz o processo recusar a inicialização; não existe modo de autenticação simulada em produção.
4. Copie o **hostname real do novo aplicativo**. Não adivinhe prefixos nem reutilize o hostname da aplicação principal.

## Cliente Google

Crie um cliente OAuth de tipo aplicativo da Web no Google Cloud/Google Auth Platform. Para o piloto restrito, mantenha a audiência em modo de teste e adicione o e-mail Google de cada participante autorizado conforme as restrições do Google. A remoção do limite do aplicativo não altera a audiência/restrições do provedor. Essa lista do Google é separada dos convites individuais do aplicativo. Os nomes e rótulos da interface do Google podem variar.

Para uma URL pública `https://seu-dominio:porta/artesaos-piloto/`, cadastre exatamente:

- Origem JavaScript: `https://seu-dominio:porta`.
- URI de redirecionamento: `https://seu-dominio:porta/artesaos-piloto/auth/google/callback`.

Solicitamos somente openid e email; não acesso ao Gmail. Configure Client ID e Client Secret nas opções do aplicativo. Não cole o segredo em chat, Git, logs ou arquivos de configuração públicos.

## Opções

- `public_url`: endereço HTTPS completo, terminando em `/artesaos-piloto/`. Use sempre este mesmo endereço, inclusive em casa.
- `google_client_id` e `google_client_secret`: cliente Web configurado no Google.
- `admin_emails`: contas Google autorizadas a administrar o aplicativo.
- `smtp_host`, `smtp_port`, `smtp_user`, `smtp_password`, `smtp_from`: envio automático opcional. Deixe todos vazios para envio manual; ver CONVITES.md.
- `mercadopago_access_token`: token privado opcional para habilitar o Pix com confirmação automática. Informe no campo protegido na configuração do add-on Home Assistant; somente e-mails listados em `admin_emails` podem solicitar cobranças. Salve e reinicie o add-on, sem desinstalar. Não cole o token no navegador, no chat, no Git nem nos logs. Para teste e retomada, consulte `docs/operacao/PIX-QR-PDV-001-TOKEN-HA.md` no repositório.

Os campos antigos test_email/test_invite foram removidos a partir de 0.1.17. Seus valores restantes em opções antigas são ignorados pelo aplicativo; não recriam convites ao reiniciar. Os convites já gravados no controle são preservados. Gerencie pessoas e códigos exclusivamente na aba Convites da administração. O comando CLI invite foi desativado; permanece apenas o comando emergencial de revogação de conta, não o fluxo comum de convites.

As seções históricas abaixo descrevem versões anteriores. Para a operação atual, consulte CONVITES.md e Atualização 0.1.17. Se o OAuth continua em modo Teste no Google, as permissões de testadores do Google continuam independentes dos convites do aplicativo.

## Rota no NGINX Home Assistant SSL proxy

O aplicativo oficial suporta `customize.default` para incluir arquivos no servidor HTTPS existente. Não substituir o nginx.conf ou as rotas principais.

Depois de conhecer o hostname real do piloto, gere o fragmento com:

```sh
python3 generate-nginx.py --upstream-host HOSTNAME_REAL_DO_PILOTO --output nginx_proxy_default_artesaos.conf
```

O gerador exige um hostname válido e não sobrescreve arquivos. O resultado deve ir para `/share/nginx_proxy_default_artesaos.conf`, que corresponde ao padrão `nginx_proxy_default*.conf` já presente no proxy. O campo `customize.servers` continua inalterado. A rota preserva o prefixo, encaminha o Host com a porta externa e desativa logs de acesso do piloto para não registrar códigos OAuth.

Somente depois de o piloto estar configurado/iniciado e o hostname resolvido, valide `nginx -t` no contêiner do proxy, considerando o arquivo adicional, antes da ativação efetiva. Faça a alteração localmente, com cópia das opções anteriores e possibilidade de restaurá-las; não depender apenas do acesso remoto. Habilitar `customize.active` aplica os arquivos correspondentes existentes, portanto confira se há outros arquivos com esse padrão antes de habilitar. Nenhuma configuração é aplicada por esta distribuição.

## Primeiro teste

Abra o endereço HTTPS do piloto diretamente em uma aba, fora do iframe do Ingress. Digite o convite da primeira conta, entre pelo Google e crie somente registros fictícios. Use outro perfil/contexto do navegador para a segunda conta; confirme listas vazias e parâmetros separados. Teste criar/editar/arquivar, importar/exportar dados fictícios, sair e entrar novamente, tentativa com convite de outra conta, troca de conta mantendo aba antiga e revogação. Confirme que o Fabricação e Orçamentos original e seus dados permanecem intactos.

## Migração futura

O núcleo comum permanece independente do Home Assistant. A hospedagem temporária não aprova automaticamente o piloto para terceiros. A migração ao host dedicado exigirá seu pedido, URL/cliente Google ajustados e repetição dos testes de autenticação, isolamento, backup e proteção de dados.

## Evidência de desenvolvimento

A compilação e a suíte automatizada passaram, incluindo rejeição de assinatura/audiência/nonce/validade/e-mail incorretos; convites e estados de uso único; sessão expirada/revogada; origem/CSRF; aba de conta antiga; separação de produtos/clientes/orçamentos/parâmetros/exportação/arquivamento e reinício. O navegador exercitou cookies Secure, login e CRUD de duas contas em HTTPS local com certificado e provedor fictícios. A sintaxe do fragmento Nginx passou em contêiner descartável. A auditoria das dependências de produção não apontou vulnerabilidades conhecidas nesta rodada. Esses resultados não substituem o teste real no Google/HA nem uma avaliação independente.

## Atualização 0.1.1 — retorno após login

Atualize somente o aplicativo Artesão Digital — Testes, sem desinstalar. Contas, convites registrados e configurações permanecem no volume existente. Não é necessário recriar o cliente Google nem alterar a rota Nginx que já está funcionando.

Depois de autenticar no Google, o piloto exibe brevemente Concluindo acesso, confirma a sessão e abre Produtos automaticamente. A mesma regra vale para o primeiro acesso com convite e para o novo login de conta já ativada com convite vazio. Se a sessão não for reconhecida, a página mostra o problema e oferece entrar novamente, em vez de um retorno silencioso.

O teste local usa um provedor controlado e verifica conteúdo da aplicação visível, inclusive através de Nginx HTTPS. A validação com Google real na sua instalação ainda é necessária: faça primeiro logout/login com a conta já ativada; use o segundo convite somente depois de confirmar a entrada automática da primeira conta. Não use links diretos como substituto deste teste.

O rodapé identifica separadamente a versão do piloto e a versão-base do Fabricação e Orçamentos. Os metadados são gerados no build a partir do manifesto e pacote; core-base.json registra o commit-base e deve ser atualizado conscientemente ao incorporar uma nova versão validada do projeto principal. A compilação recusa divergência entre a versão declarada da base e o pacote.

## Atualização 0.1.2 — Artesão Digital

O nome visível passa a Artesão Digital e a entrada após login é Orçamentos. O rodapé fica fixo com as duas versões. Atualize apenas o aplicativo de testes existente: seu identificador, volume, conta Google, convites e rota permanecem os mesmos; não é outra instalação. O nome de apresentação no console do Google pode ser alterado separadamente, sem recriar credenciais, e não é modificado por esta atualização.

### Botão Abrir interface Web

Na página Info do aplicativo, o botão abre o login pelo mesmo hostname usado no navegador do Home Assistant e pela porta HTTPS8443, já atendida pelo Nginx desta instalação de teste. Não é aberta uma nova porta do piloto. Para o botão usar o domínio correto do certificado e do cliente Google, acesse o Home Assistant pelo endereço HTTPS habitual. Se estiver no HA por IP local, use diretamente o endereço público configurado no piloto; o botão padrão do HA usa o hostname da página atual. Esse atalho é específico do ambiente temporário de testes e não altera a futura implantação standalone.

## Atualização 0.1.3 — carregamento da interface

A versão anterior podia redirecionar requisições dos arquivos JavaScript para a tela de login; o navegador recusava HTML como módulo e mostrava apenas a barra da conta. Agora os arquivos compilados em dist/assets são servidos como recursos públicos com MIME correto. Esses arquivos não incluem credenciais nem dados dos usuários. HTML com contexto da conta, sessão, operações e APIs de dados continuam autenticados e isolados. Atualize somente o aplicativo existente, sem reinstalar ou recriar contas/convites.

## Carregamento no mesmo domínio do Home Assistant

A partir da 0.1.4, o adaptador registra um service worker restrito ao caminho configurado do piloto. Ele busca os recursos pela rede, sem cache local, para impedir que o worker da interface do Home Assistant forneça HTML antigo no lugar dos módulos JavaScript. A ativação remove apenas entradas de cache desse caminho; não remove o registro nem os demais recursos do Home Assistant. Não há funcionamento offline. Se o navegador não conseguir concluir a preparação, o login fica indisponível com uma mensagem explícita. Isso não substitui sessão, autorização por conta ou proteção de CSRF no servidor.

## Sessão expirada e saída (0.1.5)

Se a tela ficar aberta além do prazo da sessão, Sair continua levando ao login e remove os cookies restantes. As sessões continuam com os mesmos prazos; não são renovadas por esta correção. Se faltar conexão, a tela informa que não foi possível sair e permite tentar novamente. Não considera uma falha de rede como encerramento confirmado. Sessões válidas continuam protegidas por origem, CSRF e identificação da aba.

Ao atualizar uma instalação 0.1.3, confirme que o rodapé passou para Artesão Digital 0.1.5 (base 0.1.19). Feche a aba antiga, abra o login pelo domínio HTTPS habitual e confira o acesso e F5 comuns sem Ctrl+Shift+R. Não desinstale nem copie dados do aplicativo principal. A configuração Google/Nginx e os convites existentes são preservados.

## Antes dos primeiros participantes externos

Revise a escolha no Google: manter em Teste e adicionar os e-mails dos participantes, ou publicar a configuração OAuth conforme as exigências do Google. Não é necessário publicar o OAuth para este piloto se os e-mails já estiverem na lista de teste. Isso não dispensa o convite individual do aplicativo. A abertura dos novos campos não representa certificação de segurança; valide primeiro o isolamento com duas contas e mantenha dados fictícios enquanto a revisão de segurança e a proteção dos dados em repouso estiverem pendentes.

Os convites adicionados nos campos 3, 4 e 5 são registrados ao salvar as opções e reiniciar o aplicativo, com a mesma validade de 24 horas dos anteriores. Preencha perto do momento de usar: reiniciar não renova um convite já expirado, consumido ou revogado. Não recrie as contas existentes nem desinstale para atualizar.

## Atualização 0.1.7 — interesse no piloto e administração

A tela de login informa que o piloto exige convite. O formulário de interesse pede **nome e e-mail obrigatórios**; WhatsApp é opcional. O usuário deve concordar com a finalidade indicada. O envio apenas registra interesse: não cria conta, não emite convite e não envia mensagens automaticamente.

### E-mails administrativos

Na configuração do aplicativo, preencha `admin_emails` com os e-mails Google das pessoas autorizadas. A lista inicia vazia, sem conceder administração à primeira pessoa que entrar. Enquanto estiver vazia, a coleta de interesses fica indisponível. Na execução independente, `PILOT_ADMIN_EMAILS` aceita uma lista separada por vírgulas. E-mails inválidos impedem a inicialização para evitar uma configuração enganosa.

A entrada administrativa é `/artesaos-piloto/admin/login`, também acessível pelo link na tela de login de usuários. Ela usa o **mesmo cliente Google e o mesmo callback já configurado**. No Google em modo Teste, acrescente à lista de testadores os e-mails administrativos também. Não precisa de outro cliente OAuth, senha local ou mudança no Nginx.

O administrador autentica sua identidade no Google e o servidor compara o e-mail verificado com `admin_emails`. Um e-mail digitado, um link ou uma sessão comum de usuário não concedem administração. Essa autenticação usa uma sessão administrativa separada, com cookies restritos ao caminho administrativo, duração máxima de uma hora e expiração após quinze minutos de inatividade. Cada operação protegida revalida a sessão e a lista autorizada; retirar um e-mail das opções e reiniciar remove sua autorização. A conta administrativa não precisa consumir convite nem uma das cinco vagas de usuário. Para usar também a aplicação, a mesma pessoa precisa do acesso de usuário normal.

A tela inicial da administração consulta somente a lista de interessados, em páginas de 25 registros, com nome, e-mail, WhatsApp quando informado e data. A paginação só aparece quando necessária. Não inclui gestão completa de usuários, redefinição de senhas, envio de mensagens ou upload de logo.

### Proteção dos interessados e seus limites

O formulário valida os campos no servidor, exige origem correta e um token de formulário vinculado a cookie Secure/HttpOnly e de uso único, válido por quinze minutos. Tem limites de tentativas e campo anti-robô. O limite usa o endereço observado pelo servidor, sem confiar em cabeçalhos que visitantes possam forjar; atrás do Nginx, esse limite pode ser compartilhado entre visitantes. Retornos de registro não revelam se um contato já existia e não substituem dados anteriores. A capacidade é de até cinco mil registros ativos.

Os contatos novos ficam em `pilot-interest.sqlite`, com o conteúdo cifrado por AES-256-GCM e chaves de pesquisa derivadas por HMAC. O processo cria `pilot-interest.key`, de 32 bytes, com permissão restrita. A cifra autentica também a identificação e data do registro. A falta ou troca da chave após uso faz o sistema recusar esse armazenamento, sem descartar os contatos silenciosamente. Conserve **o banco e a chave** ao restaurar. Não publique, envie pelo chat ou versione nenhum desses arquivos.

**Limite importante:** a chave é mantida no volume do próprio aplicativo. Quem tiver acesso ao banco e à chave poderá decifrar os contatos. Isto não cifra todo o banco de usuários, os dados comerciais, as opções do Home Assistant nem o arquivo de backup completo. Backups devem continuar com acesso restrito e proteção própria. Esta implementação não constitui certificação, nem substitui revisão independente de segurança.

A lista ativa mantém contatos por noventa dias. A limpeza roda na inicialização, na consulta/registro e periodicamente; cópias antigas de backup não são apagadas por essa rotina. A política e exclusão de backups precisam ser administradas pelo responsável da instalação. Valide com dados fictícios e confira as permissões com contas distintas antes de coletar contatos reais.

### Logo incluída no pacote

As orientações de identidade visual recebidas em 30/10/2026 estão no [Guia rápido de uso da marca](branding/GUIA-DA-MARCA.md), também disponível em [PDF](branding/GUIA-DA-MARCA.pdf). O guia é uma versão de trabalho e registra variantes, cores, fontes, margens, tamanhos mínimos e comunicação. Sua incorporação documental não significa que todas as aplicações já estejam implementadas na interface.

Para novas aplicações, usar a logo principal no login e a horizontal no cabeçalho, preservando proporção e espaço livre. A versão colorida se destina a fundos claros; a negativa, ao Verde Mata; a branca, a fundos escuros; e a monocromática verde, a aplicações de uma cor. O símbolo isolado se destina a espaços pequenos, com o nome por perto. Preservar identificação acessível e alternativa textual.

Os doze PNGs originais fornecidos estão em `pilot/branding/`: `logo_principal.png`, `logo_horizontal.png`, `simbolo.png` e suas variantes `_branca`, `_mono_verde` e `_negativa`. O ZIP recebido também contém `proposta02_completo_transparente.png`, preservado na mesma pasta como referência histórica. Os arquivos foram incorporados sem alteração. A partir de 0.1.9, a interface usa as versões principal colorida e horizontal negativa conforme o contexto.

O build copia `pilot/branding/logo_principal.png` para `dist/pilot-logo.png` e `pilot/branding/logo_horizontal_negativa.png` para `dist/pilot-logo-horizontal.png`. O pacote exportado usa a pasta `branding/`. Aceita PNG de até 2 MB. O login e a conclusão de acesso usam a principal; as áreas autenticadas de usuário e administração usam a horizontal negativa sobre Verde Mata, com alternativa textual e identificação acessível. O arquivo histórico `logo.png` é apenas fallback para builds sem a principal. Não há upload administrativo.

O tema do adaptador do piloto aplica Georgia (alternativa Times New Roman) aos títulos, Arial (alternativa Helvetica) aos textos e controles, Linho ao fundo, Carvão Verde ao texto e Verde Mata aos elementos principais. Areia aparece em bordas e detalhes; Terracota no foco de teclado. Os estilos ficam restritos ao piloto, sem alterar o tema do aplicativo principal.

### Conferência manual após atualização

Atualize sem desinstalar, preserve os pares de e-mail/convite existentes e configure `admin_emails`. Reinicie; abra o login pelo domínio HTTPS. Teste o interesse sem WhatsApp, rejeição sem e-mail, login administrativo da conta autorizada, rejeição de uma conta comum e saída. Verifique nome/contato na administração e ausência de paginação com poucos registros. O mesmo Google/callback/Nginx existente é preservado; não use dados pessoais reais na primeira conferência.

## Atualização 0.1.8 — base 0.1.19 para 0.1.23

Código-base incorporado: versão 0.1.23, commit `f56f0e5707ad81f74f42c351171d4132f793cf9a`. A versão própria é 0.1.8; instalação e conferência no Home Assistant continuam manuais. O rodapé e o arquivo de build identificam essa base efetivamente incorporada. A base inclui as melhorias das listas e filtros, seleção para catálogo, validação dos formulários, cadastro de materiais, unidades de compra/consumo e fluxo de fabricação atualizado.

A atualização mantém as adaptações do Artesão Digital: autenticação Google, convites, contas isoladas, administração restrita, lista de interesse cifrada, logo, marca e metadados de duas versões. Cada banco de produtos continua no diretório do seu usuário; não há banco comercial compartilhado. A migração de materiais da base roda dentro desse banco individual, ao acessá-lo, sem ler arquivos da instalação principal.

Antes de instalar a futura atualização, faça uma cópia completa e protegida do volume de dados com o aplicativo parado. Preserve bancos de cada usuário, controle de acesso, lista de interesse e sua chave. Não confunda a cópia interna de produtos antigos com um backup completo da instalação. A cópia anterior deve ser mantida intacta: para voltar à versão antiga, restaure esse backup, em vez de abrir bancos já alterados com um código antigo.

A base cria tabelas de materiais e de acompanhamento/cópia de registros antigos. Registros de fabricação antigos aguardam uma referência de compra válida do primeiro material cadastrado, em gramas ou quilos. Não é inventada uma conversão para outro tipo de unidade. A conversão preserva os preços finais salvos, inclui etapas adicionais e produtos arquivados, e guarda os dados anteriores em tabela própria. O preço da referência escolhido determina o novo cálculo; por isso, confira-o antes de cadastrar o primeiro material. Produtos novos não são capturados retroativamente por esse lote de migração. Não aplicar preços calculados automaticamente.

As novas faixas de multiplicadores podem deixar parâmetros antigos fora do intervalo aceito: revise-os explicitamente, sem substituir valores silenciosamente. A nova seleção de catálogo começa desmarcada para produtos antigos e não altera a autorização de divulgação nem publica produtos na internet.

O ensaio reproduzível de atualização é `node --import tsx scripts/verify-pilot-upgrade.mjs`, executado na fonte com histórico Git e dependências disponíveis. Ele arquiva o código anterior real do piloto, cria dados fictícios de duas contas e verifica preservação de dados, cálculos, referências inválidas, isolamento, reinício, contatos/administração e restauração do backup na versão anterior. Não usa nem migra dados reais.


## Atualização 0.1.10 — entrada e navegação

A página de entrada apresenta primeiro as condições do piloto gratuito por convite e o formulário de interesse. O link “já tenho um convite/login” leva à seção de acesso abaixo, com título e borda próprios. Registrar interesse continua sem ativar uma conta.

Nas áreas de usuário, logo, navegação e saída compartilham a faixa fixa. O menu mantém uma linha com rolagem horizontal quando necessário. Em telas de até 700 px, o e-mail fica oculto para reservar espaço à navegação; o botão Sair permanece disponível. O conteúdo acompanha a altura real do cabeçalho.

Validação: compilação, 41 testes e navegador com provedor controlado, incluindo ordem dos formulários, âncora de login, menu fixo sem quebra de linha, navegação e largura de 320 px. Google e Home Assistant reais ainda precisam de conferência na instalação. Não há nova migração de banco. Antes de instalar, pare o aplicativo e faça backup completo e protegido; para reverter, restaure a cópia anterior completa.


## Atualização 0.1.12 — navegação, configurações e empresa

Produtos passa a ser a entrada do piloto, no primeiro login, no novo login e na raiz. O menu tem Produtos, Clientes, Orçamentos e Configurações, com ícones, em uma faixa abaixo do cabeçalho verde. No celular, o botão Menu abre os itens; Fechar menu ou Escape recolhe a lista. A altura do conteúdo acompanha a faixa fixa. A tela antiga de Fabricação não é mais exibida no piloto: o endereço antigo abre Produtos, cujo formulário contém os dados de fabricação, custos e aplicação explícita de preços. O aplicativo principal mantém sua navegação original.

Configurações tem uma área geral fora das abas e as abas Produtos, Clientes e Orçamentos. A área geral inclui os dados da empresa e um grupo expansível de custos, precificação e planejamento. Os valores existentes continuam no armazenamento original, sem renomear chaves ou perder dados. Materiais e categorias ficam na aba Produtos. As abas mantêm seus formulários montados ao alternar, preservando edições ainda não salvas. Os botões salvam cada grupo separadamente; salvar dados da empresa não altera os parâmetros de cálculo, nem o contrário.

**Dados da empresa:** nome da empresa, nome da pessoa responsável, telefone e e-mail para contato. Os campos são opcionais, com limites e validação no servidor. O cadastro fica no banco individual da conta, protegido pela sessão, contexto e CSRF do piloto. Alterações concorrentes são recusadas; reabra a página antes de tentar novamente. Não há envio de mensagens nem divulgação automática. A inclusão dessas informações no documento final foi promovida explicitamente para o pacote experimental 0.1.15; a listagem continua sem repetir esses dados.

**Migração e restauração:** cria-se a tabela adicional `company_profile` apenas nos bancos das contas do piloto, ao abri-los. Os dados comerciais, convites e parâmetros anteriores são preservados. Antes de atualizar, pare o aplicativo e faça backup completo e protegido do volume e configurações. Para reverter, restaure a cópia anterior completa; não execute apenas código antigo sobre o volume atualizado.

**Validação:** compilação, 41 testes automatizados e Chromium com provedor controlado, incluindo login para Produtos, menu móvel e desktop, abas por teclado, preservação de rascunhos, persistência dos dados da empresa e isolamento entre contas. Esses testes não substituem a validação real do Google, Home Assistant/Supervisor e hardware ARM.


## Atualização 0.1.13 — preparação inicial e cálculo

A tela de boas-vindas é obrigatória até sua conclusão, inclusive para contas existentes ainda sem esse registro. Dados já salvos são aproveitados. É possível sair e retomar; apenas alterações efetivamente salvas são preservadas. O servidor bloqueia APIs comerciais enquanto a etapa estiver pendente, e o acesso às telas também passa pela verificação inicial. Concluir em uma conta não conclui em outra.

Para concluir: informar nome da empresa, responsável, telefone válido e e-mail; cadastrar ao menos um material válido; informar pelo menos uma tarifa positiva de hora humana, energia ou desgaste de máquina; informar horas produtivas mensais maiores que zero; informar pelo menos uma despesa operacional positiva; manter os parâmetros numéricos válidos. Materiais de custo direto recebem o valor utilizado em cada produto. Tarifas horárias vazias são gravadas como zero; despesas operacionais vazias representam zero. A conclusão é registrada separadamente e não apaga dados.

As horas produtivas mensais são necessárias para calcular a taxa operacional. Em cada etapa de um produto, o rateio usa o tempo de máquina quando ele é positivo; quando é zero, usa o tempo humano. Não soma os dois tempos para o rateio. Os custos de energia/desgaste continuam associados somente à máquina, e o custo de trabalho humano permanece separado. Ao cadastrar um produto, informe seus tempos, usando zero para o tempo não utilizado, e os materiais consumidos. A preparação inicial não inventa quantidades ou tempos de produção. Alterações de cálculo não aplicam novos preços comerciais automaticamente.

Os multiplicadores mínimos são atacado 1,5; loja de fábrica 2,0; varejo 3,0. A correção de campos ausentes, vazios, não numéricos ou inferiores aos mínimos ocorre no banco individual ao inicializar ou consultar as configurações, e nos novos salvamentos. Os outros campos são preservados e a revisão é incrementada. Multiplicadores acima do máximo ou com precisão não permitida pedem correção explícita. A área de custos fica sempre visível, sem grupo recolhido.

Produtos de cliente não exibem controle de catálogo e sua marcação é desfeita ao selecionar essa origem. Registros antigos são corrigidos no banco da conta, incluindo arquivados; edição, importação e ações em lote seguem a mesma restrição. A privacidade e os demais dados do produto são preservados.

**Migração:** cria a tabela `pilot_onboarding`, normaliza os mínimos e tarifas vazias e desmarca produtos de clientes nos bancos individuais do piloto, ao abri-los. Não incorpora nova base e não altera a instalação principal. Faça backup completo e protegido com o aplicativo parado. Para reverter, restaure o volume anterior completo.

**Validação:** compilação, 43 testes automatizados e Chromium com provedor controlado, incluindo cadastro inicial incompleto após novo login, preservação e conclusão, bloqueio por API, isolamento, normalização persistente, catálogo de clientes e rateio manual sem dupla cobrança. A instalação real, Google e hardware final continuam pendentes de validação pelo responsável.


## Atualização 0.1.14 — suporte técnico

Após entrar, o rodapé fixo oferece **Suporte técnico**, que abre o formulário de chamado. É possível escolher **Dúvida de uso** ou **Relatar erro**, informar assunto (até 160 caracteres) e descrição (até 6.000 caracteres). O acesso também funciona durante a preparação inicial, sem liberar as demais operações comerciais. Não inclua senhas ou credenciais no texto. Os envios são vinculados à conta autenticada pelo servidor; o formulário não escolhe outra conta como remetente.

A aba **Meus chamados** das configurações mostra apenas os chamados da conta, com filtros por tipo/status e paginação de 20 itens. A área de suporte acessível pelo rodapé oferece o mesmo histórico e permite continuar as conversas. Respostas e alterações de status são mostradas com data e autoria de cliente/equipe. Os dados ficam no sistema; não há envio automático de e-mail ou WhatsApp, anexos, captura de tela ou cópia automática dos dados comerciais.

Na administração, **Chamados de suporte** abre a **Central de suporte** com todos os chamados, identificação da conta remetente, filtros, histórico, campo de resposta e escolha do status após a atualização. Os status são Em aberto, Em análise, Respondido, Aguardando resposta do cliente e Finalizado. Ao enviar nova mensagem, o usuário devolve o chamado a Em aberto; em um chamado finalizado, o botão informa explicitamente que a mensagem irá reabri-lo. Alterações concorrentes são recusadas sem apagar o texto digitado; atualize a conversa e revise antes de reenviar.

Cada acesso revalida sessão, contexto da aba e autorização administrativa; alterações também exigem CSRF e origem válida. Usuários não consultam nem respondem chamados de outras contas. Identificadores de envio evitam duplicar chamados e mensagens ao repetir a mesma solicitação após falha de rede. Há limites de tamanho e frequência de envio, 100 chamados simultaneamente em andamento por conta e 500 registros de histórico por chamado. Ao atingir o limite de histórico, abra outro chamado e informe o número anterior.

**Armazenamento e atualização:** cria `pilot-support.sqlite` no volume do piloto, separado dos bancos comerciais individuais, com permissão de arquivo restrita. O arquivo central permite a consulta administrativa de todas as contas; as APIs aplicam o isolamento dos usuários. O conteúdo dos chamados é persistido nesse banco; não se trata da base cifrada de interessados. Inclua o volume inteiro no backup protegido, com o aplicativo parado, antes de instalar; para reverter, restaure a cópia anterior completa. Não há alteração na instalação principal nem nova base incorporada.

**Validações:** compilação, 45 testes automatizados e navegador com provedor controlado. A cobertura inclui abertura durante as boas-vindas, rodapé e aba, isolamento entre contas, permissões/CSRF/contexto, conversa cliente/admin, filtros/paginação, concorrência, reenvio sem duplicação, persistência após reinício e status de finalização/reabertura. Google real, Home Assistant/Supervisor e hardware final continuam dependendo da conferência na instalação.


## Atualização 0.1.15 — PDF, logo e preparação jurídica (experimental)

Em Configurações gerais, a logo da empresa é opcional e separada da marca Artesão Digital. Selecione PNG/JPEG/WebP até 5 MB, confira a prévia otimizada e salve. O servidor valida e regrava PNG de até 1024 pixels por dimensão e 500 KB. Há uma imagem ativa por conta, revisão contra sobrescrita, substituição e remoção. Não existe histórico de logos no aplicativo; cópias antigas de bancos/backups podem conter imagens anteriores. Não há backup da instalação pessoal configurado atualmente.

Ao finalizar um orçamento, empresa textual, cliente, itens, valores e observações daquela edição são capturados na mesma transação da gravação. Reabrir e finalizar cria outra edição. Marcar Enviado não cria uma nova edição nem envia mensagem. Orçamentos finalizados antes desta entrega não recebem identificação histórica inventada: reabra como rascunho e finalize novamente para registrar dados atuais.

No editor, Documento final permite escolher uma edição, preparar, visualizar e baixar PDF. Compartilhar PDF aparece quando o navegador informa suporte a arquivos; se falhar, use Baixar PDF. Abrir/encerrar o compartilhamento não confirma entrega. O usuário deve confirmar Enviado separadamente. Use observações comerciais para pagamento, validade e prazo manuais.

Guarde a cópia efetivamente entregue: PDFs são gerados em memória, sem arquivo permanente ou temporário no servidor. Nova geração preserva dados/valores daquela edição, mas usa a logo atual e pode mudar a aparência. PDF A4 com texto selecionável e fontes Noto Sans sob OFL, até 40 páginas e duas gerações simultâneas por processo. Caracteres sem glifo disponível recebem “?”; confira o arquivo antes de entregar.

**Migração e recuperação:** acrescenta company_logo e quote_documents aos bancos individuais, além de pilot-legal.sqlite no volume central. Preserva autenticação, convites, dados e base 0.1.23. Antes de atualizar, pare o aplicativo e produza uma cópia completa e protegida do volume/configurações. Atualmente não existe rotina de backup configurada: esta orientação não afirma que uma cópia já exista. Para reverter, pare o aplicativo e restaure a cópia anterior completa com o código correspondente; não execute apenas código antigo sobre banco atualizado. Teste local com dados fictícios não prova recuperação da instalação real.

**Jurídico:** /legal tem contato público sem login e informa preparação. Aceite e textos definitivos ficam desativados por padrão. Minutas reconstruídas estão em legal-drafts, com dados do responsável e pendências; não foram juridicamente aprovadas. Ativação futura por legal-config.json local e reinício; ver legal-drafts/05-plano-de-implementacao.md. Após Google/convite, o aceite precede boas-vindas e APIs comerciais/suporte. Administração continua separada.

Este pacote não conclui o primeiro release piloto. Google/HA, celular físico, servidor efetivo, backup e recuperação, exportação completa/saída, retenção/incidentes/fornecedores e revisão jurídica permanecem pendentes. Evidências locais em VALIDACAO-0.1.15.md.


## Atualização 0.1.16 — administração e convites

A administração mantém Interessados no piloto e Chamados de suporte e acrescenta Usuários cadastrados e Convites. A primeira mostra contas ativadas, e-mail Google e acesso autorizado/revogado (não presença online). Exibir dados consulta a identificação da empresa e, para novos convites, os contatos de origem. Dados ainda não preenchidos são informados como ausentes.

Em Convites, informe nome, e-mail e/ou WhatsApp e escolha o canal. Salvar registra o convite e gera automaticamente o código, válido por 24 horas. A mensagem pronta inclui o código. Sem SMTP, use Abrir no meu e-mail ou Copiar mensagem; no WhatsApp, use Abrir no WhatsApp para revisar e enviar. Não há status nem confirmação de envio no produto. Com SMTP configurado, Salvar no canal e-mail tenta o envio automático; nenhum provedor vem configurado. Consulte CONVITES.md para campos, TLS, credenciais e limites.

**Regra nova, aprovada pelo responsável:** o contato não precisa ser e-mail Google. O primeiro uso válido vincula o código a uma única conta Google verificada, que passa a ser usada nos próximos logins. Convites emitidos pelas opções/CLI anteriormente conservam a restrição original por e-mail. Não convertemos seus códigos nem inventamos nomes/datas ausentes. Convites aceitos saem da lista padrão e a conta aparece em Usuários cadastrados; a página visível atualiza a lista em até 15 segundos quando não houver formulário em edição, além de atualização manual.

**Atualização/recuperação:** novos campos no controle de convites, tabelas de metadados/controle técnico e arquivo pilot-invitations.key. Inclua banco e chave no backup completo e protegido, com aplicativo parado. Ainda não existe rotina real de backup configurada: antes de atualizar, produza e valide a cópia da instalação. Para reverter, restaure volume/configurações anteriores completos e o código correspondente. A perda da chave impede recuperar códigos cifrados; o servidor não a substitui silenciosamente sobre dados existentes.

O limite de cinco contas é preservado; convites válidos reservam vagas. Código completo é visível somente ao administrador ao abrir o convite, não na listagem nem nos dados de usuário. Nome, telefone e código ficam cifrados; o e-mail permanece no controle existente. Uma chave no mesmo volume não protege contra comprometimento de ambos. Retenção e descarte ainda precisam de definição jurídica/operacional.

O principal pode permanecer parado sem afetar o piloto. Mantenha o Nginx, que encaminha o acesso. O responsável confirmou recuperação do login após reiniciar o proxy quando o IP do piloto mudou; veja MANUTENCAO.md. Esta atualização não altera automaticamente sua rede, proxy, Google ou configurações pessoais.

Validações e limites em VALIDACAO-0.1.16.md. SMTP real, Google real, telefone físico e Home Assistant/hardware final ainda precisam de conferência. Textos jurídicos definitivos permanecem desativados; a versão continua experimental.


## Atualização 0.1.17 — convites centralizados, sem vencimento

Não preencha mais convites nas opções do aplicativo. Administre-os em Convites na interface Web, com nome, e-mail/WhatsApp, canal e Salvar. Não há teto fixo de cinco cadastros; o servidor mantém limites temporários de frequência, mensagens e recursos para proteger a instalação.

Novos convites não possuem vencimento. Os ativos na atualização também passam a não vencer. Códigos expirados ou revogados anteriormente continuam inativos. A posse de um código ativo permite à primeira conta Google verificada usá-lo; códigos sem vencimento exigem cuidado com encaminhamento e devem ser revogados quando não forem mais desejados. Uso único, geração aleatória forte e armazenamento cifrado permanecem.

Em Exibir convite, Revogar impede seu uso. Ativar novamente abre o formulário para conferir contato/nome; Salvar gera novo código e nova mensagem. O anterior continua inválido, inclusive após reinício. Para legados sem nome, informe-o agora; não inventamos identificação histórica. A mensagem nova precisa ser enviada (WhatsApp manual ou e-mail conforme configuração). Não há estado de envio na lista. Ações em convite aceito não revogam uma conta já ativada.

Busca por e-mail/telefone e filtros de situação ajudam a localizar convites. Usuários cadastrados tem busca por e-mail e paginação. Bancos de contas são abertos sob demanda; até oito instâncias simultâneas permanecem no cache e as ociosas são fechadas/reabertas preservando dados. Se todas estiverem ocupadas, uma nova conta em uso pode receber uma resposta temporária para tentar novamente. Isso não limita o total de usuários registrados nem garante capacidade ilimitada do hardware.

Migração acrescenta indicador de ausência de vencimento, vínculos de substituição e índices HMAC de telefone derivados da chave existente. Preserva bancos, sessões, empresa, convites, chave e código dos convites ativos. Antes de atualizar, produza cópia completa e protegida do volume/opções com o aplicativo parado, incluindo as chaves. Para reverter, restaure a cópia anterior completa e seu código correspondente. O responsável informou que ainda não tem uma rotina real de backup configurada.

O esquema público atual do Supervisor ignora/remove opções desconhecidas ao validar. O aplicativo também ignora os campos antigos, sem alterar URL, credenciais Google, administradores ou SMTP. A instalação real ainda precisa de conferência após atualizar; eventuais avisos de opções antigas não devem motivar reinstalação/apagamento de dados.

Validações e limites em VALIDACAO-0.1.17.md. Não é release estável; Google/HA/ARM/celular físico, SMTP real, backup e revisão jurídica/operacional continuam pendentes.
