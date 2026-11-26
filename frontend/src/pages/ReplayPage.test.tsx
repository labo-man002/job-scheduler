import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { expect, it, vi } from "vitest";
import { api } from "@/api/client";
import { ReplayPage } from "./ReplayPage";

vi.mock("@/api/client", () => ({ api: { GET: vi.fn() } }));

it("runs the selected scenario and clears results when the scenario changes", async () => {
  const metrics = { occupancy: 0.5, completed: 1, unscheduled: 0, makespan_ticks_from_zero: 3, completed_jobs_per_hour: 20 };
  vi.mocked(api.GET).mockImplementation((async () => ({
    data: { source: "Synthetic test", seconds_per_tick: 60, fifo: metrics, priority: metrics, jobs: [] },
    response: new Response(),
  })) as typeof api.GET);
  render(<QueryClientProvider client={new QueryClient()}><ReplayPage /></QueryClientProvider>);
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "Run comparison" }));
  expect(await screen.findByRole("region", { name: "Comparison results" })).toBeInTheDocument();
  expect(api.GET).toHaveBeenCalledWith("/replay/{scenario_name}", { params: { path: { scenario_name: "oracle" } } });
  await user.selectOptions(screen.getByLabelText("Scenario"), "contention");
  expect(screen.queryByRole("region", { name: "Comparison results" })).toBeNull();
});
