import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router-dom";
import { loadReplayRun, saveReplayRun, type ReplayRun, type RunRequest } from "@/api/replay";
import { Button } from "@/components/ui/button";
import {
  ReplayTopologyFields, resizeReplayTopology, type ReplayTopology,
} from "@/components/ReplayTopologyFields";

type Workload = NonNullable<RunRequest["preset"]> | "import";
type Scenario = NonNullable<RunRequest["scenario"]>;

const linear: ReplayTopology = { kind: "linear" };

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function editableTopology(value: unknown): ReplayTopology {
  if (!isRecord(value) || value.kind !== "leaf_spine") return linear;
  if (!Array.isArray(value.leaves) || !value.leaves.length || !value.leaves.every(Number.isSafeInteger) ||
      !Array.isArray(value.uplinks) || !value.uplinks.every(link => isRecord(link) &&
        Number.isSafeInteger(link.leaf) && Number.isSafeInteger(link.spine)) ||
      !Array.isArray(value.attachments) || !value.attachments.every(link => isRecord(link) &&
        Number.isSafeInteger(link.node) && Number.isSafeInteger(link.leaf))) {
    throw new Error("The leaf–spine scenario has invalid topology fields.");
  }
  return value as ReplayTopology;
}

function readScenario(text: string): Scenario {
  const value: unknown = JSON.parse(text);
  if (!isRecord(value) || ![1, 2].includes(Number(value.schema_version)) ||
      typeof value.source !== "string" || !value.source.trim() || !Number.isSafeInteger(value.seconds_per_tick) ||
      Number(value.seconds_per_tick) < 1 || !Array.isArray(value.jobs) || !value.jobs.length ||
      !Array.isArray(value.nodes) || !value.nodes.length || value.nodes.length > 4 ||
      !value.nodes.every(node => isRecord(node) && Number.isSafeInteger(node.id) && Number(node.id) > 0 &&
        Number.isSafeInteger(node.gpus) && Number(node.gpus) > 0 && Number(node.gpus) <= 1024)) {
    throw new Error("Choose a compatible replay Scenario JSON file with 1–4 nodes and a nonempty job trace.");
  }
  if (value.topology != null) editableTopology(value.topology);
  return value as Scenario;
}

function effectiveNodeIds(count: number, original: readonly number[]) {
  return original.length === count ? [...original] : Array.from({ length: count }, (_, index) => index + 1);
}

function requestId() {
  if (typeof crypto.randomUUID === "function") return crypto.randomUUID();
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 15) | 64;
  bytes[8] = (bytes[8] & 63) | 128;
  const hex = Array.from(bytes, byte => byte.toString(16).padStart(2, "0")).join("");
  return [hex.slice(0, 8), hex.slice(8, 12), hex.slice(12, 16), hex.slice(16, 20), hex.slice(20)].join("-");
}

