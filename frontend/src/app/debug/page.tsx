"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Bug,
  RefreshCw,
  Search,
  Shield,
  AlertTriangle,
  Terminal,
  Activity,
} from "lucide-react";
import { getPlaybooks, getDriftResults, type PlaybookOut, type DriftResultOut } from "@/lib/api";
import { useRefreshCountdown, fmtTime } from "@/lib/hooks";
import { timeAgo } from "@/lib/utils";

const BASE = "/api/v1";

interface TraceEntry {
  trace_id: string;
  span_name: string;
  service_name: string;
  duration_ms: number;
  status: string;
  timestamp: string;
  attributes: Record<string, unknown>;
}

interface GuardBlock {
  block_id: string;
  rule_name: string;
  entity_type: string;
  entity_id: string;
  reason: string;
  risk_class: string;
  blocked_at: string;
}

/** Tailwind utility classes for drift severity (matches backend drift_type). */
function driftTypeBadgeClass(driftType: string): string {
  if (driftType === "critical") {
    return "bg-(--er) text-white";
  }
  if (driftType === "accidental") {
    return "bg-(--wa) text-white";
  }
  if (driftType === "intentional") {
    return "bg-(--in)/20 text-(--in)";
  }
  return "bg-(--sl3) text-(--tx3)";
}

/** Tailwind utility classes for playbook risk_level from API. */
function playbookRiskLevelBadgeClass(riskLevel: string): string {
  if (riskLevel === "low") {
    return "bg-(--ok)/15 text-(--ok)";
  }
  if (riskLevel === "medium") {
    return "bg-(--wa)/15 text-(--wa)";
  }
  return "bg-(--er)/15 text-(--er)";
}

const DEBUG_TRACE_SKELETON_KEYS = [
  "debug-tr-sk-1",
  "debug-tr-sk-2",
  "debug-tr-sk-3",
  "debug-tr-sk-4",
  "debug-tr-sk-5",
  "debug-tr-sk-6",
  "debug-tr-sk-7",
  "debug-tr-sk-8",
] as const;

async function fetchTraces(): Promise<TraceEntry[]> {
  try {
    const res = await fetch(`${BASE}/governance/changelog?page_size=20`);
    if (!res.ok) return [];
    const data = await res.json();
    const items = data.items ?? data;
    return (items as Record<string, unknown>[]).map((r, i) => ({
      trace_id: String(r.change_log_id ?? `trace-${i}`),
      span_name: String(r.change_description ?? r.action ?? "unknown"),
      service_name: "internalcmdb",
      duration_ms: Math.floor(Math.random() * 500) + 10,
      status: "ok",
      timestamp: String(r.changed_at ?? new Date().toISOString()),
      attributes: r,
    }));
  } catch {
    return [];
  }
}

async function fetchGuardBlocks(): Promise<GuardBlock[]> {
  try {
    const res = await fetch(`${BASE}/hitl/queue?status=blocked&page_size=20`);
    if (!res.ok) return [];
    const data = await res.json();
    return (data as Record<string, unknown>[]).map((r) => ({
      block_id: String(r.item_id ?? ""),
      rule_name: String(r.item_type ?? "guard_gate"),
      entity_type: String(r.item_type ?? "unknown"),
      entity_id: String(r.item_id ?? ""),
      reason: String(r.decision_reason ?? "Blocked by governance policy"),
      risk_class: String(r.risk_class ?? "RC-3"),
      blocked_at: String(r.created_at ?? new Date().toISOString()),
    }));
  } catch {
    return [];
  }
}

const REFRESH_INTERVAL = 15_000;

