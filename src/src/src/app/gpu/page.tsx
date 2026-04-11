"use client";

import { useQuery } from "@tanstack/react-query";
import { getGpuDevices, type GpuDevice, type Page } from "@/lib/api";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Progress } from "@/components/ui/progress";
import { ChevronLeft, ChevronRight } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

function utilColor(pct: number | null) {
  if (pct === null) return "bg-(--sl3) text-(--tx3)";
  if (pct >= 80) return "bg-(--er) text-white";
  if (pct >= 50) return "bg-(--wa) text-white";
  return "bg-(--ok) text-white";
}

export default function GpuPage() {
  const [page, setPage] = useState(1);
  const { data, isLoading } = useQuery<Page<GpuDevice>>({
    queryKey: ["gpu-devices", page],
    queryFn: () => getGpuDevices(`page=${page}&page_size=30`),
  });

  const total = data?.meta.total ?? 0;
  const totalPages = Math.ceil(total / 30);

  return (
    <div className="page-in" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <h1 className="df-page-title">GPU Devices</h1>

      <div className="overflow-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Host</TableHead>
              <TableHead>#</TableHead>
              <TableHead>Vendor</TableHead>
              <TableHead>Model</TableHead>
              <TableHead className="text-right">VRAM (MB)</TableHead>
              <TableHead>Utilisation</TableHead>
              <TableHead className="text-right">Temp °C</TableHead>
              <TableHead className="text-right">Power W</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading
              ? Array.from({ length: 8 }).map((_, i) => (
                  <TableRow key={i}>
                    {Array.from({ length: 8 }).map((__, j) => (
                      <TableCell key={j}><Skeleton className="h-4 w-full" /></TableCell>
                    ))}
                  </TableRow>
                ))
              : data?.items.map((g) => (
                  <TableRow key={g.gpu_device_id}>
                    <TableCell>
                      <Link href={`/hosts/${g.host_id}`} className="hover:underline font-medium text-sm">
                        {g.host_id.slice(0, 8)}…
                      </Link>
                    </TableCell>
                    <TableCell className="text-xs" style={{ fontFamily: "var(--fM)" }}>{g.gpu_index}</TableCell>
                    <TableCell className="text-sm text-(--tx3)">{g.vendor_name ?? "—"}</TableCell>
                    <TableCell className="text-sm">{g.model_name ?? "—"}</TableCell>
                    <TableCell className="text-right" style={{ fontFamily: "var(--fM)", fontSize: 13 }}>
                      {g.memory_used_mb != null && g.memory_total_mb != null
                        ? `${g.memory_used_mb} / ${g.memory_total_mb}`
                        : g.memory_total_mb ?? "—"}
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2 min-w-25">
                        <Progress
                          value={g.utilization_gpu_pct ?? 0}
                          className="h-1.5 flex-1"
                        />
                        <Badge className={`${utilColor(g.utilization_gpu_pct)} text-xs px-1 py-0`}>
                          {g.utilization_gpu_pct ?? "—"}%
                        </Badge>
                      </div>
                    </TableCell>
                    <TableCell className="text-right" style={{ fontFamily: "var(--fM)", fontSize: 13 }}>{g.temperature_celsius ?? "—"}</TableCell>
                    <TableCell className="text-right" style={{ fontFamily: "var(--fM)", fontSize: 13 }}>{g.power_draw_watts ?? "—"}</TableCell>
                  </TableRow>
                ))}
          </TableBody>
        </Table>
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-between text-sm">
          <span className="text-(--tx3)">{total} devices · page {page} / {totalPages}</span>
          <div className="flex gap-1">
            <Button size="sm" variant="outline" disabled={page === 1} onClick={() => setPage((p) => p - 1)}>
              <ChevronLeft size={14} />
            </Button>
            <Button size="sm" variant="outline" disabled={page === totalPages} onClick={() => setPage((p) => p + 1)}>
              <ChevronRight size={14} />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
