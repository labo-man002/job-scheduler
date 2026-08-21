import { useEffect, useMemo, useRef, useState } from "react";
import { Canvas, type ThreeEvent, useFrame, useThree } from "@react-three/fiber";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import type { components } from "@/api/schema.d.ts";
import { NODE_STATUS_COLOR } from "@/lib/nodeStatus";
import { buildEdges, buildWrapGhosts, nodeTitle } from "@/lib/topologyMath";

type NodeOut = components["schemas"]["NodeOut"];

const UNIT = 1.4;
const NODE_SIZE = 0.85;
const EDGE_COLOR = "#94a3b8";
const SELECTED_OUTLINE_COLOR = "#0f172a";

// Shared across every cube instance -- there's no reason for each node to allocate its
// own geometry when they're all the same size.
const NODE_GEOMETRY = new THREE.BoxGeometry(NODE_SIZE, NODE_SIZE, NODE_SIZE);
const SELECTED_OUTLINE_GEOMETRY = new THREE.EdgesGeometry(NODE_GEOMETRY);

function worldPos(coords: number[], dimension: number[]): [number, number, number] {
  const p = coords.map((c, i) => (c - (dimension[i] - 1) / 2) * UNIT);
  return [p[0] ?? 0, p[1] ?? 0, p[2] ?? 0];
}

// Hand-rolled instead of pulling in @react-three/drei just for OrbitControls --
// avoids a large dependency for one helper.
function Controls() {
  const { camera, gl } = useThree();
  const controlsRef = useRef<OrbitControls | null>(null);

  useEffect(() => {
    const controls = new OrbitControls(camera, gl.domElement);
    controls.enableDamping = false; // direct response, not floaty -- stays consistent with the flat/technical rest of the UI
    controlsRef.current = controls;
    return () => controls.dispose();
  }, [camera, gl]);

  useFrame(() => controlsRef.current?.update());
  return null;
}

function Edge({ from, to, dashed = false }: { from: [number, number, number]; to: [number, number, number]; dashed?: boolean }) {
  const ref = useRef<THREE.Line>(null);
  const geometry = useMemo(() => new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(...from), new THREE.Vector3(...to)]), [from, to]);

  // Not JSX-managed (it's constructed imperatively above), so R3F won't auto-dispose it
  // when `geometry` is replaced by a new useMemo result -- do it ourselves, or every
  // cluster switch leaks the previous cluster's edge geometries.
  useEffect(() => () => geometry.dispose(), [geometry]);

  useEffect(() => {
    if (dashed) ref.current?.computeLineDistances();
  }, [dashed, geometry]);

  return (
    // @ts-expect-error -- R3F's <line> JSX element name collides with the DOM <line> type; this is the three.js Line object.
    <line ref={ref} geometry={geometry}>
      {dashed ? <lineDashedMaterial color={EDGE_COLOR} dashSize={0.15} gapSize={0.12} /> : <lineBasicMaterial color={EDGE_COLOR} />}
    </line>
  );
}

function NodeCube({
  node,
  dimension,
  selected,
  onSelect,
  onHover,
  onUnhover,
}: {
  node: NodeOut;
  dimension: number[];
  selected: boolean;
  onSelect: () => void;
  onHover: (e: ThreeEvent<PointerEvent>) => void;
  onUnhover: () => void;
}) {
  const color = NODE_STATUS_COLOR[node.status];
  const pos = worldPos(node.coordinates, dimension);
  return (
    <group position={pos}>
      <mesh
        geometry={NODE_GEOMETRY}
        onClick={(e) => {
          e.stopPropagation();
          onSelect();
        }}
        onPointerOver={(e) => {
          e.stopPropagation();
          onHover(e);
        }}
        onPointerOut={onUnhover}
      >
        <meshBasicMaterial color={color.fill} />
      </mesh>
      {selected && (
        <lineSegments geometry={SELECTED_OUTLINE_GEOMETRY}>
          <lineBasicMaterial color={SELECTED_OUTLINE_COLOR} />
        </lineSegments>
      )}
    </group>
  );
}

