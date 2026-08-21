import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";
import { Button } from "@/components/ui/button";
import { JOB_STATUS_COLOR } from "@/lib/jobStatus";
import { formatApiError } from "@/lib/apiError";

const CANCELLABLE_STATUSES = new Set(["QUEUED", "RUNNING"]);

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
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["jobs"] }),
  });

  if (jobQuery.isPending) return <p className="p-6 text-muted-foreground">Loading job…</p>;
  if (jobQuery.isError) return <p className="p-6 text-destructive">Failed to load job: {String(jobQuery.error)}</p>;

  const job = jobQuery.data;
  const color = JOB_STATUS_COLOR[job.status];

  return (
    <div className="p-6 max-w-2xl space-y-4">
      <div>
        <Link to="/jobs" className="text-sm text-muted-foreground hover:underline">
          ← Jobs
        </Link>
        <div className="flex items-center gap-2 mt-1">
          <h1 className="text-2xl font-semibold">Job {job.job_id}</h1>
          <span className="flex items-center gap-1.5 text-sm text-muted-foreground">
            <span className="inline-block h-2.5 w-2.5" style={{ backgroundColor: color.fill }} />
            {color.label}
          </span>
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

      <section className="space-y-2">
        <h2 className="text-sm font-medium">Requirements</h2>
        <div className="space-y-1 font-mono text-sm">
          {job.requirements.map((r) => (
            <div key={r.resource_type} className="flex items-center justify-between rounded-md border px-3 py-1.5">
              <span className="text-muted-foreground">{r.resource_type}</span>
              <span>{r.amount}</span>
            </div>
          ))}
        </div>
      </section>

      <section className="space-y-2">
        <h2 className="text-sm font-medium">Allocation</h2>
        {allocationQuery.isPending && <p className="text-sm text-muted-foreground">Loading…</p>}
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
          </div>
        )}
      </section>

      <section className="space-y-2">
        <h2 className="text-sm font-medium">Event history</h2>
        {eventsQuery.isPending && <p className="text-sm text-muted-foreground">Loading…</p>}
        {eventsQuery.isError && <p className="text-sm text-destructive">Failed to load events: {String(eventsQuery.error)}</p>}
        {eventsQuery.data && (
          <ol className="space-y-1">
            {eventsQuery.data.map((event, i) => (
              <li key={i} className="flex items-center justify-between rounded-md border px-3 py-1.5 text-sm">
                <span>
                  <span className="font-mono">{event.event_type}</span> — {event.comment}
                </span>
                <span className="font-mono text-xs text-muted-foreground">{new Date(event.time).toLocaleString()}</span>
              </li>
            ))}
          </ol>
        )}
      </section>
    </div>
  );
}
