# Operação da Central 0.1.18 — mesma porta pública, hostname exclusivo

Destino proposto: **https://instagram.romeropi.duckdns.org:8443/panel**.

Não abrir portas no roteador nem expor 8099/9443. A 0.1.18 remove a porta/montagem SSL/listener da 0.1.17; o HTTPS pertence ao NGINX existente. Login, senha, slug, banco e mídias continuam os mesmos. Esta mudança prepara teste, não ativa Meta nem declara homologação.

## 1. Preparação e recuperação

- Mantenha acesso local já funcional ao HA, independente do proxy externo. Não faça a primeira mudança de certificado/proxy dependendo somente do acesso externo.
- Guarde privadamente as opções atuais da Central, DuckDNS e NGINX. Não envie opções completas: podem conter tokens/senhas. Preserve bancos e `/data`; não desinstale a Central.
- No Terminal & SSH do HA, crie uma cópia local protegida dos certificados atuais (não enviar/versionar):
  ```sh
  umask 077
  IG_ROLLBACK="/ssl/ig-proxy-rollback-$(date +%Y%m%d-%H%M%S)"
  mkdir "$IG_ROLLBACK"
  cp -p /ssl/fullchain.pem /ssl/privkey.pem "$IG_ROLLBACK/"
  chmod 700 "$IG_ROLLBACK"
  chmod 600 "$IG_ROLLBACK/privkey.pem"
  ```
  Anote o caminho local. Se algum comando falhar, resolva a cópia antes de alterar o certificado. Não presuma que backup de aplicativo inclua `/ssl`.
- Confirme no NGINX as opções já documentadas: `customize.active: true`, `customize.servers: nginx_proxy/*.conf`, `real_ip_from: []`, TLS em 443 interno com encaminhamento público atual 8443. Se divergirem, não substitua opções nem adapte diretivas por tentativa.

Se a 0.1.17 já estiver instalada, atualize primeiro para **0.1.18** preservando opções/dados: isso elimina o listener 9443 e mantém Ingress. Se criou encaminhamento 9443 exclusivamente para esta tentativa, desabilite somente essa regra. Depois prepare certificado e proxy; não use a URL antiga 9443 durante a transição.

## 2. Certificado — requisito antes do novo host

O proprietário confirmou que o certificado atual tem somente `DNS:romeropi.duckdns.org`; ele **não** cobre o hostname da Central.

Na configuração do aplicativo **Duck DNS**, acrescente à lista `domains` existente esta entrada, mantendo todas as entradas atuais, token, aliases, algoritmo, arquivos e demais opções:

```yaml
- "*.romeropi.duckdns.org > romeropi.duckdns.org"
```

A documentação oficial do DuckDNS suporta essa sintaxe wildcard. Mantenha `romeropi.duckdns.org` também na lista; não troque a lista inteira pelo wildcard. O certificado renovado deve continuar cobrindo o HA e cobrir o novo host. Salve e execute a emissão pelo fluxo do aplicativo DuckDNS já usado no HA. O proxy pode recarregar certificados automaticamente conforme sua versão; por isso backup e acesso local vêm primeiro.

**Antes de instalar o novo servidor NGINX**, confirme somente os nomes públicos:

```sh
openssl x509 -in /ssl/fullchain.pem -noout -ext subjectAltName
openssl x509 -in /ssl/fullchain.pem -noout -checkhost romeropi.duckdns.org
openssl x509 -in /ssl/fullchain.pem -noout -checkhost instagram.romeropi.duckdns.org
```

Os dois `-checkhost` precisam indicar correspondência; a lista deve conter o domínio atual e `*.romeropi.duckdns.org` (ou o host exato). Se não houver emissão/cobertura, pare nesta etapa: não apague chaves, não ignore certificado e não ative o novo host. Não altere o domínio principal do NGINX.

## 3. Atualizar a Central e instalar o arquivo adicional

1. Atualize o catálogo e a Central para **0.1.18** no Supervisor, preservando opções e dados. Os testes do Dockerfile serão executados no build do dispositivo. Confirme a versão no log; a aplicação agora atende somente HTTP interno 8099.
2. Ajuste somente estes campos da Central, preservando todas as demais opções/flags:
   ```yaml
   public_base_url: "https://instagram.romeropi.duckdns.org:8443"
   meta_oauth_redirect_uri: "https://instagram.romeropi.duckdns.org:8443/oauth/meta/callback"
   ```
   `certfile`/`keyfile` antigos permanecem aceitos no schema para compatibilidade, mas são ignorados pela Central. Quem lê o certificado é o NGINX. Não altere flags Meta/webhook/rascunhos.
