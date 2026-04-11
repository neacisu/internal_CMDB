"use client";

import { useMemo, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { getHITLConfig, updateHITLConfig, type HITLConfig } from "@/lib/api";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Save, Users } from "lucide-react";

const FIELDS: {
  key: keyof HITLConfig;
  label: string;
  unit: string;
  description: string;
  min: number;
  max: number;
}[] = [
  {
    key: "rc4_escalation_minutes",
    label: "RC-4 Escalation",
    unit: "minutes",
    description: "Minutes before an RC-4 (critical) HITL item is escalated to the next tier if unresolved.",
    min: 1,
    max: 1440,
  },
  {
    key: "rc3_escalation_minutes",
    label: "RC-3 Escalation",
    unit: "minutes",
    description: "Minutes before an RC-3 (high) HITL item is escalated if unresolved.",
    min: 1,
    max: 1440,
  },
  {
    key: "rc2_escalation_hours",
    label: "RC-2 Escalation",
    unit: "hours",
    description: "Hours before an RC-2 (medium) HITL item is escalated if unresolved.",
    min: 1,
    max: 168,
  },
  {
    key: "max_escalations",
    label: "Max Escalations",
    unit: "levels",
    description: "Maximum number of escalation levels before the item is flagged for manual review.",
    min: 1,
    max: 10,
  },
];

export default function HITLPanel() {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<HITLConfig | null>(null);

  const { data, isLoading, error } = useQuery<HITLConfig>({
    queryKey: ["settings", "hitl"],
    queryFn: getHITLConfig,
    staleTime: 30_000,
  });

  // Derive displayed form values: user edits (form) take priority over API data.
  const displayForm = useMemo<HITLConfig | null>(
    () => form ?? (data ? { ...data } : null),
    [form, data],
  );

  const saveMut = useMutation({
    mutationFn: (f: HITLConfig) => updateHITLConfig(f),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["settings"] });
      toast.success("HITL settings saved");
    },
    onError: (e) => toast.error(String(e)),
  });

  if (isLoading) return (
    <div className="flex flex-col gap-3">
      {[1, 2, 3, 4].map(i => <Skeleton key={i} className="h-20 w-full rounded-[10px]" />)}
    </div>
  );

  if (error || !data) return (
    <p className="text-(--er) text-sm">Failed to load: {(error as Error)?.message ?? "Unknown error"}</p>
  );

  if (!displayForm) return null;

  return (
    <div className="flex flex-col gap-5">
      <Card className="bg-(--sl2) border-[oklch(0.24_0.012_255)]">
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-[15px] font-(--fD)">
            <Users className="h-4 w-4 text-(--tx3)" />
            Governance Thresholds
          </CardTitle>
          <CardDescription className="text-(--tx3) text-sm">
            Escalation timing for each risk class.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-5">
          {FIELDS.map(({ key, label, unit, description, min, max }) => (
            <div key={key} className="flex flex-col gap-1.5">
              <div className="flex items-center gap-2">
                <Label htmlFor={key} className="text-(--tx1) text-sm font-medium">{label}</Label>
                <span className="text-(--tx3) text-xs">({unit})</span>
              </div>
              <p className="text-(--tx3) text-xs leading-relaxed">{description}</p>
              <Input
                id={key}
                type="number"
                min={min}
                max={max}
                className="w-36"
                value={displayForm[key]}
                onChange={e =>
                  setForm(_f => ({ ...displayForm, [key]: Number(e.target.value) }))
                }
              />
            </div>
          ))}
        </CardContent>
      </Card>

      <div className="flex justify-end">
        <Button onClick={() => displayForm && saveMut.mutate(displayForm)} disabled={saveMut.isPending}>
          <Save className="h-4 w-4" />
          {saveMut.isPending ? "Saving…" : "Save HITL Settings"}
        </Button>
      </div>
    </div>
  );
}
