"use client";

import { useQuery } from "@tanstack/react-query";
import { getHosts, type Host, type Page } from "@/lib/api";
import Link from "next/link";
import { Skeleton } from "@/components/ui/skeleton";
import { Cpu, Container, RefreshCw } from "lucide-react";
import { cn } from "@/lib/utils";
import { useRefreshCountdown, fmtTime, useFleetVitalsSSE } from "@/lib/hooks";

const HOSTS_INTERVAL = 60_000;

export function HostGrid() {
  const { data, isLoading, dataUpdatedAt } = useQuery<Page<Host>>({
    queryKey: ["hosts", "all"],
    queryFn: () => getHosts("page_size=48"),
    refetchInterval: HOSTS_INTERVAL,
  });
  // Real-time vitals shared with Dashboard via SSE hook
  const { vitals } = useFleetVitalsSSE();
  const { secsLeft, progress, lastRefreshed } = useRefreshCountdown(dataUpdatedAt, HOSTS_INTERVAL);

  if (isLoading)
    return (
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-2">
        {["hg-sk-01", "hg-sk-02", "hg-sk-03", "hg-sk-04", "hg-sk-05", "hg-sk-06", "hg-sk-07", "hg-sk-08", "hg-sk-09", "hg-sk-10", "hg-sk-11", "hg-sk-12"].map((k) => (
          <Skeleton key={k} className="h-20 w-full" />
        ))}
      </div>
    );

  if (!data?.items.length)
    return <p className="text-sm text-muted-foreground">No hosts found</p>;

  return (
    <div>
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-2">
      {data.items.map((host) => {
        const v = vitals.find(vv => vv.host_code === host.host_code);
        const memPct = v?.memory_pct;
        return (
          <Link
            key={host.host_id}
            href={`/hosts/${host.host_id}`}
            className={cn(
              "border border-[oklch(0.22_0.012_255/70%)] rounded-lg p-3 hover:bg-(--sl3) hover:border-[oklch(0.28_0.012_255)] transition-all duration-100 flex flex-col gap-1",
              "bg-(--sl2)"
            )}
          >
            <span className="text-[14.4px] font-medium truncate text-(--tx1)" title={host.hostname}>
              {host.hostname}
            </span>
            <span className="text-[12px] text-(--tx3) truncate" style={{ fontFamily: "var(--fM)" }}>
              {host.primary_private_ipv4 ?? host.primary_public_ipv4 ?? "no IP"}
            </span>
            <div className="flex gap-1 mt-1 items-center">
              {host.is_gpu_capable && (
                <span title="GPU capable">
                  <Cpu size={12} className="text-purple-400" />
                </span>
              )}
              {host.is_docker_host && (
                <span title="Docker host">
                  <Container size={12} className="text-blue-400" />
                </span>
              )}
              {v?.status === "online" && (
                <span className="ml-auto flex items-center gap-1" style={{ fontFamily: "var(--fM)", fontSize: 10 }}>
                  {v.cpu_pct != null && (() => {
                    let color = "var(--ok)";
                    if (v.cpu_pct > 85) color = "var(--er)";
                    else if (v.cpu_pct > 60) color = "var(--wa)";
                    return <span style={{ color }} title="CPU%">C:{v.cpu_pct}%</span>;
                  })()}
                  {memPct != null && (() => {
                    let color = "var(--ok)";
                    if (memPct > 85) color = "var(--er)";
                    else if (memPct > 60) color = "var(--wa)";
                    return (
                      <span style={{ color }}>
                        {memPct}%
                      </span>
                    );
                  })()}
                  {v.gpu_pct != null && (() => {
                    let color = "var(--ok)";
                    if (v.gpu_pct > 85) color = "var(--er)";
                    else if (v.gpu_pct > 60) color = "var(--wa)";
                    return <span style={{ color }} title="GPU%">G:{v.gpu_pct}%</span>;
                  })()}
                  {v.load_avg.length > 0 && (
                    <span style={{ color: "var(--tx4)" }}>
                      {v.load_avg[0].toFixed(1)}
                    </span>
                  )}
                </span>
              )}
            </div>
          </Link>
        );
      })}
      </div>
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
