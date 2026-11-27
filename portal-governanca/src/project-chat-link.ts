export type ProjectChatRepository = {
  fullName: string;
  role: string;
  path?: string;
  latestIssue?: { number: number; title: string; state: string; url: string; createdAt: string; updatedAt: string } | null;
  latestIssueState?: "unavailable" | "available" | "empty";
};

export type ProjectChatContext = {
  id: string;
  name: string;
  domain: string;
  summary: string;
  status: string;
  statusReason: string;
  age: string;
  repositories: ProjectChatRepository[];
};

function bounded(value: string, max: number): string {
  const normalized = value.trim().replace(/\s+/g, " ");
  return normalized.length > max ? normalized.slice(0, max - 1).trimEnd() + "…" : normalized;
}

/**
 * Creates a ChatGPT Web new-chat URL with a compact, non-secret project brief.
 * ChatGPT's query-string prefill is undocumented and may change independently.
 */
export function buildProjectChatUrl(context: ProjectChatContext): string {
  const repositories = context.repositories.slice(0, 12).map(repository => {
    const base = `- ${repository.fullName} (${repository.role})${repository.path ? ` · caminho: ${repository.path}` : ""}\n  https://github.com/${repository.fullName}`;
    if (repository.latestIssue) {
      const issue = repository.latestIssue;
      return base + `\n  Última Issue criada: #${issue.number} — ${bounded(issue.title, 180)} (${issue.state})\n  Consultar Issue: ${issue.url}\n  Criada em: ${issue.createdAt}; atualizada em: ${issue.updatedAt}`;
    }
    if (repository.latestIssueState === "empty") return base + "\n  Issues: nenhuma Issue encontrada no GitHub.";
    if (repository.latestIssueState === "unavailable") return base + "\n  Última Issue: consulta indisponível; não presumir que o repositório não tenha Issues.";
    return base + "\n  Última Issue: dado ainda não disponível no snapshot do Portal.";
  });
  if (context.repositories.length > 12) {
    repositories.push(`- Mais ${context.repositories.length - 12} repositório(s) relacionado(s) estão cadastrados no Portal; consulte o catálogo do projeto para os demais.`);
  }

  const prompt = [
    "Quero iniciar uma nova conversa de trabalho sobre um projeto do meu portfólio. Use o contexto abaixo como ponto de partida.",
    "",
    "## Projeto",
    `Nome: ${bounded(context.name, 180)}`,
    `ID no Portal: ${bounded(context.id, 120)}`,
    `Área: ${bounded(context.domain, 160)}`,
    `Resumo: ${bounded(context.summary, 1200) || "Não informado"}`,
    `Status no Portal: ${bounded(context.status, 80)}`,
    `Evidência do status: ${bounded(context.statusReason, 400) || "Não informada"}`,
    `Idade: ${bounded(context.age, 100)}`,
    "",
    "## Repositórios relacionados e Issues",
    ...(repositories.length ? repositories : ["- Nenhum repositório cadastrado."]),
    "",
    "## Orientações",
    "- Comece consultando diretamente a última Issue indicada para cada repositório relevante; abra o link e leia a Issue e seus comentários antes de propor trabalho.",
    "- Use o número e o link da Issue como ponto de entrada, mas confira se ela continua sendo a mais recente quando iniciar a tarefa.",
    "- Considere esses dados como um resumo inicial, não como prova de que o código ou o runtime foram inspecionados agora.",
    "- Não presuma acesso aos repositórios privados. Se precisar consultar código ou estado atual, verifique se a integração GitHub está disponível nesta conversa.",
    "- Não invente decisões, versões, testes, publicações ou homologações. Diferencie fatos confirmados, inferências e dúvidas.",
    "- Antes de propor mudanças, entenda a missão, as decisões e a continuidade já registradas no repositório do projeto.",
    "- Ajude a continuar o trabalho a partir deste contexto, sem recomeçar do zero."
  ].join("\n");

  return "https://chatgpt.com/?q=" + encodeURIComponent(prompt);
}
