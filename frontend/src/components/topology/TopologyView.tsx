import { useMemo } from "react";
import type { components } from "@/api/schema.d.ts";
import { NODE_STATUS_COLOR, NODE_STATUS_ORDER } from "@/lib/nodeStatus";
import {
  buildEdges,
  buildWrapGhosts,
  coordKey,
  depthOf,
  neighborCoords,
  nodeTitle,
  nodesByCoordKey,
  originNode,
  project3D,
} from "@/lib/topologyMath";

type NodeOut = components["schemas"]["NodeOut"];

const CELL = 56;
const GAP = 7;
const STEP = CELL + GAP;
const GHOST_OPACITY = 0.3;
const EDGE_COLOR = "#94a3b8";

interface TopologyViewProps {
  dimension: number[];
  wrap: boolean;
  nodes: NodeOut[];
  selectedNodeId: number | null;
  onSelectNode: (node: NodeOut | null) => void;
}

function NodeBox({
  node,
  x,
  y,
  selected,
  onSelect,
}: {
  node: NodeOut;
  x: number;
  y: number;
  selected: boolean;
  onSelect: () => void;
}) {
  const color = NODE_STATUS_COLOR[node.status];
  return (
    <g transform={`translate(${x}, ${y})`} onClick={onSelect} className="cursor-pointer">
      <title>{nodeTitle(node)}</title>
      <rect
        width={CELL}
        height={CELL}
        fill={color.fill}
        stroke={selected ? "#0f172a" : color.border}
        strokeWidth={selected ? 2 : 1}
      />
      <text
        x={CELL / 2}
        y={CELL / 2}
        textAnchor="middle"
        dominantBaseline="middle"
        fill={color.text}
        className="select-none font-mono text-[11px]"
      >
        {node.coordinates.join(",")}
      </text>
    </g>
  );
}

function GhostBox({ node, x, y }: { node: NodeOut; x: number; y: number }) {
  const color = NODE_STATUS_COLOR[node.status];
  return (
    <g transform={`translate(${x}, ${y})`} opacity={GHOST_OPACITY} className="pointer-events-none">
      <rect width={CELL} height={CELL} fill={color.fill} stroke={color.border} strokeWidth={1} />
    </g>
  );
}

export function StatusLegend() {
  return (
    <div className="flex items-center gap-4 text-xs text-muted-foreground">
      {NODE_STATUS_ORDER.map((status) => (
        <div key={status} className="flex items-center gap-1.5">
          <span className="inline-block h-2.5 w-2.5" style={{ backgroundColor: NODE_STATUS_COLOR[status].fill }} />
          {NODE_STATUS_COLOR[status].label}
        </div>
      ))}
    </div>
  );
}

function Ring({
  nodes,
  dimension,
  wrap,
  selectedNodeId,
  onSelectNode,
}: {
  nodes: NodeOut[];
  dimension: number[];
  wrap: boolean;
  selectedNodeId: number | null;
  onSelectNode: (node: NodeOut) => void;
}) {
  const sorted = [...nodes].sort((a, b) => a.coordinates[0] - b.coordinates[0]);

  if (!wrap) {
    const width = sorted.length * STEP;
    return (
      <svg width={width} height={CELL} className="overflow-visible">
        <g>
          {sorted.slice(0, -1).map((node, i) => (
            <line key={node.node_id} x1={i * STEP + CELL} y1={CELL / 2} x2={(i + 1) * STEP} y2={CELL / 2} stroke={EDGE_COLOR} strokeWidth={1} />
          ))}
        </g>
        <g>
          {sorted.map((node, i) => (
            <NodeBox key={node.node_id} node={node} x={i * STEP} y={0} selected={node.node_id === selectedNodeId} onSelect={() => onSelectNode(node)} />
          ))}
        </g>
      </svg>
    );
  }

  const n = dimension[0];
  const radius = Math.max(60, (n * STEP) / (2 * Math.PI));
  const size = radius * 2 + CELL * 2;
  const center = size / 2;
  const positions = sorted.map((node, i) => {
    const angle = (2 * Math.PI * i) / n - Math.PI / 2;
    return { node, cx: center + radius * Math.cos(angle), cy: center + radius * Math.sin(angle) };
  });

  return (
    <svg width={size} height={size} className="overflow-visible">
      <g>
        {positions.map((p, i) => {
          const next = positions[(i + 1) % n];
          return <line key={p.node.node_id} x1={p.cx} y1={p.cy} x2={next.cx} y2={next.cy} stroke={EDGE_COLOR} strokeWidth={1} />;
        })}
      </g>
      <g>
        {positions.map(({ node, cx, cy }) => (
          <NodeBox key={node.node_id} node={node} x={cx - CELL / 2} y={cy - CELL / 2} selected={node.node_id === selectedNodeId} onSelect={() => onSelectNode(node)} />
        ))}
      </g>
    </svg>
  );
}

