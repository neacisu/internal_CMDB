"use client";

import { type ReactNode } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  getFleetHealth,
  getGpuSummary,
  getFleetHealthDashboard,
  getHealthScores,
  type FleetHealthSummary,
  type GpuSummaryItem,
  type HealthScoreOut,
} from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Progress } from "@/components/ui/progress";
import { Button } from "@/components/ui/button";
import { useRefreshCountdown, fmtTime } from "@/lib/hooks";
import {
  Activity,
  RefreshCw,
  Server,
  Cpu,
  Radio,
  Gauge,
  Thermometer,
  Zap,
} from "lucide-react";

const REFRESH_INTERVAL = 6_000;

const METRICS_FLEET_STRIP_SKELETON_KEYS = [
  "metrics-fleet-sk-a",
  "metrics-fleet-sk-b",
  "metrics-fleet-sk-c",
] as const;

const METRICS_HEATMAP_SKELETON_KEYS = [
  "metrics-hm-sk-01",
  "metrics-hm-sk-02",
  "metrics-hm-sk-03",
  "metrics-hm-sk-04",
  "metrics-hm-sk-05",
  "metrics-hm-sk-06",
  "metrics-hm-sk-07",
  "metrics-hm-sk-08",
  "metrics-hm-sk-09",
  "metrics-hm-sk-10",
  "metrics-hm-sk-11",
  "metrics-hm-sk-12",
] as const;

const METRICS_GPU_ROW_SKELETON_KEYS = [
  "metrics-gpu-sk-a",
  "metrics-gpu-sk-b",
  "metrics-gpu-sk-c",
  "metrics-gpu-sk-d",
] as const;

function statusColor(s: string) {
  if (s === "online") return "var(--ok)";
  if (s === "degraded") return "var(--wa)";
  return "var(--er)";
}

function utilColor(pct: number | null) {
  if (pct === null) return "bg-(--sl3) text-(--tx3)";
  if (pct >= 80) return "bg-(--er) text-white";
  if (pct >= 50) return "bg-(--wa) text-white";
  return "bg-(--ok) text-white";
}

