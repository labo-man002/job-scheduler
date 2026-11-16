import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { ArrowLeft, Plus, X } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/api/client";
import type { components } from "@/api/schema.d.ts";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { formatApiError } from "@/lib/apiError";

type Priority = components["schemas"]["Priority"];
type ResourceType = components["schemas"]["ResourceType"];

const PRIORITIES: Priority[] = ["LOW", "NORMAL", "HIGH", "URGENT"];
const RESOURCE_TYPES: ResourceType[] = ["CPU", "GPU", "MEM"];

const INPUT_CLASS = "h-8 rounded-md border bg-background px-2 text-sm";

interface RequirementRow {
  resource_type: ResourceType;
  amount: number;
}

export function JobSubmitPage() {
  const navigate = useNavigate();
  const clientsQuery = useQuery({
    queryKey: ["clients"],
    queryFn: async () => {
      const { data, error } = await api.GET("/clients");
      if (error) throw error;
      return data;
    },
  });

  const [clientId, setClientId] = useState<number | "">("");
  const [priority, setPriority] = useState<Priority>("NORMAL");
  const [duration, setDuration] = useState(60);
  const [requirements, setRequirements] = useState<RequirementRow[]>([{ resource_type: "CPU", amount: 1 }]);
  const [formError, setFormError] = useState<string | null>(null);

  const submit = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/jobs", {
        body: { client_id: clientId as number, priority, duration, requirements },
      });
      if (error) throw error;
      return data;
    },
    onSuccess: (job) => {
      toast.success(`Job ${job.job_id} submitted`);
      navigate(`/jobs/${job.job_id}`);
    },
  });

  function updateRequirement(index: number, patch: Partial<RequirementRow>) {
    setRequirements((rows) => rows.map((row, i) => (i === index ? { ...row, ...patch } : row)));
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setFormError(null);

    if (clientId === "") {
      setFormError("Pick a client.");
      return;
    }
    const resourceTypes = requirements.map((r) => r.resource_type);
    if (new Set(resourceTypes).size !== resourceTypes.length) {
      setFormError("Each resource type can only appear once across requirements.");
      return;
    }

    submit.mutate();
  }

  return (
    <div className="p-6 max-w-lg space-y-4">
      <div>
        <Link to="/jobs" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground hover:underline">
          <ArrowLeft className="size-3.5" />
          Jobs
        </Link>
        <h1 className="text-2xl font-semibold tracking-tight mt-1">Submit job</h1>
      </div>

      <Card className="p-5">
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="space-y-1">
          <label htmlFor="job-client" className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Client
          </label>
          <select
            id="job-client"
            className={`${INPUT_CLASS} w-full`}
            value={clientId}
            onChange={(e) => setClientId(e.target.value === "" ? "" : Number(e.target.value))}
          >
            <option value="">Select a client…</option>
            {(clientsQuery.data ?? []).map((c) => (
              <option key={c.client_id} value={c.client_id}>
                {c.owner} (client {c.client_id})
              </option>
            ))}
          </select>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-1">
            <label htmlFor="job-priority" className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Priority
            </label>
            <select
              id="job-priority"
              className={`${INPUT_CLASS} w-full`}
              value={priority}
              onChange={(e) => setPriority(e.target.value as Priority)}
            >
              {PRIORITIES.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-1">
            <label htmlFor="job-duration" className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Duration (minutes)
            </label>
            <input
              id="job-duration"
              type="number"
              min={1}
              required
              className={`${INPUT_CLASS} w-full`}
              value={duration}
              onChange={(e) => setDuration(Number(e.target.value))}
            />
          </div>
        </div>

        <div className="space-y-2">
          <label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Resource requirements</label>
          {requirements.map((row, i) => (
            <div key={i} className="flex gap-2">
              <select
                aria-label={`Resource type for requirement ${i + 1}`}
                className={INPUT_CLASS}
                value={row.resource_type}
                onChange={(e) => updateRequirement(i, { resource_type: e.target.value as ResourceType })}
              >
                {RESOURCE_TYPES.map((rt) => (
                  <option key={rt} value={rt}>
                    {rt}
                  </option>
                ))}
              </select>
              <input
                aria-label={`Amount for requirement ${i + 1}`}
                type="number"
                min={1}
                required
                className={`${INPUT_CLASS} w-24`}
                value={row.amount}
                onChange={(e) => updateRequirement(i, { amount: Number(e.target.value) })}
              />
              <Button
                type="button"
                variant="ghost"
                size="icon-sm"
                aria-label={`Remove requirement ${i + 1}`}
                disabled={requirements.length === 1}
                onClick={() => setRequirements((rows) => rows.filter((_, idx) => idx !== i))}
              >
                <X />
              </Button>
            </div>
          ))}
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => setRequirements((rows) => [...rows, { resource_type: "CPU", amount: 1 }])}
          >
            <Plus />
            Add requirement
          </Button>
        </div>

        {(formError || submit.isError) && (
          <p className="text-sm text-destructive">{formError ?? formatApiError(submit.error)}</p>
        )}

        <Button type="submit" disabled={submit.isPending}>
          {submit.isPending ? "Submitting…" : "Submit job"}
        </Button>
      </form>
      </Card>
    </div>
  );
}
