import { useState, type ReactNode } from "react";
import { Button } from "@/components/ui/button";

const pageSize = 50;

export function ReplayRows<T>({ rows, label, children }: {
  rows: readonly T[];
  label: string;
  children: (visible: readonly T[]) => ReactNode;
}) {
  const [page, setPage] = useState(0);
  const lastPage = Math.max(0, Math.ceil(rows.length / pageSize) - 1);
  const current = Math.min(lastPage, page);
  const start = current * pageSize;
  const end = Math.min(start + pageSize, rows.length);
  return <>
    {children(rows.slice(start, end))}
    {lastPage > 0 && <nav aria-label={label + " pages"} className="mt-3 flex flex-wrap items-center gap-3 text-sm">
      <Button type="button" variant="outline" disabled={!current} onClick={() => setPage(current - 1)}>Previous</Button>
      <span>{label} {start + 1}–{end} of {rows.length}</span>
      <Button type="button" variant="outline" disabled={current === lastPage} onClick={() => setPage(current + 1)}>Next</Button>
    </nav>}
  </>;
}
