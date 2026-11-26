import {describe,expect,it} from "vitest";
import {normalizeSupervisorApp} from "../server/supervisor-data.mjs";
describe("inventário Supervisor somente leitura",()=>{
 it("normaliza somente campos permitidos do endpoint de info",()=>{
  const result=normalizeSupervisorApp({result:"ok",data:{
   slug:"core_mosquitto",name:"Mosquitto",state:"started",version:"7.1.3",version_latest:"7.1.3",
   update_available:false,boot:"auto",watchdog:true,ingress_panel:false,protected:true,auto_update:false,
   options:{password:"DO_NOT_RETURN"},schema:{password:"secret"},network:{"1883/tcp":1883}
  }});
  expect(result).toEqual({slug:"core_mosquitto",name:"Mosquitto",state:"started",version:"7.1.3",versionLatest:"7.1.3",updateAvailable:false,boot:"auto",watchdog:true,ingressPanel:false,protected:true,autoUpdate:false});
  expect(JSON.stringify(result)).not.toContain("DO_NOT_RETURN");
  expect(JSON.stringify(result)).not.toContain("password");
  expect(JSON.stringify(result)).not.toContain("network");
 });
 it("usa slug solicitado quando a resposta não o repete",()=>expect(normalizeSupervisorApp({data:{name:"App",state:"started"}},"known_app").slug).toBe("known_app"));
 it("descarta resposta sem nome confiável",()=>expect(normalizeSupervisorApp({data:{slug:"x"}})).toBeNull());
 it("não aceita array ou payload inválido",()=>expect(()=>normalizeSupervisorApp({data:[]})).toThrow("inválida"));
});
