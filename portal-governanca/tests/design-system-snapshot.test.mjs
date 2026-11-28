import {createHash} from "node:crypto";
import {readFile} from "node:fs/promises";
import {describe,expect,it} from "vitest";
const lock=JSON.parse(await readFile(new URL("../config/design-system.lock.json",import.meta.url),"utf8"));
const provenance=JSON.parse(await readFile(new URL("../vendor/design-system/PROVENANCE.json",import.meta.url),"utf8"));
describe("snapshot versionado do Design System",()=>{
 it("fixa um commit completo e mantém lock e proveniência alinhados",()=>{expect(lock.sha).toMatch(/^[0-9a-f]{40}$/);expect(lock.sha).toBe(provenance.source_commit);expect(lock.sourceChannel).toBe("desenvolvimento");expect(provenance.source_repository).toBe("mmcromero/design-system");expect(provenance.files.length).toBeGreaterThan(0);});
 it("verifica cada arquivo vendorizado pelo Git blob SHA",async()=>{for(const file of provenance.files){const bytes=await readFile(new URL("../vendor/design-system/"+file.path,import.meta.url));const actual=createHash("sha1").update("blob "+bytes.length+"\0").update(bytes).digest("hex");expect(actual,file.path).toBe(file.git_blob_sha);}});
 it("mantém as versões dos manifests iguais às versões fixadas",async()=>{const tokens=JSON.parse(await readFile(new URL("../vendor/design-system/packages/tokens/package.json",import.meta.url),"utf8"));const components=JSON.parse(await readFile(new URL("../vendor/design-system/packages/components/package.json",import.meta.url),"utf8"));expect(lock.packages["@mmcromero/ds-tokens"]).toBe(tokens.version);expect(lock.packages["@mmcromero/ds-components"]).toBe(components.version);});
});
