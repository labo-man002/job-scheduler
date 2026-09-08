import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ChevronRight, Server } from "lucide-react";
import { api } from "@/api/client";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/EmptyState";

function ClusterCardSkeleton() {
  return (
    <Card className="p-4">
      <div className="flex items-center gap-3">
        <Skeleton className="size-9 shrink-0" />
        <div className="w-full space-y-2">
          <Skeleton className="h-4 w-32" />
          <Skeleton className="h-3 w-48" />
        </div>
      </div>
      <Skeleton className="mt-3 h-1.5 w-full" />
    </Card>
  );
}

export function ClustersPage() {
  const { data, isPending, isError, error } = useQuery({
    queryKey: ["clusters"],
    queryFn: async () => {
      const { data, error } = await api.GET("/clusters");
      if (error) throw error;
      return data;
    },
  });

  if (isError) return <p className="p-6 text-destructive">Failed to load clusters: {String(error)}</p>;

  return (
    <div className="p-6 max-w-3xl">
      <h1 className="text-2xl font-semibold tracking-tight mb-4">Clusters</h1>
      {isPending ? (
        <div className="space-y-3">
          {[0, 1, 2].map((i) => (
            <ClusterCardSkeleton key={i} />
          ))}
        </div>
      ) : data.length === 0 ? (
        <EmptyState icon={Server} title="No clusters yet" description="Clusters are created via the backend API." />
      ) : (
        <ul className="space-y-3">
          {data.map((cluster) => {
            const freeRatio = cluster.total_capacity === 0 ? 0 : cluster.free_capacity / cluster.total_capacity;
            return (
              <li key={cluster.cluster_id}>
                <Link to={`/clusters/${cluster.cluster_id}`} className="block group">
                  <Card className="p-4 transition-shadow hover:shadow-md">
                    <div className="flex items-center justify-between gap-4">
                      <div className="flex items-center gap-3">
                        <div className="flex size-9 items-center justify-center rounded-md bg-secondary text-secondary-foreground">
                          <Server className="size-4" />
                        </div>
                        <div>
                          <div className="font-medium">{cluster.cluster_name}</div>
                          <div className="font-mono text-xs text-muted-foreground">
                            {cluster.topology_type} · {cluster.free_capacity}/{cluster.total_capacity} free
                          </div>
                        </div>
                      </div>
                      <ChevronRight className="size-4 text-muted-foreground transition-transform group-hover:translate-x-0.5" />
                    </div>
                    <div className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-muted">
                      <div className="h-full rounded-full bg-primary transition-all" style={{ width: `${freeRatio * 100}%` }} />
                    </div>
                  </Card>
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
