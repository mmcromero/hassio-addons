import { describe, expect, it } from "vitest";
import { getProjectStatus } from "../src/project-status.ts";

const repo = (overrides = {}) => ({ latestCommit: null, openPulls: [], latestRelease: null, latestWorkflowRun: null, ...overrides });
const approval = (createdAt = "2026-01-01T00:00:00.000Z") => ({ type: "homologation", projectId: "demo", status: "PASS", createdAt });

describe("classificação automática do ciclo de vida do projeto", () => {
  it("marca como cancelado somente com decisão explícita", () => {
    const result = getProjectStatus("demo", [repo()], [], [{ category: "project_cancelled", occurredAt: "2026-02-01T00:00:00.000Z" }]);
    expect(result).toMatchObject({ status: "cancelled", label: "CANCELADO", variant: "error" });
  });

  it("marca como finalizado somente com encerramento explícito", () => {
    const result = getProjectStatus("demo", [repo()], [], [{ category: "project_end", occurredAt: "2026-02-01T00:00:00.000Z" }]);
    expect(result).toMatchObject({ status: "finished", label: "FINALIZADO" });
  });

  it("não confunde uma homologação aprovada com finalização", () => {
    const result = getProjectStatus("demo", [repo()], [approval()], [], "2026-02-01T00:00:00.000Z");
    expect(result).toMatchObject({ status: "homologated", label: "HOMOLOGADO" });
  });

  it("retorna para desenvolvimento quando há commit posterior à homologação", () => {
    const result = getProjectStatus("demo", [repo({ latestCommit: { date: "2026-01-03T00:00:00.000Z" } })], [approval()], [], "2026-02-01T00:00:00.000Z");
    expect(result.status).toBe("development");
  });

  it("não mantém homologado quando a homologação mais recente falhou", () => {
    const result = getProjectStatus("demo", [repo()], [
      approval("2026-01-01T00:00:00.000Z"),
      { type: "homologation", projectId: "demo", status: "FAIL", createdAt: "2026-01-05T00:00:00.000Z" }
    ], [], "2026-02-01T00:00:00.000Z");
    expect(result.status).toBe("unknown");
  });

  it("não trata pull request em rascunho como teste", () => {
    const result = getProjectStatus("demo", [repo({ openPulls: [{ updatedAt: "2026-01-02T00:00:00.000Z", draft: true }] })], [], [], "2026-02-01T00:00:00.000Z");
    expect(result.status).toBe("unknown");
  });

  it("classifica workflow ativo como em teste", () => {
    const result = getProjectStatus("demo", [repo({ latestWorkflowRun: { status: "in_progress", updatedAt: "2026-01-02T00:00:00.000Z" } })], [], [], "2026-02-01T00:00:00.000Z");
    expect(result.status).toBe("testing");
  });

  it("classifica PR aberto como em teste", () => {
    const result = getProjectStatus("demo", [repo({ openPulls: [{ updatedAt: "2026-01-02T00:00:00.000Z" }] })], [], [], "2026-02-01T00:00:00.000Z");
    expect(result).toMatchObject({ status: "testing", label: "EM TESTE" });
  });

  it("não inventa classificação sem evidências", () => {
    const result = getProjectStatus("demo", [repo()], [], [], "2026-02-01T00:00:00.000Z");
    expect(result).toMatchObject({ status: "unknown", label: "STATUS NÃO IDENTIFICADO" });
  });

  it("reconhece homologação histórica vinculada ao ID legado do Artesão", () => {
    const result = getProjectStatus("artesao-digital", [repo()], [{ type: "homologation", projectId: "artesao_digital", status: "PASS", createdAt: "2026-01-01T00:00:00.000Z" }], [], "2026-02-01T00:00:00.000Z");
    expect(result.status).toBe("homologated");
  });

  it("ignora homologação de outro projeto", () => {
    const result = getProjectStatus("demo", [repo()], [{ ...approval(), projectId: "other" }], [], "2026-02-01T00:00:00.000Z");
    expect(result.status).toBe("unknown");
  });
});
