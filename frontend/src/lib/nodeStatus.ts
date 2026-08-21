import type { components } from "@/api/schema.d.ts";

type NodeStatus = components["schemas"]["NodeStatus"];

export const NODE_STATUS_COLOR: Record<NodeStatus, { fill: string; border: string; text: string; label: string }> = {
  IDLE: { fill: "#16a34a", border: "#15803d", text: "#ffffff", label: "Idle" },
  ALLOCATED: { fill: "#2563eb", border: "#1d4ed8", text: "#ffffff", label: "Allocated" },
  MIXED: { fill: "#d97706", border: "#b45309", text: "#ffffff", label: "Mixed" },
  DOWN: { fill: "#dc2626", border: "#b91c1c", text: "#ffffff", label: "Down" },
};

export const NODE_STATUS_ORDER: NodeStatus[] = ["IDLE", "ALLOCATED", "MIXED", "DOWN"];
