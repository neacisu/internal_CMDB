"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  getHealthScores,
  getInsights,
  getSelfHealHistory,
  type HealthScoreOut,
  type InsightOut,
  type SelfHealActionOut,
} from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { useRefreshCountdown, fmtTime } from "@/lib/hooks";
import Link from "next/link";
import {
  Brain,
  RefreshCw,
  Activity,
  AlertTriangle,
  ShieldCheck,
  Wrench,
  MessageSquare,
  ChevronRight,
} from "lucide-react";

const REFRESH_INTERVAL = 15_000;

const COGNITIVE_HEALTH_HEATMAP_SKELETON_KEYS = [
  "cog-hm-sk-01",
  "cog-hm-sk-02",
  "cog-hm-sk-03",
  "cog-hm-sk-04",
  "cog-hm-sk-05",
  "cog-hm-sk-06",
  "cog-hm-sk-07",
  "cog-hm-sk-08",
  "cog-hm-sk-09",
  "cog-hm-sk-10",
  "cog-hm-sk-11",
  "cog-hm-sk-12",
  "cog-hm-sk-13",
  "cog-hm-sk-14",
  "cog-hm-sk-15",
  "cog-hm-sk-16",
] as const;

function severityColor(s: string) {
  if (s === "critical") return "bg-(--er) text-white";
  if (s === "warning") return "bg-(--wa) text-white";
  return "bg-(--sl3) text-(--tx3)";
}

function scoreColor(score: number) {
  if (score > 80) return "var(--ok)";
  if (score >= 60) return "var(--wa)";
  return "var(--er)";
}

