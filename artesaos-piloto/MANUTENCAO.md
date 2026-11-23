# Manutenção do Artesão Digital e do aplicativo principal

## Independência dos aplicativos

O Artesão Digital incorpora o código-base do Fabricação e Orçamentos. Essa incorporação é feita no desenvolvimento; não é uma chamada ao aplicativo principal em execução. Cada instalação tem seu próprio aplicativo, processo e volume de dados.

Por isso, o Fabricação e Orçamentos pode ser parado e, futuramente, desinstalado sem ser uma dependência de execução do Artesão Digital. Não copie bancos ou opções entre os dois aplicativos.

O acesso atual ao Artesão Digital continua dependendo do seu próprio aplicativo em execução, da configuração Google e da rota HTTPS no NGINX Home Assistant SSL proxy. Parar o principal não é parar o Nginx.

## Parar o Fabricação e Orçamentos

1. Abra no Home Assistant a página do aplicativo **Fabricação e Orçamentos** e confira o nome. Não selecione Artesão Digital nem NGINX Home Assistant SSL proxy.
2. Clique em **Parar**. Se desejar mantê-lo parado após reiniciar o Home Assistant, desative a inicialização automática desse aplicativo.
3. Mantenha **Artesão Digital — Testes** e **NGINX Home Assistant SSL proxy** em execução.
4. Abra o endereço HTTPS habitual terminado em `/artesaos-piloto/login`; entre com uma conta já cadastrada e confira Produtos e os dados esperados.
5. Para voltar a usar o principal, inicie somente o aplicativo Fabricação e Orçamentos e acesse sua interface pelo Home Assistant/Ingress.

Parar o processo não desinstala o aplicativo nem deve remover seu volume de dados.

## Desinstalar o principal futuramente

Faça esta etapa somente quando decidir que não precisa mais dele.

1. Confira se existem dados do Fabricação e Orçamentos que deseja conservar. A desinstalação pode remover o armazenamento do aplicativo.
2. Com o principal parado, produza e valide uma cópia completa e protegida dos seus dados e configurações, guardada fora do volume que será removido. Uma exportação parcial de produtos não substitui uma cópia completa.
3. Não presuma que já exista backup: o responsável informou que ainda não há uma rotina de backup configurada. Esta orientação não cria nem testa uma cópia na instalação real.
4. Desinstale somente **Fabricação e Orçamentos**. Preserve a instalação e o volume do Artesão Digital e a configuração do proxy.
5. Confira novamente o acesso ao Artesão Digital. Desinstalar o principal não exige remover o repositório compartilhado da loja, usado também para atualizar o piloto.

## Acesso após atualização ou mudança de IP interno

Foi observado o erro `{"error":"Acesso permitido somente pelo Ingress."}` ao abrir o piloto. Essa mensagem pertence à proteção do principal. Os logs do piloto mostraram mudança do endereço interno; o usuário confirmou que reiniciar **somente o NGINX Home Assistant SSL proxy** restabeleceu o acesso.

O resultado é compatível com resolução antiga do hostname no proxy. Se o mesmo sintoma reaparecer após atualizar ou reiniciar o piloto:

1. Confirme que o Artesão Digital está em execução e que está abrindo o endereço habitual do piloto.
2. Reinicie somente o NGINX Home Assistant SSL proxy e teste novamente. As rotas HTTPS atendidas pelo proxy podem ficar brevemente indisponíveis durante esse reinício.
3. Se persistir, confira o hostname real do piloto e o bloco `location /artesaos-piloto/` antes de mudar a configuração. Registre a mensagem de erro e os logs sem senhas, códigos ou tokens.

Não remova a proteção de Ingress do principal para contornar esse problema. Não reinstale aplicativos nem apague bancos como primeiro recurso. Uma eventual resolução dinâmica de DNS precisa usar o resolvedor real da instalação; não há endereço DNS universal aprovado nesta sessão.

## Estado desta orientação

Procedimento documentado a pedido do responsável. Não foram parados, desinstalados ou reconfigurados aplicativos remotamente nesta sessão. A recuperação do acesso por reinício do proxy foi executada e confirmada pelo usuário. O primeiro release estável e a configuração/teste de backup continuam pendentes.
