export type RecordArea = "homologation" | "evidence" | "decision";
export type RecordLike = { type: string; eventType?: string | null; category?: string | null; sourceName?: string | null; missionStatus?: string | null };

const AREA_TYPES: Record<RecordArea, readonly string[]> = {
  homologation: ["homologation"],
  evidence: ["evidence", "agent_event", "timeline_event"],
  decision: ["decision", "mission", "mission_status", "timeline_event"]
};

export function recordsForArea<T extends RecordLike>(records: readonly T[], area: RecordArea): T[] {
  const accepted = new Set(AREA_TYPES[area]);
  return records.filter(record => accepted.has(record.type));
}

export function recordSourceLabel(record: RecordLike): string {
  if (record.type === "agent_event") return "Evento de agente" + (record.eventType ? " · " + record.eventType : "");
  if (record.type === "timeline_event") return "Marco histórico" + (record.category ? " · " + record.category.replaceAll("_", " ") : "");
  if (record.type === "mission") return "Missão registrada";
  if (record.type === "mission_status") return "Estado de missão" + (record.missionStatus ? " · " + record.missionStatus : "");
  if (record.type === "homologation") return "Homologação";
  if (record.type === "evidence") return "Evidência";
  if (record.type === "decision") return "Decisão";
  return record.sourceName || record.type;
}
