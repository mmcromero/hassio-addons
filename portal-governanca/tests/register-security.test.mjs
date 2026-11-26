import {readFile} from "node:fs/promises";
import {describe,expect,it} from "vitest";
const read=async path=>readFile(new URL(path,import.meta.url),"utf8");
describe("cadastro controlado do Portal",()=>{
 it("mantém tokens de leitura e escrita separados no entrypoint",async()=>{
  const run=await read("../addon/run.sh"),config=await read("../addon/config.yaml");
  expect(run).toContain("GITHUB_TOKEN=");
  expect(run).toContain("GITHUB_WRITE_TOKEN=");
  expect(config).toContain("github_write_token: \"\"");
  expect(config).toContain('github_write_token: "password?"');
 });
 it("não disponibiliza a credencial de escrita na interface",async()=>{
  const client=await read("../src/api/client.ts"),server=await read("../server/index.mjs");
  expect(client).not.toContain("GITHUB_WRITE_TOKEN");
  expect(server).toContain("sameOrigin(req)");
  expect(server).toContain('pathname==="/api/v1/projects/register"&&req.method==="POST"');
 });
 it("não adiciona permissões ou portas Home Assistant",async()=>{
  const config=await read("../addon/config.yaml");
  expect(config).not.toMatch(/(hassio_api|homeassistant_api|docker_api|host_network|privileged|ports):/);
 });
});
