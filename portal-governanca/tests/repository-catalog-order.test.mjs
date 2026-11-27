import { describe, expect, it } from "vitest";
import { orderRegisteredRepositories } from "../src/repository-catalog-order.ts";

describe("ordenação do catálogo de repositórios", () => {
  it("lista os projetos cadastrados primeiro e ordena alfabeticamente dentro dos grupos", () => {
    const repositories = [
      { fullName: "mmcromero/zeta", markerStatus: "available" },
      { fullName: "mmcromero/portal", markerStatus: "registered" },
      { fullName: "mmcromero/alfa", markerStatus: "available" },
      { fullName: "mmcromero/artesao", markerStatus: "registered" },
      { fullName: "mmcromero/invalido", markerStatus: "invalid" }
    ];

    expect(orderRegisteredRepositories(repositories).map(item => item.fullName)).toEqual([
      "mmcromero/artesao",
      "mmcromero/portal",
      "mmcromero/alfa",
      "mmcromero/invalido",
      "mmcromero/zeta"
    ]);
  });

  it("não altera a lista original e preserva todos os repositórios", () => {
    const repositories = [
      { fullName: "mmcromero/novo", markerStatus: "available" },
      { fullName: "mmcromero/existente", markerStatus: "registered" }
    ];
    const originalOrder = repositories.map(item => item.fullName);
    const ordered = orderRegisteredRepositories(repositories);

    expect(repositories.map(item => item.fullName)).toEqual(originalOrder);
    expect(ordered).toHaveLength(repositories.length);
    expect(new Set(ordered.map(item => item.fullName)).size).toBe(repositories.length);
  });

  it("mantém o catálogo válido quando não há projetos cadastrados", () => {
    const repositories = [
      { fullName: "mmcromero/b", markerStatus: "available" },
      { fullName: "mmcromero/a", markerStatus: "available" }
    ];
    expect(orderRegisteredRepositories(repositories).map(item => item.fullName)).toEqual([
      "mmcromero/a",
      "mmcromero/b"
    ]);
  });
});