function ReplayForm({ startingRun }: { startingRun?: ReplayRun }) {
  const [workload, setWorkload] = useState<Workload>("oracle");
  const [imported, setImported] = useState<Scenario>();
  const [importError, setImportError] = useState("");
  const [reading, setReading] = useState(false);
  const originalTopology = startingRun?.inputs.topology ?? imported?.topology;
  const [topology, setTopology] = useState<ReplayTopology>(() => editableTopology(originalTopology));
  const [nodes, setNodes] = useState<string[]>(() => startingRun?.gpus_per_node.map(String) ?? ["2"]);
  const sourceNodes: unknown = startingRun?.inputs.scenario.nodes ?? imported?.nodes;
  const originalIds = Array.isArray(sourceNodes) ? sourceNodes.map(node => Number(node.id)) : [];
  const nodeIds = effectiveNodeIds(nodes.length, originalIds);
  const [failedRequest, setFailedRequest] = useState<RunRequest>();
  const submitting = useRef(false);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const run = useMutation({
    mutationFn: saveReplayRun,
    onSuccess: (saved) => {
      queryClient.setQueryData(["replay-run", saved.id], saved);
      void queryClient.invalidateQueries({ queryKey: ["replay-history"] });
    },
    onSettled: () => { submitting.current = false; },
  });
  const counts = nodes.map(Number);
  const invalidCounts = counts.some(n => !Number.isInteger(n) || n < 1 || n > 1024);
  const missingImport = workload === "import" && !imported;

  function edit() {
    setFailedRequest(undefined);
    run.reset();
  }

  async function importScenario(file: File) {
    edit();
    setImported(undefined);
    setImportError("");
    setNodes(["2"]);
    setTopology(linear);
    setReading(true);
    try {
      const scenario = readScenario(await file.text());
      setImported(scenario);
      setNodes(scenario.nodes.map(node => String(node.gpus)));
      setTopology(editableTopology(scenario.topology));
    } catch (error) {
      setImportError(error instanceof SyntaxError ? "This file does not contain valid JSON." :
        error instanceof Error ? error.message : "The scenario file could not be read.");
    } finally {
      setReading(false);
    }
  }

  function submit() {
    if (submitting.current || invalidCounts || missingImport || reading) return;
    const source = startingRun ? { starting_run_id: startingRun.id }
      : workload === "import" ? { scenario: imported } : { preset: workload };
    const body = failedRequest ?? {
      request_id: requestId(),
      ...source,
      gpus_per_node: counts,
      ...(topology.kind === "leaf_spine" || editableTopology(originalTopology).kind === "leaf_spine" ? { topology } : {}),
    };
    submitting.current = true;
    run.mutate(body, {
      onSuccess: saved => navigate(`/replay/runs/${saved.id}`),
      onError: () => setFailedRequest(body),
    });
  }

  return <form className="space-y-5" onSubmit={event => { event.preventDefault(); submit(); }}>
    <fieldset className="space-y-5" disabled={run.isPending || reading}>
      {startingRun
        ? <p className="text-sm">Workload snapshot <strong>{startingRun.workload_label}</strong>. The saved trace will be reused.</p>
        : <label className="flex flex-wrap items-center gap-3 text-sm font-medium">Scenario
            <select className="rounded-md border bg-background px-3 py-2" value={workload}
              onChange={e => {
                const next = e.target.value as Workload;
                if (next === "import" || workload === "import") {
                  setNodes(["2"]);
                  setTopology(linear);
                  setImported(undefined);
                  setImportError("");
                }
                setWorkload(next);
                edit();
              }}>
              <option value="oracle">Hand-check workload</option>
              <option value="contention">Contention workload</option>
              <option value="import">Import Scenario JSON</option>
            </select>
          </label>}
      {workload === "import" && <div className="space-y-2">
        <label className="grid gap-1 text-sm font-medium">
          Scenario JSON file
          <input className="max-w-full rounded border px-2 py-1" type="file" accept=".json,application/json"
            onChange={event => {
              const file = event.target.files?.[0];
              if (file) void importScenario(file);
            }} />
        </label>
        {reading && <p role="status" className="text-sm">Reading scenario…</p>}
        {importError && <p role="alert" className="text-sm text-destructive">{importError}</p>}
        {imported && <p className="text-sm">{imported.source} · {imported.jobs.length} jobs · {imported.seconds_per_tick} seconds per tick</p>}
      </div>}
      <fieldset className="space-y-3 rounded-xl border p-4">
        <legend className="px-2 font-semibold">Cluster configuration</legend>
        <label>Node count <select className="ml-2 rounded border bg-background p-1" value={nodes.length}
          onChange={e => {
            const count = Number(e.target.value);
            setNodes(Array.from({ length: count }, (_, i) => nodes[i] ?? "2"));
            setTopology(value => resizeReplayTopology(value, effectiveNodeIds(count, originalIds)));
            edit();
          }}>
          {[1, 2, 3, 4].map(n => <option key={n}>{n}</option>)}
        </select></label>
        <div className="flex flex-wrap gap-4">{nodes.map((count, index) =>
          <label key={index} className="grid gap-1 text-sm">Node {nodeIds[index]} GPUs
            <input className="w-24 rounded border bg-background p-2" type="number" min={1} max={1024} required
              value={count} onChange={e => {
                setNodes(nodes.map((n, i) => i === index ? e.target.value : n));
                edit();
              }} />
          </label>
        )}</div>
        <p className="text-sm text-muted-foreground">1–1,024 whole GPUs per node</p>
        <ReplayTopologyFields nodeIds={nodeIds} value={topology} onChange={value => { setTopology(value); edit(); }} />
      </fieldset>
    </fieldset>
    <Button type="submit" disabled={run.isPending || invalidCounts || missingImport || reading}>
      {run.isPending ? "Running…" : failedRequest ? "Retry comparison" : "Run comparison"}
    </Button>
    {run.isError && <p role="alert" className="text-destructive">{run.error.message} Your configuration is still here.</p>}
  </form>;
}

export function ReplayPage() {
  return <main className="mx-auto max-w-4xl space-y-5 px-4 py-8">
    <header className="space-y-2">
      <h1 className="text-3xl font-semibold tracking-tight">Queue policy replay</h1>
      <p className="text-muted-foreground">Compare FIFO and Priority on the same workload with fixed job durations.</p>
      <Link className="text-sm text-primary underline" to="/replay/runs">Run history</Link>
    </header>
    <ReplayForm />
  </main>;
}

export function ReplayForkPage() {
  const { runId = "" } = useParams();
  const run = useQuery({ queryKey: ["replay-run", runId], queryFn: () => loadReplayRun(runId) });
  return <main className="mx-auto max-w-4xl space-y-5 px-4 py-8">
    <Link className="text-sm text-primary underline" to={`/replay/runs/${runId}`}>Back to saved result</Link>
    <h1 className="text-3xl font-semibold tracking-tight">New run from saved inputs</h1>
    {run.isPending && <p role="status">Loading saved inputs…</p>}
    {run.isError && <p role="alert" className="text-destructive">{run.error.message}</p>}
    {run.data && (run.data.can_reuse
      ? <ReplayForm key={runId} startingRun={run.data} />
      : <p>This saved input format is unavailable for reuse. You can still inspect its recorded result.</p>)}
  </main>;
}
