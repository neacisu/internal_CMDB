"use client";

import { useQuery } from "@tanstack/react-query";
import { getDashboardSummary, type DashboardSummary } from "@/lib/api";
import { KpiCard } from "@/components/dashboard/kpi-card";
import { GpuPanel } from "@/components/dashboard/gpu-panel";
import { HostGrid } from "@/components/dashboard/host-grid";
import { TrendCharts } from "@/components/dashboard/trend-charts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { Server, Cpu, Container, Activity, Database, LayoutGrid, RefreshCw } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";

export default function DashboardPage() {
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery<DashboardSummary>({
    queryKey: ["dashboard", "summary"],
    queryFn: getDashboardSummary,
    refetchInterval: 30_000,
  });

  return (
    <div className="page-in" style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div>
          <h1 className="df-page-title">Dashboard</h1>
          <p className="df-page-sub">
            Infrastructure overview · refreshes every 30 s
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => queryClient.invalidateQueries({ queryKey: ["dashboard"] })}
        >
          <RefreshCw size={13} />
          Refresh
        </Button>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 14 }} className="lg:grid-cols-6! sm:grid-cols-3!">
        {isLoading ? (
          Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-24 w-full" />
          ))
        ) : (
          <>
            <KpiCard
              title="Hosts"
              value={data?.host_count ?? 0}
              sub={`${data?.cluster_count ?? 0} cluster(s)`}
              icon={Server}
              color="var(--g3)"
            />
            <KpiCard
              title="GPU Devices"
              value={data?.gpu_count ?? 0}
              sub={`${data?.total_gpu_vram_gb?.toFixed(0) ?? 0} GB VRAM`}
              icon={Cpu}
              color="var(--pu)"
            />
            <KpiCard
              title="Docker Hosts"
              value={data?.docker_host_count ?? 0}
              sub={`${data?.service_instance_count ?? 0} instances`}
              icon={Container}
              color="var(--in)"
            />
            <KpiCard
              title="Services"
              value={data?.service_count ?? 0}
              icon={LayoutGrid}
              color="var(--wa)"
            />
            <KpiCard
              title="Collections (24h)"
              value={data?.collection_runs_24h ?? 0}
              sub={
                data?.last_run_ts
                  ? `Last: ${new Date(data.last_run_ts).toLocaleTimeString()}`
                  : "No recent runs"
              }
              icon={Activity}
              color="var(--ok)"
            />
            <KpiCard
              title="Total RAM"
              value={`${data?.total_ram_gb?.toFixed(0) ?? 0} GB`}
              icon={Database}
              color="var(--in)"
            />
          </>
        )}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Host activity trends</CardTitle>
        </CardHeader>
        <CardContent>
          <TrendCharts />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>GPU devices</CardTitle>
        </CardHeader>
        <CardContent>
          <GpuPanel />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>All hosts</CardTitle>
        </CardHeader>
        <CardContent>
          <HostGrid />
        </CardContent>
      </Card>
    </div>
  );
}
