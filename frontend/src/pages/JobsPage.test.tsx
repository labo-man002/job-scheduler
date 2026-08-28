import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { JobsPage } from "./JobsPage";
import { api } from "@/api/client";

vi.mock("@/api/client", () => ({
  api: { GET: vi.fn() },
}));

const CLIENTS = [{ client_id: 1, owner: "alice", institute_id: 1, client_status: "ONLINE" }];

const JOBS = [
  { job_id: 1, client_id: 1, status: "RUNNING", priority: "NORMAL", duration: 30, submitted_at: "2026-08-21T10:00:00Z" },
];

function mockGet(jobs: unknown = JOBS, clients: unknown = CLIENTS) {
  vi.mocked(api.GET)
    .mockReset()
    .mockImplementation(((path: string) => {
      if (path === "/clients") return Promise.resolve({ data: clients, error: undefined, response: new Response(null, { status: 200 }) });
      if (path === "/jobs") return Promise.resolve({ data: jobs, error: undefined, response: new Response(null, { status: 200 }) });
      throw new Error(`unexpected path ${path}`);
    }) as typeof api.GET);
}

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <JobsPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("JobsPage", () => {
  it("lists jobs with the owning client's name once loaded", async () => {
    mockGet();
    renderPage();
    // "alice" also appears in the client-filter <option>, so query the job row
    // itself (unambiguous) and check its text, rather than the ambiguous name alone.
    const jobRow = await screen.findByText(/job 1/i);
    expect(jobRow.closest("li")?.textContent).toMatch(/alice/i);
  });

  it("shows a generic empty state when there are no jobs and no filters are set", async () => {
    mockGet([]);
    renderPage();
    expect(await screen.findByText(/no jobs yet/i)).toBeInTheDocument();
  });

  it("shows a filtered empty state once a status filter is applied", async () => {
    mockGet([]);
    renderPage();
    await screen.findByText(/no jobs yet/i);

    await userEvent.selectOptions(screen.getByDisplayValue(/all statuses/i), "RUNNING");

    expect(await screen.findByText(/no jobs match these filters/i)).toBeInTheDocument();
  });

  it("shows an error message when the jobs request fails", async () => {
    vi.mocked(api.GET)
      .mockReset()
      .mockImplementation(((path: string) => {
        if (path === "/clients") return Promise.resolve({ data: CLIENTS, error: undefined, response: new Response(null, { status: 200 }) });
        if (path === "/jobs") return Promise.resolve({ data: undefined, error: { detail: "boom" }, response: new Response(null, { status: 500 }) });
        throw new Error(`unexpected path ${path}`);
      }) as typeof api.GET);

    renderPage();
    expect(await screen.findByText(/failed to load jobs/i)).toBeInTheDocument();
  });
});
