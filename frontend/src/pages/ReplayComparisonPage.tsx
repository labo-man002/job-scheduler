import { useQueries } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";
import { loadReplayRun, type Comparison, type ReplayRun } from "@/api/replay";
import { ReplayRows } from "@/components/ReplayRows";
import { policyLabels, replayPolicies, runName } from "@/lib/replayDisplay";

const number = new Intl.NumberFormat(undefined, { maximumFractionDigits: 3 });
const signed = new Intl.NumberFormat(undefined, { maximumFractionDigits: 3, signDisplay: "exceptZero" });
type ReplayPolicy = typeof replayPolicies[number];

function topologyText(topology: unknown): string {
  if (!topology || typeof topology !== "object" || !("kind" in topology)) return "Unavailable";
  if (topology.kind === "linear") return "Linear";
  if (topology.kind !== "leaf_spine") return JSON.stringify(topology);
  const formatPairs = (pairs: unknown, first: string, second: string) =>
    Array.isArray(pairs) ? pairs.map(entry => `${entry[first]}→${entry[second]}`).join(", ") : "Unavailable";
  const fabric = topology as { leaves?: number[]; uplinks?: unknown; attachments?: unknown };
  return `Leaf–spine · leaves ${fabric.leaves?.join(", ") ?? "Unavailable"} · leaf→spine ${formatPairs(fabric.uplinks, "leaf", "spine")} · node→leaf ${formatPairs(fabric.attachments, "node", "leaf")}`;
}

function meanWait(result: Comparison, policy: ReplayPolicy) {
  const waits = result.jobs.flatMap(job => {
    const wait = policy === "fifo" ? job.fifo_wait : job.priority_wait;
    return wait == null ? [] : [wait * result.seconds_per_tick];
  });
  return waits.length ? waits.reduce((sum, value) => sum + value, 0) / waits.length : null;
}

function metricRows(baseline: Comparison, alternative: Comparison, policy: ReplayPolicy) {
  const before = baseline[policy];
  const after = alternative[policy];
  return [
    { label: "Completed jobs", before: before.completed, after: after.completed },
    { label: "Last completion from trace origin (s)", before: before.makespan_ticks_from_zero * baseline.seconds_per_tick,
      after: after.makespan_ticks_from_zero * alternative.seconds_per_tick },
    { label: "Mean wait of completed jobs (s)", before: meanWait(baseline, policy), after: meanWait(alternative, policy) },
    { label: "Unscheduled jobs", before: before.unscheduled, after: after.unscheduled },
    { label: "GPU occupancy (%)", deltaUnit: " pp", before: before.occupancy == null ? null : before.occupancy * 100,
      after: after.occupancy == null ? null : after.occupancy * 100 },
    { label: "Throughput (jobs/hour)", before: before.completed_jobs_per_hour, after: after.completed_jobs_per_hour },
    { label: "Cross-leaf placements", before: before.cross_leaf_placements, after: after.cross_leaf_placements },
  ];
}

function JobWaits({ baseline, alternative }: { baseline: Comparison; alternative: Comparison }) {
  const indexed = new Map(alternative.jobs.map(job => [job.id, job]));
  const toSeconds = (wait: number | null | undefined, secondsPerTick: number) => wait == null
    ? "Unscheduled" : number.format(wait * secondsPerTick);
  const delta = (before: number | null | undefined, after: number | null | undefined) =>
    before == null || after == null ? "Unavailable"
      : signed.format(after * alternative.seconds_per_tick - before * baseline.seconds_per_tick);
  return <details className="rounded-lg border p-3">
    <summary className="cursor-pointer font-semibold">Per-job waits (seconds)</summary>
    <ReplayRows rows={baseline.jobs} label="Jobs">{visible => <div className="overflow-x-auto">
      <table className="mt-3 w-full text-left text-sm tabular-nums">
        <caption className="sr-only">Per-job wait comparison in seconds</caption>
        <thead><tr>{["Job", "FIFO baseline", "FIFO alternative", "FIFO Δ", "Priority baseline", "Priority alternative", "Priority Δ"].map(label =>
          <th scope="col" key={label} className="p-2">{label}</th>)}</tr></thead>
        <tbody>{visible.map(job => {
          const other = indexed.get(job.id);
          return <tr key={job.id} className="border-t">
            <th scope="row" className="p-2">{job.id}</th>
            <td>{toSeconds(job.fifo_wait, baseline.seconds_per_tick)}</td>
            <td>{toSeconds(other?.fifo_wait, alternative.seconds_per_tick)}</td>
            <td>{delta(job.fifo_wait, other?.fifo_wait)}</td>
            <td>{toSeconds(job.priority_wait, baseline.seconds_per_tick)}</td>
            <td>{toSeconds(other?.priority_wait, alternative.seconds_per_tick)}</td>
            <td>{delta(job.priority_wait, other?.priority_wait)}</td>
          </tr>;
        })}</tbody>
      </table>
    </div>}</ReplayRows>
  </details>;
}

