import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { loadReplayRun, renameReplayRun, type ReplayRun } from "@/api/replay";
import { ReplayRows } from "@/components/ReplayRows";
import { ReplaySummary } from "@/components/ReplaySummary";
import { Button } from "@/components/ui/button";

import { clusterShape, policyLabels, replayPolicies, runName, runTime, type ReplayPolicy } from "@/lib/replayDisplay";

function RenameRun({ run }: { run: ReplayRun }) {
  const [name, setName] = useState(run.display_name ?? "");
  const queryClient = useQueryClient();
  const rename = useMutation({
    mutationFn: () => renameReplayRun(run.id, name.trim() || null),
    onSuccess: summary => {
      queryClient.setQueryData<ReplayRun>(["replay-run", run.id], previous => previous && { ...previous, ...summary });
      setName(summary.display_name ?? "");
      void queryClient.invalidateQueries({ queryKey: ["replay-history"] });
    },
  });
  return <form className="flex flex-wrap items-end gap-2"
    onSubmit={event => { event.preventDefault(); rename.mutate(); }}>
    <label className="grid gap-1 text-sm">Run name
      <input className="rounded border bg-background px-2 py-1" maxLength={120}
        value={name} disabled={rename.isPending} onChange={event => setName(event.target.value)} />
    </label>
    <Button type="submit" variant="outline"
      disabled={rename.isPending || name.trim() === (run.display_name ?? "")}>Save name</Button>
    {rename.isError && <p role="alert" className="w-full text-sm text-destructive">{rename.error.message}</p>}
  </form>;
}

function numericOutcome(run: ReplayRun, policy: ReplayPolicy, key: string) {
  const rows = run.outputs.runs.find(raw => raw.policy === policy)?.jobs;
  const values = new Map<number, number>();
  if (Array.isArray(rows)) {
    for (const row of rows) {
      if (row && typeof row.id === "number" && typeof row[key] === "number") values.set(row.id, row[key]);
    }
  }
  return values;
}

function RecordedLedgers({ run }: { run: ReplayRun }) {
  return <section className="space-y-3" aria-label="Recorded event ledgers">
    <h2 className="text-lg font-semibold">Recorded event ledgers</h2>
    {replayPolicies.map(policy => {
      const events = run.outputs.runs.find(raw => raw.policy === policy)?.events;
      return <details className="rounded-lg border p-3" key={policy}>
        <summary className="cursor-pointer font-medium">{policyLabels[policy]} events</summary>
        {Array.isArray(events) ? <ReplayRows rows={events} label={policyLabels[policy] + " events"}>{visible => <ol className="mt-3 divide-y overflow-x-auto text-sm">
          {visible.map((event, index) => <li key={index} className="py-2">
            Tick {event.tick} · Job {event.job_id} · {event.kind}
            {event.reason && <span className="ml-2 text-muted-foreground">{String(event.reason).replaceAll("_", " ")}</span>}
            {Array.isArray(event.gpus) && <span className="ml-2 text-muted-foreground">
              {event.gpus.map((gpu: { node_id: number; index: number }) => `node ${gpu.node_id} GPU ${gpu.index}`).join(", ")}
            </span>}
          </li>)}
        </ol>}</ReplayRows> : <p className="mt-3 text-sm text-muted-foreground">Event ledger unavailable for this run.</p>}
      </details>;
    })}
  </section>;
}

