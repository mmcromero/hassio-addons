# Domínio público único — dev.18 para homologação

Decisão do proprietário: a única origem oficial de acesso à aplicação no Forja 01 é
`https://artesaodigital.com.br/artesaos-piloto/`. Tailscale é administração privada
do servidor (SSH, pacotes e atualizações); não é uma segunda origem de uso/login.
Esta decisão substitui expressamente o planejamento de dois domínios preservado
no commit histórico 9376c11. Não aplicar as configurações daquela proposta.

## Configuração da aplicação — responsabilidade da infraestrutura

Em `/srv/artesao-digital-app/config/options.json`, combinar a chave abaixo com o
objeto existente, preservando todas as demais chaves/credenciais:

```json
{
  "public_url": "https://artesaodigital.com.br/artesaos-piloto/"
}
```

Não substituir o arquivo inteiro por este exemplo. Não usar allowed_origins nem
PILOT_ALLOWED_ORIGINS: o suporte adicional foi retirado. O backend continua com
uma única origem configurável por instalação, preservando o adaptador HA.
Alternativa só para ambiente de teste: variável `PILOT_PUBLIC_URL` com essa URL
completa. Não manter override divergente do options.json. O Compose oficial já
monta o arquivo, sem necessidade de alterar o mecanismo de atualização.

A configuração é lida na inicialização; sua alteração exige reinício coordenado,
fora da autorização desta entrega. O atualizador preserva config/options.json;
instalar o pacote sozinho não troca automaticamente a URL nem ativa o domínio.
Links de convite e healthcheck passam a usar a origem configurada quando ativada.
O prefixo suportado por esta distribuição continua sendo `/artesaos-piloto/`.
www, HTTP, subdomínios, portas alternativas e Host Tailscale não são aliases
implícitos. Com public_url oficial, Host Tailscale recebe 421 na aplicação; isso
não altera a conectividade SSH privada nem o endereço do atualizador Windows.

## Callback Google OAuth exato

Rota real em `server/pilot/app.ts`: `prefix + 'auth/google/callback'`.
`googleProvider` constrói redirect_uri a partir de public_url, tanto na autorização
quanto na troca do código. Configurar no cliente Web OAuth Google existente:

```text
https://artesaodigital.com.br/artesaos-piloto/auth/google/callback
```

Esse é o único callback oficial para o acesso público do Forja. Não criar callback
administrativo separado: no Debian, o login administrativo é local; o callback
comum também serve ao fluxo administrativo Google do adaptador HA quando configurado.
Nenhum redirect_uri/returnTo arbitrário é aceito. O adaptador rejeita origem/caminho
incompatíveis antes de contactar o Google; estado, nonce, PKCE, assinatura, audiência,
email verificado, expiração e uso único permanecem com os mecanismos existentes.

O fluxo atual é OIDC no servidor e não usa SDK JavaScript Google. Se a configuração
Google solicitar origem JavaScript/validação do domínio, o valor de origem é
`https://artesaodigital.com.br`, sem caminho; isso não substitui o redirect URI.
Preservar client ID/secret, consentimento e permissões/contas de teste existentes.
A infraestrutura deverá cadastrar/validar o callback público antes da ativação e
coordenar a retirada de callback antigo após o encerramento da transição. Uma URI
antiga temporariamente cadastrada no Google não faz a aplicação aceitar outro Host.
Nenhuma configuração Google foi consultada ou modificada por esta publicação.

## HTTPS e proxy — contrato, sem alteração de infraestrutura nesta tarefa

- TLS válido para artesaodigital.com.br, encaminhando o prefixo sem removê-lo ao
  mesmo serviço/instalação Forja; não criar outro banco ou outra instalação.
- Preservar Host original autorizado. Em Nginx, o contrato é
  `proxy_set_header Host $http_host;`. Preservar também Origin enviado pelo navegador;
  nunca reescrevê-lo para contornar a proteção. Host desconhecido recebe421;
  escrita sem Origin oficial exato recebe403. CSRF/contexto de sessão continuam
  obrigatórios onde já eram exigidos. Não configurar CORS permissivo/curingas.
- X-Forwarded-Host e Forwarded não concedem acesso; trustProxy:false permanece.
  Não redirecionar callbacks entre hosts nem reescrever seu caminho/parâmetros.
- Preservar CSP, cookies e políticas de não cache em HTML/auth/API/service worker.
  Não ativar cache de respostas privadas no Cloudflare. Conferir regras externas
  de cache/redirect com a infraestrutura, sem alterar regras comerciais.
- A origem pública amplia a exposição de login/administração. Preservar controles
  de rede e autenticação existentes; decisões sobre DNS/túnel/firewall/proxy/Google
  são da infraestrutura e não são executadas pelo pacote.