function RunComparison({ baseline, alternative }: { baseline: ReplayRun; alternative: ReplayRun }) {
  const oldInputs = baseline.inputs;
  const newInputs = alternative.inputs;
  const oldResult = baseline.outputs.comparison;
  const newResult = alternative.outputs.comparison;
  const traceKnown = Boolean(oldInputs.trace_sha256 && newInputs.trace_sha256);
  const sameTrace = traceKnown && oldInputs.trace_sha256 === newInputs.trace_sha256;
  const describeNodes = (run: ReplayRun) => Array.isArray(run.inputs.scenario.nodes)
    ? run.inputs.scenario.nodes.map(node => `node ${node.id}: ${node.gpus} GPUs`).join(" · ") : "Unavailable";
  const describeQueue = (run: ReplayRun) => run.inputs.queue_policies.join(", ");
  const inputs = [
    { label: "Trace SHA-256", before: oldInputs.trace_sha256, after: newInputs.trace_sha256 },
    { label: "Hardware", before: describeNodes(baseline), after: describeNodes(alternative) },
    { label: "Topology", before: topologyText(oldInputs.topology), after: topologyText(newInputs.topology) },
    { label: "Queue policies", before: describeQueue(baseline), after: describeQueue(alternative) },
    { label: "Placement", before: oldInputs.placement, after: newInputs.placement },
    { label: "Service times", before: oldInputs.service_time, after: newInputs.service_time },
    { label: "Seconds per tick", before: oldResult.seconds_per_tick, after: newResult.seconds_per_tick },
  ];
  return <>
    <section aria-label="Input differences" className="space-y-3">
      <h2 className="text-xl font-semibold">Input differences</h2>
      {!sameTrace && <p role="status" className="rounded-lg border p-3 text-sm">
        {traceKnown
          ? "The workload changed. Outcome differences may reflect both the workload and the configuration. Per-job pairing is unavailable."
          : "The workload hash is unavailable for one or both runs. The same workload cannot be verified."}
      </p>}
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead><tr><th scope="col" className="p-2">Input</th>
            <th scope="col" className="p-2">Baseline: <Link className="text-primary underline" to={`/replay/runs/${baseline.id}`}>{runName(baseline)}</Link></th>
            <th scope="col" className="p-2">Alternative: <Link className="text-primary underline" to={`/replay/runs/${alternative.id}`}>{runName(alternative)}</Link></th>
            <th scope="col" className="p-2">Status</th></tr></thead>
          <tbody>{inputs.map(({ label, before, after }) => <tr key={label} className="border-t align-top">
            <th scope="row" className="p-2">{label}</th>
            <td className="break-all p-2">{before ?? "Unavailable"}</td><td className="break-all p-2">{after ?? "Unavailable"}</td>
            <td className="p-2">{before == null || after == null || before === "Unavailable" || after === "Unavailable"
              ? "Unavailable" : before === after ? "Same" : "Changed"}</td>
          </tr>)}</tbody>
        </table>
      </div>
    </section>
    <section aria-label="Outcome differences" className="space-y-3">
      <h2 className="text-xl font-semibold">Outcome differences</h2>
      <div className="grid gap-4 lg:grid-cols-2">
        {replayPolicies.map(policy => <section key={policy} className="rounded-xl border bg-card p-4">
          <h3 className="font-semibold">{policyLabels[policy]}</h3>
          <table className="mt-2 w-full text-left text-sm tabular-nums">
            <thead><tr>{["Metric", "Baseline", "Alternative", "Δ"].map(label => <th key={label} className="py-1 pr-2" scope="col">{label}</th>)}</tr></thead>
            <tbody>{metricRows(oldResult, newResult, policy).map(({ label, before, after, deltaUnit }) => <tr key={label} className="border-t">
              <th className="py-1 pr-2 font-normal" scope="row">{label}</th>
              <td className="py-1 pr-2">{before == null ? "Unavailable" : number.format(before)}</td>
              <td className="py-1 pr-2">{after == null ? "Unavailable" : number.format(after)}</td>
              <td className="py-1 pr-2">{before == null || after == null ? "Unavailable" : signed.format(after - before) + (deltaUnit ?? "")}</td>
            </tr>)}</tbody>
          </table>
        </section>)}
      </div>
      {sameTrace && <JobWaits baseline={oldResult} alternative={newResult} />}
    </section>
  </>;
}

export function ReplayComparisonPage() {
  const [search] = useSearchParams();
  const baseline = search.get("baseline");
  const alternative = search.get("alternative");
  const [baselineRun, alternativeRun] = useQueries({
    queries: [baseline, alternative].map(id => ({
      queryKey: ["replay-run", id],
      queryFn: () => loadReplayRun(id ?? ""),
      enabled: Boolean(id),
    })),
  });
  const error = baselineRun.error ?? alternativeRun.error;
  return <main className="mx-auto max-w-6xl space-y-6 px-4 py-8">
    <Link className="text-sm text-primary underline" to={`/replay/runs?${search.toString()}`}>Run history</Link>
    <h1 className="text-3xl font-semibold tracking-tight">Compare saved runs</h1>
    {!baseline || !alternative
      ? <p>Select a baseline and an alternative in run history.</p>
      : <>
        {(baselineRun.isPending || alternativeRun.isPending) && <p role="status">Loading runs…</p>}
        {error && <p role="alert" className="text-destructive">{error.message}</p>}
        {baselineRun.data && alternativeRun.data && <RunComparison baseline={baselineRun.data} alternative={alternativeRun.data} />}
      </>}
  </main>;
}
