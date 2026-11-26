import {describe,expect,it} from "vitest";
import {normalizeSupervisorInventory} from "../server/supervisor-data.mjs";
describe("inventário Supervisor somente leitura",()=>{
 it("normaliza somente campos permitidos do endpoint v2",()=>{
  const result=normalizeSupervisorInventory({result:"ok",data:{apps:[{
   slug:"core_mosquitto",name:"Mosquitto",state:"started",version:"7.1.3",version_latest:"7.1.3",
   update_available:false,boot:"auto",watchdog:true,ingress_panel:false,protected:true,auto_update:false,
   options:{password:"DO_NOT_RETURN"},schema:{password:"secret"},network:{"1883/tcp":1883}
  }]}});
  expect(result).toEqual([{slug:"core_mosquitto",name:"Mosquitto",state:"started",version:"7.1.3",versionLatest:"7.1.3",updateAvailable:false,boot:"auto",watchdog:true,ingressPanel:false,protected:true,autoUpdate:false}]);
  expect(JSON.stringify(result)).not.toContain("DO_NOT_RETURN");
  expect(JSON.stringify(result)).not.toContain("password");
  expect(JSON.stringify(result)).not.toContain("network");
 });
 it("aceita lista vazia válida",()=>expect(normalizeSupervisorInventory({data:{apps:[]}})).toEqual([]));
 it("falha quando a resposta não contém lista",()=>expect(()=>normalizeSupervisorInventory({result:"ok",data:{}})).toThrow("sem lista de apps"));
 it("descarta registros sem slug ou nome confiável",()=>expect(normalizeSupervisorInventory({data:{apps:[{slug:"x"},{name:"Sem slug"},{slug:"ok",name:"OK"}]}})).toHaveLength(1));
});
