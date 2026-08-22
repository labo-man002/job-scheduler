import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Activity, Boxes, Clock, PlayCircle } from "lucide-react";
import { api } from "@/api/client";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/EmptyState";
import { LoadingState } from "@/components/LoadingState";
import { JOB_STATUS_COLOR } from "@/lib/jobStatus";
import { useCountUp } from "@/lib/useCountUp";
import { useNow } from "@/lib/useNow";
import { relativeTime } from "@/lib/relativeTime";

const POLL_MS = 4000;
const RECENT_EVENTS_LIMIT = 15;

function StatCard({
  icon: Icon,
  label,
  value,
  suffix = "",
}: {
  icon: typeof Activity;
  label: string;
  value: number;
  suffix?: string;
}) {
  const animated = useCountUp(value);
  return (
    <Card className="p-4">
      <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
        <Icon className="size-3.5" />
        {label}
      </div>
      <div className="mt-1 text-2xl font-semibold tabular-nums tracking-tight">
        {Math.round(animated)}
        {suffix}
      </div>
    </Card>
  );
}

export function DashboardPage() {
  const now = useNow();

  const clustersQuery = useQuery({
    queryKey: ["clusters"],
    queryFn: async () => {
      const { data, error } = await api.GET("/clusters");
      if (error) throw error;
      return data;
    },
    refetchInterval: POLL_MS,
  });

  const jobsQuery = useQuery({
    queryKey: ["jobs"],
    queryFn: async () => {
      const { data, error } = await api.GET("/jobs");
      if (error) throw error;
      return data;
    },
    refetchInterval: POLL_MS,
  });

  const eventsQuery = useQuery({
    queryKey: ["jobs", "events", "recent"],
    queryFn: async () => {
      const { data, error } = await api.GET("/jobs/events/recent", { params: { query: { limit: RECENT_EVENTS_LIMIT } } });
      if (error) throw error;
      return data;
    },
    refetchInterval: POLL_MS,
  });

  if (clustersQuery.isPending || jobsQuery.isPending)
    return (
      <div className="p-6 space-y-6">
        <Skeleton className="h-6 w-40" />
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-20 w-full" />
          ))}
        </div>
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <Skeleton className="h-64 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
      </div>
    );
  if (clustersQuery.isError) return <p className="p-6 text-destructive">Failed to load clusters: {String(clustersQuery.error)}</p>;
  if (jobsQuery.isError) return <p className="p-6 text-destructive">Failed to load jobs: {String(jobsQuery.error)}</p>;

  const clusters = clustersQuery.data;
  const jobs = jobsQuery.data;
  const events = eventsQuery.data ?? [];

  const totalCapacity = clusters.reduce((sum, c) => sum + c.total_capacity, 0);
  const freeCapacity = clusters.reduce((sum, c) => sum + c.free_capacity, 0);
  const utilizationPct = totalCapacity === 0 ? 0 : ((totalCapacity - freeCapacity) / totalCapacity) * 100;
  const runningCount = jobs.filter((j) => j.status === "RUNNING").length;
  const queuedCount = jobs.filter((j) => j.status === "QUEUED").length;

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight">Fleet Overview</h1>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCard icon={Boxes} label="Clusters" value={clusters.length} />
        <StatCard icon={Activity} label="Utilization" value={utilizationPct} suffix="%" />
        <StatCard icon={PlayCircle} label="Running" value={runningCount} />
        <StatCard icon={Clock} label="Queued" value={queuedCount} />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card className="p-4">
          <h2 className="mb-3 text-xs font-medium uppercase tracking-wide text-muted-foreground">Clusters</h2>
          {clusters.length === 0 ? (
            <EmptyState icon={Boxes} title="No clusters yet" description="Clusters are created via the backend API." />
          ) : (
            <ul className="space-y-3">
              {clusters.map((cluster) => {
                const freeRatio = cluster.total_capacity === 0 ? 0 : cluster.free_capacity / cluster.total_capacity;
                return (
                  <li key={cluster.cluster_id}>
                    <Link to={`/clusters/${cluster.cluster_id}`} className="block group">
                      <div className="flex items-center justify-between text-sm">
                        <span className="font-medium group-hover:underline">{cluster.cluster_name}</span>
                        <span className="font-mono text-xs text-muted-foreground">
                          {cluster.free_capacity}/{cluster.total_capacity} free
                        </span>
                      </div>
                      <div className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-muted">
                        <div className="h-full rounded-full bg-primary transition-all" style={{ width: `${freeRatio * 100}%` }} />
                      </div>
                    </Link>
                  </li>
                );
              })}
            </ul>
          )}
        </Card>

        <Card className="p-4">
          <h2 className="mb-3 text-xs font-medium uppercase tracking-wide text-muted-foreground">Live activity</h2>
          {eventsQuery.isPending ? (
            <LoadingState text="Loading activity…" />
          ) : events.length === 0 ? (
            <EmptyState icon={Activity} title="No activity yet" description="Job events will appear here as they happen." />
          ) : (
            <ol className="space-y-3">
              {events.map((event) => (
                <li key={`${event.job_id}-${event.event_type}-${event.time}`} className="flex items-center gap-2 text-sm">
                  <span
                    className="size-1.5 shrink-0 rounded-full"
                    style={{ backgroundColor: JOB_STATUS_COLOR[event.event_type].fill }}
                  />
                  <Link to={`/jobs/${event.job_id}`} className="font-mono text-xs hover:underline">
                    job {event.job_id}
                  </Link>
                  <span className="truncate text-muted-foreground">{event.comment}</span>
                  <span className="ml-auto shrink-0 text-xs text-muted-foreground">{relativeTime(event.time, now)}</span>
                </li>
              ))}
            </ol>
          )}
        </Card>
      </div>
    </div>
  );
}
