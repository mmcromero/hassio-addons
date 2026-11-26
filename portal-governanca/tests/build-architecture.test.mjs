import {describe,expect,it} from "vitest";
import fs from "node:fs";
import path from "node:path";
import {createHash} from "node:crypto";
const root=process.cwd();
describe("build autossuficiente do add-on",()=>{
 it("usa snapshot local do Design System sem checkout irmão",()=>{
  const pkg=JSON.parse(fs.readFileSync(path.join(root,"package.json"),"utf8"));
  expect(pkg.dependencies["@mmcromero/ds-components"]).toBe("file:vendor/design-system/packages/components");
  expect(pkg.dependencies["@mmcromero/ds-tokens"]).toBe("file:vendor/design-system/packages/tokens");
  const provenance=JSON.parse(fs.readFileSync(path.join(root,"vendor/design-system/PROVENANCE.json"),"utf8"));
  const lock=JSON.parse(fs.readFileSync(path.join(root,"config/design-system.lock.json"),"utf8"));
  expect(provenance.source_commit).toBe(lock.sha);
  expect(provenance.files).toHaveLength(19);
  expect(provenance.source_repository).toBe("mmcromero/design-system");
 });
 it("aplica a identidade oficial do catálogo e separa os quatro indicadores",()=>{
  const main=fs.readFileSync(path.join(root,"src/main.ts"),"utf8");
  const css=fs.readFileSync(path.join(root,"src/styles.css"),"utf8");
  expect(main).toContain('src="./brand-icon.png"');
  expect(main).not.toContain('<span class="mark">G</span>');
  expect((main.match(/class="metric-content"/g)||[]).length).toBe(4);
  expect(css).toContain(".metric-content{display:flex;flex-direction:column");
  expect(fs.existsSync(path.join(root,"public/brand-icon.png"))).toBe(true);
  const iconPath=fs.existsSync(path.join(root,"icon.png"))?path.join(root,"icon.png"):path.join(root,"addon/icon.png");
  const logoPath=fs.existsSync(path.join(root,"logo.png"))?path.join(root,"logo.png"):path.join(root,"addon/logo.png");
  const gitBlobSha=bytes=>createHash("sha1").update(Buffer.concat([Buffer.from("blob "+bytes.length+"\0"),bytes])).digest("hex");
  const icon=fs.readFileSync(iconPath),logo=fs.readFileSync(logoPath),brandIcon=fs.readFileSync(path.join(root,"public/brand-icon.png"));
  expect(gitBlobSha(icon)).toBe("a0fdd10938db1b6a65aa60469e83ed1c7c9bd33a");
  expect(gitBlobSha(logo)).toBe("7e500016222b0a5bf395be8ed17447edeb3e2af9");
  expect(brandIcon.equals(icon)).toBe(true);
 });
 it("Dockerfile executa npm ci, testes e build antes da imagem runtime",()=>{
  const dockerPath=fs.existsSync(path.join(root,"Dockerfile"))?path.join(root,"Dockerfile"):path.join(root,"addon/Dockerfile");
  const docker=fs.readFileSync(dockerPath,"utf8");
  expect(docker).toContain("FROM node:22-alpine AS frontend-build");
  expect(docker).toContain("RUN npm ci");
  expect(docker).toContain("RUN npm run build:design-system && npm test && npm run build:portal");
  expect(docker).toContain("COPY --from=frontend-build");
  expect(docker).not.toContain("COPY dist/");
 });
});
