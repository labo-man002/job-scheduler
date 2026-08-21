import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { ClusterDetailPage } from "./ClusterDetailPage";
import { api } from "@/api/client";

vi.mock("@/api/client", () => ({
  api: { GET: vi.fn(), PATCH: vi.fn() },
}));

const CLUSTER = {
  cluster_id: 1,
  cluster_name: "test-cluster",
  topology_type: "MESH_2D",
  dimension: [2, 2],
  wrap: false,
  total_capacity: 8,
  free_capacity: 8,
  nodes: [
    { node_id: 10, coordinates: [0, 0], status: "IDLE", resources: [{ resource_type: "CPU", total: 4, free: 4 }] },
    { node_id: 11, coordinates: [1, 0], status: "IDLE", resources: [{ resource_type: "CPU", total: 4, free: 4 }] },
    { node_id: 12, coordinates: [0, 1], status: "IDLE", resources: [{ resource_type: "CPU", total: 4, free: 4 }] },
    { node_id: 13, coordinates: [1, 1], status: "IDLE", resources: [{ resource_type: "CPU", total: 4, free: 4 }] },
  ],
};

function renderPage() {
  const queryClient = new QueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/clusters/1"]}>
        <Routes>
          <Route path="/clusters/:clusterId" element={<ClusterDetailPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

// The page now fetches /clusters/{id}, /institutes, and /reservations concurrently --
// route by path instead of returning the same fixture for every GET call.
function mockGet(cluster: typeof CLUSTER, institutes: unknown[] = [], reservations: unknown[] = []) {
  vi.mocked(api.GET)
    .mockReset()
    .mockImplementation(((path: string) => {
      if (path === "/clusters/{cluster_id}") return Promise.resolve({ data: cluster, error: undefined, response: new Response(null, { status: 200 }) });
      if (path === "/institutes") return Promise.resolve({ data: institutes, error: undefined, response: new Response(null, { status: 200 }) });
      if (path === "/reservations") return Promise.resolve({ data: reservations, error: undefined, response: new Response(null, { status: 200 }) });
      throw new Error(`unexpected path ${path}`);
    }) as typeof api.GET);
}

describe("ClusterDetailPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks(); // clears the window.confirm spy (and its call count) left over from the previous test
    mockGet(CLUSTER);
    vi.mocked(api.PATCH).mockReset();
  });

  it("prompts to select a node before anything is selected", async () => {
    renderPage();
    expect(await screen.findByText(/select a node/i)).toBeInTheDocument();
  });

  it("shows the node detail panel after clicking a node", async () => {
    renderPage();
    await screen.findByText("test-cluster");
    await userEvent.click(screen.getByText("0,0"));
    expect(await screen.findByText("node 10")).toBeInTheDocument();
  });

  it("asks for confirmation and calls the API when marking a node down, then confirmed", async () => {
    vi.mocked(api.PATCH).mockResolvedValue({ data: { detail: "ok", status_code: 200 }, error: undefined, response: new Response() } as never);
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);

    renderPage();
    await screen.findByText("test-cluster");
    await userEvent.click(screen.getByText("0,0"));
    await userEvent.click(await screen.findByRole("button", { name: /mark node down/i }));

    expect(confirmSpy).toHaveBeenCalledOnce();
    expect(api.PATCH).toHaveBeenCalledWith("/nodes/{node_id}/down", { params: { path: { node_id: 10 } } });
  });

  it("does not call the API when the confirmation is cancelled", async () => {
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(false);

    renderPage();
    await screen.findByText("test-cluster");
    await userEvent.click(screen.getByText("0,0"));
    await userEvent.click(await screen.findByRole("button", { name: /mark node down/i }));

    expect(confirmSpy).toHaveBeenCalledOnce();
    expect(api.PATCH).not.toHaveBeenCalled();
  });

  it("disables the button for a node that's already down", async () => {
    mockGet({ ...CLUSTER, nodes: [{ ...CLUSTER.nodes[0], status: "DOWN" }, ...CLUSTER.nodes.slice(1)] });

    renderPage();
    await screen.findByText("test-cluster");
    await userEvent.click(screen.getByText("0,0"));

    expect(await screen.findByRole("button", { name: /already down/i })).toBeDisabled();
  });

  it("marks a reserved node's tooltip with the reservation info", async () => {
    mockGet(
      CLUSTER,
      [{ institute_id: 5, institute_name: "Test Institute" }],
      [{ id: 1, institute_id: 5, cluster_id: 1, start_period: "2026-09-01T00:00:00Z", end_period: "2026-09-02T00:00:00Z", reason: "maintenance", node_ids: [10] }],
    );

    renderPage();
    await screen.findByText("test-cluster");

    expect(await screen.findByText(/reserved by Test Institute/i)).toBeInTheDocument();
  });
});
