"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { runScript, type ScriptMeta } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Play, AlertTriangle } from "lucide-react";
import { toast } from "sonner";

interface ScriptCardProps { script: ScriptMeta }

const categoryColors: Record<string, string> = {
  audit: "blue",
  loader: "default",
  seed: "purple",
  validation: "warning",
  mesh: "blue",
};

export function ScriptCard({ script }: ScriptCardProps) {
  const qc = useQueryClient();
  const { mutate, isPending } = useMutation({
    mutationFn: () => runScript(script.task_name),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ["jobs"] });
      toast.success(`Job started: ${data.job_id}`);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <Card className="flex flex-col">
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between gap-2">
          <CardTitle className="text-sm font-medium leading-snug">{script.display_name}</CardTitle>
          <Badge variant={(categoryColors[script.category] ?? "secondary") as "default" | "secondary" | "blue" | "purple" | "warning"}>
            {script.category}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="flex flex-col gap-3 flex-1">
        <p className="text-xs text-(--tx3) flex-1">{script.description}</p>
        <code className="text-xs text-(--tx3) truncate block" style={{ fontFamily: "var(--fM)" }}>
          {script.script_path}
        </code>
        <div className="flex items-center justify-between">
          {script.is_destructive && (
            <span className="flex items-center gap-1 text-xs text-destructive">
              <AlertTriangle size={12} /> Destructive
            </span>
          )}
          <Button
            size="sm"
            className="ml-auto"
            disabled={isPending}
            onClick={() => mutate()}
          >
            <Play size={14} className="mr-1" />
            {isPending ? "Queuing…" : "Run"}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
