"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  getDashboardSummary, getFleetHealth, getFleetVitals,
  type DashboardSummary, type FleetHealthSummary, type FleetVital,
} from "@/lib/api";
import { KpiCard } from "@/components/dashboard/kpi-card";
import { GpuPanel } from "@/components/dashboard/gpu-panel";
import { HostGrid } from "@/components/dashboard/host-grid";
import { TrendCharts } from "@/components/dashboard/trend-charts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import {
  Server, Cpu, Container, Activity, LayoutGrid,
  RefreshCw, Radio, AlertTriangle, WifiOff, Archive, Users,
} from "lucide-react";
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

  const { data: vitals } = useQuery<FleetVital[]>({
    queryKey: ["fleet", "vitals"],
    queryFn: getFleetVitals,
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
          ["kpi-sk-1", "kpi-sk-2", "kpi-sk-3", "kpi-sk-4", "kpi-sk-5", "kpi-sk-6"].map((k) => (
            <Skeleton key={k} className="h-28 w-full" />
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
              title="Active Agents"
              value={fleet?.online ?? 0}
              sub={`${fleet?.total ?? 0} total · ${fleet?.offline ?? 0} offline`}
              icon={Users}
              color="var(--ok)"
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
              {fleet && (() => {
                const plural = fleet.unassigned_agents === 1 ? "" : "s";
                const unassignedPart = fleet.unassigned_agents > 0
                  ? ` • ${fleet.unassigned_agents} unassigned agent${plural}`
                  : "";
                return (
                  <span>
                    {fleet.registered_agents} / {fleet.expected_hosts || fleet.total} hosts covered
                    {unassignedPart}
                  </span>
                );
              })()}
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
              {["fleet-sk-1", "fleet-sk-2", "fleet-sk-3", "fleet-sk-4"].map((k) => (
                <Skeleton key={k} className="h-20 w-24" />
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

      {/* ── Fleet Vitals Table ──────────────────────────────── */}
      {vitals && vitals.length > 0 && (
        <Card>
          <CardHeader style={{ paddingBottom: 12 }}>
            <CardTitle style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <Activity size={15} style={{ color: "var(--in)" }} />
              Fleet Vitals
              <span style={{ fontFamily: "var(--fM)", fontSize: 11, color: "var(--tx4)", fontWeight: 400, marginLeft: "auto" }}>
                {vitals.filter(v => v.status === "online").length} / {vitals.length} agents online
              </span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontFamily: "var(--fM)", fontSize: 12 }}>
                <thead>
                  <tr style={{ borderBottom: "1px solid var(--sl3)", textAlign: "left" }}>
                    <th style={{ padding: "6px 10px", fontWeight: 600, color: "var(--tx3)" }}>Host</th>
                    <th style={{ padding: "6px 10px", fontWeight: 600, color: "var(--tx3)" }}>Status</th>
                    <th style={{ padding: "6px 10px", fontWeight: 600, color: "var(--tx3)" }}>RAM</th>
                    <th style={{ padding: "6px 10px", fontWeight: 600, color: "var(--tx3)" }}>Memory %</th>
                    <th style={{ padding: "6px 10px", fontWeight: 600, color: "var(--tx3)" }}>Disk /</th>
                    <th style={{ padding: "6px 10px", fontWeight: 600, color: "var(--tx3)" }}>Load</th>
                    <th style={{ padding: "6px 10px", fontWeight: 600, color: "var(--tx3)" }}>Docker</th>
                  </tr>
                </thead>
                <tbody>
                  {vitals.filter(v => v.status === "online").map((v) => {
                    const memPct = v.memory_pct ?? 0;
                    const diskPct = v.disk_root_pct ?? 0;
                    let memColor = "var(--ok)";
                    if (memPct > 85) memColor = "var(--er)";
                    else if (memPct > 60) memColor = "var(--wa)";
                    let diskColor = "var(--ok)";
                    if (diskPct > 85) diskColor = "var(--er)";
                    else if (diskPct > 60) diskColor = "var(--wa)";
                    return (
                      <tr key={v.agent_id} style={{ borderBottom: "1px solid var(--sl2)" }}>
                        <td style={{ padding: "7px 10px", fontWeight: 500 }}>{v.host_code}</td>
                        <td style={{ padding: "7px 10px" }}>
                          <span style={{
                            display: "inline-flex", alignItems: "center", gap: 4,
                            padding: "2px 8px", borderRadius: 10, fontSize: 10, fontWeight: 600,
                            background: v.status === "online" ? "oklch(0.45 0.12 145 / 0.15)" : "oklch(0.45 0.12 25 / 0.15)",
                            color: v.status === "online" ? "var(--ok)" : "var(--er)",
                          }}>
                            <span style={{ width: 5, height: 5, borderRadius: "50%", background: "currentColor" }} />
                            {v.status}
                          </span>
                        </td>
                        <td style={{ padding: "7px 10px", color: "var(--tx3)" }}>
                          {v.memory_total_gb == null ? "—" : `${v.memory_total_gb} GB`}
                        </td>
                        <td style={{ padding: "7px 10px" }}>
                          {v.memory_pct == null ? "—" : (
                            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                              <div style={{ flex: 1, height: 6, borderRadius: 3, background: "var(--sl2)", minWidth: 40, maxWidth: 80 }}>
                                <div style={{ width: `${memPct}%`, height: "100%", borderRadius: 3, background: memColor, transition: "width 0.3s" }} />
                              </div>
                              <span style={{ color: memColor, fontWeight: 600, minWidth: 32 }}>{memPct}%</span>
                            </div>
                          )}
                        </td>
                        <td style={{ padding: "7px 10px" }}>
                          {v.disk_root_pct == null ? "—" : (
                            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                              <div style={{ flex: 1, height: 6, borderRadius: 3, background: "var(--sl2)", minWidth: 40, maxWidth: 80 }}>
                                <div style={{ width: `${diskPct}%`, height: "100%", borderRadius: 3, background: diskColor, transition: "width 0.3s" }} />
                              </div>
                              <span style={{ color: diskColor, fontWeight: 600, minWidth: 32 }}>{diskPct}%</span>
                            </div>
                          )}
                        </td>
                        <td style={{ padding: "7px 10px", color: "var(--tx3)" }}>
                          {v.load_avg.length > 0 ? v.load_avg.slice(0, 3).map(l => l.toFixed(1)).join(" / ") : "—"}
                        </td>
                        <td style={{ padding: "7px 10px" }}>
                          {v.containers_total > 0 ? (
                            <span style={{ color: "var(--in)" }}>
                              <Container size={11} style={{ display: "inline", verticalAlign: "middle", marginRight: 3 }} />
                              {v.containers_running}/{v.containers_total}
                            </span>
                          ) : (
                            <span style={{ color: "var(--tx4)" }}>—</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

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
