import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ChevronRight, ListTodo, Plus } from "lucide-react";
import { api } from "@/api/client";
import type { components } from "@/api/schema.d.ts";
import { JOB_STATUS_COLOR } from "@/lib/jobStatus";
import { Card } from "@/components/ui/card";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/EmptyState";

type JobStatus = components["schemas"]["JobStatus"];

const JOB_STATUSES: JobStatus[] = ["PENDING", "QUEUED", "RUNNING", "COMPLETED", "CANCELLED", "FAILED"];

const SELECT_CLASS = "h-8 rounded-md border bg-background px-2 text-sm";

function JobRowSkeleton() {
  return (
    <Card className="flex items-center justify-between gap-4 p-4">
      <div className="w-full space-y-2">
        <Skeleton className="h-4 w-40" />
        <Skeleton className="h-3 w-56" />
      </div>
      <Skeleton className="h-5 w-20 shrink-0 rounded-full" />
    </Card>
  );
}

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
    <div className="p-6 max-w-3xl space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">Jobs</h1>
        <Button asChild size="sm">
          <Link to="/jobs/new">
            <Plus />
            New job
          </Link>
        </Button>
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

      {jobsQuery.isPending && (
        <div className="space-y-3">
          {[0, 1, 2].map((i) => (
            <JobRowSkeleton key={i} />
          ))}
        </div>
      )}
      {jobsQuery.isError && <p className="text-destructive">Failed to load jobs: {String(jobsQuery.error)}</p>}
      {jobsQuery.data && jobsQuery.data.length === 0 && (status || clientId !== "" ? (
        <EmptyState icon={ListTodo} title="No jobs match these filters" description="Try a different status or client." />
      ) : (
        <EmptyState icon={ListTodo} title="No jobs yet" description="Submit one to get started." />
      ))}

      {jobsQuery.data && jobsQuery.data.length > 0 && (
        <ul className="space-y-3">
          {jobsQuery.data.map((job) => {
            const color = JOB_STATUS_COLOR[job.status];
            return (
              <li key={job.job_id}>
                <Link to={`/jobs/${job.job_id}`} className="block group">
                  <Card
                    className="flex items-center justify-between gap-4 p-4 pl-3 transition-shadow hover:shadow-md"
                    style={{ borderLeft: `3px solid ${color.fill}` }}
                  >
                    <div>
                      <div className="font-mono text-sm">
                        job {job.job_id} · {ownerByClientId.get(job.client_id) ?? `client ${job.client_id}`}
                      </div>
                      <div className="text-sm text-muted-foreground">
                        {job.priority} · {job.duration}min · submitted {new Date(job.submitted_at).toLocaleString()}
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <StatusBadge fill={color.fill} label={color.label} pulse={job.status === "RUNNING"} />
                      <ChevronRight className="size-4 text-muted-foreground transition-transform group-hover:translate-x-0.5" />
                    </div>
                  </Card>
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
