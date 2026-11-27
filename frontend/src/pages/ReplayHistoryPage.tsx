import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";
import { listReplayRuns } from "@/api/replay";
import { Button } from "@/components/ui/button";
import { clusterShape, runName, runTime } from "@/lib/replayDisplay";

export function ReplayHistoryPage() {
  const [search, setSearch] = useSearchParams();
  const [cursors, setCursors] = useState<Array<string | null>>([null]);
  const cursor = cursors[cursors.length - 1];
  const { data: page, isPending, isError, error, refetch } = useQuery({
    queryKey: ["replay-history", cursor],
    queryFn: () => listReplayRuns(cursor),
  });
  const baseline = search.get("baseline");
  const alternative = search.get("alternative");

  function select(role: "baseline" | "alternative", id: string) {
    const next = new URLSearchParams(search);
    next.set(role, id);
    setSearch(next, { replace: true });
  }

  return <main className="mx-auto max-w-5xl space-y-5 px-4 py-8">
    <Link className="text-sm text-primary underline" to="/replay">New replay</Link>
    <h1 className="text-3xl font-semibold tracking-tight">Run history</h1>
    {isPending && <p role="status">Loading run history…</p>}
    {isError && <div className="space-y-2">
      <p role="alert" className="text-destructive">{error.message}</p>
      <Button variant="outline" type="button" onClick={() => void refetch()}>Retry history</Button>
    </div>}
    {page?.items.length === 0 && <p>No saved runs yet.</p>}
    {page && page.items.length > 0 && <>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <caption className="sr-only">Choose a baseline and an alternative to compare saved experiments</caption>
          <thead><tr>{["Run", "Cluster", "Baseline", "Alternative", "Actions"].map(label => <th className="p-2" scope="col" key={label}>{label}</th>)}</tr></thead>
          <tbody>{page.items.map(run => <tr key={run.id} className="border-t">
            <th className="p-2 font-medium" scope="row">
              {runName(run)}
              <time className="block font-normal text-muted-foreground" dateTime={run.created_at}>{runTime(run.created_at)}</time>
            </th>
            <td className="p-2">{clusterShape(run.gpus_per_node)}</td>
            <td className="p-2"><input type="radio" name="baseline" aria-label={`Baseline: ${runName(run)}`}
              checked={baseline === run.id} onChange={() => select("baseline", run.id)} /></td>
            <td className="p-2"><input type="radio" name="alternative" aria-label={`Alternative: ${runName(run)}`}
              checked={alternative === run.id} onChange={() => select("alternative", run.id)} /></td>
            <td className="space-y-1 p-2 text-primary">
              <Link className="block underline" to={`/replay/runs/${run.id}`}>Open result</Link>
              {run.can_reuse && <Link className="block underline" to={`/replay/runs/${run.id}/fork`}>Use as starting point</Link>}
            </td>
          </tr>)}</tbody>
        </table>
      </div>
      {baseline && alternative
        ? <Button asChild><Link to={`/replay/compare?${new URLSearchParams({ baseline, alternative }).toString()}`}>Compare saved runs</Link></Button>
        : <p className="text-sm text-muted-foreground">Select a baseline and an alternative to compare their outcomes.</p>}
    </>}
    {(cursor || page?.next_before_id) && <nav className="flex gap-2" aria-label="Run history pages">
      <Button variant="outline" type="button" disabled={!cursor} onClick={() => setCursors(previous => previous.slice(0, -1))}>Previous runs</Button>
      <Button variant="outline" type="button" disabled={!page?.next_before_id} onClick={() => {
        if (page?.next_before_id) setCursors([...cursors, page.next_before_id]);
      }}>Older runs</Button>
    </nav>}
  </main>;
}