function GhostCube({ node, coords, dimension }: { node: NodeOut; coords: number[]; dimension: number[] }) {
  const color = NODE_STATUS_COLOR[node.status];
  const pos = worldPos(coords, dimension);
  return (
    <mesh position={pos} geometry={NODE_GEOMETRY}>
      <meshBasicMaterial color={color.fill} transparent opacity={0.3} depthWrite={false} />
    </mesh>
  );
}

interface Lattice3DThreeProps {
  nodes: NodeOut[];
  dimension: number[];
  wrap: boolean;
  selectedNodeId: number | null;
  onSelectNode: (node: NodeOut) => void;
}

const CONTAINER_HEIGHT = 560;

export function Lattice3DThree({ nodes, dimension, wrap, selectedNodeId, onSelectNode }: Lattice3DThreeProps) {
  const edges = useMemo(() => buildEdges(nodes, 3), [nodes]);
  const { ghosts, connectors } = useMemo(() => (wrap ? buildWrapGhosts(nodes, dimension, 1) : { ghosts: [], connectors: [] }), [nodes, dimension, wrap]);
  const [hover, setHover] = useState<{ node: NodeOut; x: number; y: number } | null>(null);

  // Clear a stale tooltip if the underlying cluster/node data changes out from under a
  // stationary cursor (e.g. switching clusters, or a future refetch) -- otherwise it'd
  // keep showing whatever node was last hovered until the next pointer move.
  useEffect(() => setHover(null), [nodes]);

  // Edge/connector endpoints, memoized on the actual inputs that determine them (not
  // recomputed inline in JSX) -- worldPos() returns a fresh array literal every call, so
  // computing it inline gave every <Edge> a new `from`/`to` reference on every render,
  // including ones triggered purely by hover state changes, defeating Edge's own
  // useMemo and rebuilding every edge's BufferGeometry on every mouse move.
  const edgeEndpoints = useMemo(
    () => edges.map(({ from, to }) => ({ from: worldPos(from.coordinates, dimension), to: worldPos(to.coordinates, dimension) })),
    [edges, dimension],
  );
  const connectorEndpoints = useMemo(
    () => connectors.map((c) => ({ from: worldPos(c.from, dimension), to: worldPos(c.to, dimension) })),
    [connectors, dimension],
  );

  const span = Math.max(...dimension) * UNIT;
  // Orthographic zoom sets the visible world-space extent as canvasSizePx / zoom -- it's
  // independent of camera position, so without this a large cluster renders with most
  // nodes outside the viewport and a small one renders tiny in mostly-empty space.
  // ISO_MARGIN accounts for the 3-axis oblique view foreshortening some of that extent;
  // it's an approximation, not an exact fit, tuned by eye against the seeded test clusters.
  const ISO_MARGIN = 1.6;
  const zoom = Math.min(120, Math.max(15, CONTAINER_HEIGHT / (span * ISO_MARGIN + NODE_SIZE)));

  return (
    <div className="relative">
      <div style={{ height: CONTAINER_HEIGHT }} className="rounded-md border">
        <Canvas orthographic camera={{ position: [span, span, span], zoom, near: 0.1, far: 1000 }}>
          <Controls />
          {edgeEndpoints.map(({ from, to }, i) => (
            <Edge key={`e${i}`} from={from} to={to} />
          ))}
          {connectorEndpoints.map(({ from, to }, i) => (
            <Edge key={`c${i}`} from={from} to={to} dashed />
          ))}
          {ghosts.map(({ node, coords }, i) => (
            <GhostCube key={`g${i}`} node={node} coords={coords} dimension={dimension} />
          ))}
          {nodes.map((node) => (
            <NodeCube
              key={node.node_id}
              node={node}
              dimension={dimension}
              selected={node.node_id === selectedNodeId}
              onSelect={() => onSelectNode(node)}
              onHover={(e) => setHover({ node, x: e.clientX, y: e.clientY })}
              onUnhover={() => setHover(null)}
            />
          ))}
        </Canvas>
      </div>
      {hover && (
        <div
          className="pointer-events-none fixed z-50 rounded-sm border bg-popover px-2 py-1 font-mono text-xs text-popover-foreground"
          style={{ left: hover.x + 12, top: hover.y + 12 }}
        >
          {nodeTitle(hover.node)}
        </div>
      )}
      <p className="mt-2 text-xs text-muted-foreground">Drag to orbit, scroll to zoom. Click a node to select it.</p>
    </div>
  );
}