Não gerar nginx.conf completo sem examinar a infraestrutura real. Esta lista é o
contrato da aplicação, não evidência de configuração ou funcionamento do servidor.
Tailscale/SSH/usuário/porta do kit Windows continuam como documentados em FORJA_01.md.

## Sessões, PWA e transição de origem

Cookies preservados: Secure, SameSite=Lax, host-only (sem Domain), HttpOnly quando
aplicável e paths existentes. A nova origem requer novo login. Cookies, localStorage,
CacheStorage e instalações PWA do endereço anterior não são compartilhados ou
transferidos automaticamente. A mesma identidade Google reutiliza usuário/tenant e
dados já gravados no servidor, sem novo convite para conta ativa ou duplicar negócios.

Salvar/conferir alterações na origem antiga antes da transição. Após a ativação,
abrir a URL oficial e autenticar; instalar a PWA novamente a partir dela, se desejado.
Não apagar dados de navegador nem desinstalar automaticamente a PWA antiga. Uma PWA
antiga continua apontando ao host anterior; ela não muda sua origem pelo pacote.
A proteção PWA-UPDATE-001 continua válida dentro da origem, mas não migra dados ou
sessões entre endereços. Não prometer aviso de atualização para uma origem retirada.

Manifest/start_url/scope, navegação, APIs, worker network-only e controle de versão
continuam relativos ao prefixo. Não há novo cache comercial, IndexedDB, offline,
sincronização, schema ou sistema de autenticação. A contingência HA continua manual,
sem sincronização; não ativar os dois servidores em paralelo no mesmo domínio.
A publicação do add-on não altera sua configuração ou roteia o domínio para o Pi.

## Instalação futura e retorno — Nível1

Baixar-Pacote.cmd e Verificar-Download.cmd apenas baixam/validam. A instalação por
Atualizar-Forja-01.cmd exige autorização separada, plano/aceites/sudo existentes.
Pacote Debian é compose-source: a imagem é construída no staging na instalação.
Nível1 preservado: backup recomendado, certificação não é pré-requisito; preservar
banco/config/volumes e conferir integridade/versão/health continua obrigatório.
Nenhum schema/checksum de migração muda nesta versão.

Antes da ativação, guardar configuração/imagem anterior segundo os procedimentos
ATUALIZACOES.md e RECUPERACAO.md. Se houver falha no domínio público, primeiro
investigar TLS/Host/prefixo/callback conforme os testes abaixo; não tornar Host/Origin
permissivos para contornar erro de proxy. Retorno de código usa a ferramenta existente,
imagem/recibo anterior e compatibilidade de schema verificada, sem apagar dados,
recriar volumes ou restaurar banco automaticamente. Retorno de configuração/proxy
fica com a infraestrutura, mediante autorização, restaurando a configuração anterior
guardada sem expor credenciais. O retorno à URL antiga só pode ser medida temporária
explicitamente autorizada; não reintroduz o requisito de dois domínios.

Restaurar uma imagem não altera Google Cloud/DNS/Cloudflare: coordenar essas partes
separadamente. Reiniciar fluxos OAuth em andamento após a transição/retorno.
Rollback real e recuperação no Forja/HA não foram executados nem homologados.

## Homologação dirigida

1. Com autorização operacional própria, conferir instalação dev.18/commit/healthy/logs.
2. Após configurações da infraestrutura, abrir URL oficial, fazer login Google com
   conta já ativa, conferir retorno ao mesmo domínio/dados e logout/novo login.
3. Fazer login administrativo local e recuperação conforme procedimento existente,
   em teste autorizado; não expor códigos temporários ou senhas em logs/relatórios.
4. Conferir desktop e Android/PWA: navegação, reabertura, ícones, prefixo, atualização
   e ausência de cache privado. Reinstalar PWA no novo endereço só por ação do usuário.
5. Em ambiente isolado: Host desconhecido/Tailscale→421, Origin errado/ausente→403,
   callback/estado inválido ou repetido recusados; sessões/CSRF continuam obrigatórios.

Testes reproduzíveis: `test/pilot-public-origin.test.ts`, `test/pilot-google.test.ts`
e `scripts/verify-public-origin-browser.py`. Chromium usa apenas fixture TLS local,
host público mapeado a loopback na porta8298 e Google/contas sintéticos; testes de API
exercitam também Host/Origin exatos sem porta. Não comprovam Google/DNS/TLS/proxy reais,
Windows físico, Android/PWA instalada, Supervisor ou Forja. A suíte completa e os
checks operacionais da fonte exata são registrados no recibo oficial da distribuição.

## Impacto na Central de Pendências

Sem impacto comercial: nenhuma pendência de negócio é criada, alterada ou resolvida.
Falhas de origem/autenticação mantêm as respostas de segurança existentes, sem novo
sistema de alertas. Testes de criação/resolução de pendências: não aplicáveis.
