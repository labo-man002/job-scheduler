import { describe, expect, it } from "vitest";
import { buildEdges, buildWrapGhosts, coordKey, depthOf, neighborCoords, originNode, project3D } from "./topologyMath";

function grid(dimension: number[]) {
  const nodes: { coordinates: number[] }[] = [];
  function recurse(axis: number, current: number[]) {
    if (axis === dimension.length) {
      nodes.push({ coordinates: [...current] });
      return;
    }
    for (let i = 0; i < dimension[axis]; i++) {
      current.push(i);
      recurse(axis + 1, current);
      current.pop();
    }
  }
  recurse(0, []);
  return nodes;
}

describe("neighborCoords", () => {
  it("steps within bounds", () => {
    expect(neighborCoords([1, 1], [3, 3], false, 0, 1)).toEqual([2, 1]);
    expect(neighborCoords([1, 1], [3, 3], false, 1, -1)).toEqual([1, 0]);
  });

  it("returns null past the edge when not wrapping", () => {
    expect(neighborCoords([0, 1], [3, 3], false, 0, -1)).toBeNull();
    expect(neighborCoords([2, 1], [3, 3], false, 0, 1)).toBeNull();
  });

  it("wraps around past the edge when wrapping", () => {
    expect(neighborCoords([0, 1], [3, 3], true, 0, -1)).toEqual([2, 1]);
    expect(neighborCoords([2, 1], [3, 3], true, 0, 1)).toEqual([0, 1]);
  });
});

describe("buildEdges", () => {
  it("finds all 4 edges of a 2x2 grid", () => {
    const edges = buildEdges(grid([2, 2]), 2);
    expect(edges).toHaveLength(4);
  });

  it("finds all 12 edges of a 2x2x2 cube", () => {
    const edges = buildEdges(grid([2, 2, 2]), 3);
    expect(edges).toHaveLength(12);
  });

  it("finds all edges of a 3x3 grid (2 per interior connection, 12 undirected total)", () => {
    // 3x3 grid: 2 horizontal edges per row * 3 rows + 2 vertical edges per column * 3 columns = 12
    const edges = buildEdges(grid([3, 3]), 2);
    expect(edges).toHaveLength(12);
  });

  it("never connects two nodes that differ on more than one axis", () => {
    const edges = buildEdges(grid([3, 3]), 2);
    for (const { from, to } of edges) {
      const diffAxes = from.coordinates.filter((c, i) => c !== to.coordinates[i]).length;
      expect(diffAxes).toBe(1);
    }
  });
});

describe("buildWrapGhosts", () => {
  it("produces x, y, and corner ghosts for a 3x3 grid when combinatorial shifts are allowed", () => {
    const { ghosts, connectors } = buildWrapGhosts(grid([3, 3]), [3, 3], 2);
    expect(ghosts).toHaveLength(7); // 3 x-ghosts + 3 y-ghosts + 1 corner ghost
    expect(connectors).toHaveLength(6); // corner ghost gets no connector, only single-axis ghosts do

    const cornerGhost = ghosts.find((g) => coordKey(g.coords) === coordKey([3, 3]));
    expect(cornerGhost).toBeDefined();
    expect(coordKey(cornerGhost!.node.coordinates)).toBe(coordKey([0, 0]));
  });

  it("caps ghosts to single-axis shifts when maxShiftAxes is 1 (no corner ghost)", () => {
    const { ghosts, connectors } = buildWrapGhosts(grid([3, 3]), [3, 3], 1);
    expect(ghosts).toHaveLength(6); // 3 x-ghosts + 3 y-ghosts, no corner
    expect(connectors).toHaveLength(6);
    expect(ghosts.some((g) => coordKey(g.coords) === coordKey([3, 3]))).toBe(false);
  });

  it("skips ghosting on an axis of width 1 (no self-referencing wrap)", () => {
    const { ghosts, connectors } = buildWrapGhosts(grid([1, 3]), [1, 3], 2);
    // the width-1 axis contributes nothing; only the width-3 axis's 1 zero-coordinate node ghosts
    expect(ghosts).toHaveLength(1);
    expect(connectors).toHaveLength(1);
  });

  it("returns nothing for a non-wrapping cluster (caller's responsibility to check wrap)", () => {
    const { ghosts, connectors } = buildWrapGhosts([], [3, 3], 2);
    expect(ghosts).toHaveLength(0);
    expect(connectors).toHaveLength(0);
  });

  it("generalizes to 3 axes with single-axis shifts", () => {
    const { ghosts, connectors } = buildWrapGhosts(grid([2, 2, 2]), [2, 2, 2], 1);
    // each of the 8 corners of a 2x2x2 cube has all 3 coords in {0,1}; nodes with a 0 on
    // some axis get one single-axis ghost per zero axis they have.
    // (0,0,0) has 3 zero axes -> 3 ghosts; (0,0,1),(0,1,0),(1,0,0) have 2 each -> 2 ghosts each;
    // (0,1,1),(1,0,1),(1,1,0) have 1 each -> 1 ghost each; (1,1,1) has 0 -> 0 ghosts.
    expect(ghosts).toHaveLength(3 + 2 * 3 + 1 * 3);
    expect(connectors.length).toBe(ghosts.length); // every single-axis ghost in a full cube has a boundary neighbor
  });
});

describe("project3D", () => {
  // Regression test for a real bug caught in review: increasing axis 1 must move the
  // projected point DOWN the screen (larger y), matching Grid2D's ArrowDown convention
  // (coords[1] * STEP, also increasing). The initial isometric formula had this inverted,
  // making ArrowUp/ArrowDown feel backwards specifically in the 3D lattice view.
  it("moves down-screen (increasing y) as axis 1 increases, matching the 2D grid's convention", () => {
    const a = project3D([0, 0, 0], 40);
    const b = project3D([0, 1, 0], 40);
    expect(b.y).toBeGreaterThan(a.y);
  });

  it("keeps x and z projecting onto the same axis when equal (they cancel out)", () => {
    const p = project3D([2, 0, 2], 40);
    expect(p.x).toBeCloseTo(0);
  });
});

describe("depthOf", () => {
  it("sums coordinates as a painter's-algorithm depth proxy", () => {
    expect(depthOf([1, 2, 3])).toBe(6);
    expect(depthOf([0, 0, 0])).toBe(0);
  });
});

describe("originNode", () => {
  it("picks the all-zero-coordinate node regardless of input order", () => {
    const nodes = [{ coordinates: [1, 1] }, { coordinates: [0, 0] }, { coordinates: [2, 0] }];
    expect(originNode(nodes)?.coordinates).toEqual([0, 0]);
  });

  it("falls back to numeric lexicographic order when there's no exact origin", () => {
    const nodes = [{ coordinates: [1, 5] }, { coordinates: [1, 2] }, { coordinates: [2, 0] }];
    expect(originNode(nodes)?.coordinates).toEqual([1, 2]);
  });

  it("returns undefined for an empty node list", () => {
    expect(originNode([])).toBeUndefined();
  });
});
