import {readFile} from "node:fs/promises";
import {describe,expect,it} from "vitest";
const root=new URL("../",import.meta.url);
const readFirst=async paths=>{for(const path of paths){try{return await readFile(new URL(path,root),"utf8");}catch(error){if(error.code!=="ENOENT")throw error;}}throw new Error("Entrypoint ausente");};
describe("isolamento do ambiente do Portal e do bridge",()=>{
 it("remove tokens Supervisor do shell e do processo principal",async()=>{
  const entrypoint=await readFirst(["addon/run.sh","run.sh"]);
  expect(entrypoint).toContain('SUPERVISOR_TOKEN="$SUPERVISOR_READ_TOKEN"');
  expect(entrypoint).toContain("unset SUPERVISOR_TOKEN HASSIO_TOKEN SUPERVISOR_API SUPERVISOR_READ_TOKEN");
  expect(entrypoint).toMatch(/exec su-exec portal:portal env -i[\s\\]+/);
  expect(entrypoint).toContain('GITHUB_TOKEN="$GITHUB_TOKEN"');
  expect(entrypoint).toContain("NODE_ENV=production");
  expect(entrypoint).toContain("PORTAL_MODE=ingress");
  const mainEnv=entrypoint.slice(entrypoint.indexOf("exec su-exec"));
  expect(mainEnv).not.toContain("SUPERVISOR_TOKEN=");
  expect(mainEnv).not.toContain("HASSIO_TOKEN=");
 });
 it("passa ao bridge somente o token Supervisor e ambiente mínimo",async()=>{
  const entrypoint=await readFirst(["addon/run.sh","run.sh"]);
  const bridgeStart=entrypoint.indexOf("su-exec 65534:65534");
  const bridgeEnv=entrypoint.slice(bridgeStart,entrypoint.indexOf("# Remover aliases"));
  expect(bridgeEnv).toContain("su-exec 65534:65534 env -i");
  expect(bridgeEnv).toContain("SUPERVISOR_TOKEN=");
  expect(bridgeEnv).toContain("node /app/server/supervisor-bridge.mjs");
  expect(bridgeEnv).not.toContain("GITHUB_TOKEN");
  expect(bridgeEnv).not.toContain("GITHUB_WRITE_TOKEN");
 });
});
