import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarClock, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/EmptyState";
import { formatApiError } from "@/lib/apiError";

const INPUT_CLASS = "h-8 rounded-md border bg-background px-2 text-sm";

export function AdminReservationsPage() {
  const queryClient = useQueryClient();
  const [instituteId, setInstituteId] = useState<number | "">("");
  const [clusterId, setClusterId] = useState<number | "">("");
  const [nodeIds, setNodeIds] = useState<Set<number>>(new Set());
  const [startPeriod, setStartPeriod] = useState("");
  const [endPeriod, setEndPeriod] = useState("");
  const [reason, setReason] = useState("");
  const [filterInstituteId, setFilterInstituteId] = useState<number | "">("");

  const institutesQuery = useQuery({
    queryKey: ["institutes"],
    queryFn: async () => {
      const { data, error } = await api.GET("/institutes");
      if (error) throw error;
      return data;
    },
  });
  const instituteNameById = new Map((institutesQuery.data ?? []).map((i) => [i.institute_id, i.institute_name]));

  const clustersQuery = useQuery({
    queryKey: ["clusters"],
    queryFn: async () => {
      const { data, error } = await api.GET("/clusters");
      if (error) throw error;
      return data;
    },
  });

  // Only fetched once a cluster is picked -- that's where the node_ids to reserve come from (#65's node list).
  const clusterDetailQuery = useQuery({
    queryKey: ["clusters", clusterId],
    enabled: clusterId !== "",
    queryFn: async () => {
      const { data, error } = await api.GET("/clusters/{cluster_id}", { params: { path: { cluster_id: clusterId as number } } });
      if (error) throw error;
      return data;
    },
  });

  const reservationsQuery = useQuery({
    queryKey: ["reservations", { filterInstituteId }],
    queryFn: async () => {
      const { data, error } = await api.GET("/reservations", {
        params: { query: { institute_id: filterInstituteId === "" ? undefined : filterInstituteId } },
      });
      if (error) throw error;
      return data;
    },
  });

  const create = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/reservations", {
        body: {
          institute_id: instituteId as number,
          cluster_id: clusterId as number,
          node_ids: [...nodeIds],
          start_period: new Date(startPeriod).toISOString(),
          end_period: new Date(endPeriod).toISOString(),
          reason,
        },
      });
      if (error) throw error;
      return data;
    },
    onSuccess: () => {
      toast.success("Reservation created");
      setNodeIds(new Set());
      setReason("");
      queryClient.invalidateQueries({ queryKey: ["reservations"] });
    },
  });

  const cancel = useMutation({
    mutationFn: async (id: number) => {
      const { data, error } = await api.DELETE("/reservations/{reservation_id}", { params: { path: { reservation_id: id } } });
      if (error) throw error;
      return data;
    },
    onSuccess: () => {
      toast.success("Reservation cancelled");
      queryClient.invalidateQueries({ queryKey: ["reservations"] });
    },
  });

  function toggleNode(nodeId: number) {
    setNodeIds((prev) => {
      const next = new Set(prev);
      if (next.has(nodeId)) next.delete(nodeId);
      else next.add(nodeId);
      return next;
    });
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (instituteId !== "" && clusterId !== "" && nodeIds.size > 0 && startPeriod && endPeriod && reason.trim()) create.mutate();
  }

  const canSubmit = instituteId !== "" && clusterId !== "" && nodeIds.size > 0 && startPeriod && endPeriod && reason.trim() && !create.isPending;

  return (
    <div className="max-w-2xl space-y-4">
      <form onSubmit={handleSubmit} className="space-y-3 rounded-lg border p-4">
        <div className="flex flex-wrap gap-2">
          <select className={INPUT_CLASS} value={instituteId} onChange={(e) => setInstituteId(e.target.value === "" ? "" : Number(e.target.value))}>
            <option value="">Institute…</option>
            {(institutesQuery.data ?? []).map((i) => (
              <option key={i.institute_id} value={i.institute_id}>
                {i.institute_name}
              </option>
            ))}
          </select>
          <select
            className={INPUT_CLASS}
            value={clusterId}
            onChange={(e) => {
              setClusterId(e.target.value === "" ? "" : Number(e.target.value));
              setNodeIds(new Set());
            }}
          >
            <option value="">Cluster…</option>
            {(clustersQuery.data ?? []).map((c) => (
              <option key={c.cluster_id} value={c.cluster_id}>
                {c.cluster_name}
              </option>
            ))}
          </select>
        </div>

        {clusterId !== "" && (
          <div className="space-y-1">
            <label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Nodes to reserve</label>
            {clusterDetailQuery.isPending && <Skeleton className="h-16 w-full" />}
            {clusterDetailQuery.data && (
              <div className="flex max-h-40 flex-wrap gap-1.5 overflow-y-auto rounded-md border p-2">
                {clusterDetailQuery.data.nodes.map((node) => (
                  <label
                    key={node.node_id}
                    className={`flex cursor-pointer items-center gap-1 rounded-md border px-2 py-1 font-mono text-xs ${
                      nodeIds.has(node.node_id) ? "border-primary bg-primary/10" : ""
                    }`}
                  >
                    <input type="checkbox" className="sr-only" checked={nodeIds.has(node.node_id)} onChange={() => toggleNode(node.node_id)} />
                    {node.coordinates.join(",")}
                  </label>
                ))}
              </div>
            )}
          </div>
        )}

        <div className="flex flex-wrap gap-2">
          <input
            type="datetime-local"
            className={INPUT_CLASS}
            value={startPeriod}
            onChange={(e) => setStartPeriod(e.target.value)}
            aria-label="Start period"
          />
          <input
            type="datetime-local"
            className={INPUT_CLASS}
            value={endPeriod}
            onChange={(e) => setEndPeriod(e.target.value)}
            aria-label="End period"
          />
          <input
            className={`${INPUT_CLASS} min-w-48 flex-1`}
            placeholder="Reason"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
        </div>

        <Button type="submit" size="sm" disabled={!canSubmit}>
          <Plus />
          Create reservation
        </Button>
        {create.isError && <p className="text-sm text-destructive">{formatApiError(create.error)}</p>}
      </form>

      <select
        className={INPUT_CLASS}
        value={filterInstituteId}
        onChange={(e) => setFilterInstituteId(e.target.value === "" ? "" : Number(e.target.value))}
      >
        <option value="">All institutes</option>
        {(institutesQuery.data ?? []).map((i) => (
          <option key={i.institute_id} value={i.institute_id}>
            {i.institute_name}
          </option>
        ))}
      </select>

      {reservationsQuery.isPending && (
        <div className="space-y-2">
          {[0, 1].map((i) => (
            <Skeleton key={i} className="h-16 w-full" />
          ))}
        </div>
      )}
      {reservationsQuery.isError && <p className="text-destructive">Failed to load reservations: {String(reservationsQuery.error)}</p>}
      {reservationsQuery.data && reservationsQuery.data.length === 0 && (
        <EmptyState icon={CalendarClock} title="No reservations" description="Create one above to block off nodes for an institute." />
      )}
      {reservationsQuery.data && reservationsQuery.data.length > 0 && (
        <ul className="space-y-2">
          {reservationsQuery.data.map((reservation) => (
            <li key={reservation.id}>
              <Card className="flex items-center justify-between gap-3 p-3">
                <div className="flex items-start gap-3">
                  <CalendarClock className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
                  <div>
                    <div className="font-mono text-sm">
                      {instituteNameById.get(reservation.institute_id) ?? `institute ${reservation.institute_id}`} · cluster{" "}
                      {reservation.cluster_id} · nodes [{reservation.node_ids.join(",")}]
                    </div>
                    <div className="text-sm text-muted-foreground">
                      {new Date(reservation.start_period).toLocaleString()} → {new Date(reservation.end_period).toLocaleString()} ·{" "}
                      {reservation.reason}
                    </div>
                  </div>
                </div>
                <Button
                  variant="ghost"
                  size="icon-sm"
                  aria-label="Cancel reservation"
                  disabled={cancel.isPending}
                  onClick={() => {
                    if (window.confirm("Cancel this reservation?")) cancel.mutate(reservation.id);
                  }}
                >
                  <Trash2 />
                </Button>
              </Card>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
