# PWA-DATA-001 — Integridade dos dados durante atualizações

PENDENTE — registro aprovado na R1.4, sem implementação nesta distribuição.
A futura homologação PWA-02 deverá contemplar formulários parcialmente preenchidos,
alterações locais não salvas, atualização com sessão ativa, revisão antes de logout
ou recarga, preservação dos dados gravados, recuperação de rascunhos, operações
offline/retorno da conexão e cenários de perda ou duplicação de dados.
Este registro não autoriza implementar PWA-02, offline, autosave ou recuperação.

Homologação imediata dev.17 limitada a instalação/versão, acesso/login, funcionamento
básico, AD-UX-002 e ausência de erros críticos aparentes. Primeira adoção do controle
de versão: proprietário único aceita recarregar manualmente abas dev.16. Atualizações
posteriores usam PWA-UPDATE-001; não prometer retroatividade antes da adoção.

---

# UX-Loading-01 — situação da prioridade de feedback

Implementado em desenvolvimento na dev.16; detalhes em docs/UX-Loading-01.md no
repositório. Publicação/instalação/homologação física pendentes. Não repetir o pacote
nem incorporar outras alterações por consequência. Investigação de desempenho segue
adiada para depois do piloto/homologação. A diretriz abaixo preserva a motivação.

---

# Prioridade imediata — feedback visual de espera (03/11/2026)

Fase atual: homologação, validação funcional, correções e melhorias visuais.
Incluir no próximo pacote feedback visual discreto e consistente de carregamento e
processamento, especialmente no login e na navegação administrativa. Pode ser uma
entrega independente, sem incorporar outras alterações.

Critério principal: o usuário percebe claramente que a solicitação foi recebida e
que deve aguardar, preservando a identidade visual e o fluxo funcional existentes.
Não apresentar sucesso antes da confirmação real da operação. Implementação ainda
não iniciada por este registro; preparar o próximo pacote dentro desse escopo.

## Desempenho — etapa posterior ao piloto/homologação

Manter no backlog investigação de latência, benchmarking, medidas e ajustes finos
de desempenho ou otimizações sem relação direta com falhas funcionais. Não acoplar
essa investigação ao feedback visual nem usá-la como condição para sua entrega.
Correções de falhas funcionais continuam no foco atual, sem ampliar automaticamente
seu escopo para uma análise geral de desempenho.

Impacto na Central de Pendências: nenhum previsto para o indicador visual de espera;
não criar alerta/pendência comercial para representar simples carregamento.
Reavaliar apenas se a futura implementação demonstrar impacto adicional.

---

# Prioridades posteriores à 0.2.0-dev.12 — registrar, não implementar

## Alta: auditoria abrangente

LGPD, segurança, bases legais, retenção, exclusão, exportação e tratamento de dados
pessoais. Revisão jurídica dos textos iniciais beta e processos reais da instalação.
Revisar armazenamento, backups, permissões e segurança de arquivos enviados.

## Central de Resultados e Indicadores

Gráficos de faturamento/evolução, custos/despesas/resultados, produtos, feiras/eventos,
visitantes/conversão, novos contatos por evento, origem e retorno de contatos captados.
Usar eventos/IDs/snapshots históricos; não recalcular vendas antigas com preços atuais.
Nenhum gráfico entregue neste pacote.

## Catálogos personalizados

Escolher tabela de preços ao gerar catálogo (atacado/varejo/outra disponível),
independentemente da classificação informativa do cliente.

Backlog anterior preservado abaixo (fretes, notificações, licenciamento, imagens, PWA
etc.); itens não promovidos expressamente continuam fora do escopo.

---

# Backlog do Artesão Digital

## Regras

“Colocar no backlog” registra em **Ideias Futuras**, sem execução automática. “Backlog do pacote” ou decisão explícita promove para entrega.

## Pacote experimental 0.1.15

- Logo individual opcional, única por conta, otimizada, substituível e removível; sem histórico de imagens.
- Dados da empresa no documento final (promovido explicitamente).
- PDF em memória, edições e valores preservados, logo atual, baixar e compartilhar quando suportado; envio confirmado separadamente.
- Aviso de guarda da cópia entregue; testes e medidas locais. Validação real e capacidade do servidor continuam pendentes.
- Estrutura jurídica preparada, desativada por padrão, com minutas em legal-drafts.

## Pacote experimental 0.1.16 — fechamento autorizado

- Administração: lista de usuários que efetivamente ativaram a conta com convite e Google, com e-mail, total e situação do acesso; separada dos interessados e dos convites não usados. Botão Exibir dados com empresa, responsável, telefone e e-mail de contato; somente consulta nesta etapa.
- Convites: formulário nome/e-mail/WhatsApp e canal; Salvar gera código e mensagem; novos códigos vinculam à primeira conta Google que usar; aceitos saem da lista e entram em Usuários cadastrados. Sem controle de envio no produto.
- WhatsApp com mensagem pronta via wa.me; SMTP opcional para e-mail automático após configurar no servidor. Validação real de envio ainda pendente.
- Manutenção: documentar parada/desinstalação futura do principal e recuperação do acesso por reinício do Nginx.
- Fechamento/publicação autorizados expressamente após estimativa de 10 a 20 minutos. Outras ideias futuras não são promovidas por esta autorização.

## Pacote experimental 0.1.17 — autorizado

- Convites somente pela administração; retirada dos cinco pares das opções e da trava de cinco contas em produção.
- Sem vencimento nos novos/atuais ativos; antigos expirados/revogados não são reativados automaticamente.
- Revogar e Ativar novamente com novo código, mantendo anterior inválido; preservação de contas, contatos e chave.
- Busca/paginação e bancos abertos sob demanda, sem limite fixo de cadastro.
- Fechamento/publicação autorizados pelo usuário; outras ideias futuras não foram promovidas.

## Próximo Pacote — legal e operação

- Revisar e ativar documentos públicos, identificação/contato, aceite antes das boas-vindas e informação de cookies da instalação.
- Definir retenção, incidentes, direitos, saída/exportação completa e descarte.
- Inventariar fornecedores/transferências, público etário, papéis e obrigações; revisão jurídica atualizada.

## Para o primeiro release piloto

- Concluir pacote legal; testar celular real, Google real e hospedagem/HA.
- Conferir cálculos, isolamento de contas/logos/documentos/chamados, atualização, reinício e restauração.
- Backup inexistente atualmente: definir, configurar e testar recuperação protegida em outro dispositivo/local.
- Revisar textos contra operação e normas vigentes. Investigação de desempenho/memória/benchmarking foi adiada para depois do piloto/homologação pela diretriz de 03/11/2026; não bloqueia o pacote de feedback visual.
- Corrigir falhas que impeçam o fluxo, alterem valores ou exponham dados. Compilar/publicar este pacote não declara release estável.

## Ideias Futuras

- Administração completa de usuários: quantidade, acessos, recuperação/revogação.
- Upload/substituição da marca Artesão Digital pela administração (distinto da logo individual).
- Catálogo público.
- Envio automático por API do WhatsApp Business; e-mail SMTP foi promovido explicitamente para a preparação atual.
- Aprovação/assinatura eletrônica.
- Pagamentos.
- Cálculo automático de frete e prazo.
