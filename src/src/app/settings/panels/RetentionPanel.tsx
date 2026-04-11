"use client";

import { useMemo, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { getRetentionConfig, updateRetentionConfig, type RetentionConfig } from "@/lib/api";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Save, Archive } from "lucide-react";

const FIELDS: { key: keyof RetentionConfig; label: string; description: string }[] = [
  { key: "job_history_days", label: "Job History", description: "How long to retain job execution history." },
  { key: "audit_events_days", label: "Audit Events", description: "Retention window for audit log events." },
  { key: "snapshots_days", label: "Snapshots", description: "How long to keep infrastructure snapshots." },
  { key: "llm_calls_days", label: "LLM Calls", description: "Retention window for LLM call logs." },
  { key: "metric_points_days", label: "Metric Points", description: "How long metric data points are stored." },
  { key: "insights_days", label: "Insights", description: "Retention window for AI-generated insights." },
];

export default function RetentionPanel() {
  const queryClient = useQueryClient();
  const [editedForm, setEditedForm] = useState<RetentionConfig | null>(null);

  const { data, isLoading, error } = useQuery<RetentionConfig>({
    queryKey: ["settings", "retention"],
    queryFn: getRetentionConfig,
    staleTime: 30_000,
  });

  // Derive displayed form: user edits take priority over API data.
  const form = useMemo<RetentionConfig | null>(
    () => editedForm ?? (data ? { ...data } : null),
    [editedForm, data],
  );

  const saveMut = useMutation({
    mutationFn: (f: RetentionConfig) => updateRetentionConfig(f),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["settings"] });
      toast.success("Retention settings saved");
    },
    onError: (e) => toast.error(String(e)),
  });

  if (isLoading) return (
    <div className="flex flex-col gap-3">
      {[1, 2, 3].map(i => <Skeleton key={i} className="h-16 w-full rounded-[10px]" />)}
    </div>
  );

  if (error || !data) return (
    <p className="text-(--er) text-sm">Failed to load: {(error as Error)?.message ?? "Unknown error"}</p>
  );

  if (!form) return null;

  return (
    <div className="flex flex-col gap-5">
      <Card className="bg-(--sl2) border-[oklch(0.24_0.012_255)]">
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-[15px] font-(--fD)">
            <Archive className="h-4 w-4 text-(--tx3)" />
            Data Retention Windows
          </CardTitle>
          <CardDescription className="text-(--tx3) text-sm">
            Configure how long each data type is retained. Valid range: 7–1825 days.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
            {FIELDS.map(({ key, label, description }) => (
              <div key={key} className="flex flex-col gap-1.5">
                <Label htmlFor={key} className="text-(--tx1) text-sm font-medium">{label}</Label>
                <p className="text-(--tx3) text-xs">{description}</p>
                <div className="flex items-center gap-2">
                  <Input
                    id={key}
                    type="number"
                    min={7}
                    max={1825}
                    className="w-28"
                    value={form[key]}
                    onChange={e =>
                      setEditedForm(_f => ({ ...form, [key]: Number(e.target.value) }))
                    }
                  />
                  <span className="text-(--tx3) text-sm">days</span>
                </div>
                <p className="text-(--tx3) text-xs opacity-60">Range: 7–1825</p>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <div className="flex justify-end">
        <Button onClick={() => form && saveMut.mutate(form)} disabled={saveMut.isPending}>
          <Save className="h-4 w-4" />
          {saveMut.isPending ? "Saving…" : "Save Retention Settings"}
        </Button>
      </div>
    </div>
  );
}
