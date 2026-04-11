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
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { useRefreshCountdown, fmtTime } from "@/lib/hooks";
import { timeAgo } from "@/lib/utils";
import Link from "next/link";
import {
  Brain, RefreshCw, Activity, AlertTriangle, ShieldCheck, Wrench,
  MessageSquare, ChevronRight, Server, Heart,
} from "lucide-react";

const REFRESH_INTERVAL = 15_000;

const HEATMAP_SKELETON_PLACEHOLDER_KEYS = [
  "heatmap-ph-a", "heatmap-ph-b", "heatmap-ph-c", "heatmap-ph-d", "heatmap-ph-e",
  "heatmap-ph-f", "heatmap-ph-g", "heatmap-ph-h", "heatmap-ph-i",
] as const;

function fleetHealthColor(score: number): string {
  return scoreColor(score);
}

function healthStatusBadgeClass(status: string): string {
  if (status === "healthy") return "bg-[oklch(0.25_0.08_145)] text-[oklch(0.65_0.18_145)]";
  if (status === "warning") return "bg-[oklch(0.25_0.08_85)] text-[oklch(0.7_0.15_85)]";
  return "bg-[oklch(0.25_0.08_25)] text-[oklch(0.65_0.18_25)]";
}

function severityColor(s: string) {
  if (s === "critical") return "bg-[oklch(0.35_0.12_25)] text-[oklch(0.85_0.1_25)]";
  if (s === "warning") return "bg-[oklch(0.35_0.12_85)] text-[oklch(0.85_0.1_85)]";
  return "bg-(--sl3) text-(--tx3)";
}

function scoreColor(score: number) {
  if (score > 80) return "oklch(0.65 0.18 145)";
  if (score >= 60) return "oklch(0.7 0.15 85)";
  return "oklch(0.65 0.18 25)";
}

function scoreBg(score: number) {
  if (score > 80) return "oklch(0.25 0.08 145)";
  if (score >= 60) return "oklch(0.25 0.08 85)";
  return "oklch(0.25 0.08 25)";
}

function KpiCard({ label, value, icon: Icon, color }: Readonly<{
  label: string; value: string | number; icon: React.ElementType; color?: string;
}>) {
  return (
    <Card>
      <CardContent className="flex items-center gap-3 py-3 px-4">
        <div className="flex items-center justify-center w-9 h-9 rounded-lg" style={{ background: "var(--sl4)" }}>
          <Icon size={17} style={{ color: color || "var(--tx3)" }} />
        </div>
        <div className="flex flex-col min-w-0">
          <span className="text-[22px] font-bold leading-none" style={{ fontFamily: "var(--fD)" }}>{value}</span>
          <span className="text-[11px] mt-0.5" style={{ color: "var(--tx3)" }}>{label}</span>
        </div>
      </CardContent>
    </Card>
  );
}

