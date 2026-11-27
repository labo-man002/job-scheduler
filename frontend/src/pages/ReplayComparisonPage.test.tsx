import { render, screen, within } from "@testing-library/react";
import { QueryClientProvider, QueryClient } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";
import { api } from "@/api/client";
import { ReplayComparisonPage } from "./ReplayComparisonPage";

vi.mock("@/api/client", () => ({ api: { GET: vi.fn() } }));

function result(id: string, hash: string, tick: number) {
  const metrics = { completed: 1, unscheduled: 0, makespan_ticks_from_zero: 3, occupancy: 0.5,
    completed_jobs_per_hour: 10, cross_leaf_placements: null };
  return {
    id, workload_label: id,
    inputs: { scenario: {nodes: [{id:1, gpus:1}]}, topology: {kind:"linear"}, placement: "pack",
      trace_sha256: hash, queue_policies: ["fifo","priority"], service_time: "fixed" },
    outputs: { comparison: { seconds_per_tick: tick, fifo: metrics, priority: metrics,
      jobs: [{id: 1, fifo_wait: 1, priority_wait: 1}] } },
  };
}

function compare(hash: string) {
  const get = vi.mocked(api.GET);
  get.mockImplementationOnce((async () => ({data: result("base", "trace", 30), response: new Response()})) as typeof api.GET);
  get.mockImplementationOnce((async () => ({data: result("alt", hash, 60), response: new Response()})) as typeof api.GET);
  render(<QueryClientProvider client={new QueryClient()}>
    <MemoryRouter initialEntries={["/replay/compare?baseline=base&alternative=alt"]}><ReplayComparisonPage /></MemoryRouter>
  </QueryClientProvider>);
}

it("uses wall-clock units when traces share job IDs but use different tick sizes", async () => {
  compare("trace");
  const region = await screen.findByRole("region", {name:"Outcome differences"});
  const rows = within(region).getAllByRole("row", {name:/Last completion from trace origin/});
  expect(rows).toHaveLength(2);
  expect(within(rows[0]).getByText("+90")).toBeVisible();
  expect(screen.getByText("Per-job waits (seconds)")).toBeVisible();
});

it("suppresses per-job pairing and warns about attribution when workloads differ", async () => {
  compare("different");
  expect(await screen.findByText(/The workload changed/)).toBeVisible();
  expect(screen.queryByText("Per-job waits (seconds)")).toBeNull();
});
