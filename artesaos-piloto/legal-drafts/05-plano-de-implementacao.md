> MINUTA PRELIMINAR — não ativada. Requer revisão jurídica brasileira e conferência das normas vigentes. Reconstruída em 31/10/2026 a partir da passagem de bastão; não reproduz literalmente arquivos perdidos.

# Estrutura implementada e ativação futura

`server/pilot/legal.ts` mantém arquivo de versões e aceites em `pilot-legal.sqlite`. Sem `legal-config.json` ativo no volume, os documentos e o bloqueio ficam desativados. O contato e as informações de preparação continuam públicos em `/legal` dentro do prefixo do piloto.

Arquivo local: `enabled`, `reviewed`, `terms`, `privacy`, `cookies`; cada documento tem `version`, `effectiveAt` (data ISO já vigente) e `text`. `reviewed: true` é declaração operacional, não verificação jurídica automática. Não há configuração ativa incluída no pacote.

O arquivo é lido ao iniciar. Cada par tipo/versão é imutável: mudar texto ou vigência exige nova versão. Mudar a versão dos Termos exige novo aceite; alterar apenas Privacidade/Cookies não solicita automaticamente aceite contratual. Avaliar alterações relevantes com revisão jurídica.

APIs autenticadas: GET `/api/legal/status`, POST `/api/legal/accept`. O aceite exige confirmação explícita, versão e hash atuais; registra conta e hora ISO do servidor. Sessão, contexto da aba, origem e CSRF são verificados. O bloqueio cobre APIs comerciais e suporte do usuário; administração mantém sua autenticação independente para trabalho operacional.

Antes de ativar: inserir somente textos revisados, preservar cópia protegida do volume, testar com contas fictícias e reiniciar. Não mudar versões existentes. Não existe painel de edição jurídica nesta entrega.
