import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, History, ListChecks, Server } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { StatusBadge } from "@/components/StatusBadge";
import { TopologyView } from "@/components/topology/TopologyView";
import { JOB_STATUS_COLOR } from "@/lib/jobStatus";
import { formatApiError } from "@/lib/apiError";
import { LoadingState } from "@/components/LoadingState";
import { Skeleton } from "@/components/ui/skeleton";

const CANCELLABLE_STATUSES = new Set(["QUEUED", "RUNNING"]);

function SectionHeading({ icon: Icon, children }: { icon: typeof ListChecks; children: React.ReactNode }) {
  return (
    <h2 className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground">
      <Icon className="size-3.5" />
      {children}
    </h2>
  );
}

// Shows *where* on the cluster this job actually landed -- the interesting part of
// placement (Pack vs. Spread) is spatial, and a flat list of node ids hides that entirely.
function AllocationTopology({ clusterId, jobId, allocatedNodeIds }: { clusterId: number; jobId: number; allocatedNodeIds: Set<number> }) {
  const [selectedNodeId, setSelectedNodeId] = useState<number | null>(null);

  const clusterQuery = useQuery({
    queryKey: ["clusters", clusterId],
    queryFn: async () => {
      const { data, error } = await api.GET("/clusters/{cluster_id}", { params: { path: { cluster_id: clusterId } } });
      if (error) throw error;
      return data;
    },
  });

  if (clusterQuery.isPending) return <Skeleton className="h-40 w-full" />;
  if (clusterQuery.isError) return <p className="text-sm text-destructive">Failed to load cluster topology: {String(clusterQuery.error)}</p>;

  const cluster = clusterQuery.data;
  const allocationInfoByNodeId = new Map<number, string>();
  for (const nodeId of allocatedNodeIds) allocationInfoByNodeId.set(nodeId, `allocated to job ${jobId}`);

  return (
    <div className="space-y-2">
      <Link to={`/clusters/${clusterId}`} className="text-xs text-muted-foreground hover:text-foreground hover:underline">
        {cluster.cluster_name} ({cluster.topology_type}) →
      </Link>
      <div className="flex justify-center overflow-x-auto rounded-md border p-4">
        <TopologyView
          dimension={cluster.dimension}
          wrap={cluster.wrap}
          nodes={cluster.nodes}
          selectedNodeId={selectedNodeId}
          onSelectNode={(node) => setSelectedNodeId(node?.node_id ?? null)}
          reservationInfoByNodeId={allocationInfoByNodeId}
        />
      </div>
    </div>
  );
}

