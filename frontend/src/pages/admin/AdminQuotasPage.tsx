import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Gauge, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/api/client";
import type { components } from "@/api/schema.d.ts";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/EmptyState";
import { formatApiError } from "@/lib/apiError";

type ResourceType = components["schemas"]["ResourceType"];

const RESOURCE_TYPES: ResourceType[] = ["CPU", "GPU", "MEM"];
const INPUT_CLASS = "h-8 rounded-md border bg-background px-2 text-sm";

export function AdminQuotasPage() {
  const queryClient = useQueryClient();
  const [instituteId, setInstituteId] = useState<number | "">("");
  const [resourceType, setResourceType] = useState<ResourceType>("CPU");
  const [limit, setLimit] = useState(100);
  const [period, setPeriod] = useState(""); // "YYYY-MM", optional -- blank lets the backend default to the current month
  const [filterInstituteId, setFilterInstituteId] = useState<number | "">("");

  const institutesQuery = useQuery({
    queryKey: ["institutes"],
    queryFn: async () => {
      const { data, error } = await api.GET("/institutes");
      if (error) throw error;
      return data;
    },
  });
  const instituteNameById = new Map((institutesQuery.data ?? []).map((i) => [i.institute_id, i.institute_name]));

  const quotasQuery = useQuery({
    queryKey: ["quotas", { filterInstituteId }],
    queryFn: async () => {
      const { data, error } = await api.GET("/quotas", {
        params: { query: { institute_id: filterInstituteId === "" ? undefined : filterInstituteId } },
      });
      if (error) throw error;
      return data;
    },
  });

  const create = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/quotas", {
        body: {
          institute_id: instituteId as number,
          resource_type: resourceType,
          limit,
          period: period ? `${period}-01T00:00:00Z` : undefined,
        },
      });
      if (error) throw error;
      return data;
    },
    onSuccess: () => {
      toast.success("Quota set");
      queryClient.invalidateQueries({ queryKey: ["quotas"] });
    },
  });

  const remove = useMutation({
    mutationFn: async (id: number) => {
      const { data, error } = await api.DELETE("/quotas/{quota_id}", { params: { path: { quota_id: id } } });
      if (error) throw error;
      return data;
    },
    onSuccess: () => {
      toast.success("Quota deleted");
      queryClient.invalidateQueries({ queryKey: ["quotas"] });
    },
  });

  const limitValid = Number.isInteger(limit) && limit > 0;

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (instituteId !== "" && limitValid) create.mutate();
  }

  return (
    <div className="max-w-2xl space-y-4">
      <form onSubmit={handleSubmit} className="flex flex-wrap gap-2">
        <select
          aria-label="Institute"
          className={INPUT_CLASS}
          value={instituteId}
          onChange={(e) => setInstituteId(e.target.value === "" ? "" : Number(e.target.value))}
        >
          <option value="">Institute…</option>
          {(institutesQuery.data ?? []).map((i) => (
            <option key={i.institute_id} value={i.institute_id}>
              {i.institute_name}
            </option>
          ))}
        </select>
        <select aria-label="Resource type" className={INPUT_CLASS} value={resourceType} onChange={(e) => setResourceType(e.target.value as ResourceType)}>
          {RESOURCE_TYPES.map((rt) => (
            <option key={rt} value={rt}>
              {rt}
            </option>
          ))}
        </select>
        <input
          aria-label="Limit"
          type="number"
          min={1}
          step={1}
          className={`${INPUT_CLASS} w-24`}
          value={limit}
          onChange={(e) => setLimit(Number(e.target.value))}
        />
        <input
          aria-label="Month (defaults to the current month if left blank)"
          type="month"
          className={INPUT_CLASS}
          value={period}
          onChange={(e) => setPeriod(e.target.value)}
          title="Month this quota applies to (defaults to the current month if left blank)"
        />
        <Button type="submit" size="sm" disabled={instituteId === "" || !limitValid || create.isPending}>
          <Plus />
          Set quota
        </Button>
      </form>
      {create.isError && <p className="text-sm text-destructive">{formatApiError(create.error)}</p>}

      <select
        aria-label="Filter by institute"
        className={INPUT_CLASS}
        value={filterInstituteId}
        onChange={(e) => setFilterInstituteId(e.target.value === "" ? "" : Number(e.target.value))}
      >
        <option value="">All institutes</option>
        {(institutesQuery.data ?? []).map((i) => (
          <option key={i.institute_id} value={i.institute_id}>
            {i.institute_name}
          </option>
        ))}
      </select>

      {quotasQuery.isPending && (
        <div className="space-y-2">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-12 w-full" />
          ))}
        </div>
      )}
      {quotasQuery.isError && <p className="text-destructive">Failed to load quotas: {String(quotasQuery.error)}</p>}
      {quotasQuery.data && quotasQuery.data.length === 0 && (
        <EmptyState icon={Gauge} title="No quotas set" description="Set one above to cap an institute's concurrent resource usage." />
      )}
      {quotasQuery.data && quotasQuery.data.length > 0 && (
        <ul className="space-y-2">
          {quotasQuery.data.map((quota) => (
            <li key={quota.id}>
              <Card className="flex items-center justify-between gap-3 p-3">
                <div className="flex items-center gap-3">
                  <Gauge className="size-4 text-muted-foreground" />
                  <span className="font-mono text-sm">
                    {instituteNameById.get(quota.institute_id) ?? `institute ${quota.institute_id}`} · {quota.resource_type} ≤{" "}
                    {quota.limit} · {new Date(quota.period).toLocaleDateString(undefined, { year: "numeric", month: "long" })}
                  </span>
                </div>
                <Button
                  variant="ghost"
                  size="icon-sm"
                  aria-label="Delete quota"
                  disabled={remove.isPending}
                  onClick={() => {
                    if (window.confirm("Delete this quota?")) remove.mutate(quota.id);
                  }}
                >
                  <Trash2 />
                </Button>
              </Card>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
