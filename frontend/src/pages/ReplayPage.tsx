import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { api } from "@/api/client";
import { Button } from "@/components/ui/button";

type Scenario = "oracle" | "contention";

function Experiment({ scenario }: { scenario: Scenario }) {
  const replay = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.GET("/replay/{scenario_name}", {
        params: { path: { scenario_name: scenario } },
      });
      if (error || !data) throw new Error("Replay failed. Check the backend connection and try again.");
      return data;
    },
  });
  const result = replay.data;
  return <>
    <Button disabled={replay.isPending} onClick={() => replay.mutate()}>
      {replay.isPending ? "Running…" : "Run comparison"}
    </Button>
    {replay.isError && <p role="alert" className="text-destructive">{replay.error.message}</p>}
    {result && <section aria-label="Comparison results" className="space-y-6">
      <p className="text-sm text-muted-foreground">{result.source} · {result.seconds_per_tick} seconds per tick</p>
      <div className="grid gap-4 sm:grid-cols-2">
        {(["fifo", "priority"] as const).map(policy => {
          const m = result[policy];
          const percent = m.occupancy == null ? null : m.occupancy * 100;
          return <article key={policy} className="space-y-3 rounded-xl border bg-card p-5">
            <h2 className="font-semibold">{policy === "fifo" ? "FIFO" : "Priority"}</h2>
            <p className="text-3xl font-semibold tabular-nums">{percent == null ? "—" : percent.toFixed(1) + "%"} <span className="text-sm font-normal">GPU occupancy</span></p>
            <div aria-hidden="true" className="h-2 overflow-hidden rounded bg-muted"><div className="h-full bg-primary" style={{ width: (percent ?? 0) + "%" }} /></div>
            <dl className="grid grid-cols-2 gap-1 text-sm">
              <dt>Finish time</dt><dd>{m.makespan_ticks_from_zero} ticks</dd>
              <dt>Throughput</dt><dd>{m.completed_jobs_per_hour?.toFixed(1) ?? "—"} jobs/hour</dd>
              <dt>Completed</dt><dd>{m.completed}</dd>
              <dt>Unscheduled</dt><dd>{m.unscheduled}</dd>
            </dl>
          </article>;
        })}
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm tabular-nums">
          <caption className="pb-3 text-left font-semibold">Queue wait by job (ticks)</caption>
          <thead><tr>{["Job", "Priority", "GPUs", "FIFO wait", "Priority wait"].map(label => <th key={label} className="p-2">{label}</th>)}</tr></thead>
          <tbody>{result.jobs.map(job => <tr key={job.id} className="border-t">
            <th className="p-2">{job.id}</th><td>{job.priority}</td><td>{job.gpus}</td>
            <td>{job.fifo_wait ?? "Unscheduled"}</td><td>{job.priority_wait ?? "Unscheduled"}</td>
          </tr>)}</tbody>
        </table>
      </div>
    </section>}
  </>;
}

export function ReplayPage() {
  const [scenario, setScenario] = useState<Scenario>("oracle");
  return <main className="mx-auto max-w-4xl space-y-5 px-4 py-8">
    <h1 className="text-3xl font-semibold tracking-tight">Queue policy replay</h1>
    <p className="text-muted-foreground">Compare FIFO and Priority on the same synthetic workload with fixed job durations.</p>
    <label className="flex flex-wrap items-center gap-3 text-sm font-medium">Scenario
      <select className="rounded-md border bg-background px-3 py-2" value={scenario} onChange={e => setScenario(e.target.value as Scenario)}>
        <option value="oracle">Two-GPU hand check</option><option value="contention">Three-node contention</option>
      </select>
    </label>
    <Experiment key={scenario} scenario={scenario} />
  </main>;
}