export function JobDetailPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const queryClient = useQueryClient();
  const id = Number(jobId);

  const jobQuery = useQuery({
    queryKey: ["jobs", id],
    queryFn: async () => {
      const { data, error } = await api.GET("/jobs/{job_id}", { params: { path: { job_id: id } } });
      if (error) throw error;
      return data;
    },
  });

  const eventsQuery = useQuery({
    queryKey: ["jobs", id, "events"],
    queryFn: async () => {
      const { data, error } = await api.GET("/jobs/{job_id}/events", { params: { path: { job_id: id } } });
      if (error) throw error;
      return [...data].sort((a, b) => new Date(a.time).getTime() - new Date(b.time).getTime());
    },
  });

  const allocationQuery = useQuery({
    queryKey: ["jobs", id, "allocation"],
    queryFn: async () => {
      // A job with no allocation yet (still QUEUED) 404s -- that's expected, not an error.
      const { data, error, response } = await api.GET("/jobs/{job_id}/allocation", { params: { path: { job_id: id } } });
      if (response.status === 404) return null;
      if (error) throw error;
      return data;
    },
  });

  const cancel = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.DELETE("/jobs/{job_id}", { params: { path: { job_id: id } } });
      if (error) throw error;
      return data;
    },
    onSuccess: () => {
      toast.success(`Job ${id} cancelled`);
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
    },
  });

  if (jobQuery.isPending)
    return (
      <div className="p-6 max-w-2xl space-y-4">
        <div className="space-y-2">
          <Skeleton className="h-4 w-16" />
          <Skeleton className="h-6 w-32" />
          <Skeleton className="h-4 w-72" />
        </div>
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  if (jobQuery.isError) return <p className="p-6 text-destructive">Failed to load job: {String(jobQuery.error)}</p>;

  const job = jobQuery.data;
  const color = JOB_STATUS_COLOR[job.status];

  return (
    <div className="p-6 max-w-2xl space-y-4">
      <div>
        <Link to="/jobs" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground hover:underline">
          <ArrowLeft className="size-3.5" />
          Jobs
        </Link>
        <div className="flex items-center gap-2 mt-1">
          <h1 className="text-2xl font-semibold tracking-tight">Job {job.job_id}</h1>
          <StatusBadge fill={color.fill} label={color.label} pulse={job.status === "RUNNING"} />
        </div>
        <p className="font-mono text-sm text-muted-foreground">
          client {job.client_id} · {job.priority} · {job.duration}min · submitted {new Date(job.submitted_at).toLocaleString()}
        </p>
      </div>

      {CANCELLABLE_STATUSES.has(job.status) && (
        <div>
          <Button
            variant="destructive"
            size="sm"
            disabled={cancel.isPending}
            onClick={() => {
              if (window.confirm(`Cancel job ${job.job_id}?`)) cancel.mutate();
            }}
          >
            {cancel.isPending ? "Cancelling…" : "Cancel job"}
          </Button>
          {cancel.isError && <p className="mt-1 text-sm text-destructive">Failed to cancel: {formatApiError(cancel.error)}</p>}
        </div>
      )}

      <Card className="space-y-2 p-4">
        <SectionHeading icon={ListChecks}>Requirements</SectionHeading>
        <div className="space-y-1 font-mono text-sm">
          {job.requirements.map((r) => (
            <div key={r.resource_type} className="flex items-center justify-between rounded-md border px-3 py-1.5">
              <span className="text-muted-foreground">{r.resource_type}</span>
              <span>{r.amount}</span>
            </div>
          ))}
        </div>
      </Card>

      <Card className="space-y-2 p-4">
        <SectionHeading icon={Server}>Allocation</SectionHeading>
        {allocationQuery.isPending && <LoadingState text="Loading…" />}
        {allocationQuery.isError && <p className="text-sm text-destructive">Failed to load allocation: {String(allocationQuery.error)}</p>}
        {allocationQuery.data === null && <p className="text-sm text-muted-foreground">No allocation yet.</p>}
        {allocationQuery.data && (
          <div className="space-y-1 font-mono text-sm">
            <div className="text-muted-foreground">
              {allocationQuery.data.allocation_status} · began {new Date(allocationQuery.data.begin_time).toLocaleString()}
              {allocationQuery.data.end_time && ` · ended ${new Date(allocationQuery.data.end_time).toLocaleString()}`}
            </div>
            {allocationQuery.data.resource_nodes.map((rn) => (
              <div key={rn.resource_node_id} className="flex items-center justify-between rounded-md border px-3 py-1.5">
                <span className="text-muted-foreground">node {rn.node_id}</span>
                <span>{rn.resource_type}</span>
              </div>
            ))}
            <AllocationTopology
              clusterId={allocationQuery.data.cluster_id}
              jobId={job.job_id}
              allocatedNodeIds={new Set(allocationQuery.data.resource_nodes.map((rn) => rn.node_id))}
            />
          </div>
        )}
      </Card>

      <Card className="space-y-3 p-4">
        <SectionHeading icon={History}>Event history</SectionHeading>
        {eventsQuery.isPending && <LoadingState text="Loading…" />}
        {eventsQuery.isError && <p className="text-sm text-destructive">Failed to load events: {String(eventsQuery.error)}</p>}
        {eventsQuery.data && (
          <ol className="space-y-4 border-l pl-4">
            {eventsQuery.data.map((event, i) => (
              <li key={i} className="relative">
                <span
                  className="absolute -left-[21px] top-1 size-2.5 rounded-full ring-4 ring-background"
                  style={{ backgroundColor: JOB_STATUS_COLOR[event.event_type].fill }}
                />
                <div className="flex items-center justify-between">
                  <span className="font-mono text-sm">{event.event_type}</span>
                  <span className="font-mono text-xs text-muted-foreground">{new Date(event.time).toLocaleString()}</span>
                </div>
                <p className="text-sm text-muted-foreground">{event.comment}</p>
              </li>
            ))}
          </ol>
        )}
      </Card>
    </div>
  );
}