export default function MetricsPage() {
  const queryClient = useQueryClient();

  const { data: fleet, dataUpdatedAt } = useQuery<FleetHealthSummary>({
    queryKey: ["fleet", "health"],
    queryFn: getFleetHealth,
    refetchInterval: REFRESH_INTERVAL,
    staleTime: 4_000,
  });

  const { data: fleetHosts } = useQuery({
    queryKey: ["fleet", "dashboard"],
    queryFn: getFleetHealthDashboard,
    refetchInterval: REFRESH_INTERVAL,
    staleTime: 4_000,
  });

  const { data: gpus, isLoading: gpuLoading } = useQuery<GpuSummaryItem[]>({
    queryKey: ["dashboard", "gpu-summary"],
    queryFn: getGpuSummary,
    refetchInterval: 15_000,
    staleTime: 10_000,
  });

  const { data: healthScores } = useQuery<HealthScoreOut[]>({
    queryKey: ["cognitive", "health-scores"],
    queryFn: getHealthScores,
    refetchInterval: 15_000,
    staleTime: 10_000,
  });

  const { secsLeft, progress, lastRefreshed } = useRefreshCountdown(dataUpdatedAt, REFRESH_INTERVAL);

  let gpuUtilizationBody: ReactNode;
  if (gpuLoading) {
    gpuUtilizationBody = (
      <div className="space-y-2">
        {METRICS_GPU_ROW_SKELETON_KEYS.map((skKey) => (
          <Skeleton key={skKey} className="h-10 w-full" />
        ))}
      </div>
    );
  } else if (gpus && gpus.length > 0) {
    gpuUtilizationBody = (
      <div className="space-y-3">
        {gpus.map((g) => (
          <div key={`${g.host_id}-${g.gpu_index}`} className="flex items-center gap-3">
            <div className="min-w-24 text-sm truncate" title={g.hostname}>
              {g.hostname}
              <span className="text-xs text-(--tx3) ml-1">#{g.gpu_index}</span>
            </div>
            <div className="flex-1 flex items-center gap-2">
              <Progress value={g.utilization_gpu_pct ?? 0} className="h-2 flex-1" />
              <Badge className={`${utilColor(g.utilization_gpu_pct)} text-xs px-1.5 py-0 w-12 justify-center`}>
                {g.utilization_gpu_pct ?? 0}%
              </Badge>
            </div>
            <div className="flex gap-3 text-xs text-(--tx3)" style={{ fontFamily: "var(--fM)" }}>
              <span title="Temperature" className="flex items-center gap-0.5">
                <Thermometer size={10} /> {g.temperature_celsius ?? "—"}°
              </span>
              <span title="Power" className="flex items-center gap-0.5">
                <Zap size={10} /> {g.power_draw_watts ?? "—"}W
              </span>
              <span title="VRAM" className="flex items-center gap-0.5">
                <Gauge size={10} /> {g.memory_used_mb ?? 0}/{g.memory_total_mb ?? 0}MB
              </span>
            </div>
          </div>
        ))}
      </div>
    );
  } else {
    gpuUtilizationBody = <p className="text-sm text-(--tx3)">No GPU devices registered.</p>;
  }

  return (
    <div className="page-in" style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
        <div>
          <h1 className="df-page-title" style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <Activity size={22} style={{ color: "var(--g2)" }} />
            Live Metrics
          </h1>
          <p className="df-page-sub">
            Fleet health, GPU utilization, and LLM performance
            {lastRefreshed && (
              <span style={{ fontFamily: "var(--fM)", fontSize: 11, color: "var(--tx4)", marginLeft: 8 }}>
                · ↻ {fmtTime(lastRefreshed)}
              </span>
            )}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="live-badge">
            <div className="live-dot-wrap">
              <div className="live-dot-core" />
              <div className="live-dot-ring" />
            </div>
            LIVE
          </div>
          <div className="countdown-pill">
            <RefreshCw size={11} style={{ opacity: 0.55 }} />
            <span style={{ minWidth: 20, textAlign: "right" }}>{secsLeft}s</span>
            <div className="countdown-track">
              <div className="countdown-fill" style={{ transform: `scaleX(${progress})` }} />
            </div>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => queryClient.invalidateQueries()}
          >
            <RefreshCw size={13} />
            Refresh
          </Button>
        </div>
      </div>

      {/* Fleet status strip */}
      <Card>
        <CardHeader style={{ paddingBottom: 8 }}>
          <CardTitle className="flex items-center gap-2">
            <Radio size={15} style={{ color: "var(--g2)" }} />
            Fleet Agent Status
          </CardTitle>
        </CardHeader>
        <CardContent>
          {fleet ? (
            <div className="flex gap-3 flex-wrap">
              <div className="agent-status-card online">
                <div className="agent-status-v">{fleet.online}</div>
                <span className="agent-status-l">Online</span>
              </div>
              <div className="agent-status-card degraded">
                <div className="agent-status-v">{fleet.degraded}</div>
                <span className="agent-status-l">Degraded</span>
              </div>
              <div className="agent-status-card offline">
                <div className="agent-status-v">{fleet.offline}</div>
                <span className="agent-status-l">Offline</span>
              </div>
            </div>
          ) : (
            <div className="flex gap-3">
              {METRICS_FLEET_STRIP_SKELETON_KEYS.map((skKey) => (
                <Skeleton key={skKey} className="h-16 w-20" />
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Fleet Heatmap */}
      <Card>
        <CardHeader style={{ paddingBottom: 8 }}>
          <CardTitle className="flex items-center gap-2">
            <Server size={15} style={{ color: "var(--in)" }} />
            Fleet Heatmap
          </CardTitle>
        </CardHeader>
        <CardContent>
          {fleetHosts ? (
            <div className="flex gap-2 flex-wrap">
              {fleetHosts.map((h) => (
                <div
                  key={h.host_code}
                  title={`${h.hostname} — ${h.status}`}
                  style={{
                    width: 44,
                    height: 44,
                    borderRadius: 6,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    background: statusColor(h.status),
                    opacity: h.has_agent ? 0.85 : 0.35,
                    cursor: "default",
                    border: "1px solid rgba(255,255,255,0.1)",
                  }}
                >
                  <Server size={14} style={{ color: "#fff" }} />
                </div>
              ))}
            </div>
          ) : (
            <div className="flex gap-2 flex-wrap">
              {METRICS_HEATMAP_SKELETON_KEYS.map((skKey) => (
                <Skeleton key={skKey} className="h-11 w-11 rounded" />
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* GPU utilization */}
      <Card>
        <CardHeader style={{ paddingBottom: 8 }}>
          <CardTitle className="flex items-center gap-2">
            <Cpu size={15} style={{ color: "var(--pu)" }} />
            GPU Utilization
          </CardTitle>
        </CardHeader>
        <CardContent>{gpuUtilizationBody}</CardContent>
      </Card>

      {/* Health Score distribution */}
      {healthScores && healthScores.length > 0 && (
        <Card>
          <CardHeader style={{ paddingBottom: 8 }}>
            <CardTitle className="flex items-center gap-2">
              <Gauge size={15} style={{ color: "var(--ok)" }} />
              Cognitive Health Scores
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex gap-3 flex-wrap">
              <div className="rounded-md border border-(--ok)/30 bg-(--ok)/10 px-3 py-2 text-center min-w-16">
                <p className="text-lg font-semibold text-(--ok)">
                  {healthScores.filter((s) => s.score > 80).length}
                </p>
                <p className="text-xs text-(--tx3)">Healthy</p>
              </div>
              <div className="rounded-md border border-(--wa)/30 bg-(--wa)/10 px-3 py-2 text-center min-w-16">
                <p className="text-lg font-semibold text-(--wa)">
                  {healthScores.filter((s) => s.score >= 60 && s.score <= 80).length}
                </p>
                <p className="text-xs text-(--tx3)">Warning</p>
              </div>
              <div className="rounded-md border border-(--er)/30 bg-(--er)/10 px-3 py-2 text-center min-w-16">
                <p className="text-lg font-semibold text-(--er)">
                  {healthScores.filter((s) => s.score < 60).length}
                </p>
                <p className="text-xs text-(--tx3)">Critical</p>
              </div>
              <div className="rounded-md border border-border bg-(--sl2) px-3 py-2 text-center min-w-16">
                <p className="text-lg font-semibold">
                  {Math.round(healthScores.reduce((a, s) => a + s.score, 0) / healthScores.length)}
                </p>
                <p className="text-xs text-(--tx3)">Avg Score</p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