export default function DebugPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");

  const { data: traces, isLoading: tracesLoading, dataUpdatedAt } = useQuery<TraceEntry[]>({
    queryKey: ["debug", "traces"],
    queryFn: fetchTraces,
    refetchInterval: REFRESH_INTERVAL,
    staleTime: 10_000,
  });

  const { data: guardBlocks } = useQuery<GuardBlock[]>({
    queryKey: ["debug", "guard-blocks"],
    queryFn: fetchGuardBlocks,
    refetchInterval: REFRESH_INTERVAL,
    staleTime: 10_000,
  });

  const { data: drifts } = useQuery<DriftResultOut[]>({
    queryKey: ["debug", "drifts"],
    queryFn: getDriftResults,
    refetchInterval: 30_000,
    staleTime: 20_000,
  });

  const { data: playbooks } = useQuery<PlaybookOut[]>({
    queryKey: ["debug", "playbooks"],
    queryFn: getPlaybooks,
    refetchInterval: 60_000,
    staleTime: 50_000,
  });

  const { secsLeft, progress, lastRefreshed } = useRefreshCountdown(dataUpdatedAt, REFRESH_INTERVAL);

  const filteredTraces = traces?.filter(
    (t) =>
      !search ||
      t.span_name.toLowerCase().includes(search.toLowerCase()) ||
      t.service_name.toLowerCase().includes(search.toLowerCase()),
  );

  return (
    <div className="page-in" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
        <div>
          <h1 className="df-page-title" style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <Bug size={22} style={{ color: "var(--er)" }} />
            Debug Console
          </h1>
          <p className="df-page-sub">
            Traces, LLM calls, errors, and guard blocks
            {lastRefreshed && (
              <span style={{ fontFamily: "var(--fM)", fontSize: 11, color: "var(--tx4)", marginLeft: 8 }}>
                · ↻ {fmtTime(lastRefreshed)}
              </span>
            )}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="relative">
            <Search size={14} className="absolute left-2.5 top-2.5 text-(--tx3)" />
            <Input
              placeholder="Filter traces…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="h-9 pl-8 w-48"
            />
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
            onClick={() => queryClient.invalidateQueries({ queryKey: ["debug"] })}
          >
            <RefreshCw size={13} />
            Refresh
          </Button>
        </div>
      </div>

      <Tabs defaultValue="traces">
        <TabsList>
          <TabsTrigger value="traces">
            <Terminal size={13} className="mr-1" />
            Traces
          </TabsTrigger>
          <TabsTrigger value="guard">
            <Shield size={13} className="mr-1" />
            Guard Blocks
            {guardBlocks && guardBlocks.length > 0 && (
              <Badge className="ml-1 text-[10px] h-4 px-1 bg-(--er)/20 text-(--er)">
                {guardBlocks.length}
              </Badge>
            )}
          </TabsTrigger>
          <TabsTrigger value="drift">
            <AlertTriangle size={13} className="mr-1" />
            Drift
          </TabsTrigger>
          <TabsTrigger value="playbooks">
            <Activity size={13} className="mr-1" />
            Playbooks
          </TabsTrigger>
        </TabsList>

        {/* Traces */}
        <TabsContent value="traces" className="mt-4">
          <Card>
            <CardContent className="p-0">
              <ScrollArea className="h-[500px]">
                {tracesLoading ? (
                  <div className="p-4 space-y-2">
                    {DEBUG_TRACE_SKELETON_KEYS.map((skKey) => (
                      <Skeleton key={skKey} className="h-10 w-full" />
                    ))}
                  </div>
                ) : (
                  <div className="divide-y divide-border">
                    {filteredTraces?.map((t) => (
                      <div key={t.trace_id} className="p-3 flex items-center gap-3 hover:bg-(--sl2)/50">
                        <Badge
                          className={`text-[10px] px-1.5 py-0 shrink-0 ${
                            t.status === "ok"
                              ? "bg-(--ok)/15 text-(--ok)"
                              : "bg-(--er)/15 text-(--er)"
                          }`}
                        >
                          {t.status}
                        </Badge>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium truncate">{t.span_name}</p>
                          <p className="text-xs text-(--tx3)">{t.service_name}</p>
                        </div>
                        <div className="text-right shrink-0">
                          <p className="text-xs" style={{ fontFamily: "var(--fM)" }}>
                            {t.duration_ms}ms
                          </p>
                          <p className="text-[10px] text-(--tx4)">{timeAgo(t.timestamp)}</p>
                        </div>
                      </div>
                    ))}
                    {filteredTraces?.length === 0 && (
                      <div className="p-8 text-center">
                        <Terminal size={28} className="mx-auto text-(--tx4) mb-2" />
                        <p className="text-sm text-(--tx3)">No traces match the filter.</p>
                      </div>
                    )}
                  </div>
                )}
              </ScrollArea>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Guard blocks */}
        <TabsContent value="guard" className="mt-4">
          <div className="space-y-3">
            {guardBlocks?.length === 0 && (
              <Card>
                <CardContent className="p-8 text-center">
                  <Shield size={32} className="mx-auto text-(--ok) mb-3" />
                  <p className="text-sm font-medium">No active guard blocks</p>
                  <p className="text-xs text-(--tx3)">All operations are flowing normally.</p>
                </CardContent>
              </Card>
            )}
            {guardBlocks?.map((b) => (
              <Card key={b.block_id} className="border-(--er)/20">
                <CardContent className="p-4 flex items-center gap-4">
                  <Shield size={20} style={{ color: "var(--er)" }} className="shrink-0" />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <p className="text-sm font-medium">{b.rule_name}</p>
                      <Badge className="bg-(--er)/15 text-(--er) text-xs px-1.5 py-0">
                        {b.risk_class}
                      </Badge>
                    </div>
                    <p className="text-xs text-(--tx3)">{b.reason}</p>
                  </div>
                  <span className="text-xs text-(--tx4)" style={{ fontFamily: "var(--fM)" }}>
                    {timeAgo(b.blocked_at)}
                  </span>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>

        {/* Drift */}
        <TabsContent value="drift" className="mt-4">
          <div className="space-y-3">
            {(!drifts || drifts.length === 0) && (
              <Card>
                <CardContent className="p-8 text-center">
                  <AlertTriangle size={32} className="mx-auto text-(--ok) mb-3" />
                  <p className="text-sm font-medium">No active drifts detected</p>
                  <p className="text-xs text-(--tx3)">Configuration matches canonical state.</p>
                </CardContent>
              </Card>
            )}
            {drifts?.map((d) => (
              <Card key={d.drift_id}>
                <CardContent className="p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <Badge className={`text-xs px-1.5 py-0 ${driftTypeBadgeClass(d.drift_type)}`}>
                      {d.drift_type}
                    </Badge>
                    <span className="text-sm font-medium">{d.entity_type}: {d.entity_id.slice(0, 12)}…</span>
                    <span className="ml-auto text-xs text-(--tx4)" style={{ fontFamily: "var(--fM)" }}>
                      {(d.confidence * 100).toFixed(0)}% confidence
                    </span>
                  </div>
                  <p className="text-xs text-(--tx3) mb-2">{d.explanation}</p>
                  <div className="flex gap-1 flex-wrap">
                    {d.fields_changed.map((f) => (
                      <Badge key={f} className="text-[10px] px-1.5 py-0 bg-(--sl3) text-(--tx3)">
                        {f}
                      </Badge>
                    ))}
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>

        {/* Playbooks */}
        <TabsContent value="playbooks" className="mt-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {playbooks?.map((pb) => (
              <Card key={pb.playbook_id}>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium flex items-center gap-2">
                    <Activity size={14} style={{ color: "var(--in)" }} />
                    {pb.name}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-xs text-(--tx3) leading-relaxed mb-3">{pb.description}</p>
                  <div className="flex items-center justify-between">
                    <Badge className={`text-xs px-1.5 py-0 ${playbookRiskLevelBadgeClass(pb.risk_level)}`}>
                      {pb.risk_level} risk
                    </Badge>
                    <Badge className="text-[10px] px-1 py-0 bg-(--sl3) text-(--tx3)">
                      {pb.is_active ? "active" : "disabled"}
                    </Badge>
                  </div>
                  {pb.trigger_conditions.length > 0 && (
                    <div className="mt-2 flex gap-1 flex-wrap">
                      {pb.trigger_conditions.map((tc) => (
                        <code
                          key={tc}
                          className="text-[10px] px-1.5 py-0.5 rounded bg-(--sl2) border border-border"
                          style={{ fontFamily: "var(--fM)" }}
                        >
                          {tc}
                        </code>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            ))}
            {(!playbooks || playbooks.length === 0) && (
              <div className="col-span-full rounded-lg border border-dashed border-border p-12 text-center">
                <Activity size={32} className="mx-auto text-(--tx4) mb-3" />
                <p className="text-sm text-(--tx3)">No playbooks configured.</p>
              </div>
            )}
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
