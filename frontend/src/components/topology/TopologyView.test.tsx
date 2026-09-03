import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { components } from "@/api/schema.d.ts";
import { TopologyView } from "./TopologyView";

type NodeOut = components["schemas"]["NodeOut"];

function makeNode(node_id: number, coordinates: number[]): NodeOut {
  return {
    node_id,
    coordinates,
    status: "IDLE",
    resources: [{ resource_type: "CPU", total: 4, free: 4 }],
  };
}

// A 2x2 grid: (0,0)=1, (1,0)=2, (0,1)=3, (1,1)=4
function make2x2Grid(): NodeOut[] {
  return [makeNode(1, [0, 0]), makeNode(2, [1, 0]), makeNode(3, [0, 1]), makeNode(4, [1, 1])];
}

describe("TopologyView", () => {
  it("labels every node by its coordinates, not its id", () => {
    render(<TopologyView dimension={[2, 2]} wrap={false} nodes={make2x2Grid()} selectedNodeId={null} onSelectNode={vi.fn()} />);
    for (const coords of ["0,0", "1,0", "0,1", "1,1"]) expect(screen.getByText(coords)).toBeInTheDocument();
  });

  it("calls onSelectNode with the clicked node", async () => {
    const onSelectNode = vi.fn();
    render(<TopologyView dimension={[2, 2]} wrap={false} nodes={make2x2Grid()} selectedNodeId={null} onSelectNode={onSelectNode} />);
    await userEvent.click(screen.getByText("0,1")); // node 3 is at [0,1]
    expect(onSelectNode).toHaveBeenCalledWith(expect.objectContaining({ node_id: 3 }));
  });

  it("seeds a selection at the origin node when the container is focused with nothing selected", () => {
    const onSelectNode = vi.fn();
    const { container } = render(
      <TopologyView dimension={[2, 2]} wrap={false} nodes={make2x2Grid()} selectedNodeId={null} onSelectNode={onSelectNode} />,
    );
    const region = container.querySelector('[role="application"]') as HTMLElement;
    region.focus();
    expect(onSelectNode).toHaveBeenCalledWith(expect.objectContaining({ node_id: 1 })); // node at [0,0]
  });

  it("moves selection to the structurally-adjacent node on ArrowRight/ArrowDown", async () => {
    const onSelectNode = vi.fn();
    const { container, rerender } = render(
      <TopologyView dimension={[2, 2]} wrap={false} nodes={make2x2Grid()} selectedNodeId={1} onSelectNode={onSelectNode} />,
    );
    const region = container.querySelector('[role="application"]') as HTMLElement;
    region.focus();

    await userEvent.keyboard("{ArrowRight}");
    expect(onSelectNode).toHaveBeenLastCalledWith(expect.objectContaining({ node_id: 2 })); // [0,0] -> [1,0]

    rerender(<TopologyView dimension={[2, 2]} wrap={false} nodes={make2x2Grid()} selectedNodeId={2} onSelectNode={onSelectNode} />);
    await userEvent.keyboard("{ArrowDown}");
    expect(onSelectNode).toHaveBeenLastCalledWith(expect.objectContaining({ node_id: 4 })); // [1,0] -> [1,1]
  });

  it("does not move past the edge of a non-wrapping cluster", async () => {
    const onSelectNode = vi.fn();
    const { container } = render(
      <TopologyView dimension={[2, 2]} wrap={false} nodes={make2x2Grid()} selectedNodeId={1} onSelectNode={onSelectNode} />,
    );
    const region = container.querySelector('[role="application"]') as HTMLElement;
    region.focus();

    await userEvent.keyboard("{ArrowLeft}"); // node 1 is at [0,0]; no neighbor to the left
    expect(onSelectNode).not.toHaveBeenCalled();
  });

  it("wraps to the opposite edge when the cluster wraps", async () => {
    const onSelectNode = vi.fn();
    const { container } = render(
      <TopologyView dimension={[2, 2]} wrap={true} nodes={make2x2Grid()} selectedNodeId={1} onSelectNode={onSelectNode} />,
    );
    const region = container.querySelector('[role="application"]') as HTMLElement;
    region.focus();

    await userEvent.keyboard("{ArrowLeft}"); // node 1 is at [0,0]; wraps to [1,0] = node 2
    expect(onSelectNode).toHaveBeenLastCalledWith(expect.objectContaining({ node_id: 2 }));
  });

  it("clears the selection on Escape", async () => {
    const onSelectNode = vi.fn();
    const { container } = render(
      <TopologyView dimension={[2, 2]} wrap={false} nodes={make2x2Grid()} selectedNodeId={1} onSelectNode={onSelectNode} />,
    );
    const region = container.querySelector('[role="application"]') as HTMLElement;
    region.focus();

    await userEvent.keyboard("{Escape}");
    expect(onSelectNode).toHaveBeenCalledWith(null);
  });

  it("ignores a 3rd-axis key ('[' / ']') when the cluster only has 2 axes", async () => {
    const onSelectNode = vi.fn();
    const { container } = render(
      <TopologyView dimension={[2, 2]} wrap={false} nodes={make2x2Grid()} selectedNodeId={1} onSelectNode={onSelectNode} />,
    );
    const region = container.querySelector('[role="application"]') as HTMLElement;
    region.focus();

    await userEvent.keyboard("[["); // "[[" types a literal "[" -- user-event's keyboard() syntax reserves a bare "["
    expect(onSelectNode).not.toHaveBeenCalled();
  });
});
