export function coordKey(coords: number[]) {
  return coords.join(",");
}

function mod(n: number, m: number): number {
  return ((n % m) + m) % m;
}

// Deterministic "first" node for a cluster -- the one at the origin (all-zero
// coordinates), falling back to numeric (not string) lexicographic order on the
// off chance a cluster has no node at the exact origin.
export function originNode<T extends { coordinates: number[] }>(nodes: T[]): T | undefined {
  return [...nodes].sort((a, b) => {
    for (let i = 0; i < a.coordinates.length; i++) {
      if (a.coordinates[i] !== b.coordinates[i]) return a.coordinates[i] - b.coordinates[i];
    }
    return 0;
  })[0];
}

export function nodesByCoordKey<T extends { coordinates: number[] }>(nodes: T[]): Map<string, T> {
  const map = new Map<string, T>();
  for (const node of nodes) map.set(coordKey(node.coordinates), node);
  return map;
}

// Coordinates one step away from `coords` along `axis`, respecting wrap. Returns null
// when the step runs off the edge of a non-wrapping cluster -- used by keyboard nav to
// know when there's nowhere to go.
export function neighborCoords(coords: number[], dimension: number[], wrap: boolean, axis: number, delta: 1 | -1): number[] | null {
  const next = [...coords];
  const raw = next[axis] + delta;
  if (raw < 0 || raw >= dimension[axis]) {
    if (!wrap) return null;
    next[axis] = mod(raw, dimension[axis]);
  } else {
    next[axis] = raw;
  }
  return next;
}

// Real structural edges: pairs of nodes whose coordinates differ by exactly 1 along
// exactly one axis. Generalizes across any axis count (a 2D grid and a 3D lattice use
// the same rule), and is deliberately blind to wrap -- wrap connectivity is a separate,
// visually distinct concern handled by buildWrapGhosts below.
export function buildEdges<T extends { coordinates: number[] }>(nodes: T[], axisCount: number): { from: T; to: T }[] {
  const byKey = nodesByCoordKey(nodes);
  const edges: { from: T; to: T }[] = [];
  for (const node of byKey.values()) {
    for (let axis = 0; axis < axisCount; axis++) {
      const coords = [...node.coordinates];
      coords[axis] += 1;
      const neighbor = byKey.get(coordKey(coords));
      if (neighbor) edges.push({ from: node, to: neighbor });
    }
  }
  return edges;
}

interface WrapGhost<T> {
  node: T;
  coords: number[];
}

interface WrapConnector {
  from: number[];
  to: number[];
}

// Torus wrap: for every node sitting at coordinate 0 on some axis, echo it one step past
// the far edge of that axis (dimension[axis]) at reduced opacity, plus a connector back to
// the real boundary node -- shows exactly where the topology wraps to instead of a caption
// saying so. maxShiftAxes caps how many axes a single ghost may be shifted on at once: 2D
// grids use every combination (so a corner node gets an x-ghost, a y-ghost, and one
// diagonal corner-ghost) since that's only ever at most 3 extra nodes; a 3D lattice caps
// it at 1 to avoid a combinatorial (up to 7x) explosion of ghost nodes per corner.
export function buildWrapGhosts<T extends { coordinates: number[] }>(
  nodes: T[],
  dimension: number[],
  maxShiftAxes: number,
): { ghosts: WrapGhost<T>[]; connectors: WrapConnector[] } {
  const byKey = nodesByCoordKey(nodes);
  const axisCount = dimension.length;
  const ghosts: WrapGhost<T>[] = [];
  const connectors: WrapConnector[] = [];

  for (const node of nodes) {
    const zeroAxes: number[] = [];
    for (let axis = 0; axis < axisCount; axis++) {
      if (node.coordinates[axis] === 0 && dimension[axis] > 1) zeroAxes.push(axis);
    }

    const limit = Math.min(maxShiftAxes, zeroAxes.length);
    const subsets: number[][] = [];
    (function recurse(start: number, current: number[]) {
      if (current.length > 0) subsets.push([...current]);
      if (current.length === limit) return;
      for (let i = start; i < zeroAxes.length; i++) {
        current.push(zeroAxes[i]);
        recurse(i + 1, current);
        current.pop();
      }
    })(0, []);

    for (const axes of subsets) {
      const coords = [...node.coordinates];
      for (const axis of axes) coords[axis] = dimension[axis];
      ghosts.push({ node, coords });

      if (axes.length === 1) {
        const axis = axes[0];
        const boundary = [...node.coordinates];
        boundary[axis] = dimension[axis] - 1;
        if (byKey.has(coordKey(boundary))) connectors.push({ from: boundary, to: coords });
      }
    }
  }

  return { ghosts, connectors };
}

const ISO_COS30 = Math.cos(Math.PI / 6);
const ISO_SIN30 = Math.sin(Math.PI / 6);

// Isometric projection of a 3-axis coordinate to a 2D screen point, `unit` pixels per
// grid step. +y (axis 1) must move the point DOWN on screen (not up, despite the usual
// isometric convention of treating the 2nd axis as "height") -- this axis has no
// up/down meaning here, it's just another grid axis, so it must move the same screen
// direction as ArrowDown/axis-1 in the 2D grid view for keyboard nav to feel consistent
// between the 2D and 3D views.
export function project3D(coords: number[], unit: number) {
  const [x, y, z] = coords;
  return {
    x: (x - z) * ISO_COS30 * unit,
    y: (x + z) * ISO_SIN30 * unit + y * unit,
  };
}

export function depthOf(coords: number[]) {
  return coords.reduce((sum, c) => sum + c, 0);
}

interface NodeLike {
  node_id: number;
  coordinates: number[];
  status: string;
  resources: { resource_type: string; free: number; total: number }[];
}

export function nodeTitle(node: NodeLike) {
  const resources = node.resources.map((r) => `${r.resource_type} ${r.free}/${r.total}`).join(", ");
  return `node ${node.node_id} [${node.coordinates.join(",")}] ${node.status} -- ${resources}`;
}
