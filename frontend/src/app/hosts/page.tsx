"use client";

import { useQuery } from "@tanstack/react-query";
import { getHosts, getClusters, getFleetVitals, type Host, type Page, type Cluster, type FleetVital } from "@/lib/api";
import Link from "next/link";
import { useState } from "react";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { ChevronLeft, ChevronRight, Search, Cpu, Container } from "lucide-react";

export default function HostsPage() {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [gpuOnly, setGpuOnly] = useState(false);

  const params = [
    `page=${page}`,
    `page_size=20`,
    gpuOnly ? "gpu_capable=true" : "",
  ]
    .filter(Boolean)
    .join("&");

  const { data, isLoading } = useQuery<Page<Host>>({
    queryKey: ["hosts", page, gpuOnly],
    queryFn: () => getHosts(params),
  });

  const { data: clusters } = useQuery<Cluster[]>({
    queryKey: ["clusters"],
    queryFn: getClusters,
  });

  const { data: vitals } = useQuery<FleetVital[]>({
    queryKey: ["fleet", "vitals"],
    queryFn: getFleetVitals,
    refetchInterval: 10_000,
  });

  const clusterMap = Object.fromEntries(
    (clusters ?? []).map((c) => [c.cluster_id, c.name])
  );

  const vitalsMap = Object.fromEntries(
    (vitals ?? []).map((v) => [v.host_code, v])
  );

  const filtered = data?.items.filter((h) =>
    !search ||
    h.hostname.toLowerCase().includes(search.toLowerCase()) ||
    (h.primary_private_ipv4 ?? "").includes(search)
  );

  const total = data?.meta.total ?? 0;
  const totalPages = Math.ceil(total / 20);

  return (
    <div className="page-in" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div className="flex items-center justify-between">
        <h1 className="df-page-title">Hosts</h1>
        <div className="flex items-center gap-2">
          <div className="relative">
            <Search size={14} className="absolute left-2.5 top-2.5 text-(--tx3)" />
            <Input
              placeholder="Filter hosts…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="h-9 pl-8 w-56"
            />
          </div>
          <Button
            size="sm"
            variant={gpuOnly ? "default" : "outline"}
            onClick={() => { setGpuOnly((g) => !g); setPage(1); }}
          >
            <Cpu size={14} className="mr-1" />
            GPU only
          </Button>
        </div>
      </div>

      <div className="overflow-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Hostname</TableHead>
              <TableHead>Cluster</TableHead>
              <TableHead>IP (private)</TableHead>
              <TableHead>OS</TableHead>
              <TableHead>Arch</TableHead>
              <TableHead>Caps</TableHead>
              <TableHead>Agent</TableHead>
              <TableHead>CPU</TableHead>
              <TableHead>RAM / Load</TableHead>
              <TableHead>GPU</TableHead>
              <TableHead className="text-right">Confidence</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading
              ? Array.from({ length: 10 }).map((_, i) => (
                  <TableRow key={`skeleton-row-${String(i)}`}>
                    {Array.from({ length: 11 }).map((__, j) => (
                      <TableCell key={`skeleton-cell-${String(i)}-${String(j)}`}><Skeleton className="h-4 w-full" /></TableCell>
                    ))}
                  </TableRow>
                ))
              : filtered?.map((host) => (
                  <TableRow key={host.host_id} className="hover:bg-accent/50">
                    <TableCell>
                      <Link
                        href={`/hosts/${host.host_id}`}
                        className="font-medium hover:underline"
                      >
                        {host.hostname}
                      </Link>
                      {host.fqdn && (
                        <span className="text-xs text-(--tx3) block">{host.fqdn}</span>
                      )}
                    </TableCell>
                    <TableCell className="text-sm text-(--tx3)">
                      {host.cluster_id ? (clusterMap[host.cluster_id] ?? host.cluster_id) : "—"}
                    </TableCell>
                    <TableCell className="text-xs" style={{ fontFamily: "var(--fM)" }}>
                      {host.primary_private_ipv4 ?? host.primary_public_ipv4 ?? "—"}
                    </TableCell>
                    <TableCell className="text-xs text-(--tx3) max-w-45 truncate">
                      {host.os_version_text ?? "—"}
                    </TableCell>
                    <TableCell className="text-xs" style={{ fontFamily: "var(--fM)" }}>
                      {host.architecture_text ?? "—"}
                    </TableCell>
                    <TableCell>
                      <div className="flex gap-1">
                        {host.is_gpu_capable && (
                          <Badge variant="purple" className="text-xs px-1 py-0">
                            <Cpu size={10} className="mr-0.5" />GPU
                          </Badge>
                        )}
                        {host.is_docker_host && (
                          <Badge variant="blue" className="text-xs px-1 py-0">
                            <Container size={10} className="mr-0.5" />Docker
                          </Badge>
                        )}
                      </div>
                    </TableCell>
                    <TableCell>
                      {(() => {
                        const v = vitalsMap[host.host_code];
                        if (!v) return <span className="text-xs text-(--tx4)">—</span>;
                        let color = "var(--er)";
                        if (v.status === "online") color = "var(--ok)";
                        else if (v.status === "degraded") color = "var(--wa)";
                        return (
                          <span className="flex items-center gap-1 text-xs" style={{ fontFamily: "var(--fM)" }}>
                            <span style={{ width: 6, height: 6, borderRadius: "50%", background: color, flexShrink: 0 }} />
                            {v.status}
                          </span>
                        );
                      })()}
                    </TableCell>
                    <TableCell className="text-xs" style={{ fontFamily: "var(--fM)" }}>
                      {(() => {
                        const v = vitalsMap[host.host_code];
                        if (v?.status !== "online" || v.cpu_pct == null) return <span className="text-(--tx4)">—</span>;
                        let color = "var(--ok)";
                        if (v.cpu_pct > 85) color = "var(--er)";
                        else if (v.cpu_pct > 60) color = "var(--wa)";
                        return <span style={{ color }}>{v.cpu_pct}%</span>;
                      })()}
                    </TableCell>
                    <TableCell className="text-xs" style={{ fontFamily: "var(--fM)" }}>
                      {(() => {
                        const v = vitalsMap[host.host_code];
                        if (v?.status !== "online") return "—";
                        const parts: string[] = [];
                        if (v.memory_pct != null) parts.push(`${v.memory_pct}%`);
                        if (v.load_avg.length > 0) parts.push(`⚡${v.load_avg[0].toFixed(1)}`);
                        return parts.join(" · ") || "—";
                      })()}
                    </TableCell>
                    <TableCell className="text-xs" style={{ fontFamily: "var(--fM)" }}>
                      {(() => {
                        const v = vitalsMap[host.host_code];
                        if (v?.status !== "online" || v.gpu_pct == null) return <span className="text-(--tx4)">—</span>;
                        let color = "var(--ok)";
                        if (v.gpu_pct > 85) color = "var(--er)";
                        else if (v.gpu_pct > 60) color = "var(--wa)";
                        return <span style={{ color }}>{v.gpu_pct}%</span>;
                      })()}
                    </TableCell>
                    <TableCell className="text-right text-xs" style={{ fontFamily: "var(--fM)" }}>
                      {host.confidence_score == null
                        ? "—"
                        : `${(host.confidence_score * 100).toFixed(0)}%`}
                    </TableCell>
                  </TableRow>
                ))}
          </TableBody>
        </Table>
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-between text-sm">
          <span className="text-(--tx3)">
            {total} hosts · page {page} / {totalPages}
          </span>
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
