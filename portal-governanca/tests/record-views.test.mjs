import { describe, expect, it } from "vitest";
import { recordsForArea, recordSourceLabel } from "../src/record-views.ts";

describe("Portal record area projections", () => {
  const records = [
    { type: "homologation" }, { type: "evidence" }, { type: "decision" },
    { type: "agent_event", eventType: "conclusao" }, { type: "timeline_event", category: "project_started" },
    { type: "mission" }, { type: "mission_status", missionStatus: "planned" }
  ];
  it("keeps homologations as explicit human QA records", () => {
    expect(recordsForArea(records, "homologation").map(r => r.type)).toEqual(["homologation"]);
  });
  it("surfaces real agent and historical events as evidence without duplicating storage", () => {
    expect(recordsForArea(records, "evidence").map(r => r.type)).toEqual(["evidence", "agent_event", "timeline_event"]);
  });
  it("consolidates decisions, missions and lifecycle events into the history view", () => {
    expect(recordsForArea(records, "decision").map(r => r.type)).toEqual(["decision", "timeline_event", "mission", "mission_status"]);
  });
  it("labels automatic sources without implying they are manual approvals", () => {
    expect(recordSourceLabel({ type: "agent_event", eventType: "conclusao" })).toBe("Evento de agente · conclusao");
    expect(recordSourceLabel({ type: "mission_status", missionStatus: "planned" })).toBe("Estado de missão · planned");
  });
});