function OverviewTab({ scores, scoresLoading, insights, healHistory }: Readonly<{
  scores: HealthScoreOut[] | undefined;
  scoresLoading: boolean;
  insights: InsightOut[] | undefined;
  healHistory: SelfHealActionOut[] | undefined;
}>) {
  const healthy = scores?.filter((s) => s.score > 80).length ?? 0;
  const warning = scores?.filter((s) => s.score >= 60 && s.score <= 80).length ?? 0;
  const critical = scores?.filter((s) => s.score < 60).length ?? 0;
  const avgScore = scores && scores.length > 0
    ? Math.round(scores.reduce((s, h) => s + h.score, 0) / scores.length) : 0;

  const criticalInsights = insights?.filter(i => i.severity === "critical").length ?? 0;
  const warningInsights = insights?.filter(i => i.severity === "warning").length ?? 0;

  return (
    <div className="flex flex-col gap-5">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <KpiCard icon={Heart} label="Fleet Health" value={`${avgScore}/100`}
          color={fleetHealthColor(avgScore)} />
        <KpiCard icon={Server} label="Hosts Scored" value={scores?.length ?? 0} />
        <KpiCard icon={AlertTriangle} label="Active Insights" value={insights?.length ?? 0}
          color={criticalInsights > 0 ? "oklch(0.65 0.18 25)" : undefined} />
        <KpiCard icon={Wrench} label="Self-Heal Actions" value={healHistory?.length ?? 0} />
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <Link href="/cognitive/chat" className="no-underline">
          <Card className="hover:border-[oklch(0.5_0.15_290)]/40 transition-colors cursor-pointer">
            <CardContent className="p-4 flex items-center gap-3">
              <MessageSquare size={18} style={{ color: "oklch(0.65 0.15 290)" }} />
              <div>
                <p className="text-sm font-medium">Ask Infrastructure</p>
                <p className="text-xs" style={{ color: "var(--tx3)" }}>NL query with RAG</p>
              </div>
              <ChevronRight size={14} className="ml-auto" style={{ color: "var(--tx4)" }} />
            </CardContent>
          </Card>
        </Link>
        <Link href="/cognitive/insights" className="no-underline">
          <Card className="hover:border-[oklch(0.5_0.15_85)]/40 transition-colors cursor-pointer">
            <CardContent className="p-4 flex items-center gap-3">
              <AlertTriangle size={18} style={{ color: "oklch(0.7 0.15 85)" }} />
              <div>
                <p className="text-sm font-medium">Insights</p>
                <p className="text-xs" style={{ color: "var(--tx3)" }}>
                  {criticalInsights > 0 && <span className="text-[oklch(0.65_0.18_25)]">{criticalInsights} critical</span>}
                  {criticalInsights > 0 && warningInsights > 0 && ", "}
                  {warningInsights > 0 && <span className="text-[oklch(0.7_0.15_85)]">{warningInsights} warning</span>}
                  {criticalInsights === 0 && warningInsights === 0 && `${insights?.length ?? 0} active`}
                </p>
              </div>
              <ChevronRight size={14} className="ml-auto" style={{ color: "var(--tx4)" }} />
            </CardContent>
          </Card>
        </Link>
        <Link href="/hitl" className="no-underline">
          <Card className="hover:border-[oklch(0.5_0.15_220)]/40 transition-colors cursor-pointer">
            <CardContent className="p-4 flex items-center gap-3">
              <ShieldCheck size={18} style={{ color: "oklch(0.65 0.15 220)" }} />
              <div>
                <p className="text-sm font-medium">HITL Queue</p>
                <p className="text-xs" style={{ color: "var(--tx3)" }}>Human review</p>
              </div>
              <ChevronRight size={14} className="ml-auto" style={{ color: "var(--tx4)" }} />
            </CardContent>
          </Card>
        </Link>
      </div>

      <Card>
        <CardHeader style={{ paddingBottom: 12 }}>
          <div className="flex items-center justify-between">
            <CardTitle className="text-sm flex items-center gap-2">
              <Activity size={15} style={{ color: "oklch(0.65 0.18 145)" }} />
              Health Score Heatmap
            </CardTitle>
            <div className="flex gap-3 text-xs" style={{ fontFamily: "var(--fM)" }}>
              <span style={{ color: "oklch(0.65 0.18 145)" }}>● {healthy} healthy</span>
              <span style={{ color: "oklch(0.7 0.15 85)" }}>● {warning} warning</span>
              <span style={{ color: "oklch(0.65 0.18 25)" }}>● {critical} critical</span>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {scoresLoading ? (
            <div className="flex gap-2 flex-wrap">
              {HEATMAP_SKELETON_PLACEHOLDER_KEYS.map((id) => (
                <Skeleton key={id} className="h-16 w-20 rounded" />
              ))}
            </div>
          ) : (
            <div className="flex gap-2 flex-wrap">
              {scores?.map((s) => {
                const hostCode = typeof s.breakdown.host_code === "string"
                  ? s.breakdown.host_code
                  : s.entity_id.slice(0, 8);
                return (
                  <div
                    key={s.entity_id}
                    title={`${hostCode} — Score: ${s.score}/100 | CPU: ${s.breakdown.cpu_pct ?? "?"}% | MEM: ${s.breakdown.mem_pct ?? "?"}% | DISK: ${s.breakdown.disk_pct ?? "?"}%`}
                    style={{
                      minWidth: 76,
                      padding: "8px 10px",
                      borderRadius: 8,
                      display: "flex",
                      flexDirection: "column",
                      alignItems: "center",
                      gap: 2,
                      background: scoreBg(s.score),
                      border: `1px solid ${scoreColor(s.score)}33`,
                      cursor: "default",
                    }}
                  >
                    <span style={{ fontSize: 18, fontFamily: "var(--fD)", fontWeight: 700, color: scoreColor(s.score) }}>
                      {s.score}
                    </span>
                    <span style={{ fontSize: 10, fontFamily: "var(--fM)", color: "var(--tx3)" }}>
                      {hostCode}
                    </span>
                  </div>
                );
              })}
              {(!scores || scores.length === 0) && (
                <p className="text-sm" style={{ color: "var(--tx3)" }}>No health scores available yet.</p>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card>
          <CardHeader style={{ paddingBottom: 8 }}>
            <CardTitle className="text-sm flex items-center gap-2">
              <AlertTriangle size={15} style={{ color: "oklch(0.7 0.15 85)" }} />
              Active Insights
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-col gap-2">
              {(!insights || insights.length === 0) && (
                <p className="text-sm" style={{ color: "var(--tx3)" }}>No active insights.</p>
              )}
              {insights?.slice(0, 8).map((ins) => (
                <div key={ins.insight_id} className="rounded-md border border-border p-2.5 flex items-start gap-2.5">
                  <Badge className={`${severityColor(ins.severity)} text-[10px] px-1.5 py-0 shrink-0 mt-0.5`}>
                    {ins.severity}
                  </Badge>
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-medium leading-tight">{ins.title || ins.description.slice(0, 80)}</p>
                    {ins.entity_id && (
                      <p className="text-[10px] mt-0.5" style={{ fontFamily: "var(--fM)", color: "var(--tx4)" }}>
                        {ins.entity_type}: {ins.entity_id.slice(0, 12)}…
                      </p>
                    )}
                  </div>
                  <span className="text-[10px] shrink-0" style={{ fontFamily: "var(--fM)", color: "var(--tx4)" }}>
                    {ins.confidence ? `${(ins.confidence * 100).toFixed(0)}%` : ""}
                  </span>
                </div>
              ))}
              {insights && insights.length > 8 && (
                <Link href="/cognitive/insights" className="text-xs" style={{ color: "var(--in)" }}>
                  View all {insights.length} insights →
                </Link>
              )}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader style={{ paddingBottom: 8 }}>
            <CardTitle className="text-sm flex items-center gap-2">
              <Wrench size={15} style={{ color: "oklch(0.65 0.15 220)" }} />
              Self-Heal Log
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-col gap-2">
              {(!healHistory || healHistory.length === 0) && (
                <p className="text-sm" style={{ color: "var(--tx3)" }}>No self-healing actions recorded.</p>
              )}
              {healHistory?.slice(0, 8).map((a) => (
                <div key={a.action_id} className="rounded-md border border-border p-2.5 flex items-center gap-2.5">
                  <Badge className={`text-[10px] px-1.5 py-0 ${
                    a.status === "completed"
                      ? "bg-[oklch(0.25_0.08_145)] text-[oklch(0.65_0.18_145)]"
                      : "bg-(--sl3) text-(--tx3)"
                  }`}>
                    {a.status}
                  </Badge>
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-medium">{a.playbook_name}</p>
                    <p className="text-[10px]" style={{ color: "var(--tx3)" }}>{a.result_summary}</p>
                  </div>
                  {a.executed_at && (
                    <span className="text-[10px] shrink-0" style={{ fontFamily: "var(--fM)", color: "var(--tx4)" }}>
                      {timeAgo(a.executed_at)}
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

function HealthTab({ scores, isLoading }: Readonly<{ scores: HealthScoreOut[] | undefined; isLoading: boolean }>) {
  if (isLoading) return <Skeleton className="h-64 w-full" />;
  if (!scores || scores.length === 0) return <p className="text-sm" style={{ color: "var(--tx3)" }}>No health scores available.</p>;

  return (
    <Card>
      <CardContent className="p-0">
        <div className="overflow-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Host</TableHead>
                <TableHead>Score</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>CPU</TableHead>
                <TableHead>Memory</TableHead>
                <TableHead>Disk</TableHead>
                <TableHead>CPU Health</TableHead>
                <TableHead>Mem Health</TableHead>
                <TableHead>Disk Health</TableHead>
                <TableHead>Svc Health</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {scores.map((s) => {
                const b = s.breakdown;
                const cpuPct = Number(b.cpu_pct ?? 0);
                const memPct = Number(b.mem_pct ?? 0);
                const diskPct = Number(b.disk_pct ?? 0);
                return (
                  <TableRow key={s.entity_id}>
                    <TableCell className="text-xs font-medium" style={{ fontFamily: "var(--fM)" }}>
                      <div className="flex items-center gap-1.5">
                        <Server size={12} style={{ color: "var(--tx3)" }} />
                        {String(b.host_code || s.entity_id.slice(0, 8))}
                      </div>
                    </TableCell>
                    <TableCell>
                      <span className="text-sm font-bold" style={{ fontFamily: "var(--fD)", color: scoreColor(s.score) }}>
                        {s.score}
                      </span>
                    </TableCell>
                    <TableCell>
                      <Badge className={`text-[10px] px-1.5 py-0 ${healthStatusBadgeClass(s.status)}`}>
                        {s.status}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-xs" style={{ fontFamily: "var(--fM)" }}>
                      <div className="flex items-center gap-1.5 min-w-20">
                        <Progress value={cpuPct} className="flex-1 h-1.5" />
                        <span style={{ color: cpuPct > 85 ? "oklch(0.65 0.18 25)" : "var(--tx3)" }}>{cpuPct.toFixed(1)}%</span>
                      </div>
                    </TableCell>
                    <TableCell className="text-xs" style={{ fontFamily: "var(--fM)" }}>
                      <div className="flex items-center gap-1.5 min-w-20">
                        <Progress value={memPct} className="flex-1 h-1.5" />
                        <span style={{ color: memPct > 85 ? "oklch(0.65 0.18 25)" : "var(--tx3)" }}>{memPct.toFixed(1)}%</span>
                      </div>
                    </TableCell>
                    <TableCell className="text-xs" style={{ fontFamily: "var(--fM)" }}>
                      <div className="flex items-center gap-1.5 min-w-20">
                        <Progress value={diskPct} className="flex-1 h-1.5" />
                        <span style={{ color: diskPct > 80 ? "oklch(0.65 0.18 25)" : "var(--tx3)" }}>{diskPct.toFixed(0)}%</span>
                      </div>
                    </TableCell>
                    <TableCell className="text-xs" style={{ fontFamily: "var(--fM)", color: "var(--tx3)" }}>
                      {String(b.cpu_health ?? "—")}/25
                    </TableCell>
                    <TableCell className="text-xs" style={{ fontFamily: "var(--fM)", color: "var(--tx3)" }}>
                      {String(b.memory_health ?? "—")}/25
                    </TableCell>
                    <TableCell className="text-xs" style={{ fontFamily: "var(--fM)", color: "var(--tx3)" }}>
                      {String(b.disk_health ?? "—")}/25
                    </TableCell>
                    <TableCell className="text-xs" style={{ fontFamily: "var(--fM)", color: "var(--tx3)" }}>
                      {String(b.service_health ?? "—")}/25
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      </CardContent>
    </Card>
  );
}

function InsightsTab({ insights }: Readonly<{ insights: InsightOut[] | undefined }>) {
  if (!insights || insights.length === 0) {
    return <p className="text-sm" style={{ color: "var(--tx3)" }}>No active insights.</p>;
  }

  const byCategory: Record<string, InsightOut[]> = {};
  for (const ins of insights) {
    const cat = ins.category || "general";
    if (!byCategory[cat]) byCategory[cat] = [];
    byCategory[cat].push(ins);
  }

  return (
    <div className="flex flex-col gap-4">
      {Object.entries(byCategory).map(([cat, items]) => (
        <Card key={cat}>
          <CardHeader style={{ paddingBottom: 8 }}>
            <CardTitle className="text-sm capitalize">{cat} ({items.length})</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-2">
            {items.map((ins) => (
              <div key={ins.insight_id} className="rounded-md border border-border p-3 flex items-start gap-3">
                <Badge className={`${severityColor(ins.severity)} text-[10px] px-1.5 py-0 shrink-0 mt-0.5`}>
                  {ins.severity}
                </Badge>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium leading-tight">{ins.title}</p>
                  <p className="text-xs mt-1" style={{ color: "var(--tx3)" }}>{ins.description}</p>
                  {ins.entity_id && (
                    <p className="text-[10px] mt-0.5" style={{ fontFamily: "var(--fM)", color: "var(--tx4)" }}>
                      {ins.entity_type}: {ins.entity_id}
                    </p>
                  )}
                </div>
                <span className="text-[10px] shrink-0" style={{ fontFamily: "var(--fM)", color: "var(--tx4)" }}>
                  {ins.confidence ? `${(ins.confidence * 100).toFixed(0)}% conf.` : ""}
                </span>
              </div>
            ))}
          </CardContent>
        </Card>
      ))}
    </div>
  );
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
    queryFn: () => getInsights("status=active&page_size=50"),
    refetchInterval: REFRESH_INTERVAL,
    staleTime: 10_000,
  });

  const { data: healHistory } = useQuery<SelfHealActionOut[]>({
    queryKey: ["cognitive", "self-heal-history"],
    queryFn: () => getSelfHealHistory("page_size=20"),
    refetchInterval: REFRESH_INTERVAL,
    staleTime: 10_000,
  });

  const { secsLeft, progress, lastRefreshed } = useRefreshCountdown(dataUpdatedAt, REFRESH_INTERVAL);

  return (
    <div className="page-in" style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
        <div>
          <h1 className="df-page-title" style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <Brain size={22} style={{ color: "oklch(0.65 0.15 290)" }} />
            Cognitive Dashboard
          </h1>
          <p className="df-page-sub">
            AI-powered infrastructure intelligence
            {lastRefreshed && (
              <span style={{ fontFamily: "var(--fM)", fontSize: 11, color: "var(--tx4)", marginLeft: 8 }}>
                · ↻ {fmtTime(lastRefreshed)}
              </span>
            )}
          </p>
        </div>
        <div className="flex items-center gap-2.5 flex-wrap">
          <div className="flex items-center gap-3 text-xs" style={{ fontFamily: "var(--fM)", color: "var(--tx3)" }}>
            <span className="flex items-center gap-1"><Server size={12} /> {scores?.length ?? 0} hosts</span>
            <span className="flex items-center gap-1"><AlertTriangle size={12} /> {insights?.length ?? 0} insights</span>
          </div>
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
          <Button variant="outline" size="sm"
            onClick={() => queryClient.invalidateQueries({ queryKey: ["cognitive"] })}>
            <RefreshCw size={13} /> Refresh
          </Button>
        </div>
      </div>

      <Tabs defaultValue="overview">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="health">Health Scores</TabsTrigger>
          <TabsTrigger value="insights">Insights ({insights?.length ?? 0})</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="mt-4">
          <OverviewTab scores={scores} scoresLoading={scoresLoading} insights={insights} healHistory={healHistory} />
        </TabsContent>

        <TabsContent value="health" className="mt-4">
          <HealthTab scores={scores} isLoading={scoresLoading} />
        </TabsContent>

        <TabsContent value="insights" className="mt-4">
          <InsightsTab insights={insights} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
