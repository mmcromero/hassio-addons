import {readFile} from "node:fs/promises";
import {describe,expect,it} from "vitest";

const css=await readFile(new URL("../src/styles.css",import.meta.url),"utf8");

describe("estrutura vertical do Portal",()=>{
 it("mantém o workspace no fluxo superior sem centralização vertical automática",()=>{
  expect(css).toMatch(/\.workspace\{[^}]*display:flex;[^}]*flex-direction:column;[^}]*margin:0 auto;/);
  expect(css).not.toMatch(/\.workspace\{[^}]*margin:auto;/);
 });
 it("faz o conteúdo ocupar o espaço disponível e mantém o rodapé no fim",()=>{
  expect(css).toMatch(/\.workspace main\{flex:1 0 auto\}/);
  expect(css).toMatch(/footer\{[^}]*margin-top:auto;/);
 });
});
