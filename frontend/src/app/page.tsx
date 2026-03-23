"use client";

import { useQuery } from "@tanstack/react-query";
import {
  getDashboardSummary, getFleetHealth,
  type DashboardSummary, type FleetHealthSummary,
} from "@/lib/api";
import { KpiCard } from "@/components/dashboard/kpi-card";
import { GpuPanel } from "@/components/dashboard/gpu-panel";
import { HostGrid } from "@/components/dashboard/host-grid";
import { TrendCharts } from "@/components/dashboard/trend-charts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import {
  Server, Cpu, Container, Activity, Database, LayoutGrid,
  RefreshCw, Radio, AlertTriangle, WifiOff, Archive,
} from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { useRefreshCountdown, fmtTime } from "@/lib/hooks";

const DASHBOARD_INTERVAL = 30_000;
const FLEET_INTERVAL = 6_000;

export default function DashboardPage() {
  const queryClient = useQueryClient();

  const { data, isLoading, dataUpdatedAt } = useQuery<DashboardSummary>({
    queryKey: ["dashboard", "summary"],
    queryFn: getDashboardSummary,
    refetchInterval: DASHBOARD_INTERVAL,
  });

  const { data: fleet, dataUpdatedAt: fleetUpdatedAt } = useQuery<FleetHealthSummary>({
    queryKey: ["fleet", "health"],
    queryFn: getFleetHealth,
    refetchInterval: FLEET_INTERVAL,
  });

  const { secsLeft, progress, lastRefreshed } = useRefreshCountdown(dataUpdatedAt, DASHBOARD_INTERVAL);
  const { secsLeft: fleetSecs, progress: fleetProgress, lastRefreshed: fleetRefreshed } =
    useRefreshCountdown(fleetUpdatedAt, FLEET_INTERVAL);

  return (
    <div className="page-in" style={{ display: "flex", flexDirection: "column", gap: 24 }}>

      {/* ── Header ──────────────────────────────────────────── */}
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
        <div>
          <h1 className="df-page-title">Dashboard</h1>
          <p className="df-page-sub" style={{ display: "flex", alignItems: "center", gap: 8 }}>
            Infrastructure overview
            {lastRefreshed && (
              <span style={{ fontFamily: "var(--fM)", fontSize: 11, color: "var(--tx4)" }}>
                · last ↻ {fmtTime(lastRefreshed)}
              </span>
            )}
          </p>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
          {/* LIVE badge */}
          <div className="live-badge">
            <div className="live-dot-wrap">
              <div className="live-dot-core" />
              <div className="live-dot-ring" />
            </div>
            LIVE
          </div>

          {/* Countdown pill */}
          <div className="countdown-pill">
            <RefreshCw size={11} style={{ opacity: 0.55, flexShrink: 0 }} />
            <span style={{ minWidth: 24, textAlign: "right" }}>{secsLeft}s</span>
            <div className="countdown-track">
              <div className="countdown-fill" style={{ transform: `scaleX(${progress})` }} />
            </div>
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
      </div>

      {/* ── KPI Cards ────────────────────────────────────────── */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 14 }} className="lg:grid-cols-6! sm:grid-cols-3!">
        {isLoading ? (
          Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-28 w-full" />
          ))
        ) : (
          <>
            <KpiCard
              title="Hosts"
              value={data?.host_count ?? 0}
              sub={`${data?.cluster_count ?? 0} cluster(s)`}
              icon={Server}
              color="var(--g3)"
              lastRefreshed={lastRefreshed}
              dataUpdatedAt={dataUpdatedAt}
            />
            <KpiCard
              title="GPU Devices"
              value={data?.gpu_count ?? 0}
              sub={`${data?.total_gpu_vram_gb?.toFixed(0) ?? 0} GB VRAM`}
              icon={Cpu}
              color="var(--pu)"
              lastRefreshed={lastRefreshed}
              dataUpdatedAt={dataUpdatedAt}
            />
            <KpiCard
              title="Docker Hosts"
              value={data?.docker_host_count ?? 0}
              sub={`${data?.service_instance_count ?? 0} instances`}
              icon={Container}
              color="var(--in)"
              lastRefreshed={lastRefreshed}
              dataUpdatedAt={dataUpdatedAt}
            />
            <KpiCard
              title="Services"
              value={data?.service_count ?? 0}
              icon={LayoutGrid}
              color="var(--wa)"
              lastRefreshed={lastRefreshed}
              dataUpdatedAt={dataUpdatedAt}
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
              lastRefreshed={lastRefreshed}
              dataUpdatedAt={dataUpdatedAt}
            />
            <KpiCard
              title="Total RAM"
              value={`${data?.total_ram_gb?.toFixed(0) ?? 0} GB`}
              icon={Database}
              color="var(--in)"
              lastRefreshed={lastRefreshed}
              dataUpdatedAt={dataUpdatedAt}
            />
          </>
        )}
      </div>

      {/* ── Fleet Agent Health ───────────────────────────────── */}
      <Card>
        <CardHeader style={{ paddingBottom: 12 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
            <CardTitle style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <Radio size={15} style={{ color: "var(--g2)" }} />
              Collector Agents
            </CardTitle>
            <div style={{ display: "flex", alignItems: "center", gap: 8, fontFamily: "var(--fM)", fontSize: 11, color: "var(--tx4)" }}>
              {fleet && (
                <span>
                  {fleet.registered_agents} / {fleet.expected_hosts || fleet.total} hosts covered
                  {fleet.unassigned_agents > 0 ? ` • ${fleet.unassigned_agents} unassigned agent${fleet.unassigned_agents !== 1 ? "s" : ""}` : ""}
                </span>
              )}
              <div className="countdown-pill" style={{ minWidth: "unset", padding: "3px 8px" }}>
                <RefreshCw size={10} style={{ opacity: 0.5, flexShrink: 0 }} />
                <span>{fleetSecs}s</span>
                <div className="countdown-track" style={{ minWidth: 36 }}>
                  <div className="countdown-fill" style={{ transform: `scaleX(${fleetProgress})` }} />
                </div>
              </div>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {fleet === undefined ? (
            <div style={{ display: "flex", gap: 12 }}>
              {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="h-20 w-24" />
              ))}
            </div>
          ) : (
            <>
              <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
                <div className="agent-status-card online">
                  <div className="agent-status-v">{fleet.online}</div>
                  <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
                    <div className="live-dot-wrap" style={{ width: 6, height: 6 }}>
                      <div className="live-dot-core" style={{ width: 6, height: 6 }} />
                      <div className="live-dot-ring" style={{ borderWidth: 1 }} />
                    </div>
                    <span className="agent-status-l">Online</span>
                  </div>
                </div>
                <div className="agent-status-card degraded">
                  <div className="agent-status-v">{fleet.degraded}</div>
                  <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
                    <AlertTriangle size={10} style={{ color: "oklch(0.78 0.18 74)" }} />
                    <span className="agent-status-l">Degraded</span>
                  </div>
                </div>
                <div className="agent-status-card offline">
                  <div className="agent-status-v">{fleet.offline}</div>
                  <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
                    <WifiOff size={10} style={{ color: "var(--er)" }} />
                    <span className="agent-status-l">Offline</span>
                  </div>
                </div>
                <div className="agent-status-card retired">
                  <div className="agent-status-v">{fleet.retired}</div>
                  <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
                    <Archive size={10} style={{ color: "var(--tx4)" }} />
                    <span className="agent-status-l">Retired</span>
                  </div>
                </div>
              </div>
              {fleetRefreshed && (
                <p style={{ fontFamily: "var(--fM)", fontSize: 11, color: "var(--tx4)", marginTop: 10 }}>
                  ↻ {fmtTime(fleetRefreshed)}
                </p>
              )}
            </>
          )}
        </CardContent>
      </Card>

      {/* ── Trend Charts ─────────────────────────────────────── */}
      <Card>
        <CardHeader>
          <CardTitle>Host activity trends</CardTitle>
        </CardHeader>
        <CardContent>
          <TrendCharts />
        </CardContent>
      </Card>

      {/* ── GPU Devices ──────────────────────────────────────── */}
      <Card>
        <CardHeader>
          <CardTitle>GPU devices</CardTitle>
        </CardHeader>
        <CardContent>
          <GpuPanel />
        </CardContent>
      </Card>

      {/* ── All Hosts ────────────────────────────────────────── */}
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
