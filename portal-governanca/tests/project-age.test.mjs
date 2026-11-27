import { describe, expect, it } from "vitest";
import { getProjectAge } from "../src/project-age.ts";

describe("idade do projeto nos cards", () => {
  it("calcula dias desde o início confirmado", () => {
    const result = getProjectAge([
      { category: "project_start", occurredAt: "2024-01-01T00:00:00.000Z", confidence: "confirmed" }
    ], "2024-01-04T00:00:00.000Z");
    expect(result).toEqual({ days: 3, confidence: "confirmed", ended: false });
  });

  it("usa o encerramento registrado como fim do contador", () => {
    const result = getProjectAge([
      { category: "project_start", occurredAt: "2024-01-01T00:00:00.000Z", confidence: "confirmed" },
      { category: "project_end", occurredAt: "2024-01-03T00:00:00.000Z", confidence: "confirmed" }
    ], "2024-01-10T00:00:00.000Z");
    expect(result).toEqual({ days: 2, confidence: "confirmed", ended: true });
  });

  it("preserva a indicação de início estimado", () => {
    const result = getProjectAge([
      { category: "first_issue", occurredAt: "2024-01-01T00:00:00.000Z", confidence: "estimated" }
    ], "2024-01-02T00:00:00.000Z");
    expect(result.confidence).toBe("estimated");
    expect(result.days).toBe(1);
  });

  it("não inventa dias quando não há evidência de início", () => {
    expect(getProjectAge([], "2024-01-02T00:00:00.000Z")).toEqual({ days: null, confidence: "unknown", ended: false });
  });

  it("não calcula dias para evidência com confiança desconhecida", () => {
    const result = getProjectAge([
      { category: "first_issue", occurredAt: "2024-01-01T00:00:00.000Z", confidence: "unknown" }
    ], "2024-01-02T00:00:00.000Z");
    expect(result).toEqual({ days: null, confidence: "unknown", ended: false });
  });
});
