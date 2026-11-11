import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { JobSubmitPage } from "./JobSubmitPage";
import { api } from "@/api/client";

vi.mock("@/api/client", () => ({
  api: { GET: vi.fn(), POST: vi.fn() },
}));

const CLIENTS = [
  { client_id: 1, owner: "alice", institute_id: 1, client_status: "ONLINE" },
  { client_id: 2, owner: "bob", institute_id: 1, client_status: "OFFLINE" },
];

function renderPage() {
  const queryClient = new QueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/jobs/new"]}>
        <Routes>
          <Route path="/jobs/new" element={<JobSubmitPage />} />
          <Route path="/jobs/:jobId" element={<p>job detail page</p>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("JobSubmitPage", () => {
  beforeEach(() => {
    vi.mocked(api.GET).mockReset().mockResolvedValue({ data: CLIENTS, error: undefined, response: new Response() } as never);
    vi.mocked(api.POST).mockReset();
  });

  it("requires a client to be selected", async () => {
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter>
          <JobSubmitPage />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    await screen.findByText("alice (client 1)");
    await userEvent.click(screen.getByRole("button", { name: /submit job/i }));

    expect(await screen.findByText(/pick a client/i)).toBeInTheDocument();
    expect(api.POST).not.toHaveBeenCalled();
  });

  it("rejects duplicate resource types across requirement rows without calling the API", async () => {
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter>
          <JobSubmitPage />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    await screen.findByText("alice (client 1)");
    await userEvent.selectOptions(screen.getByLabelText("Client"), "1"); // pick client "alice"
    await userEvent.click(screen.getByRole("button", { name: /add requirement/i })); // now 2 rows, both default to CPU

    await userEvent.click(screen.getByRole("button", { name: /submit job/i }));

    expect(await screen.findByText(/each resource type can only appear once/i)).toBeInTheDocument();
    expect(api.POST).not.toHaveBeenCalled();
  });

  it("submits resource and network requirements without a node-count choice", async () => {
    vi.mocked(api.POST).mockResolvedValue({
      data: { detail: "Job submitted", status_code: 201, job_id: 1000, status: "QUEUED" },
      error: undefined,
      response: new Response(),
    } as never);

    renderPage();
    await screen.findByText("alice (client 1)");
    await userEvent.selectOptions(screen.getByLabelText("Client"), "1");
    await userEvent.clear(screen.getByLabelText("Amount for requirement 1"));
    await userEvent.type(screen.getByLabelText("Amount for requirement 1"), "2");
    await userEvent.click(screen.getByRole("checkbox"));
    await userEvent.type(screen.getByLabelText("Minimum path bandwidth (Gbps)"), "100");
    await userEvent.type(screen.getByLabelText("Maximum path latency (µs)"), "10");
    await userEvent.click(screen.getByRole("button", { name: /submit job/i }));

    expect(api.POST).toHaveBeenCalledWith("/jobs", {
      body: {
        client_id: 1,
        priority: "NORMAL",
        duration: 60,
        require_full_connectivity: true,
        min_bandwidth_gbps: 100,
        max_latency_us: 10,
        requirements: [{ resource_type: "CPU", amount: 2 }],
      },
    });
  });

  it("submits and navigates to the new job's detail page on success", async () => {
    vi.mocked(api.POST).mockResolvedValue({
      data: { detail: "Job submitted", status_code: 201, job_id: 999, status: "QUEUED" },
      error: undefined,
      response: new Response(),
    } as never);

    renderPage();
    await screen.findByText("alice (client 1)");
    await userEvent.selectOptions(screen.getByLabelText("Client"), "1");
    await userEvent.click(screen.getByRole("button", { name: /submit job/i }));

    expect(await screen.findByText("job detail page")).toBeInTheDocument();
    expect(api.POST).toHaveBeenCalledWith("/jobs", {
      body: {
        client_id: 1,
        priority: "NORMAL",
        duration: 60,
        require_full_connectivity: false,
        requirements: [{ resource_type: "CPU", amount: 1 }],
      },
    });
  });
});
