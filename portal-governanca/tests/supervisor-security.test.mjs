import {readFile} from "node:fs/promises";
import {describe,expect,it} from "vitest";
const root=new URL("../",import.meta.url);
const readFirst=async paths=>{for(const path of paths){try{return await readFile(new URL(path,root),"utf8");}catch(error){if(error.code!=="ENOENT")throw error;}}throw new Error("Arquivo de configuração ausente");};
describe("fronteira de segurança do bridge Supervisor",()=>{
 it("solicita exclusivamente o papel default",async()=>{
  const config=await readFirst(["addon/config.yaml","config.yaml"]);
  expect(config).toContain("hassio_api: true");
  expect(config).toContain("hassio_role: default");
  expect(config).not.toMatch(/hassio_role:\s*(manager|admin|homeassistant|backup)/);
  expect(config).not.toMatch(/(homeassistant_api|docker_api|host_network|privileged|ports):/);
 });
 it("mantém token fora do processo principal",async()=>{
  const run=await readFirst(["addon/run.sh","run.sh"]);
  expect(run).toContain("su-exec 65534:65534 env -i");
  expect(run).toContain('SUPERVISOR_TOKEN="$SUPERVISOR_READ_TOKEN"');
  expect(run).toContain("unset SUPERVISOR_TOKEN HASSIO_TOKEN SUPERVISOR_API SUPERVISOR_READ_TOKEN");
  expect(run).toContain('HA_BRIDGE_URL="http://127.0.0.1:8098"');
  const main=await readFile(new URL("server/index.mjs",root),"utf8");
  expect(main).not.toContain("process.env.SUPERVISOR_TOKEN");
  expect(main).not.toContain("Authorization: Bearer");
 });
 it("fixa o único endpoint upstream e não implementa proxy genérico",async()=>{
  const bridge=await readFile(new URL("server/supervisor-bridge.mjs",root),"utf8");
  expect(bridge).toContain('const UPSTREAM="http://supervisor"');
  expect(bridge).toContain('"/addons/"+encodeURIComponent(slug)+"/info"');
  expect(bridge).toContain("config.inventorySlugs");
  expect(bridge).not.toContain("/v2/apps/status");
  expect(bridge).toContain('req.method!=="GET"');
  expect(bridge).toContain('pathname!=="/v1/inventory"');
  expect(bridge).toContain("127.0.0.1");
  expect(bridge).not.toContain("req.url,");
 });
});
