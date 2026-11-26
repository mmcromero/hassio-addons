import {describe,it,expect,beforeEach,afterEach} from "vitest";
import {mkdtemp,rm} from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import {createLedger} from "../server/ledger.mjs";

describe("timeline histórica no ledger append-only",()=>{
 let dir,file,ledger;
 beforeEach(async()=>{dir=await mkdtemp(path.join(os.tmpdir(),"portal-timeline-"));file=path.join(dir,"history.ndjson");ledger=createLedger({filePath:file});});
 afterEach(async()=>rm(dir,{recursive:true,force:true}));
 const event={type:"timeline_event",eventId:"github:commit:abc123",occurredAt:"2024-02-03T12:00:00.000Z",confidence:"confirmed",category:"project_start",sourceName:"GitHub Commit",title:"Primeiro commit encontrado",summary:"Commit inicial",projectId:"portal-governanca",repository:"mmcromero/portal-governanca",sha:"abcdef1234567",sourceUrl:"https://github.com/mmcromero/portal-governanca/commit/abcdef1234567",origin:"GitHubHistoryCollector"};
 it("persiste a data original, a fonte, a confiança e a evidência",async()=>{
  const row=await ledger.append(event);
  expect(row).toMatchObject({eventId:event.eventId,occurredAt:event.occurredAt,confidence:"confirmed",category:"project_start",sourceName:"GitHub Commit",sourceUrl:event.sourceUrl});
  const result=await ledger.listTimelineEvents({projectId:"portal-governanca"});
  expect(result).toMatchObject({total:1,integrity:"valid"});
  expect(result.events[0].occurredAt).toBe(event.occurredAt);
 });
 it("deduplica a mesma evidência sem acrescentar outra linha",async()=>{
  const first=await ledger.append(event),second=await ledger.append({...event,title:"Texto alterado"});
  expect(second.id).toBe(first.id);
  expect((await ledger.listTimelineEvents({projectId:"portal-governanca"})).total).toBe(1);
  expect((await ledger.list()).integrity).toBe("valid");
 });
 it("valida e persiste um dia ativo por data local",async()=>{
  const row=await ledger.append({...event,eventId:"github:activity-day:portal:2026-11-01",category:"activity_day",sourceName:"GitHub Commits",title:"Atividade registrada — 2026-11",summary:"Atividade observada em 2026-11-01",sha:"",sourceUrl:"",activeDays:1});
  expect(row.activeDays).toBe(1);
  await expect(ledger.append({...event,eventId:"github:activity-day:portal:2026-12-01",category:"activity_month",activeDays:32})).rejects.toMatchObject({code:"INVALID_TIMELINE_EVENT"});
 });
 it("isola a consulta por projeto",async()=>{
  await ledger.append(event);
  await ledger.append({...event,eventId:"github:issue:other:1",projectId:"outro-projeto",category:"first_issue",sourceName:"GitHub Issue",sha:"",sourceUrl:"https://github.com/mmcromero/outro/issues/1"});
  expect((await ledger.listTimelineEvents({projectId:"portal-governanca"})).total).toBe(1);
  expect((await ledger.listTimelineEvents({projectId:"outro-projeto"})).total).toBe(1);
 });
 it("rejeita data, confiança e URL de evidência inválidas",async()=>{
  await expect(ledger.append({...event,occurredAt:"ontem"})).rejects.toMatchObject({code:"INVALID_TIMELINE_EVENT"});
  await expect(ledger.append({...event,confidence:"maybe"})).rejects.toMatchObject({code:"INVALID_TIMELINE_EVENT"});
  await expect(ledger.append({...event,sourceUrl:"javascript:alert(1)"})).rejects.toMatchObject({code:"INVALID_SOURCE_URL"});
 });
 it("preserva um evento explícito de encerramento para congelar o contador",async()=>{
  const row=await ledger.append({...event,eventId:"owner:project_end:portal-governanca",occurredAt:"2026-11-26T19:00:00.000Z",confidence:"confirmed",category:"project_end",sourceName:"Decisão registrada no Portal",title:"Projeto encerrado",summary:"Encerramento declarado pelo proprietário.",sha:"",sourceUrl:""});
  expect(row).toMatchObject({category:"project_end",confidence:"confirmed",occurredAt:"2026-11-26T19:00:00.000Z"});
  expect((await ledger.listTimelineEvents({projectId:"portal-governanca"})).events[0].category).toBe("project_end");
 });
 it("preserva event_id dos eventos do protocolo de agentes",async()=>{
  await ledger.append({type:"agent_event",title:"Início",summary:"Evento real",eventId:"123e4567-e89b-12d3-a456-426614174000",eventType:"inicio",projectId:"portal-governanca",agentId:"agent",taskId:"task"});
  expect((await ledger.listEvents({projectId:"portal-governanca"})).events[0].eventId).toBe("123e4567-e89b-12d3-a456-426614174000");
 });
});
