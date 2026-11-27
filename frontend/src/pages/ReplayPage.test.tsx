import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes, useParams } from "react-router-dom";
import { expect, it, vi } from "vitest";
import { api } from "@/api/client";
import { ReplayPage } from "./ReplayPage";

vi.mock("@/api/client", () => ({ api: { POST: vi.fn() } }));

function SavedLocation() {
  const { id } = useParams();
  return <p>Saved run {id}</p>;
}

function openReplay() {
  return render(<QueryClientProvider client={new QueryClient()}>
    <MemoryRouter initialEntries={["/replay"]}><Routes>
      <Route path="/replay" element={<ReplayPage />} />
      <Route path="/replay/runs/:id" element={<SavedLocation />} />
    </Routes></MemoryRouter>
  </QueryClientProvider>);
}

it("retries an interrupted save with the same request ID and opens the persisted run", async () => {
  const post = vi.mocked(api.POST);
  post.mockRejectedValueOnce(new Error("Connection lost"));
  post.mockImplementationOnce((async () => ({ data: { id: "saved" }, response: new Response() })) as typeof api.POST);
  openReplay();
  const user = userEvent.setup();
  await user.selectOptions(screen.getByLabelText("Node count"), "2");
  await user.clear(screen.getByLabelText("Node 2 GPUs"));
  await user.type(screen.getByLabelText("Node 2 GPUs"), "4");
  await user.click(screen.getByRole("button", { name: "Run comparison" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Connection lost");
  await user.click(screen.getByRole("button", { name: "Retry comparison" }));
  expect(await screen.findByText("Saved run saved")).toBeVisible();
  expect(post.mock.calls[0]).toEqual(["/replay/runs", {body: {
    request_id: expect.any(String), preset: "oracle", gpus_per_node: [2, 4],
  }}]);
  expect(post.mock.calls[1]).toEqual(post.mock.calls[0]);
});

it("keeps an invalid scenario file out of the replay request", async () => {
  openReplay();
  const user = userEvent.setup();
  await user.selectOptions(screen.getByLabelText("Scenario"), "import");
  await user.upload(screen.getByLabelText("Scenario JSON file"), new File(["{}"], "invalid.json", {type: "application/json"}));
  expect(await screen.findByRole("alert")).toHaveTextContent("compatible replay");
  expect(screen.getByRole("button", {name:"Run comparison"})).toBeDisabled();
});

it("submits the imported trace with its node identifiers and edited GPU capacity", async () => {
  const post = vi.mocked(api.POST);
  post.mockImplementationOnce((async () => ({ data: { id: "imported" }, response: new Response() })) as typeof api.POST);
  openReplay();
  const user = userEvent.setup();
  const scenario = {
    schema_version: 1, source: "Synthetic Slurm import", seconds_per_tick: 1,
    nodes: [{ id: 17, gpus: 2 }],
    jobs: [{id: 1, arrival: 0, duration: 2, gpus: 1, priority: "NORMAL"}],
  };
  await user.selectOptions(screen.getByLabelText("Scenario"), "import");
  await user.upload(screen.getByLabelText("Scenario JSON file"),
    new File([JSON.stringify(scenario)], "scenario.json", {type:"application/json"}));
  const capacity = await screen.findByLabelText("Node 17 GPUs");
  await user.clear(capacity);
  await user.type(capacity, "4");
  await user.click(screen.getByRole("button", {name:"Run comparison"}));
  expect(await screen.findByText("Saved run imported")).toBeVisible();
  expect(post).toHaveBeenLastCalledWith("/replay/runs", {body: {request_id: expect.any(String), scenario, gpus_per_node: [4]}});
});