3. O arquivo pronto é [instagram.conf](instagram.conf). Revise-o antes de copiar. Com SAN confirmado, crie `/share/nginx_proxy/` se ainda não existir e adicione **somente** `/share/nginx_proxy/instagram.conf`. Use Studio Code Server/Terminal ou método já disponível. Não sobrescreva um arquivo existente com esse nome sem comparar/guardar a versão anterior.
4. Esse arquivo entra por **customize.servers**, no contexto `http`. **Não** coloque em `nginx_proxy_default*.conf` nem em `customize.default`: ali o contexto é outro. Preserve integralmente os fragmentos Avisaqui/Artesão Digital/Instagram antigo e as opções gerais do NGINX. A porta interna 443 já existente é compartilhada por hostname; não há nova regra de roteador.
5. Se houver acesso confirmado ao `nginx -t` dentro do aplicativo, valide no contexto completo antes de recarregar. O Terminal & SSH observado não possui Docker; não use comandos `docker`/`ha apps exec` presumidos nesse terminal. A candidata passou em `nginx -t` e testes HTTP reais locais, mas isso não comprova os includes/certificado do seu ambiente.
6. Com backup, acesso local e arquivo revisado, reinicie **somente o NGINX SSL proxy** pela interface do HA. Confira o log e que o proxy permaneceu em execução. Há uma breve interrupção do HTTPS compartilhado; não reinicie o HA ou outros aplicativos. Em caso de erro, execute o rollback abaixo pelo acesso local.
7. Confira que o acesso HTTPS antigo ao HA, Avisaqui e Artesão Digital continua funcionando. Abra a Central na URL nova. A sessão pode exigir login novamente porque o cookie é vinculado ao novo hostname; a senha/conta/dados são os mesmos.

## 4. Aceite mínimo sem Meta

- HTTPS novo com certificado válido, sem avisos e sem bypass de service worker.
- Mesmo login `admin`/senha; Mensagens e Editorial presentes. **Testar navegador e proxy (sem Meta)** deve retornar teste aprovado e versão 0.1.18 no mesmo hostname `instagram.romeropi.duckdns.org:8443`.
- `/health`, `/bridge/pending` e `/sw-modern.js` no novo host devem retornar 404; o proxy publica uma lista explícita de rotas. A health interna continua existindo para diagnóstico local.
- O login tem limite no NGINX por IP (429), além dos controles existentes da aplicação. Não teste força bruta no HA para comprovar isso; o caso já passou localmente.
- O webhook existente em `romeropi.duckdns.org:8443` não mudou. Não iniciar consentimento real agora. Antes de uma tentativa futura autorizada, cadastrar/revisar o novo callback exato no mesmo app Meta.
- Se houve encaminhamento 9443 criado exclusivamente para a 0.1.17, desabilite apenas essa regra. Atualizar o pacote não remove regras do roteador por conta própria.

Retorne somente: versão, correspondência dos dois nomes no certificado, proxy iniciado, acesso antigo preservado e resultado do probe. Não envie cookie, URL de retorno, state, código, senha ou token.

## Rollback

1. Pelo acesso local ao HA, mova **somente** `/share/nginx_proxy/instagram.conf` para um nome fora do padrão `*.conf`, por exemplo `instagram.conf.disabled`. Se havia versão anterior, restaure essa versão em vez de removê-la.
2. Se o certificado novo prejudicar o domínio antigo, restaure privadamente `fullchain.pem` e `privkey.pem` da cópia protegida e as opções anteriores do DuckDNS. Evite deixar a renovação sobrescrever novamente o certificado enquanto corrige a configuração.
3. Reinicie somente o NGINX e confirme o HA externo. Restaure as duas URLs anteriores da Central se necessário; o Ingress permanece disponível. Não volte a abrir 9443 como fallback.
4. Preserve dados e logs seguros para diagnóstico. A instalação no HA, certificado novo, includes reais e aceite externo só podem ser marcados como concluídos após evidência do operador.
