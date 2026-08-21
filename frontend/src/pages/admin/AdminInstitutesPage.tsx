import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Building2, Plus } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/EmptyState";
import { formatApiError } from "@/lib/apiError";

const INPUT_CLASS = "h-8 rounded-md border bg-background px-2 text-sm";

export function AdminInstitutesPage() {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");

  const institutesQuery = useQuery({
    queryKey: ["institutes"],
    queryFn: async () => {
      const { data, error } = await api.GET("/institutes");
      if (error) throw error;
      return data;
    },
  });

  const create = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/institutes", { body: { institute_name: name } });
      if (error) throw error;
      return data;
    },
    onSuccess: (institute) => {
      toast.success(`Institute "${institute.institute_name}" registered`);
      setName("");
      queryClient.invalidateQueries({ queryKey: ["institutes"] });
    },
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (name.trim()) create.mutate();
  }

  return (
    <div className="max-w-xl space-y-4">
      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          className={`${INPUT_CLASS} flex-1`}
          placeholder="Institute name"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <Button type="submit" size="sm" disabled={!name.trim() || create.isPending}>
          <Plus />
          Register
        </Button>
      </form>
      {create.isError && <p className="text-sm text-destructive">{formatApiError(create.error)}</p>}

      {institutesQuery.isPending && (
        <div className="space-y-2">
          {[0, 1].map((i) => (
            <Skeleton key={i} className="h-12 w-full" />
          ))}
        </div>
      )}
      {institutesQuery.isError && <p className="text-destructive">Failed to load institutes: {String(institutesQuery.error)}</p>}
      {institutesQuery.data && institutesQuery.data.length === 0 && (
        <EmptyState icon={Building2} title="No institutes yet" description="Register one above to get started." />
      )}
      {institutesQuery.data && institutesQuery.data.length > 0 && (
        <ul className="space-y-2">
          {institutesQuery.data.map((institute) => (
            <li key={institute.institute_id}>
              <Card className="flex items-center gap-3 p-3">
                <Building2 className="size-4 text-muted-foreground" />
                <span className="font-medium">{institute.institute_name}</span>
                <span className="font-mono text-xs text-muted-foreground">institute {institute.institute_id}</span>
              </Card>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
