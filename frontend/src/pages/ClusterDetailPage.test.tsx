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

describe("ClusterDetailPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks(); // clears the window.confirm spy (and its call count) left over from the previous test
    vi.mocked(api.GET).mockReset().mockResolvedValue({ data: CLUSTER, error: undefined, response: new Response() } as never);
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
    vi.mocked(api.GET).mockResolvedValue({
      data: { ...CLUSTER, nodes: [{ ...CLUSTER.nodes[0], status: "DOWN" }, ...CLUSTER.nodes.slice(1)] },
      error: undefined,
      response: new Response(),
    } as never);

    renderPage();
    await screen.findByText("test-cluster");
    await userEvent.click(screen.getByText("0,0"));

    expect(await screen.findByRole("button", { name: /already down/i })).toBeDisabled();
  });
});
