import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { api } from "@/api/client";
import { Button } from "@/components/ui/button";
import { ReplaySummary } from "@/components/ReplaySummary";

type Scenario = "oracle" | "contention";

function Experiment({ scenario, counts }: { scenario: Scenario; counts: number[] }) {
  const replay = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/replay/{scenario_name}", {
        params: { path: { scenario_name: scenario } },
        body: { gpus_per_node: counts },
      });
      if (error || !data) throw new Error("Replay failed. Check the backend connection and try again.");
      return data;
    },
  });
  const result = replay.data;
  return <>
    <Button disabled={replay.isPending || counts.some(n => !Number.isInteger(n) || n < 1 || n > 1024)} onClick={() => replay.mutate()}>
      {replay.isPending ? "Running…" : "Run comparison"}
    </Button>
    {replay.isError && <p role="alert" className="text-destructive">{replay.error.message}</p>}
    {result && <section aria-label="Comparison results" className="space-y-6">
      <p className="text-sm text-muted-foreground">{counts.length} nodes · {counts.join(" + ")} GPUs · {result.seconds_per_tick} seconds per tick</p>
      <ReplaySummary result={result} capacity={counts.reduce((sum, n) => sum + n, 0)} />
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
  const [nodes, setNodes] = useState<string[]>(["2"]);
  return <main className="mx-auto max-w-4xl space-y-5 px-4 py-8">
    <h1 className="text-3xl font-semibold tracking-tight">Queue policy replay</h1>
    <p className="text-muted-foreground">Compare FIFO and Priority on the same synthetic workload with fixed job durations.</p>
    <label className="flex flex-wrap items-center gap-3 text-sm font-medium">Scenario
      <select className="rounded-md border bg-background px-3 py-2" value={scenario} onChange={e => setScenario(e.target.value as Scenario)}>
        <option value="oracle">Hand-check workload</option><option value="contention">Contention workload</option>
      </select>
    </label>
    <fieldset className="space-y-3 rounded-xl border p-4">
      <legend className="px-2 font-semibold">Cluster configuration</legend>
      <label>Node count <select className="ml-2 rounded border bg-background p-1" value={nodes.length}
        onChange={e => setNodes(Array.from({ length: Number(e.target.value) }, (_, i) => nodes[i] ?? "2"))}>
        {[1, 2, 3, 4].map(n => <option key={n}>{n}</option>)}
      </select></label>
      <div className="flex flex-wrap gap-4">{nodes.map((count, index) =>
        <label key={index} className="grid gap-1 text-sm">Node {index + 1} GPUs
          <input className="w-24 rounded border bg-background p-2" type="number" min={1} max={1024} required
            value={count} onChange={e => setNodes(nodes.map((n, i) => i === index ? e.target.value : n))} />
        </label>
      )}</div>
      <p className="text-sm text-muted-foreground">Linear topology · 1–1,024 whole GPUs per node</p>
    </fieldset>
    <Experiment key={scenario + "/" + nodes.join(",")} scenario={scenario} counts={nodes.map(Number)} />
  </main>;
}
