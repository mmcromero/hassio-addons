> **Registro histórico da distribuição anterior.** Não é autorização de publicação, instalação, proxy ou dispensa de backup nesta RC. Consulte docs/rc/RELEASE.md.

# AVISAQUI-HTTPS-001 — publicação controlada da candidata 0.1.13

**Situação:** preparação em PR #28; este documento não é uma ordem de execução.
**Ambiente:** laboratório Home Assistant Raspberry Pi 4.
**Restrições:** preservar o acesso local :8090, o slug `pager_virtual`, o banco `/data`, as rotas do Home Assistant e `/artesaos-piloto/`. Nenhuma nova porta no roteador. Sem requisito de novo backup, conforme decisão do proprietário para o laboratório.

## Arquitetura

- Público: `https://romeirop.duckdns.org:8443/avisaqui/`
- NGINX: Home Assistant SSL Proxy, configuração personalizada `customize.active=true`
- Destino interno proposto: `http://45c28620-pager-virtual:8095/`
- Local: `http://192.168.0.6:8090/` (porta publicada pela configuração local)
- `proxy_pass` com barra final remove o prefixo externo `/avisaqui/` antes de encaminhar ao Fastify.
- Exemplo de configuração: `docs/AVISAQUI-HTTPS-001-nginx.conf.example`. Nunca editar o arquivo `nginx_proxy_default_artesaos.conf`.

## Ordem da ativação (depende de autorização específica)

1. Confirmar CI do último commit: testes Node, sintaxe, imagem ARM64 e smoke com volume persistente.
2. Revisar diferenças do PR #28 e autorizar explicitamente merge.
3. Publicar a candidata 0.1.13 no repositório de add-ons e atualizar **somente** o Pager Virtual no Home Assistant, mediante nova autorização.
4. Confirmar que `http://192.168.0.6:8090/` continua acessível e que login/KDS continuam funcionais.
5. Definir em **Pager Virtual → Configuração**: `public_url: https://romeirop.duckdns.org:8443/avisaqui/`; reiniciar **somente** o Pager Virtual, se necessário. O HTTPS ainda não está ativado nessa etapa.
6. Criar arquivo **novo e separado** em `/share/nginx_proxy_default_avisaqui.conf` a partir do exemplo. Não sobrescrever outros arquivos.
7. Validar a sintaxe da configuração e ativar/recarregar apenas o NGINX SSL Proxy, conforme a interface do Home Assistant. Confirmar primeiro acesso Home Assistant e Artesão Digital.
8. Abrir o endereço público `/avisaqui/` e testar login, logout, navegação, KDS, QR Code, SSE e Web Push em dispositivo externo.
9. Configurar o agente Windows com a URL HTTPS contendo o prefixo (usar a **versão atualizada do agente** da branch de origem, não o ZIP antigo), sem publicar a credencial.
10. Enviar uma comanda **sintética** para a fila virtual. Confirmar recebimento no KDS e ausência de duplicação; a impressão física permanece independente.

## Portões de aceite

- HTTP local continua funcionando sem HTTPS.
- HTTPS público usa login autenticado, cookie Secure quando cabível e controle por restaurante.
- Mestre não pode ser cadastrado remotamente.
- KDS e cliente SSE mantêm sessão e comunicação.
- PWA e Web Push abrem a página do cliente dentro de `/avisaqui/`.
- Agente Windows envia evento no endpoint `/avisaqui/api/integracoes/impressao/pedidos`.
- Home Assistant e Artesão Digital continuam acessíveis nas rotas atuais.
- Não há redirecionamento de `/avisaqui/` para páginas da raiz do Home Assistant.

## Reversão rápida no laboratório

- Se a **rota externa** falhar: desativar/remover somente o arquivo novo `nginx_proxy_default_avisaqui.conf` e recarregar o NGINX; manter os arquivos existentes.
- Se a **aplicação** falhar: permanecer no acesso local para diagnóstico; a reversão de versão depende de um pacote anterior disponível e da compatibilidade do banco.
- Se **NGINX** não iniciar após alteração: retirar a configuração nova pelo editor do Home Assistant e reiniciar o proxy. Não editar o arquivo do Artesão Digital.
- Como não foi solicitado backup novo, **não há garantia de recuperação de dados em caso de corrupção**; o plano visa reverter configuração e pacote, não recuperar dados perdidos.

## Evidências pendentes

- CI do commit final do PR #28.
- Resolução do nome interno do contêiner a partir do NGINX.
- Certificado HTTPS válido no acesso por :8443.
- Testes reais de login e SSE.
- Web Push em Android/iOS conforme suporte do dispositivo.
- Agente Windows atualizado e seu OCR em teste de ponta a ponta.

**Nada deste documento foi executado no Home Assistant.**
