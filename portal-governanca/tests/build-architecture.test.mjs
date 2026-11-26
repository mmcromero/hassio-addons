import {describe,expect,it} from "vitest";
import fs from "node:fs";
import path from "node:path";
const root=process.cwd();
describe("build autossuficiente do add-on",()=>{
 it("usa snapshot local do Design System sem checkout irmão",()=>{
  const pkg=JSON.parse(fs.readFileSync(path.join(root,"package.json"),"utf8"));
  expect(pkg.dependencies["@mmcromero/ds-components"]).toBe("file:vendor/design-system/packages/components");
  expect(pkg.dependencies["@mmcromero/ds-tokens"]).toBe("file:vendor/design-system/packages/tokens");
  const provenance=JSON.parse(fs.readFileSync(path.join(root,"vendor/design-system/PROVENANCE.json"),"utf8"));
  const lock=JSON.parse(fs.readFileSync(path.join(root,"config/design-system.lock.json"),"utf8"));
  expect(provenance.source_commit).toBe(lock.sha);\n  expect(provenance.files).toHaveLength(19);
  expect(provenance.source_repository).toBe("mmcromero/design-system");
 });
 it("Dockerfile executa npm ci, testes e build antes da imagem runtime",()=>{
  const dockerPath=fs.existsSync(path.join(root,"Dockerfile"))?path.join(root,"Dockerfile"):path.join(root,"addon/Dockerfile");\n  const docker=fs.readFileSync(dockerPath,"utf8");
  expect(docker).toContain("FROM node:22-alpine AS frontend-build");
  expect(docker).toContain("RUN npm ci");
  expect(docker).toContain("RUN npm run build:design-system && npm test && npm run build:portal");
  expect(docker).toContain("COPY --from=frontend-build");
  expect(docker).not.toContain("COPY dist/");
 });
});
