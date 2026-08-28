import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { ClustersPage } from "./ClustersPage";
import { api } from "@/api/client";

vi.mock("@/api/client", () => ({
  api: { GET: vi.fn() },
}));

const CLUSTERS = [
  { cluster_id: 1, cluster_name: "ring-a", topology_type: "RING", dimension: [4], wrap: true, total_capacity: 10, free_capacity: 4 },
];

function mockGet(data: unknown = CLUSTERS) {
  vi.mocked(api.GET)
    .mockReset()
    .mockResolvedValue({ data, error: undefined, response: new Response(null, { status: 200 }) } as never);
}

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <ClustersPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("ClustersPage", () => {
  it("lists clusters once loaded", async () => {
    mockGet();
    renderPage();
    expect(await screen.findByText("ring-a")).toBeInTheDocument();
  });

  it("shows an empty state when there are no clusters", async () => {
    mockGet([]);
    renderPage();
    expect(await screen.findByText(/no clusters yet/i)).toBeInTheDocument();
  });

  it("shows an error message when the request fails", async () => {
    vi.mocked(api.GET)
      .mockReset()
      .mockResolvedValue({ data: undefined, error: { detail: "boom" }, response: new Response(null, { status: 500 }) } as never);
    renderPage();
    expect(await screen.findByText(/failed to load clusters/i)).toBeInTheDocument();
  });
});
