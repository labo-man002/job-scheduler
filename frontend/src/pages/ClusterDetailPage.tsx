import { lazy, Suspense, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";
import type { components } from "@/api/schema.d.ts";
import { Button } from "@/components/ui/button";
import { StatusLegend, TopologyView } from "@/components/topology/TopologyView";
import { NODE_STATUS_COLOR } from "@/lib/nodeStatus";

// three.js + @react-three/fiber add ~900kB (gzipped ~240kB) to the bundle -- code-split
// so that cost is only paid by someone who actually opens the 3D view, not every visitor
// to a cluster page.
const Lattice3DThree = lazy(() => import("@/components/topology/Lattice3DThree").then((m) => ({ default: m.Lattice3DThree })));

type NodeOut = components["schemas"]["NodeOut"];

function NodeDetailPanel({ node, onMarkedDown }: { node: NodeOut; onMarkedDown: () => void }) {
  const markDown = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.PATCH("/nodes/{node_id}/down", {
        params: { path: { node_id: node.node_id } },
      });
      if (error) throw error;
      return data;
    },
    onSuccess: onMarkedDown,
  });

  const color = NODE_STATUS_COLOR[node.status];

  return (
    <div className="rounded-md border p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div className="font-mono text-sm">node {node.node_id}</div>
        <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <span className="inline-block h-2.5 w-2.5" style={{ backgroundColor: color.fill }} />
          {color.label}
        </div>
      </div>
      <div className="font-mono text-xs text-muted-foreground">[{node.coordinates.join(", ")}]</div>

      <div className="space-y-1 font-mono text-sm">
        {node.resources.map((resource) => (
          <div key={resource.resource_type} className="flex items-center justify-between">
            <span className="text-muted-foreground">{resource.resource_type}</span>
            <span>
              {resource.free}/{resource.total}
            </span>
          </div>
        ))}
      </div>

      <Button
        variant="destructive"
        size="sm"
        disabled={node.status === "DOWN" || markDown.isPending}
        onClick={() => {
          if (window.confirm(`Mark node ${node.node_id} down? This can't be undone from the UI.`)) markDown.mutate();
        }}
      >
        {node.status === "DOWN" ? "Already down" : markDown.isPending ? "Marking down…" : "Mark node down"}
      </Button>
      {markDown.isError && <p className="text-xs text-destructive">Failed to mark node down: {String(markDown.error)}</p>}
    </div>
  );
}

export function ClusterDetailPage() {
  const { clusterId } = useParams<{ clusterId: string }>();
  const queryClient = useQueryClient();
  const [selectedNodeId, setSelectedNodeId] = useState<number | null>(null);
  const [view, setView] = useState<"flat" | "3d">("flat");

  const queryKey = ["clusters", clusterId];
  const { data: cluster, isPending, isError, error } = useQuery({
    queryKey,
    queryFn: async () => {
      const { data, error } = await api.GET("/clusters/{cluster_id}", {
        params: { path: { cluster_id: Number(clusterId) } },
      });
      if (error) throw error;
      return data;
    },
  });

  if (isPending) return <p className="p-6 text-muted-foreground">Loading cluster…</p>;
  if (isError) return <p className="p-6 text-destructive">Failed to load cluster: {String(error)}</p>;

  const selectedNode = cluster.nodes.find((n) => n.node_id === selectedNodeId) ?? null;

  return (
    <div className="p-6 space-y-4">
      <div>
        <Link to="/clusters" className="text-sm text-muted-foreground hover:underline">
          ← Clusters
        </Link>
        <h1 className="text-xl font-semibold mt-1">{cluster.cluster_name}</h1>
        <p className="font-mono text-sm text-muted-foreground">
          {cluster.topology_type} · dim [{cluster.dimension.join(",")}] · wrap={String(cluster.wrap)} ·{" "}
          {cluster.free_capacity}/{cluster.total_capacity} free
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_280px] gap-6">
        <div className="space-y-3">
          {cluster.dimension.length >= 3 && (
            <div className="inline-flex gap-1">
              <Button size="sm" variant={view === "flat" ? "secondary" : "ghost"} onClick={() => setView("flat")}>
                flat
              </Button>
              <Button size="sm" variant={view === "3d" ? "secondary" : "ghost"} onClick={() => setView("3d")}>
                3d (experimental)
              </Button>
            </div>
          )}

          {view === "3d" && cluster.dimension.length >= 3 ? (
            <Suspense fallback={<p className="text-sm text-muted-foreground">Loading 3D view…</p>}>
              <Lattice3DThree
                dimension={cluster.dimension}
                wrap={cluster.wrap}
                nodes={cluster.nodes}
                selectedNodeId={selectedNodeId}
                onSelectNode={(node) => setSelectedNodeId(node.node_id)}
              />
            </Suspense>
          ) : (
            <div className="flex justify-center overflow-x-auto rounded-md border p-6">
              <TopologyView
                dimension={cluster.dimension}
                wrap={cluster.wrap}
                nodes={cluster.nodes}
                selectedNodeId={selectedNodeId}
                onSelectNode={(node) => setSelectedNodeId(node?.node_id ?? null)}
              />
            </div>
          )}
          <StatusLegend />
        </div>

        <div>
          {selectedNode ? (
            <NodeDetailPanel
              node={selectedNode}
              onMarkedDown={() => queryClient.invalidateQueries({ queryKey })}
            />
          ) : (
            <p className="text-sm text-muted-foreground">Select a node to see its details.</p>
          )}
        </div>
      </div>
    </div>
  );
}
