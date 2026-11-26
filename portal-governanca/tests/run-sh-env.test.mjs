import {readFile} from "node:fs/promises";
import {describe,expect,it} from "vitest";

const root=new URL("../",import.meta.url);\nlet entrypoint;\ntry{entrypoint=await readFile(new URL("addon/run.sh",root),"utf8");}\ncatch{entrypoint=await readFile(new URL("run.sh",root),"utf8");}

describe("isolamento do ambiente do processo Portal",()=>{
 it("remove tokens Supervisor injetados pelo Home Assistant",()=>{
  expect(entrypoint).toContain("unset SUPERVISOR_TOKEN HASSIO_TOKEN SUPERVISOR_API");
 });
 it("inicia Node com allowlist explícita de variáveis",()=>{
  expect(entrypoint).toMatch(/exec su-exec portal:portal env -i[\s\\]+/);
  expect(entrypoint).toContain('GITHUB_TOKEN="$GITHUB_TOKEN"');
  expect(entrypoint).toContain("NODE_ENV=production");
  expect(entrypoint).toContain("PORTAL_MODE=ingress");
  expect(entrypoint).not.toMatch(/SUPERVISOR_TOKEN=/);
  expect(entrypoint).not.toMatch(/HASSIO_TOKEN=/);
 });
});
