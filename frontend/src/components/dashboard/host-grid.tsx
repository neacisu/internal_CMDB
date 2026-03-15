"use client";

import { useQuery } from "@tanstack/react-query";
import { getHosts, type Host, type Page } from "@/lib/api";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Cpu, Container, RefreshCw } from "lucide-react";
import { cn } from "@/lib/utils";
import { useRefreshCountdown, fmtTime } from "@/lib/hooks";

const HOSTS_INTERVAL = 60_000;

export function HostGrid() {
  const { data, isLoading, dataUpdatedAt } = useQuery<Page<Host>>({
    queryKey: ["hosts", "all"],
    queryFn: () => getHosts("page_size=48"),
    refetchInterval: HOSTS_INTERVAL,
  });
  const { secsLeft, progress, lastRefreshed } = useRefreshCountdown(dataUpdatedAt, HOSTS_INTERVAL);

  if (isLoading)
    return (
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-2">
        {Array.from({ length: 12 }).map((_, i) => (
          <Skeleton key={i} className="h-20 w-full" />
        ))}
      </div>
    );

  if (!data?.items.length)
    return <p className="text-sm text-muted-foreground">No hosts found</p>;

  return (
    <div>
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-2">
      {data.items.map((host) => (
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
          <div className="flex gap-1 mt-1">
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
          </div>
        </Link>
      ))}
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