function SavedResults({ run }: { run: ReplayRun }) {
  const result = run.outputs.comparison;
  const fifoFinishes = numericOutcome(run, "fifo", "finish");
  const priorityFinishes = numericOutcome(run, "priority", "finish");
  return <section aria-label="Comparison results" className="space-y-6">
    <ReplaySummary result={result} capacity={run.gpus_per_node.reduce((sum, count) => sum + count, 0)} />
    <div className="grid gap-4 sm:grid-cols-2">
      {replayPolicies.map(policy => {
        const m = result[policy];
        const percent = m.occupancy == null ? null : m.occupancy * 100;
        return <article key={policy} className="space-y-3 rounded-xl border bg-card p-5">
          <h2 className="font-semibold">{policyLabels[policy]}</h2>
          <p className="text-3xl font-semibold tabular-nums">{percent == null ? "—" : percent.toFixed(1) + "%"} <span className="text-sm font-normal">GPU occupancy</span></p>
          <div aria-hidden="true" className="h-2 overflow-hidden rounded bg-muted"><div className="h-full bg-primary" style={{ width: (percent ?? 0) + "%" }} /></div>
          <dl className="grid grid-cols-2 gap-1 text-sm">
            <dt>Finish time</dt><dd>{m.makespan_ticks_from_zero} ticks</dd>
            <dt>Throughput</dt><dd>{m.completed_jobs_per_hour?.toFixed(1) ?? "Unavailable"} jobs/hour</dd>
            <dt>Completed</dt><dd>{m.completed}</dd>
            <dt>Unscheduled</dt><dd>{m.unscheduled}</dd>
          </dl>
        </article>;
      })}
    </div>
    <ReplayRows rows={result.jobs} label="Jobs">{visible => <div className="overflow-x-auto">
      <table className="w-full text-left text-sm tabular-nums">
        <caption className="pb-3 text-left font-semibold">Queue wait and finish by job (ticks)</caption>
        <thead><tr>{["Job", "Priority", "GPUs", "FIFO wait", "FIFO finish", "Priority wait", "Priority finish", "Reason"].map(label => <th key={label} className="p-2">{label}</th>)}</tr></thead>
        <tbody>{visible.map(job => <tr key={job.id} className="border-t">
          <th scope="row" className="p-2">{job.id}</th><td>{job.priority}</td><td>{job.gpus}</td>
          <td>{job.fifo_wait ?? "Unscheduled"}</td><td>{fifoFinishes.get(job.id) ?? "—"}</td>
          <td>{job.priority_wait ?? "Unscheduled"}</td><td>{priorityFinishes.get(job.id) ?? "—"}</td>
          <td>{job.reason?.replaceAll("_", " ") ?? "—"}</td>
        </tr>)}</tbody>
      </table>
    </div>}</ReplayRows>
    <RecordedLedgers run={run} />
  </section>;
}

export function ReplayRunPage() {
  const { runId = "" } = useParams();
  const query = useQuery({ queryKey: ["replay-run", runId], queryFn: () => loadReplayRun(runId) });
  const run = query.data;
  return <main className="mx-auto max-w-5xl space-y-5 px-4 py-8">
    <div className="flex flex-wrap gap-4 text-sm text-primary underline">
      <Link to="/replay">New replay</Link>
      <Link to="/replay/runs">Run history</Link>
    </div>
    {query.isPending && <p role="status">Loading saved run…</p>}
    {query.isError && <p role="alert" className="text-destructive">{query.error.message}</p>}
    {run && <>
      <header className="space-y-2">
        <h1 className="text-3xl font-semibold tracking-tight">{runName(run)}</h1>
        <p className="text-muted-foreground">{run.workload_label} · {clusterShape(run.gpus_per_node)} · {run.outputs.comparison.seconds_per_tick} seconds per tick</p>
        <p className="text-sm text-muted-foreground">
          Saved <time dateTime={run.created_at}>{runTime(run.created_at)}</time> · {run.source}
        </p>
        <div className="flex flex-wrap items-center gap-2">
          {run.can_reuse
            ? <Button variant="outline" asChild><Link to={`/replay/runs/${run.id}/fork`}>Use as starting point</Link></Button>
            : <p className="text-sm text-muted-foreground">This saved input format is unavailable for reuse.</p>}
          <Button variant="outline" asChild><Link to={`/replay/runs?baseline=${run.id}`}>Compare with another run</Link></Button>
        </div>
        <RenameRun key={run.id} run={run} />
      </header>
      <SavedResults run={run} />
    </>}
  </main>;
}
