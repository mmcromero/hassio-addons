import { projectIdsMatch } from './project-navigation';

export type ProjectLifecycleStatus =
  | "development"
  | "testing"
  | "homologated"
  | "finished"
  | "cancelled"
  | "unknown";

export type ProjectStatusResult = {
  status: ProjectLifecycleStatus;
  label: string;
  variant: "info" | "warning" | "success" | "neutral" | "error";
  reason: string;
  evidenceAt: string | null;
};

type StatusTimelineEvent = { category: string; occurredAt: string; confidence?: string };
type StatusRecord = { type: string; projectId: string | null; status: string | null; createdAt: string };
type StatusRepository = {
  latestCommit?: { date: string | null } | null;
  openPulls?: { updatedAt: string; draft?: boolean }[];
  latestRelease?: { publishedAt: string | null; prerelease: boolean } | null;
  latestWorkflowRun?: { status: string; updatedAt: string } | null;
};

const validDate = (value?: string | null): number | null => {
  if (!value) return null;
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : null;
};

export function getProjectStatus(
  projectId: string,
  repositories: StatusRepository[],
  records: StatusRecord[],
  timeline: StatusTimelineEvent[],
  now = new Date().toISOString()
): ProjectStatusResult {
  const terminal = timeline
    .filter(event => ["project_end", "project_cancelled"].includes(event.category) && validDate(event.occurredAt) !== null)
    .sort((a, b) => Date.parse(b.occurredAt) - Date.parse(a.occurredAt))[0];

  if (terminal) {
    const cancelled = terminal.category === "project_cancelled";
    return {
      status: cancelled ? "cancelled" : "finished",
      label: cancelled ? "CANCELADO" : "FINALIZADO",
      variant: cancelled ? "error" : "neutral",
      reason: cancelled ? "Cancelamento declarado explicitamente pelo proprietário." : "Encerramento declarado explicitamente pelo proprietário.",
      evidenceAt: terminal.occurredAt
    };
  }

  const projectRecords = records
    .filter(record => projectIdsMatch(record.projectId, projectId) && record.type === "homologation")
    .sort((a, b) => Date.parse(b.createdAt) - Date.parse(a.createdAt));
  const latestHomologation = projectRecords[0] ?? null;
  const approval = latestHomologation?.status === "PASS" ? latestHomologation : null;
  const approvalAt = validDate(approval?.createdAt);

  const commits = repositories.map(repo => validDate(repo.latestCommit?.date)).filter((value): value is number => value !== null);
  const pulls = repositories.flatMap(repo => repo.openPulls ?? []).filter(pull => !pull.draft).map(pull => validDate(pull.updatedAt)).filter((value): value is number => value !== null);
  const workflows = repositories.map(repo => {
    const run = repo.latestWorkflowRun;
    return run && ["queued", "in_progress", "waiting", "requested"].includes(run.status.toLowerCase())
      ? validDate(run.updatedAt)
      : null;
  }).filter((value): value is number => value !== null);
  const prereleases = repositories.map(repo => repo.latestRelease).filter(release => release?.prerelease && validDate(release.publishedAt) !== null);
  const latestCommitAt = commits.length ? Math.max(...commits) : null;
  const latestPullAt = pulls.length ? Math.max(...pulls) : null;
  const latestWorkflowAt = workflows.length ? Math.max(...workflows) : null;
  const latestPrereleaseAt = prereleases.length ? Math.max(...prereleases.map(release => validDate(release?.publishedAt)!)) : null;
  const activeTestAt = [latestPullAt, latestWorkflowAt, latestPrereleaseAt].filter((value): value is number => value !== null).reduce<number | null>((max, value) => max === null || value > max ? value : max, null);

  if (activeTestAt !== null && (approvalAt === null || activeTestAt > approvalAt)) {
    const reason = latestWorkflowAt === activeTestAt
      ? "Workflow em execução."
      : latestPrereleaseAt === activeTestAt
      ? "Release prévia publicada."
      : "Pull request aberto ou atualizado.";
    return { status: "testing", label: "EM TESTE", variant: "warning", reason, evidenceAt: new Date(activeTestAt).toISOString() };
  }

  if (approval && approvalAt !== null && (latestCommitAt === null || latestCommitAt <= approvalAt)) {
    return {
      status: "homologated",
      label: "HOMOLOGADO",
      variant: "success",
      reason: "Homologação com resultado PASS registrada no ledger.",
      evidenceAt: approval.createdAt
    };
  }

  if (latestCommitAt !== null && latestCommitAt <= Date.parse(now)) {
    return {
      status: "development",
      label: "EM DESENVOLVIMENTO",
      variant: "info",
      reason: latestCommitAt > (approvalAt ?? 0)
        ? "Commit posterior à última homologação."
        : "Há commits registrados, mas não existe homologação PASS vigente.",
      evidenceAt: new Date(latestCommitAt).toISOString()
    };
  }

  return {
    status: "unknown",
    label: "STATUS NÃO IDENTIFICADO",
    variant: "neutral",
    reason: "Ainda não há evidência suficiente para classificar o ciclo de vida.",
    evidenceAt: null
  };
}
