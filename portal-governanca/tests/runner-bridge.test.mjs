import {describe,it,expect,vi} from "vitest";
import {createRunnerBridge} from "../server/runner-bridge.mjs";

const baseUrl="http://45c28620-fabrica-software:9877";

describe("restricted Factory Runner bridge",()=>{
 it("refuses dispatch when the dedicated token is absent",async()=>{
  const bridge=createRunnerBridge({token:"",baseUrl});
  expect(bridge.configured).toBe(false);
  await expect(bridge.submitMission({missionId:"x",projectId:"avisaqui",prompt:"x"})).rejects.toMatchObject({code:"runner_not_configured"});
 });
 it("sends only the mission envelope to the internal plan-only endpoint",async()=>{
  const fetchImpl=vi.fn().mockResolvedValue({ok:true,status:202,json:async()=>({job:{execution_id:"00000000-0000-4000-8000-000000000001",status:"RECEBIDA"}})});
  const bridge=createRunnerBridge({token:"t".repeat(64),baseUrl,fetchImpl});
  const result=await bridge.submitMission({missionId:"00000000-0000-4000-8000-000000000002",projectId:"avisaqui",prompt:"Prompt completo preservado no Portal.",createdAt:"2026-11-26T14:00:00.000Z"});
  expect(bridge.configured).toBe(true);
  expect(result.job.status).toBe("RECEBIDA");
  const [url,options]=fetchImpl.mock.calls[0];
  expect(String(url)).toBe(baseUrl+"/v1/jobs");
  expect(options.headers["X-Portal-Dispatch-Token"]).toBe("t".repeat(64));
  expect(JSON.parse(options.body)).toEqual({mission_id:"00000000-0000-4000-8000-000000000002",project_id:"avisaqui",prompt:"Prompt completo preservado no Portal.",created_at:"2026-11-26T14:00:00.000Z"});
 });
 it("rejects non-approved network destinations",()=>{
  const bridge=createRunnerBridge({token:"t".repeat(64),baseUrl:"http://example.com:9877"});
  expect(bridge.configured).toBe(false);
 });
});
