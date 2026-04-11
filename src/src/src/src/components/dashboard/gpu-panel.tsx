"use client";

import { useQuery } from "@tanstack/react-query";
import { getGpuSummary, type GpuSummaryItem } from "@/lib/api";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { RefreshCw } from "lucide-react";
import { useRefreshCountdown, fmtTime } from "@/lib/hooks";

const GPU_INTERVAL = 30_000;

function utilBadge(pct: number | null) {
  if (pct === null) return <Badge variant="secondary">N/A</Badge>;
  if (pct >= 80) return <Badge variant="destructive">{pct}%</Badge>;
  if (pct >= 50) return <Badge variant="warning">{pct}%</Badge>;
  return <Badge variant="default">{pct}%</Badge>;
}

export function GpuPanel() {
  const { data, isLoading, dataUpdatedAt } = useQuery<GpuSummaryItem[]>({
    queryKey: ["dashboard", "gpu-summary"],
    queryFn: getGpuSummary,
    refetchInterval: GPU_INTERVAL,
  });
  const { secsLeft, progress, lastRefreshed } = useRefreshCountdown(dataUpdatedAt, GPU_INTERVAL);

  if (isLoading)
    return (
      <div className="space-y-2">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-10 w-full" />
        ))}
      </div>
    );

  if (!data?.length)
    return (
      <p className="text-sm text-muted-foreground py-4 text-center">No GPU devices found</p>
    );

  return (
    <div className="overflow-auto">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Host</TableHead>
            <TableHead>GPU</TableHead>
            <TableHead className="text-right">Mem (MB)</TableHead>
            <TableHead className="text-right">Util</TableHead>
            <TableHead className="text-right">Temp (°C)</TableHead>
            <TableHead className="text-right">Power (W)</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {data.map((g) => (
            <TableRow key={`${g.host_id}-${g.gpu_index}`}>
              <TableCell className="font-medium text-(--tx1)">{g.hostname}</TableCell>
              <TableCell className="text-(--tx3) text-[14.4px]" style={{ fontFamily: "var(--fM)" }}>
                {g.model_name ?? `GPU ${g.gpu_index}`}
              </TableCell>
              <TableCell className="text-right" style={{ fontFamily: "var(--fM)", fontSize: 14.4 }}>
                {g.memory_used_mb ?? "—"} / {g.memory_total_mb ?? "—"}
              </TableCell>
              <TableCell className="text-right">{utilBadge(g.utilization_gpu_pct)}</TableCell>
              <TableCell className="text-right" style={{ fontFamily: "var(--fM)", fontSize: 14.4 }}>
                {g.temperature_celsius ?? "—"}
              </TableCell>
              <TableCell className="text-right" style={{ fontFamily: "var(--fM)", fontSize: 14.4 }}>
                {g.power_draw_watts ?? "—"}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      <div className="panel-refresh-footer">
        <RefreshCw size={10} style={{ opacity: 0.5, flexShrink: 0 }} />
        <span>Last: {fmtTime(lastRefreshed)}</span>
        <span style={{ color: "var(--tx4)" }}>·</span>
        <span>Next: {secsLeft}s</span>
        <div className="countdown-track">
          <div className="countdown-fill" style={{ transform: `scaleX(${progress})` }} />
        </div>
      </div>
    </div>
  );
}
