"use client";

import { useMemo, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { getGuardConfig, updateGuardConfig, type GuardConfig } from "@/lib/api";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Save, ShieldAlert } from "lucide-react";

type FormState = { fail_closed: boolean; timeout_s: number };

export default function GuardPanel() {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<FormState | null>(null);

  const { data, isLoading, error } = useQuery<GuardConfig>({
    queryKey: ["settings", "guard"],
    queryFn: getGuardConfig,
    staleTime: 30_000,
  });

  // Derive displayed form values: user edits (form) take priority over API data.
  // This eliminates the need for a useEffect that calls setForm synchronously,
  // which would violate the react-hooks/set-state-in-effect rule.
  const displayForm = useMemo<FormState | null>(
    () => form ?? (data ? { fail_closed: data.fail_closed, timeout_s: data.timeout_s } : null),
    [form, data],
  );

  const saveMut = useMutation({
    mutationFn: (f: FormState) => updateGuardConfig(f),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["settings"] });
      toast.success("Guard settings saved");
    },
    onError: (e) => toast.error(String(e)),
  });

  if (isLoading) return (
    <div className="flex flex-col gap-4">
      <Skeleton className="h-32 w-full rounded-[10px]" />
      <Skeleton className="h-40 w-full rounded-[10px]" />
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
            <ShieldAlert className="h-4 w-4 text-(--tx3)" />
            Guard Policy
          </CardTitle>
          <CardDescription className="text-(--tx3) text-sm">
            Controls whether guard failures block actions (fail-closed) or allow them (fail-open).
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div className="flex items-center gap-3">
            <input
              id="fail-closed"
              type="checkbox"
              checked={displayForm.fail_closed}
              onChange={e => setForm(_f => ({ ...displayForm, fail_closed: e.target.checked }))}
              className="h-4 w-4 rounded border-[oklch(0.24_0.012_255)] accent-(--ok) cursor-pointer"
            />
            <Label htmlFor="fail-closed" className="cursor-pointer">
              {"Fail-closed "}
              <span className="ml-2 text-(--tx3) text-xs">
                (when checked, guard failures will block the action)
              </span>
            </Label>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="guard-timeout" className="text-(--tx3) text-sm">Timeout (seconds)</Label>
            <Input
              id="guard-timeout"
              type="number"
              min={1}
              max={120}
              className="w-36"
              value={displayForm.timeout_s}
              onChange={e => setForm(_f => ({ ...displayForm, timeout_s: Number(e.target.value) }))}            />
          </div>
        </CardContent>
      </Card>

      <Card className="bg-(--sl2) border-[oklch(0.24_0.012_255)]">
        <CardHeader className="pb-3">
          <CardTitle className="text-[15px] font-(--fD)">Tool Allowlist</CardTitle>
          <CardDescription className="text-(--tx3) text-sm">
            Read-only. Managed via configuration files.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2">
            {data.tool_allowlist.length === 0
              ? <p className="text-(--tx3) text-sm">No tools configured.</p>
              : data.tool_allowlist.map(tool => (
                <span
                  key={tool}
                  className="inline-flex items-center rounded-md px-2.5 py-1 text-xs font-(--fM) bg-(--sl3) text-sidebar-foreground border border-[oklch(0.24_0.012_255)]"
                >
                  {tool}
                </span>
              ))}
          </div>
        </CardContent>
      </Card>

      <Card className="bg-(--sl2) border-[oklch(0.24_0.012_255)]">
        <CardHeader className="pb-3">
          <CardTitle className="text-[15px] font-(--fD)">Max Actions per Session</CardTitle>
          <CardDescription className="text-(--tx3) text-sm">
            Read-only. Per-action-type session limits.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {Object.keys(data.max_actions_per_session).length === 0
            ? <p className="text-(--tx3) text-sm">No limits configured.</p>
            : (
              <Table>
                <TableHeader>
                  <TableRow className="border-[oklch(0.24_0.012_255)]">
                    <TableHead className="text-(--tx3)">Action</TableHead>
                    <TableHead className="text-(--tx3)">Max / session</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {Object.entries(data.max_actions_per_session).map(([action, limit]) => (
                    <TableRow key={action} className="border-[oklch(0.24_0.012_255)]">
                      <TableCell className="font-(--fM) text-sm">{action}</TableCell>
                      <TableCell>{limit}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
        </CardContent>
      </Card>

      <div className="flex justify-end">
        <Button onClick={() => displayForm && saveMut.mutate(displayForm)} disabled={saveMut.isPending}>
          <Save className="h-4 w-4" />
          {saveMut.isPending ? "Saving…" : "Save Guard Settings"}
        </Button>
      </div>
    </div>
  );
}
