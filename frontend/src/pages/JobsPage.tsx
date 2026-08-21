import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";
import type { components } from "@/api/schema.d.ts";
import { JOB_STATUS_COLOR } from "@/lib/jobStatus";

type JobStatus = components["schemas"]["JobStatus"];

const JOB_STATUSES: JobStatus[] = ["PENDING", "QUEUED", "RUNNING", "COMPLETED", "CANCELLED", "FAILED"];

const SELECT_CLASS = "h-8 rounded-md border bg-background px-2 text-sm";

export function JobsPage() {
  const [status, setStatus] = useState<JobStatus | "">("");
  const [clientId, setClientId] = useState<number | "">("");

  const clientsQuery = useQuery({
    queryKey: ["clients"],
    queryFn: async () => {
      const { data, error } = await api.GET("/clients");
      if (error) throw error;
      return data;
    },
  });
  const ownerByClientId = new Map((clientsQuery.data ?? []).map((c) => [c.client_id, c.owner]));

  const jobsQuery = useQuery({
    queryKey: ["jobs", { status, clientId }],
    queryFn: async () => {
      const { data, error } = await api.GET("/jobs", {
        params: { query: { status: status || undefined, client_id: clientId === "" ? undefined : clientId } },
      });
      if (error) throw error;
      return data;
    },
  });

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Jobs</h1>
        <Link to="/jobs/new" className="rounded-md border px-3 py-1.5 text-sm hover:bg-secondary/50">
          + New job
        </Link>
      </div>

      <div className="flex gap-2">
        <select className={SELECT_CLASS} value={status} onChange={(e) => setStatus(e.target.value as JobStatus | "")}>
          <option value="">All statuses</option>
          {JOB_STATUSES.map((s) => (
            <option key={s} value={s}>
              {JOB_STATUS_COLOR[s].label}
            </option>
          ))}
        </select>
        <select
          className={SELECT_CLASS}
          value={clientId}
          onChange={(e) => setClientId(e.target.value === "" ? "" : Number(e.target.value))}
        >
          <option value="">All clients</option>
          {(clientsQuery.data ?? []).map((c) => (
            <option key={c.client_id} value={c.client_id}>
              {c.owner} (client {c.client_id})
            </option>
          ))}
        </select>
      </div>

      {jobsQuery.isPending && <p className="text-muted-foreground">Loading jobs…</p>}
      {jobsQuery.isError && <p className="text-destructive">Failed to load jobs: {String(jobsQuery.error)}</p>}
      {jobsQuery.data && jobsQuery.data.length === 0 && <p className="text-muted-foreground">No jobs match these filters.</p>}

      {jobsQuery.data && jobsQuery.data.length > 0 && (
        <ul className="space-y-2">
          {jobsQuery.data.map((job) => {
            const color = JOB_STATUS_COLOR[job.status];
            return (
              <li key={job.job_id}>
                <Link to={`/jobs/${job.job_id}`} className="flex items-center justify-between rounded-md border p-4 hover:bg-secondary/50">
                  <div>
                    <div className="font-mono text-sm">
                      job {job.job_id} · {ownerByClientId.get(job.client_id) ?? `client ${job.client_id}`}
                    </div>
                    <div className="text-sm text-muted-foreground">
                      {job.priority} · {job.duration}min · submitted {new Date(job.submitted_at).toLocaleString()}
                    </div>
                  </div>
                  <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                    <span className="inline-block h-2.5 w-2.5" style={{ backgroundColor: color.fill }} />
                    {color.label}
                  </div>
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