function Grid2D({
  nodes,
  dimension,
  wrap,
  selectedNodeId,
  onSelectNode,
}: {
  nodes: NodeOut[];
  dimension: number[];
  wrap: boolean;
  selectedNodeId: number | null;
  onSelectNode: (node: NodeOut) => void;
}) {
  const edges = useMemo(() => buildEdges(nodes, 2), [nodes]);
  const { ghosts, connectors } = useMemo(() => (wrap ? buildWrapGhosts(nodes, dimension, 2) : { ghosts: [], connectors: [] }), [nodes, dimension, wrap]);

  const pos = (coords: number[]) => ({ x: coords[0] * STEP, y: coords[1] * STEP });
  const extraX = wrap && dimension[0] > 1 ? 1 : 0;
  const extraY = wrap && dimension[1] > 1 ? 1 : 0;
  const width = (dimension[0] + extraX) * STEP;
  const height = (dimension[1] + extraY) * STEP;

  return (
    <svg width={width} height={height} className="overflow-visible">
      <g>
        {edges.map(({ from, to }) => {
          const a = pos(from.coordinates);
          const b = pos(to.coordinates);
          return <line key={`${from.node_id}-${to.node_id}`} x1={a.x + CELL / 2} y1={a.y + CELL / 2} x2={b.x + CELL / 2} y2={b.y + CELL / 2} stroke={EDGE_COLOR} strokeWidth={1} />;
        })}
        {connectors.map((c, i) => {
          const a = pos(c.from);
          const b = pos(c.to);
          return <line key={i} x1={a.x + CELL / 2} y1={a.y + CELL / 2} x2={b.x + CELL / 2} y2={b.y + CELL / 2} stroke={EDGE_COLOR} strokeWidth={1} strokeDasharray="3 3" />;
        })}
      </g>
      <g>
        {ghosts.map(({ node, coords }, i) => {
          const p = pos(coords);
          return <GhostBox key={i} node={node} x={p.x} y={p.y} />;
        })}
      </g>
      <g>
        {nodes.map((node) => {
          const p = pos(node.coordinates);
          return <NodeBox key={node.node_id} node={node} x={p.x} y={p.y} selected={node.node_id === selectedNodeId} onSelect={() => onSelectNode(node)} />;
        })}
      </g>
    </svg>
  );
}

const ISO_UNIT = STEP;

function Lattice3D({
  nodes,
  dimension,
  wrap,
  selectedNodeId,
  onSelectNode,
}: {
  nodes: NodeOut[];
  dimension: number[];
  wrap: boolean;
  selectedNodeId: number | null;
  onSelectNode: (node: NodeOut) => void;
}) {
  const edges = useMemo(() => buildEdges(nodes, 3), [nodes]);
  const { ghosts, connectors } = useMemo(() => (wrap ? buildWrapGhosts(nodes, dimension, 1) : { ghosts: [], connectors: [] }), [nodes, dimension, wrap]);

  const positions = useMemo(() => {
    const map = new Map<string, { x: number; y: number }>();
    for (const node of nodes) map.set(coordKey(node.coordinates), project3D(node.coordinates, ISO_UNIT));
    for (const { coords } of ghosts) map.set(coordKey(coords), project3D(coords, ISO_UNIT));
    return map;
  }, [nodes, ghosts]);

  // Rendered in one depth-sorted pass (not ghosts-then-real) so painter's-algorithm
  // occlusion is correct even when a ghost (coordinate == dimension[axis], one step
  // past every real node on that axis) is actually nearer the viewer than some real node.
  const depthSorted = useMemo(() => {
    const real = nodes.map((node) => ({ kind: "real" as const, node, coords: node.coordinates }));
    const ghost = ghosts.map((g) => ({ kind: "ghost" as const, node: g.node, coords: g.coords }));
    return [...real, ...ghost].sort((a, b) => depthOf(a.coords) - depthOf(b.coords));
  }, [nodes, ghosts]);

  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  for (const p of positions.values()) {
    if (p.x < minX) minX = p.x;
    if (p.x > maxX) maxX = p.x;
    if (p.y < minY) minY = p.y;
    if (p.y > maxY) maxY = p.y;
  }
  const offsetX = -minX + CELL;
  const offsetY = -minY + CELL;
  const width = maxX - minX + CELL * 3;
  const height = maxY - minY + CELL * 3;

  const at = (coords: number[]) => {
    const p = positions.get(coordKey(coords))!;
    return { x: p.x + offsetX, y: p.y + offsetY };
  };

  return (
    <svg width={width} height={height} className="overflow-visible">
      <g>
        {edges.map(({ from, to }, i) => {
          const a = at(from.coordinates);
          const b = at(to.coordinates);
          return <line key={i} x1={a.x + CELL / 2} y1={a.y + CELL / 2} x2={b.x + CELL / 2} y2={b.y + CELL / 2} stroke={EDGE_COLOR} strokeWidth={1} />;
        })}
        {connectors.map((c, i) => {
          const a = at(c.from);
          const b = at(c.to);
          return <line key={i} x1={a.x + CELL / 2} y1={a.y + CELL / 2} x2={b.x + CELL / 2} y2={b.y + CELL / 2} stroke={EDGE_COLOR} strokeWidth={1} strokeDasharray="3 3" />;
        })}
      </g>
      <g>
        {depthSorted.map((entry, i) => {
          const p = at(entry.coords);
          return entry.kind === "ghost" ? (
            <GhostBox key={`ghost-${i}`} node={entry.node} x={p.x} y={p.y} />
          ) : (
            <NodeBox
              key={`node-${entry.node.node_id}`}
              node={entry.node}
              x={p.x}
              y={p.y}
              selected={entry.node.node_id === selectedNodeId}
              onSelect={() => onSelectNode(entry.node)}
            />
          );
        })}
      </g>
    </svg>
  );
}

