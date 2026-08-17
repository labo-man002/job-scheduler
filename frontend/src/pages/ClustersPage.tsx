import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";

export function ClustersPage() {
  const { data, isPending, isError, error } = useQuery({
    queryKey: ["clusters"],
    queryFn: async () => {
      const { data, error } = await api.GET("/clusters");
      if (error) throw error;
      return data;
    },
  });

  if (isPending) return <p className="p-6 text-muted-foreground">Loading clusters…</p>;
  if (isError) return <p className="p-6 text-destructive">Failed to load clusters: {String(error)}</p>;

  return (
    <div className="p-6">
      <h1 className="text-2xl font-semibold mb-4">Clusters</h1>
      {data.length === 0 ? (
        <p className="text-muted-foreground">No clusters yet.</p>
      ) : (
        <ul className="space-y-2">
          {data.map((cluster) => (
            <li key={cluster.cluster_id} className="rounded-md border p-4">
              <div className="font-medium">{cluster.cluster_name}</div>
              <div className="text-sm text-muted-foreground">
                {cluster.topology_type} · {cluster.free_capacity}/{cluster.total_capacity} free
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
