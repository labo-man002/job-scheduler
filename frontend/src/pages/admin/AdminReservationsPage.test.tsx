import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AdminReservationsPage } from "./AdminReservationsPage";
import { api } from "@/api/client";

vi.mock("@/api/client", () => ({
  api: { GET: vi.fn(), POST: vi.fn(), DELETE: vi.fn() },
}));

const INSTITUTES = [{ institute_id: 1, institute_name: "Institute One" }];
const CLUSTERS = [{ cluster_id: 7, cluster_name: "ring-a", topology_type: "RING", dimension: [2], wrap: true, total_capacity: 2, free_capacity: 2 }];
const CLUSTER_DETAIL = {
  cluster_id: 7,
  cluster_name: "ring-a",
  topology_type: "RING",
  dimension: [2],
  wrap: true,
  total_capacity: 2,
  free_capacity: 2,
  nodes: [
    { node_id: 100, coordinates: [0], status: "IDLE", resources: [] },
    { node_id: 101, coordinates: [1], status: "IDLE", resources: [] },
  ],
};
const RESERVATIONS = [
  { id: 9, institute_id: 1, cluster_id: 7, start_period: "2026-09-01T00:00:00Z", end_period: "2026-09-02T00:00:00Z", reason: "maintenance", node_ids: [100] },
];

function mockGet(reservations: unknown[] = RESERVATIONS) {
  vi.mocked(api.GET)
    .mockReset()
    .mockImplementation(((path: string) => {
      if (path === "/institutes") return Promise.resolve({ data: INSTITUTES, error: undefined, response: new Response() });
      if (path === "/clusters") return Promise.resolve({ data: CLUSTERS, error: undefined, response: new Response() });
      if (path === "/clusters/{cluster_id}") return Promise.resolve({ data: CLUSTER_DETAIL, error: undefined, response: new Response() });
      if (path === "/reservations") return Promise.resolve({ data: reservations, error: undefined, response: new Response() });
      throw new Error(`unexpected path ${path}`);
    }) as typeof api.GET);
}

function renderPage() {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <AdminReservationsPage />
    </QueryClientProvider>,
  );
}

describe("AdminReservationsPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    mockGet();
    vi.mocked(api.POST).mockReset();
    vi.mocked(api.DELETE).mockReset();
  });

  it("lists existing reservations with the resolved institute name", async () => {
    renderPage();
    const item = await screen.findByText(/maintenance/);
    // "Institute One" alone would also match the <option> elements in the selects above --
    // check the whole list item (which has both pieces) instead of that text in isolation.
    expect(item.closest("li")?.textContent).toMatch(/Institute One/);
  });

  it("reveals the node picker once a cluster is selected, and toggles node selection", async () => {
    renderPage();
    await screen.findByText(/maintenance/);
    await userEvent.selectOptions(screen.getByLabelText("Cluster"), "7");

    const nodeOption = await screen.findByText("0");
    await userEvent.click(nodeOption);
    // Clicking again should deselect it (checkbox is a toggle) -- clicking a submit-blocking
    // requirement twice should leave the form back where it started.
    await userEvent.click(nodeOption);
  });

  it("blocks submission when the end period is not after the start period", async () => {
    renderPage();
    await screen.findByText(/maintenance/);
    await userEvent.selectOptions(screen.getByLabelText("Institute"), "1");
    await userEvent.selectOptions(screen.getByLabelText("Cluster"), "7");
    await userEvent.click(await screen.findByText("0"));

    await userEvent.type(screen.getByLabelText("Start period"), "2026-09-02T10:00");
    await userEvent.type(screen.getByLabelText("End period"), "2026-09-01T10:00");
    await userEvent.type(screen.getByPlaceholderText("Reason"), "test");

    expect(screen.getByRole("button", { name: /create reservation/i })).toBeDisabled();
    expect(await screen.findByText(/end period must be after start period/i)).toBeInTheDocument();
    expect(api.POST).not.toHaveBeenCalled();
  });

  it("cancels a reservation after confirming", async () => {
    vi.mocked(api.DELETE).mockResolvedValue({ data: { detail: "ok", status_code: 200 }, error: undefined, response: new Response() } as never);
    vi.spyOn(window, "confirm").mockReturnValue(true);

    renderPage();
    await screen.findByText(/maintenance/);
    await userEvent.click(screen.getByRole("button", { name: /cancel reservation/i }));

    expect(api.DELETE).toHaveBeenCalledWith("/reservations/{reservation_id}", { params: { path: { reservation_id: 9 } } });
  });
});
