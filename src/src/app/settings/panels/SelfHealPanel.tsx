"use client";

import { useMemo, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { getSelfHealConfig, updateSelfHealConfig, type SelfHealConfig } from "@/lib/api";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Save, Wrench, AlertTriangle } from "lucide-react";

function bytesToGb(bytes: number): string {
  return (bytes / 1_073_741_824).toFixed(2);
}

export default function SelfHealPanel() {
  const queryClient = useQueryClient();
  const [editedForm, setEditedForm] = useState<SelfHealConfig | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);

  const { data, isLoading, error } = useQuery<SelfHealConfig>({
    queryKey: ["settings", "self-heal"],
    queryFn: getSelfHealConfig,
    staleTime: 30_000,
  });

  // Derive displayed form: user edits take priority over API data.
  const form = useMemo<SelfHealConfig | null>(
    () => editedForm ?? (data ? { ...data } : null),
    [editedForm, data],
  );

  const saveMut = useMutation({
    mutationFn: (f: SelfHealConfig) => updateSelfHealConfig(f),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["settings"] });
      toast.success("Self-heal settings saved");
    },
    onError: (e) => toast.error(String(e)),
  });

  const handleSave = () => {
    if (!form) return;
    if (form.log_hitl_bytes >= form.log_auto_truncate_bytes) {
      setValidationError("HITL alert threshold must be less than auto-truncate threshold.");
      return;
    }
    setValidationError(null);
    saveMut.mutate(form);
  };

  if (isLoading) return (
    <div className="flex flex-col gap-4">
      <Skeleton className="h-36 w-full rounded-[10px]" />
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
            <Wrench className="h-4 w-4 text-(--tx3)" />
            Self-Heal Thresholds
          </CardTitle>
          <CardDescription className="text-(--tx3) text-sm">
            Thresholds that trigger automatic remediation or HITL escalation.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-6">
          <div className="flex flex-col gap-2">
            <div className="flex items-center justify-between">
              <Label className="text-(--tx1) text-sm font-medium">
                Disk Threshold
              </Label>
              <span className="text-(--tx1) text-sm font-(--fM)">
                {form.disk_threshold_pct}%
              </span>
            </div>
            <p className="text-(--tx3) text-xs">
              Disk usage percentage that triggers self-heal disk cleanup.
            </p>
            <input
              type="range"
              min={50}
              max={99}
              value={form.disk_threshold_pct}
              onChange={e => setEditedForm(_f => ({ ...form, disk_threshold_pct: Number(e.target.value) }))}
              className="w-full accent-(--ok) cursor-pointer"
            />
            <div className="flex justify-between text-(--tx3) text-xs">
              <span>50%</span>
              <span>99%</span>
            </div>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="log-truncate" className="text-(--tx1) text-sm font-medium">
              Log Auto-Truncate Threshold
            </Label>
            <p className="text-(--tx3) text-xs">
              Log file size (in bytes) that triggers automatic truncation.
              Currently: <span className="font-(--fM) text-sidebar-foreground">{bytesToGb(form.log_auto_truncate_bytes)} GB</span>
            </p>
            <Input
              id="log-truncate"
              type="number"
              min={1_048_576}
              value={form.log_auto_truncate_bytes}
              onChange={e => setEditedForm(_f => ({ ...form, log_auto_truncate_bytes: Number(e.target.value) }))}
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="log-hitl" className="text-(--tx1) text-sm font-medium">
              Log HITL Alert Threshold
            </Label>
            <p className="text-(--tx3) text-xs">
              Log file size (in bytes) that triggers a HITL escalation. Must be less than auto-truncate.
              Currently: <span className="font-(--fM) text-sidebar-foreground">{bytesToGb(form.log_hitl_bytes)} GB</span>
            </p>
            <Input
              id="log-hitl"
              type="number"
              min={1_048_576}
              value={form.log_hitl_bytes}
              onChange={e => setEditedForm(_f => ({ ...form, log_hitl_bytes: Number(e.target.value) }))}
            />
          </div>

          {validationError && (
            <div className="flex items-center gap-2 rounded-lg bg-(--er)/10 border border-(--er)/30 px-3 py-2">
              <AlertTriangle className="h-4 w-4 text-(--er) shrink-0" />
              <p className="text-(--er) text-sm">{validationError}</p>
            </div>
          )}
        </CardContent>
      </Card>

      <div className="flex justify-end">
        <Button onClick={handleSave} disabled={saveMut.isPending}>
          <Save className="h-4 w-4" />
          {saveMut.isPending ? "Saving…" : "Save Self-Heal Settings"}
        </Button>
      </div>
    </div>
  );
}
