import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, User } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/EmptyState";
import { formatApiError } from "@/lib/apiError";

const INPUT_CLASS = "h-8 rounded-md border bg-background px-2 text-sm";

export function AdminClientsPage() {
  const queryClient = useQueryClient();
  const [owner, setOwner] = useState("");
  const [newClientInstituteId, setNewClientInstituteId] = useState<number | "">("");
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

  const clientsQuery = useQuery({
    queryKey: ["clients", { filterInstituteId }],
    queryFn: async () => {
      const { data, error } = await api.GET("/clients", {
        params: { query: { institute_id: filterInstituteId === "" ? undefined : filterInstituteId } },
      });
      if (error) throw error;
      return data;
    },
  });

  const create = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/clients", { body: { owner, institute_id: newClientInstituteId as number } });
      if (error) throw error;
      return data;
    },
    onSuccess: (client) => {
      toast.success(`Client "${client.owner}" registered`);
      setOwner("");
      queryClient.invalidateQueries({ queryKey: ["clients"] });
    },
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (owner.trim() && newClientInstituteId !== "") create.mutate();
  }

  return (
    <div className="max-w-xl space-y-4">
      <form onSubmit={handleSubmit} className="flex gap-2">
        <input className={`${INPUT_CLASS} flex-1`} placeholder="Owner name" value={owner} onChange={(e) => setOwner(e.target.value)} />
        <select
          className={INPUT_CLASS}
          value={newClientInstituteId}
          onChange={(e) => setNewClientInstituteId(e.target.value === "" ? "" : Number(e.target.value))}
        >
          <option value="">Institute…</option>
          {(institutesQuery.data ?? []).map((i) => (
            <option key={i.institute_id} value={i.institute_id}>
              {i.institute_name}
            </option>
          ))}
        </select>
        <Button type="submit" size="sm" disabled={!owner.trim() || newClientInstituteId === "" || create.isPending}>
          <Plus />
          Register
        </Button>
      </form>
      {create.isError && <p className="text-sm text-destructive">{formatApiError(create.error)}</p>}

      <select
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

      {clientsQuery.isPending && (
        <div className="space-y-2">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-12 w-full" />
          ))}
        </div>
      )}
      {clientsQuery.isError && <p className="text-destructive">Failed to load clients: {String(clientsQuery.error)}</p>}
      {clientsQuery.data && clientsQuery.data.length === 0 && (
        <EmptyState icon={User} title="No clients yet" description="Register one above to get started." />
      )}
      {clientsQuery.data && clientsQuery.data.length > 0 && (
        <ul className="space-y-2">
          {clientsQuery.data.map((client) => (
            <li key={client.client_id}>
              <Card className="flex items-center gap-3 p-3">
                <User className="size-4 text-muted-foreground" />
                <span className="font-medium">{client.owner}</span>
                <span className="font-mono text-xs text-muted-foreground">
                  client {client.client_id} · {instituteNameById.get(client.institute_id) ?? `institute ${client.institute_id}`} ·{" "}
                  {client.client_status}
                </span>
              </Card>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