export function TopologyView({ dimension, wrap, nodes, selectedNodeId, onSelectNode }: TopologyViewProps) {
  const axisCount = dimension.length;
  const nodesByKey = useMemo(() => nodesByCoordKey(nodes), [nodes]);

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Escape") {
      onSelectNode(null);
      return;
    }
    if (selectedNodeId == null) {
      // Escape (or simply never having clicked a node) leaves the container focused
      // with no selection -- onFocus won't fire again without an actual blur/refocus,
      // so seed one here too rather than leaving arrow keys dead until then.
      const first = originNode(nodes);
      if (first) onSelectNode(first);
      return;
    }
    const current = nodes.find((n) => n.node_id === selectedNodeId);
    if (!current) return;

    const moves: Record<string, [number, 1 | -1]> = {
      ArrowLeft: [0, -1],
      ArrowRight: [0, 1],
      ArrowUp: [1, -1],
      ArrowDown: [1, 1],
      "[": [2, -1],
      "]": [2, 1],
    };
    const move = moves[e.key];
    if (!move || move[0] >= axisCount) return;
    e.preventDefault();

    const [axis, delta] = move;
    const coords = neighborCoords(current.coordinates, dimension, wrap, axis, delta);
    if (!coords) return;
    const neighbor = nodesByKey.get(coordKey(coords));
    if (neighbor) onSelectNode(neighbor);
  }

  // A keyboard-only user has no per-node focusable element to land on (nodes are plain
  // SVG rects, not buttons) -- without this, tabbing to the container and pressing arrow
  // keys would do nothing forever, since handleKeyDown requires a selection to move from.
  function handleFocus() {
    if (selectedNodeId == null) {
      const first = originNode(nodes);
      if (first) onSelectNode(first);
    }
  }

  const select = (node: NodeOut) => onSelectNode(node);
  const selected = selectedNodeId == null ? null : (nodes.find((n) => n.node_id === selectedNodeId) ?? null);

  return (
    <div
      tabIndex={0}
      onKeyDown={handleKeyDown}
      onFocus={handleFocus}
      role="application"
      aria-label="cluster topology -- arrow keys move between nodes, Escape clears selection"
      className="inline-block rounded-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      <div aria-live="polite" className="sr-only">
        {selected ? nodeTitle(selected) : "no node selected"}
      </div>
      {axisCount === 1 && <Ring nodes={nodes} dimension={dimension} wrap={wrap} selectedNodeId={selectedNodeId} onSelectNode={select} />}
      {axisCount === 2 && <Grid2D nodes={nodes} dimension={dimension} wrap={wrap} selectedNodeId={selectedNodeId} onSelectNode={select} />}
      {axisCount >= 3 && <Lattice3D nodes={nodes} dimension={dimension} wrap={wrap} selectedNodeId={selectedNodeId} onSelectNode={select} />}
    </div>
  );
}
