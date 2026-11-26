import {readFile} from "node:fs/promises";
import {describe,expect,it} from "vitest";
const read=async path=>readFile(new URL(path,import.meta.url),"utf8");
const readFirst=async paths=>{for(const path of paths){try{return await read(path);}catch(error){if(error.code!=="ENOENT")throw error;}}throw new Error("Nenhum arquivo de fixture encontrado: "+paths.join(", "));};
describe("cadastro controlado do Portal",()=>{
 it("mantém tokens GitHub de leitura e escrita separados",async()=>{
  const run=await readFirst(["../run.sh","../addon/run.sh"]),config=await readFirst(["../config.yaml","../addon/config.yaml"]);
  expect(run).toContain("GITHUB_TOKEN=");
  expect(run).toContain("GITHUB_WRITE_TOKEN=");
  expect(config).toContain('github_write_token: ""');
  expect(config).toContain('github_write_token: "password?"');
 });
 it("não disponibiliza a credencial de escrita na interface",async()=>{
  const client=await read("../src/api/client.ts"),server=await read("../server/index.mjs");
  expect(client).not.toContain("GITHUB_WRITE_TOKEN");
  expect(server).toContain("sameOrigin(req)");
  expect(server).toContain('pathname==="/api/v1/projects/register"&&req.method==="POST"');
 });
 it("limita o Supervisor ao papel default e não abre privilégios extras",async()=>{
  const config=await readFirst(["../config.yaml","../addon/config.yaml"]);
  expect(config).toContain("hassio_api: true");
  expect(config).toContain("hassio_role: default");
  expect(config).not.toMatch(/(homeassistant_api|docker_api|host_network|privileged|ports):/);
 });
});
