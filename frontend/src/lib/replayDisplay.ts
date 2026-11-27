import type { ReplayRun } from "@/api/replay";

export const replayPolicies = ["fifo", "priority"] as const;
export const policyLabels = { fifo: "FIFO", priority: "Priority" };
export type ReplayPolicy = typeof replayPolicies[number];

export function runName(run: Pick<ReplayRun, "display_name" | "workload_label">) {
  return run.display_name || run.workload_label;
}

export function clusterShape(counts: readonly number[]) {
  return `${counts.length} ${counts.length === 1 ? "node" : "nodes"} · ${counts.join(" + ")} GPUs`;
}

export function runTime(iso: string) {
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "medium" }).format(new Date(iso));
}