export default function CognitiveDashboardPage() {
  const queryClient = useQueryClient();

  const { data: scores, isLoading: scoresLoading, dataUpdatedAt } = useQuery<HealthScoreOut[]>({
    queryKey: ["cognitive", "health-scores"],
    queryFn: getHealthScores,
    refetchInterval: REFRESH_INTERVAL,
    staleTime: 10_000,
  });

  const { data: insights } = useQuery<InsightOut[]>({
    queryKey: ["cognitive", "insights"],
    queryFn: () => getInsights("status=active&page_size=10"),
    refetchInterval: REFRESH_INTERVAL,
    staleTime: 10_000,
  });

  const { data: healHistory } = useQuery<SelfHealActionOut[]>({
    queryKey: ["cognitive", "self-heal-history"],
    queryFn: () => getSelfHealHistory("page_size=10"),
    refetchInterval: REFRESH_INTERVAL,
    staleTime: 10_000,
  });

  const { secsLeft, progress, lastRefreshed } = useRefreshCountdown(dataUpdatedAt, REFRESH_INTERVAL);

  const healthy = scores?.filter((s) => s.score > 80).length ?? 0;
  const warning = scores?.filter((s) => s.score >= 60 && s.score <= 80).length ?? 0;
  const critical = scores?.filter((s) => s.score < 60).length ?? 0;

  return (
    <div className="page-in" style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
        <div>
          <h1 className="df-page-title" style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <Brain size={22} style={{ color: "var(--pu)" }} />
            Cognitive Dashboard
          </h1>
          <p className="df-page-sub">
            AI-powered infrastructure intelligence
            {lastRefreshed && (
              <span style={{ fontFamily: "var(--fM)", fontSize: 11, color: "var(--tx4)", marginLeft: 8 }}>
                · last ↻ {fmtTime(lastRefreshed)}
              </span>
            )}
          </p>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
          <div className="live-badge">
            <div className="live-dot-wrap">
              <div className="live-dot-core" />
              <div className="live-dot-ring" />
            </div>
            LIVE
          </div>
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
            onClick={() => queryClient.invalidateQueries({ queryKey: ["cognitive"] })}
          >
            <RefreshCw size={13} />
            Refresh
          </Button>
        </div>
      </div>

      {/* Quick links */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <Link href="/cognitive/chat" className="no-underline">
          <Card className="hover:border-(--pu)/40 transition-colors cursor-pointer">
            <CardContent className="p-4 flex items-center gap-3">
              <MessageSquare size={18} style={{ color: "var(--pu)" }} />
              <div>
                <p className="text-sm font-medium">Ask Infrastructure</p>
                <p className="text-xs text-(--tx3)">NL query with RAG</p>
              </div>
              <ChevronRight size={14} className="ml-auto text-(--tx4)" />
            </CardContent>
          </Card>
        </Link>
        <Link href="/cognitive/insights" className="no-underline">
          <Card className="hover:border-(--wa)/40 transition-colors cursor-pointer">
            <CardContent className="p-4 flex items-center gap-3">
              <AlertTriangle size={18} style={{ color: "var(--wa)" }} />
              <div>
                <p className="text-sm font-medium">Insights</p>
                <p className="text-xs text-(--tx3)">{insights?.length ?? 0} active</p>
              </div>
              <ChevronRight size={14} className="ml-auto text-(--tx4)" />
            </CardContent>
          </Card>
        </Link>
        <Link href="/hitl" className="no-underline">
          <Card className="hover:border-(--in)/40 transition-colors cursor-pointer">
            <CardContent className="p-4 flex items-center gap-3">
              <ShieldCheck size={18} style={{ color: "var(--in)" }} />
              <div>
                <p className="text-sm font-medium">HITL Queue</p>
                <p className="text-xs text-(--tx3)">Human review</p>
              </div>
              <ChevronRight size={14} className="ml-auto text-(--tx4)" />
            </CardContent>
          </Card>
        </Link>
      </div>

      {/* Health Score Heatmap */}
      <Card>
        <CardHeader style={{ paddingBottom: 12 }}>
          <div className="flex items-center justify-between">
            <CardTitle style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <Activity size={15} style={{ color: "var(--g2)" }} />
              Health Score Heatmap
            </CardTitle>
            <div className="flex gap-3 text-xs" style={{ fontFamily: "var(--fM)" }}>
              <span style={{ color: "var(--ok)" }}>● {healthy} healthy</span>
              <span style={{ color: "var(--wa)" }}>● {warning} warning</span>
              <span style={{ color: "var(--er)" }}>● {critical} critical</span>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {scoresLoading ? (
            <div className="flex gap-2 flex-wrap">
              {COGNITIVE_HEALTH_HEATMAP_SKELETON_KEYS.map((skKey) => (
                <Skeleton key={skKey} className="h-12 w-12 rounded" />
              ))}
            </div>
          ) : (
            <div className="flex gap-2 flex-wrap">
              {scores?.map((s) => (
                <div
                  key={s.entity_id}
                  title={`${s.entity_id.slice(0, 8)}… — Score: ${s.score}`}
                  style={{
                    width: 48,
                    height: 48,
                    borderRadius: 6,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontSize: 13,
                    fontFamily: "var(--fM)",
                    fontWeight: 600,
                    color: "#fff",
                    background: scoreColor(s.score),
                    opacity: 0.7 + (s.score / 100) * 0.3,
                    cursor: "default",
                  }}
                >
                  {s.score}
                </div>
              ))}
              {(!scores || scores.length === 0) && (
                <p className="text-sm text-(--tx3)">No health scores available yet.</p>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }} className="lg:grid-cols-2!">
        {/* Insights Ticker */}
        <Card>
          <CardHeader style={{ paddingBottom: 8 }}>
            <CardTitle style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <AlertTriangle size={15} style={{ color: "var(--wa)" }} />
              Active Insights
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {insights?.length === 0 && (
                <p className="text-sm text-(--tx3)">No active insights.</p>
              )}
              {insights?.map((ins) => (
                <div
                  key={ins.insight_id}
                  className="rounded-md border border-border p-3 flex items-start gap-3"
                >
                  <Badge className={`${severityColor(ins.severity)} text-xs px-1.5 py-0 shrink-0`}>
                    {ins.severity}
                  </Badge>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium leading-tight">{ins.title || ins.description.slice(0, 80)}</p>
                    {ins.entity_id && (
                      <p className="text-xs text-(--tx3) mt-0.5" style={{ fontFamily: "var(--fM)" }}>
                        {ins.entity_type}: {ins.entity_id.slice(0, 12)}…
                      </p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Self-heal Log */}
        <Card>
          <CardHeader style={{ paddingBottom: 8 }}>
            <CardTitle style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <Wrench size={15} style={{ color: "var(--in)" }} />
              Self-Heal Log
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {(!healHistory || healHistory.length === 0) && (
                <p className="text-sm text-(--tx3)">No self-healing actions recorded.</p>
              )}
              {healHistory?.map((a) => (
                <div
                  key={a.action_id}
                  className="rounded-md border border-border p-3 flex items-center gap-3"
                >
                  <Badge
                    className={`text-xs px-1.5 py-0 ${
                      a.status === "completed"
                        ? "bg-(--ok)/15 text-(--ok) border-(--ok)/30"
                        : "bg-(--sl3) text-(--tx3)"
                    }`}
                  >
                    {a.status}
                  </Badge>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium">{a.playbook_name}</p>
                    <p className="text-xs text-(--tx3)">{a.result_summary}</p>
                  </div>
                  {a.executed_at && (
                    <span className="text-xs text-(--tx4) shrink-0" style={{ fontFamily: "var(--fM)" }}>
                      {new Date(a.executed_at).toLocaleTimeString()}
                    </span>
                  )}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
