import { lazy, Suspense, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Box, LayoutGrid, PowerOff } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/api/client";
import type { components } from "@/api/schema.d.ts";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { LoadingState } from "@/components/LoadingState";
import { StatusBadge } from "@/components/StatusBadge";
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
    onSuccess: () => {
      toast.success(`Node ${node.node_id} marked down`);
      onMarkedDown();
    },
  });

  const color = NODE_STATUS_COLOR[node.status];

  return (
    <Card className="space-y-3 p-4">
      <div className="flex items-center justify-between">
        <div className="font-mono text-sm">node {node.node_id}</div>
        <StatusBadge fill={color.fill} label={color.label} pulse={node.status === "ALLOCATED"} />
      </div>
      <div className="font-mono text-xs text-muted-foreground">[{node.coordinates.join(", ")}]</div>

      <div className="space-y-1 font-mono text-sm">
        {node.resources.map((resource) => (
          <div key={resource.resource_type} className="flex items-center justify-between rounded-md border px-2 py-1">
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
        <PowerOff />
        {node.status === "DOWN" ? "Already down" : markDown.isPending ? "Marking down…" : "Mark node down"}
      </Button>
      {markDown.isError && <p className="text-xs text-destructive">Failed to mark node down: {String(markDown.error)}</p>}
    </Card>
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

  const institutesQuery = useQuery({
    queryKey: ["institutes"],
    queryFn: async () => {
      const { data, error } = await api.GET("/institutes");
      if (error) throw error;
      return data;
    },
  });

  const reservationsQuery = useQuery({
    queryKey: ["reservations", "cluster", clusterId],
    queryFn: async () => {
      const { data, error } = await api.GET("/reservations", {
        params: { query: { cluster_id: Number(clusterId) } },
      });
      if (error) throw error;
      return data;
    },
  });

  const instituteNameById = new Map((institutesQuery.data ?? []).map((i) => [i.institute_id, i.institute_name]));
  const reservationInfoByNodeId = new Map<number, string>();
  for (const reservation of reservationsQuery.data ?? []) {
    const label = `reserved by ${instituteNameById.get(reservation.institute_id) ?? `institute ${reservation.institute_id}`} until ${new Date(
      reservation.end_period,
    ).toLocaleString()}`;
    for (const nodeId of reservation.node_ids) {
      const existing = reservationInfoByNodeId.get(nodeId);
      reservationInfoByNodeId.set(nodeId, existing ? `${existing}; ${label}` : label);
    }
  }

  if (isPending)
    return (
      <div className="p-6 space-y-4">
        <div className="space-y-2">
          <Skeleton className="h-4 w-16" />
          <Skeleton className="h-6 w-48" />
          <Skeleton className="h-4 w-64" />
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-[1fr_280px] gap-6">
          <Skeleton className="h-80 w-full" />
          <Skeleton className="h-40 w-full" />
        </div>
      </div>
    );
  if (isError) return <p className="p-6 text-destructive">Failed to load cluster: {String(error)}</p>;

  const selectedNode = cluster.nodes.find((n) => n.node_id === selectedNodeId) ?? null;

  return (
    <div className="p-6 space-y-4">
      <div>
        <Link to="/clusters" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground hover:underline">
          <ArrowLeft className="size-3.5" />
          Clusters
        </Link>
        <h1 className="text-xl font-semibold tracking-tight mt-1">{cluster.cluster_name}</h1>
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
                <LayoutGrid />
                flat
              </Button>
              <Button size="sm" variant={view === "3d" ? "secondary" : "ghost"} onClick={() => setView("3d")}>
                <Box />
                3d (experimental)
              </Button>
            </div>
          )}

          {view === "3d" && cluster.dimension.length >= 3 ? (
            <Suspense fallback={<LoadingState text="Loading 3D view…" />}>
              <Lattice3DThree
                dimension={cluster.dimension}
                wrap={cluster.wrap}
                nodes={cluster.nodes}
                selectedNodeId={selectedNodeId}
                onSelectNode={(node) => setSelectedNodeId(node.node_id)}
                reservationInfoByNodeId={reservationInfoByNodeId}
              />
            </Suspense>
          ) : (
            <Card className="flex justify-center overflow-x-auto p-6">
              <TopologyView
                dimension={cluster.dimension}
                wrap={cluster.wrap}
                nodes={cluster.nodes}
                selectedNodeId={selectedNodeId}
                onSelectNode={(node) => setSelectedNodeId(node?.node_id ?? null)}
                reservationInfoByNodeId={reservationInfoByNodeId}
              />
            </Card>
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
