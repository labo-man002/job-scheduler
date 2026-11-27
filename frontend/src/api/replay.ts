import { api } from "@/api/client";
import type { components } from "@/api/schema";
import { formatApiError } from "@/lib/apiError";

export type ReplayRun = components["schemas"]["ReplayRunDetail"];
export type ReplayRunSummary = components["schemas"]["ReplayRunSummary"];
export type RunRequest = components["schemas"]["CreateReplayRun"];
export type Comparison = components["schemas"]["Comparison"];

function requestError(error: unknown, fallback: string) {
  return new Error(error ? formatApiError(error) : fallback);
}

export async function saveReplayRun(body: RunRequest) {
  const { data, error } = await api.POST("/replay/runs", { body });
  if (!data) throw requestError(error, "The replay could not be saved.");
  return data;
}

export async function listReplayRuns(beforeId: string | null) {
  const { data, error } = await api.GET("/replay/runs", {
    params: { query: { limit: 20, ...(beforeId ? { before_id: beforeId } : {}) } },
  });
  if (!data) throw requestError(error, "Run history could not be loaded.");
  return data;
}

export async function loadReplayRun(id: string) {
  const { data, error } = await api.GET("/replay/runs/{run_id}", { params: { path: { run_id: id } } });
  if (!data) throw requestError(error, "The saved run could not be loaded.");
  return data;
}

export async function renameReplayRun(id: string, displayName: string | null) {
  const { data, error } = await api.PATCH("/replay/runs/{run_id}", {
    params: { path: { run_id: id } },
    body: { display_name: displayName },
  });
  if (!data) throw requestError(error, "The run could not be renamed.");
  return data;
}
