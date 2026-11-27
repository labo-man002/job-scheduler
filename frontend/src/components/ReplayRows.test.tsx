import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it } from "vitest";
import { ReplayRows } from "./ReplayRows";

it("bounds the rendered ledger and makes every event reachable", async () => {
  const rows = Array.from({ length: 101 }, (_, i) => i + 1);
  render(<ReplayRows rows={rows} label="Events">{visible => <ol>
    {visible.map(i => <li key={i}>Event {i}</li>)}
  </ol>}</ReplayRows>);
  const user = userEvent.setup();
  expect(screen.getAllByRole("listitem")).toHaveLength(50);
  await user.click(screen.getByRole("button", { name: "Next" }));
  expect(screen.getByText("Event 51")).toBeVisible();
  await user.click(screen.getByRole("button", { name: "Next" }));
  expect(screen.getAllByRole("listitem")).toHaveLength(1);
  expect(screen.getByText("Event 101")).toBeVisible();
  expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
});
