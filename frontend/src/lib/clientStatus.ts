import type { components } from "@/api/schema.d.ts";

type ClientStatus = components["schemas"]["ClientStatus"];

export const CLIENT_STATUS_COLOR: Record<ClientStatus, { fill: string; label: string }> = {
  ONLINE: { fill: "#16a34a", label: "Online" },
  OFFLINE: { fill: "#64748b", label: "Offline" },
};
