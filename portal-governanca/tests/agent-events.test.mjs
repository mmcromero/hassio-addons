import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { mkdtemp, rm } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { createLedger } from "../server/ledger.mjs";
import { filterUnrecordedAgentEvents } from "../server/agent-events.mjs";

describe("Protocolo de Agentes — Backend Ledger", () => {
  let dir, file, ledger;

  const validEvent = {
    type: "agent_event",
    title: "[INICIO] portal-governanca · fase-6b",
    summary: "Iniciando implementação do protocolo de agentes",
    projectId: "portal-governanca",
    eventId: "11111111-2222-3333-4444-555555555555",
    eventType: "inicio",
    agentId: "portal-implementador",
    taskId: "fase-6b",
    deliverables: ["docs/PROTOCOLO-AGENTES.md"],
    nextAction: "Implementar testes e UI",
    responsible: "portal-implementador",
    origin: "AgentProtocol"
  };

  beforeEach(async () => {
    dir = await mkdtemp(path.join(os.tmpdir(), "portal-ledger-agent-"));
    file = path.join(dir, "history.ndjson");
    ledger = createLedger({ filePath: file });
  });

  afterEach(async () => {
    await rm(dir, { recursive: true, force: true });
  });

  it("registra evento de agente e preserva integridade SHA-256", async () => {
    const row = await ledger.append(validEvent);
    expect(row.type).toBe("agent_event");
    expect(row.eventId).toBe(validEvent.eventId);
    expect(row.eventType).toBe("inicio");
    expect(row.hash).toBeDefined();

    const list = await ledger.list();
    expect(list.total).toBe(1);
    expect(list.integrity).toBe("valid");
  });

  it("identifica evento existente por eventId (idempotência)", async () => {
    expect(await ledger.hasEvent(validEvent.eventId)).toBe(false);
    await ledger.append(validEvent);
    expect(await ledger.hasEvent(validEvent.eventId)).toBe(true);
    expect(await ledger.hasEvent("non-existent-uuid")).toBe(false);
  });

  it("lista eventos filtrados por projectId e agentId", async () => {
    await ledger.append(validEvent);
    await ledger.append({
      ...validEvent,
      eventId: "22222222-3333-4444-5555-666666666666",
      projectId: "factory-runner",
      agentId: "worker-isolation",
      eventType: "conclusao",
      title: "[CONCLUSAO] factory-runner · isolamento"
    });

    const all = await ledger.listEvents();
    expect(all.total).toBe(2);
    expect(all.events.length).toBe(2);

    const portalOnly = await ledger.listEvents({ projectId: "portal-governanca" });
    expect(portalOnly.total).toBe(1);
    expect(portalOnly.events[0].projectId).toBe("portal-governanca");

    const factoryOnly = await ledger.listEvents({ agentId: "worker-isolation" });
    expect(factoryOnly.total).toBe(1);
    expect(factoryOnly.events[0].agentId).toBe("worker-isolation");
  });

  it("respeita limite de paginação em listEvents", async () => {
    for (let i = 0; i < 5; i++) {
      await ledger.append({
        ...validEvent,
        eventId: `event-uuid-00000000000${i}`,
        title: `Evento ${i}`
      });
    }
    const limited = await ledger.listEvents({ limit: 3 });
    expect(limited.total).toBe(5);
    expect(limited.events.length).toBe(3);
  });

  it("rejeita evento sem título ou descrição", async () => {
    await expect(ledger.append({ ...validEvent, title: "" })).rejects.toMatchObject({
      code: "REQUIRED_FIELDS"
    });
    await expect(ledger.append({ ...validEvent, summary: "" })).rejects.toMatchObject({
      code: "REQUIRED_FIELDS"
    });
  });
});

describe("Polling de agentes — idempotência antes do despacho",()=>{
 let dir,file,ledger;
 beforeEach(async()=>{
  dir=await mkdtemp(path.join(os.tmpdir(),"portal-agent-filter-"));
  file=path.join(dir,"history.ndjson");
  ledger=createLedger({filePath:file});
 });
 afterEach(async()=>{await rm(dir,{recursive:true,force:true});});
 const event=(id)=>({body:{comment:{body:"<!-- AGENT_PROTOCOL_EVENT -->\n\x60\x60\x60json\n"+JSON.stringify({event_id:id})+"\n\x60\x60\x60\n<!-- /AGENT_PROTOCOL_EVENT -->"}}});
 it("remove eventos já registrados e mantém eventos novos",async()=>{
  const id="05ce8adf-003b-494e-90b3-9ea20e799e97";
  await ledger.append({type:"agent_event",title:"Evento de teste",summary:"Evento já persistido",eventId:id,eventType:"atualizacao",projectId:"portal-governanca",agentId:"agent",taskId:"task",origin:"AgentProtocol"});
  const result=await filterUnrecordedAgentEvents([event(id),event("6f3bcfae-b089-4315-9155-75cad6ab147e")],ledger);
  expect(result.alreadyRecorded).toBe(1);
  expect(result.events).toHaveLength(1);
 });
 it("mantém comentários malformados para a validação do workflow rejeitar",async()=>{
  const result=await filterUnrecordedAgentEvents([{body:{comment:{body:"sem bloco JSON válido"}}}],ledger);
  expect(result.alreadyRecorded).toBe(0);
  expect(result.events).toHaveLength(1);
 });
});
