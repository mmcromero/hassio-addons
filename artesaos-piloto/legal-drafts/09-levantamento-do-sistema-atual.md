> MINUTA PRELIMINAR — não ativada. Requer revisão jurídica brasileira e conferência das normas vigentes. Reconstruída em 31/10/2026 a partir da passagem de bastão; não reproduz literalmente arquivos perdidos.

# Inventário técnico observado no código

Base incorporada: Fabricação e Orçamentos 0.1.23, commit f56f0e5707ad81f74f42c351171d4132f793cf9a. Desenvolvimento isolado na branch codex/artesaos-piloto; distribuição do principal preservada.

Google OIDC, convites, banco de controle de contas/sessões, banco comercial por conta, banco de interessados protegido com chave própria e banco central de suporte com autorização por dono/admin. Consultar DOCS para prazos e limites atuais. Não copiar dados nem credenciais do principal.

Novas tabelas individuais: company_logo (uma linha com imagem atual e revisão; remoção não guarda imagem) e quote_documents (dados textuais e financeiros de cada finalização, sem logo/PDF). Uma nova edição captura empresa atual; edição antiga preserva identificação textual e valores. Orçamento antigo sem snapshot precisa reabrir e finalizar, sem inventar dados históricos.

PDF usa Noto Sans incorporada por subconjunto, A4, paginação, limite de 40 páginas e duas gerações simultâneas por processo. Não há arquivo temporário no servidor. Logo validada/regravada PNG pelo servidor, até 1024 pixels por dimensão e 500 KB; navegador aceita PNG/JPEG/WebP até 5 MB para otimização. Arquivos do PDF baixados pelo usuário estão fora do armazenamento do aplicativo.

Versões jurídicas e aceites são centrais e separados das contas comerciais. O arquivo local controla ativação após reinício. Não existe migração automática da base principal, integração de envio ou backup da infraestrutura nesta entrega.


Na versão 0.1.16 experimental, a administração passa a consultar dados cadastrais dos usuários e contatos dos convites. Novos convites são autorizados pelo código e vinculados à primeira conta Google que o consumir. Nome/telefone/código recuperável ficam cifrados com pilot-invitations.key; e-mail de contato continua no controle existente. O histórico aceito é preservado mesmo saindo da lista padrão. Definir retenção/descarte desses dados.

E-mail automático depende de SMTP opcional e provedor efetivamente configurado. Link do WhatsApp leva texto e código ao serviço quando o administrador o abre; não é envio por API oficial. Esses fluxos e fornecedores devem ser incorporados ao inventário e aos textos definitivos conforme o uso real. Nenhum serviço foi configurado na instalação pessoal nesta sessão.


Na 0.1.17, novos convites e os ainda ativos não possuem vencimento. Revogação e reativação são administrativas; reativar troca o código e mantém o anterior inválido. Convites expirados/revogados anteriores não voltam automaticamente. Retenção de registros/chaves e comunicação sobre uso de códigos sem vencimento precisam integrar a revisão jurídica. Não há limite fixo de cinco contas, e as listas/cache de bancos têm limites operacionais de recursos. Nenhuma minuta foi ativada.
