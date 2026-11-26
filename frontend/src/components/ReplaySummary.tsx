import type { components } from "@/api/schema";

type Comparison = components["schemas"]["Comparison"];
const number = new Intl.NumberFormat("en", { maximumFractionDigits: 2 });

export function ReplaySummary({ result, capacity }: { result: Comparison; capacity: number }) {
  const { fifo, priority, jobs, seconds_per_tick: seconds } = result;
  const time = (ticks: number) => seconds % 60 === 0
    ? number.format(ticks * seconds / 60) + " min"
    : number.format(ticks * seconds) + " s";
  const finishDelta = priority.makespan_ticks_from_zero - fifo.makespan_ticks_from_zero;
  const headline = !fifo.completed && !priority.completed ? "Neither policy completed a job."
    : finishDelta === 0 ? "Both policies finished at " + time(fifo.makespan_ticks_from_zero) + "."
    : (finishDelta > 0 ? "FIFO" : "Priority") + " finished " + time(Math.abs(finishDelta)) + " earlier.";
  const rejected = jobs.filter(job => job.reason === "cannot_fit_empty_cluster");
  const gpuTime = (m: Comparison["fifo"]) => {
    const available = capacity * m.makespan_ticks_from_zero;
    return number.format(Math.round((m.occupancy ?? 0) * available)) + " of " + number.format(available);
  };

  return <section className="space-y-3 rounded-xl border bg-card p-5" aria-label="Run interpretation">
    <h2 className="text-xl font-semibold">{headline}</h2>
    <p>FIFO completed {fifo.completed} of {jobs.length} jobs. Priority completed {priority.completed} of {jobs.length}.</p>
    <ul className="list-disc space-y-1 pl-5">
      {["URGENT", "HIGH", "NORMAL", "LOW"].map(rank => {
        const pairs = jobs.flatMap(job => job.priority === rank && job.fifo_wait != null && job.priority_wait != null
          ? [[job.fifo_wait, job.priority_wait]] : []);
        if (!pairs.length) return null;
        const before = pairs.reduce((sum, pair) => sum + pair[0], 0) / pairs.length;
        const after = pairs.reduce((sum, pair) => sum + pair[1], 0) / pairs.length;
        const change = after === before ? "the same under both policies"
          : time(Math.abs(after - before)) + (after < before ? " shorter" : " longer") + " under Priority";
        return <li key={rank}><strong>{rank.toLowerCase()} priority ({pairs.length})</strong> — mean wait was {time(before)} with FIFO and {time(after)} with Priority, {change}.</li>;
      })}
    </ul>
    {fifo.occupancy != null && priority.occupancy != null && <p className="text-sm">
      FIFO allocated {gpuTime(fifo)} available GPU-ticks. Priority allocated {gpuTime(priority)}.
      {" "}One GPU-tick means reserving one GPU for {time(1)}. Job execution times are fixed in this experiment.
    </p>}
    {rejected.length > 0 && <p className="text-sm">Jobs exceeding this cluster’s {capacity}-GPU capacity: {rejected.map(job => "#" + job.id + " (" + job.gpus + " GPUs requested)").join(", ")}.</p>}
  </section>;
}
