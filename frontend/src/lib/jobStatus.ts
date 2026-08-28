import type { components } from "@/api/schema.d.ts";

type JobStatus = components["schemas"]["JobStatus"];

export const JOB_STATUS_COLOR: Record<JobStatus, { fill: string; label: string }> = {
  PENDING: { fill: "#64748b", label: "Pending" },
  QUEUED: { fill: "#d97706", label: "Queued" },
  RUNNING: { fill: "#2563eb", label: "Running" },
  COMPLETED: { fill: "#16a34a", label: "Completed" },
  CANCELLED: { fill: "#64748b", label: "Cancelled" },
  FAILED: { fill: "#dc2626", label: "Failed" },
};
