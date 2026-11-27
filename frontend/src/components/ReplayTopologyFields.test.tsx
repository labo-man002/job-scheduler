import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { expect, it } from "vitest";
import { ReplayTopologyFields } from "./ReplayTopologyFields";
import { resizeReplayTopology, type ReplayTopology } from "@/lib/replayTopology";

function FabricEditor() {
  const [value, setValue] = useState<ReplayTopology>({ kind: "linear" });
  return <ReplayTopologyFields nodeIds={[17, 24, 42]} value={value} onChange={setValue} />;
}

it("can change node attachments and disconnect and restore a leaf uplink", async () => {
  render(<FabricEditor />);
  const user = userEvent.setup();
  await user.selectOptions(screen.getByLabelText("Topology"), "leaf_spine");
  const uplink = screen.getByLabelText("Leaf 2 to spine 1");
  const attachment = screen.getByLabelText("Node 24 leaf");
  expect(uplink).toBeChecked();
  expect(attachment).toHaveValue("2");

  await user.click(uplink);
  await user.selectOptions(attachment, "1");
  expect(uplink).not.toBeChecked();
  expect(attachment).toHaveValue("1");

  await user.click(screen.getByRole("button", { name: "Restore fabric preset" }));
  expect(uplink).toBeChecked();
  expect(attachment).toHaveValue("2");
});

it("retains attachments for existing IDs when a saved fabric is resized", () => {
  expect(resizeReplayTopology({
    kind: "leaf_spine",
    leaves: [2, 3],
    uplinks: [{ leaf: 2, spine: 1 }],
    attachments: [{ node: 17, leaf: 3 }, { node: 24, leaf: 2 }],
  }, [17, 42])).toEqual({
    kind: "leaf_spine",
    leaves: [2, 3],
    uplinks: [{ leaf: 2, spine: 1 }],
    attachments: [{ node: 17, leaf: 3 }, { node: 42, leaf: 3 }],
  });
});
