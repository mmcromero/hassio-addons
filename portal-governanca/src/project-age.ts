export type ProjectAgeEvent = {
  occurredAt: string;
  category: string;
  confidence?: "confirmed" | "estimated" | "unknown";
};

export type ProjectAge = {
  days: number | null;
  confidence: "confirmed" | "estimated" | "unknown";
  ended: boolean;
};

const START_CATEGORIES = new Set(["project_start", "first_issue", "first_pull_request"]);

export function getProjectAge(events: ProjectAgeEvent[], now: string): ProjectAge {
  const start = events
    .filter(event => START_CATEGORIES.has(event.category) && Number.isFinite(Date.parse(event.occurredAt)))
    .sort((a, b) => Date.parse(a.occurredAt) - Date.parse(b.occurredAt))[0];
  if (!start || (start.confidence !== "confirmed" && start.confidence !== "estimated")) {
    return { days: null, confidence: "unknown", ended: false };
  }

  const end = events
    .filter(event => ["project_end", "project_cancelled"].includes(event.category) && Number.isFinite(Date.parse(event.occurredAt)))
    .sort((a, b) => Date.parse(a.occurredAt) - Date.parse(b.occurredAt))[0];
  const endAt = end?.occurredAt ?? now;
  if (!Number.isFinite(Date.parse(endAt)) || !Number.isFinite(Date.parse(start.occurredAt))) {
    return { days: null, confidence: "unknown", ended: Boolean(end) };
  }

  const days = Math.floor(Math.max(0, Date.parse(endAt) - Date.parse(start.occurredAt)) / 86_400_000);
  return {
    days,
    confidence: start.confidence === "estimated" ? "estimated" : start.confidence === "confirmed" ? "confirmed" : "unknown",
    ended: Boolean(end)
  };
}
