"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getSchedules, deleteSchedule, createSchedule, type WorkerSchedule } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Trash2, Plus } from "lucide-react";
import { formatDate } from "@/lib/utils";
import { useState } from "react";
import { toast } from "sonner";

export function SchedulerPanel() {
  const qc = useQueryClient();
  const [form, setForm] = useState({ task_name: "", cron_expression: "", description: "" });
  const [showForm, setShowForm] = useState(false);

  const { data, isLoading } = useQuery<WorkerSchedule[]>({
    queryKey: ["schedules"],
    queryFn: getSchedules,
  });

  const del = useMutation({
    mutationFn: deleteSchedule,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["schedules"] }); toast.success("Schedule deleted"); },
    onError: (e: Error) => toast.error(e.message),
  });

  const add = useMutation({
    mutationFn: () => createSchedule(form),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["schedules"] });
      setForm({ task_name: "", cron_expression: "", description: "" });
      setShowForm(false);
      toast.success("Schedule created");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0">
        <CardTitle className="text-base">Schedules</CardTitle>
        <Button size="sm" variant="outline" onClick={() => setShowForm((s) => !s)}>
          <Plus size={14} className="mr-1" />
          Add
        </Button>
      </CardHeader>
      <CardContent className="space-y-3">
        {showForm && (
          <div className="border border-[oklch(0.25_0.01_240)] rounded-[10px] p-3 space-y-3 bg-(--sl2)">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="text-xs">Task name</Label>
                <Input
                  value={form.task_name}
                  onChange={(e) => setForm((f) => ({ ...f, task_name: e.target.value }))}
                  placeholder="e.g. ssh_connectivity_check"
                  className="h-8 text-sm mt-1"
                />
              </div>
              <div>
                <Label className="text-xs">Cron expression</Label>
                <Input
                  value={form.cron_expression}
                  onChange={(e) => setForm((f) => ({ ...f, cron_expression: e.target.value }))}
                  placeholder="0 */6 * * *"
                  className="h-8 text-sm mt-1 font-mono"
                />
              </div>
            </div>
            <div>
              <Label className="text-xs">Description (optional)</Label>
              <Input
                value={form.description}
                onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
                placeholder="…"
                className="h-8 text-sm mt-1"
              />
            </div>
            <div className="flex gap-2">
              <Button
                size="sm"
                disabled={add.isPending || !form.task_name || !form.cron_expression}
                onClick={() => add.mutate()}
              >
                Save
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setShowForm(false)}>
                Cancel
              </Button>
            </div>
          </div>
        )}

        {isLoading ? (
          <div className="space-y-2">
            {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-10 w-full" />)}
          </div>
        ) : !data?.length ? (
          <p className="text-sm text-(--tx3) text-center py-4">No schedules configured</p>
        ) : (
          <div className="space-y-2">
            {data.map((s) => (
              <div
                key={s.schedule_id}
                className="flex items-start justify-between gap-3 p-3 border border-border rounded-md bg-card"
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span style={{ fontFamily: "var(--fM)", fontSize: 13 }} className="font-medium">{s.task_name}</span>
                    <Badge className="px-1 py-0" style={{ fontFamily: "var(--fM)", fontSize: 12 }} variant="secondary">
                      {s.cron_expression}
                    </Badge>
                    {!s.is_active && <Badge variant="secondary" className="text-xs">paused</Badge>}
                  </div>
                  {s.description && (
                    <p className="text-xs text-(--tx3) mt-0.5">{s.description}</p>
                  )}
                  <p className="text-xs text-(--tx3) mt-0.5">
                    Last: {s.last_run_at ? formatDate(s.last_run_at) : "never"}
                    {s.next_run_at && ` · Next: ${formatDate(s.next_run_at)}`}
                  </p>
                </div>
                <Button
                  size="sm"
                  variant="ghost"
                  className="text-destructive h-7"
                  onClick={() => del.mutate(s.schedule_id)}
                >
                  <Trash2 size={13} />
                </Button>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
