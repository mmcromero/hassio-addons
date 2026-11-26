import {describe,expect,it} from "vitest";
import fs from "node:fs";
describe("catálogo inicial do Portal",()=>{
 it("começa vazio e usa descoberta opt-in",()=>{
  const config=JSON.parse(fs.readFileSync(new URL("../config/portfolio.json",import.meta.url),"utf8"));
  expect(config.discovery).toEqual({owner:"mmcromero",manifest:".portal-governanca.json",mode:"opt-in"});
  expect(config.projects).toEqual([]);
 });
});
