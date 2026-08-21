import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { JobDetailPage } from "./JobDetailPage";
import { api } from "@/api/client";

vi.mock("@/api/client", () => ({
  api: { GET: vi.fn(), DELETE: vi.fn() },
}));

const JOB = {
  job_id: 42,
  client_id: 1,
  status: "QUEUED",
  priority: "NORMAL",
  duration: 60,
  submitted_at: "2026-08-21T10:00:00Z",
  requirements: [{ resource_type: "CPU", amount: 4 }],
};

const EVENTS = [{ event_type: "QUEUED", time: "2026-08-21T10:00:00Z", comment: "Submitted" }];

const ALLOCATION = {
  allocation_id: 5,
  job_id: 42,
  allocation_status: "ALLOCATED",
  begin_time: "2026-08-21T10:05:00Z",
  end_time: null,
  duration: null,
  resource_nodes: [{ resource_node_id: 1, node_id: 100, resource_type: "CPU" }],
};

function mockGet(job: typeof JOB, allocation: typeof ALLOCATION | null = null) {
  vi.mocked(api.GET)
    .mockReset()
    .mockImplementation(((path: string) => {
      if (path === "/jobs/{job_id}") return Promise.resolve({ data: job, error: undefined, response: new Response(null, { status: 200 }) });
      if (path === "/jobs/{job_id}/events") return Promise.resolve({ data: EVENTS, error: undefined, response: new Response(null, { status: 200 }) });
      if (path === "/jobs/{job_id}/allocation") {
        if (allocation) return Promise.resolve({ data: allocation, error: undefined, response: new Response(null, { status: 200 }) });
        return Promise.resolve({ data: undefined, error: { detail: "not found" }, response: new Response(null, { status: 404 }) });
      }
      throw new Error(`unexpected path ${path}`);
    }) as typeof api.GET);
}

function renderPage() {
  const queryClient = new QueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/jobs/42"]}>
        <Routes>
          <Route path="/jobs/:jobId" element={<JobDetailPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("JobDetailPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.mocked(api.DELETE).mockReset();
  });

  it("shows 'No allocation yet' when the allocation endpoint 404s", async () => {
    mockGet(JOB);
    renderPage();
    expect(await screen.findByText(/no allocation yet/i)).toBeInTheDocument();
  });

  it("shows a cancel button for a QUEUED job", async () => {
    mockGet(JOB);
    renderPage();
    expect(await screen.findByRole("button", { name: /cancel job/i })).toBeInTheDocument();
  });

  it("hides the cancel button for a COMPLETED job", async () => {
    mockGet({ ...JOB, status: "COMPLETED" });
    renderPage();
    await screen.findByText(/completed/i);
    expect(screen.queryByRole("button", { name: /cancel job/i })).not.toBeInTheDocument();
  });

  it("confirms before cancelling and calls the API", async () => {
    mockGet(JOB);
    vi.mocked(api.DELETE).mockResolvedValue({ data: { detail: "ok", status_code: 200 }, error: undefined, response: new Response() } as never);
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);

    renderPage();
    await userEvent.click(await screen.findByRole("button", { name: /cancel job/i }));

    expect(confirmSpy).toHaveBeenCalledOnce();
    expect(api.DELETE).toHaveBeenCalledWith("/jobs/{job_id}", { params: { path: { job_id: 42 } } });
  });

  it("does not call the API when cancellation is not confirmed", async () => {
    mockGet(JOB);
    vi.spyOn(window, "confirm").mockReturnValue(false);

    renderPage();
    await userEvent.click(await screen.findByRole("button", { name: /cancel job/i }));

    expect(api.DELETE).not.toHaveBeenCalled();
  });

  it("shows the allocated resource nodes once a job has an allocation", async () => {
    mockGet({ ...JOB, status: "RUNNING" }, ALLOCATION);
    renderPage();

    expect(await screen.findByText("node 100")).toBeInTheDocument();
  });
});
