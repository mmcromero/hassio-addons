import { describe, expect, it } from "vitest";
import { buildProjectChatUrl } from "../src/project-chat-link.ts";

describe("link de nova conversa do ChatGPT por projeto", () => {
  it("preenche o contexto básico do projeto e as referências GitHub", () => {
    const url = buildProjectChatUrl({
      id: "demo",
      name: "Projeto de demonstração",
      domain: "Operações",
      summary: "Resumo do projeto",
      status: "EM DESENVOLVIMENTO",
      statusReason: "Commit recente",
      age: "120 dias",
      repositories: [{ fullName: "mmcromero/demo", role: "Fonte", path: "src/", latestIssue: { number: 42, title: "Continuar integração do projeto", state: "open", url: "https://github.com/mmcromero/demo/issues/42", createdAt: "2026-11-26T10:00:00Z", updatedAt: "2026-11-27T10:00:00Z" }, latestIssueState: "available" }]
    });
    const parsed = new URL(url);
    expect(parsed.origin).toBe("https://chatgpt.com");
    const prompt = parsed.searchParams.get("q") || "";
    expect(prompt).toContain("Projeto de demonstração");
    expect(prompt).toContain("EM DESENVOLVIMENTO");
    expect(prompt).toContain("https://github.com/mmcromero/demo");
    expect(prompt).toContain("Última Issue criada: #42");
    expect(prompt).toContain("https://github.com/mmcromero/demo/issues/42");
    expect(prompt).toContain("Comece consultando diretamente a última Issue indicada");
    expect(prompt).toContain("Não presuma acesso aos repositórios privados");
  });

  it("limita o tamanho dos campos e a quantidade de repositórios listados", () => {
    const url = buildProjectChatUrl({
      id: "demo",
      name: "P".repeat(500),
      domain: "Área",
      summary: "S".repeat(5000),
      status: "STATUS NÃO IDENTIFICADO",
      statusReason: "R".repeat(1000),
      age: "Não identificada",
      repositories: Array.from({ length: 15 }, (_, index) => ({
        fullName: `mmcromero/repo-${index}`,
        role: "Fonte"
      }))
    });
    const prompt = new URL(url).searchParams.get("q") || "";
    expect(prompt.length).toBeLessThan(5000);
    expect(prompt).toContain("Mais 3 repositório(s)");
    expect(prompt).not.toContain("repo-12");
  });
  it("distingue ausência de Issues de falha na consulta", () => {
    const base = {
      id: "demo", name: "Projeto", domain: "Área", summary: "Resumo",
      status: "EM DESENVOLVIMENTO", statusReason: "Commit", age: "10 dias"
    };
    const emptyPrompt = new URL(buildProjectChatUrl({ ...base, repositories: [{ fullName: "mmcromero/empty", role: "Fonte", latestIssueState: "empty" }] })).searchParams.get("q") || "";
    const unavailablePrompt = new URL(buildProjectChatUrl({ ...base, repositories: [{ fullName: "mmcromero/private", role: "Fonte", latestIssueState: "unavailable" }] })).searchParams.get("q") || "";
    expect(emptyPrompt).toContain("nenhuma Issue encontrada");
    expect(unavailablePrompt).toContain("consulta indisponível");
    expect(unavailablePrompt).not.toContain("nenhuma Issue encontrada");
  });

});