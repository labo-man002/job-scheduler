import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { DashboardPage } from "./DashboardPage";
import { api } from "@/api/client";

vi.mock("@/api/client", () => ({
  api: { GET: vi.fn() },
}));

const CLUSTERS = [
  { cluster_id: 1, cluster_name: "ring-a", topology_type: "RING", dimension: [4], wrap: true, total_capacity: 10, free_capacity: 4 },
  { cluster_id: 2, cluster_name: "mesh-a", topology_type: "MESH_2D", dimension: [2, 2], wrap: false, total_capacity: 10, free_capacity: 10 },
];

const JOBS = [
  { job_id: 1, client_id: 1, status: "RUNNING", priority: "NORMAL", duration: 30, submitted_at: "2026-08-22T00:00:00Z" },
  { job_id: 2, client_id: 1, status: "QUEUED", priority: "NORMAL", duration: 30, submitted_at: "2026-08-22T00:00:00Z" },
  { job_id: 3, client_id: 1, status: "COMPLETED", priority: "NORMAL", duration: 30, submitted_at: "2026-08-22T00:00:00Z" },
];

const EVENTS = [{ job_id: 1, event_type: "RUNNING", time: "2026-08-22T00:00:00Z", comment: "Placed on 2 resource unit(s)" }];

function mockGet(clusters: unknown[] = CLUSTERS, jobs: unknown[] = JOBS, events: unknown[] = EVENTS) {
  vi.mocked(api.GET)
    .mockReset()
    .mockImplementation(((path: string) => {
      if (path === "/clusters") return Promise.resolve({ data: clusters, error: undefined, response: new Response(null, { status: 200 }) });
      if (path === "/jobs") return Promise.resolve({ data: jobs, error: undefined, response: new Response(null, { status: 200 }) });
      if (path === "/jobs/events/recent") return Promise.resolve({ data: events, error: undefined, response: new Response(null, { status: 200 }) });
      throw new Error(`unexpected path ${path}`);
    }) as typeof api.GET);
}

function renderPage() {
  const queryClient = new QueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <DashboardPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("DashboardPage", () => {
  it("shows aggregate stats computed from clusters and jobs", async () => {
    mockGet();
    renderPage();

    expect(await screen.findByText("ring-a")).toBeInTheDocument();
    // 2 clusters, 30% overall utilization ((20 total - 14 free) / 20), 1 running, 1 queued.
    expect(await screen.findByText("2")).toBeInTheDocument();
    expect(await screen.findByText("30%")).toBeInTheDocument();
  });

  it("lists recent job events with a link to the job", async () => {
    mockGet();
    renderPage();

    const jobLink = await screen.findByRole("link", { name: /job 1/i });
    expect(jobLink).toHaveAttribute("href", "/jobs/1");
    expect(await screen.findByText(/placed on 2 resource unit/i)).toBeInTheDocument();
  });

  it("shows an empty state when there is no recent activity", async () => {
    mockGet(CLUSTERS, JOBS, []);
    renderPage();

    expect(await screen.findByText(/no activity yet/i)).toBeInTheDocument();
  });
});
