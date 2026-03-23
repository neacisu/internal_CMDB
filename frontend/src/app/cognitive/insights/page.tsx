"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getInsights,
  ackInsight,
  dismissInsight,
  type InsightOut,
} from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  AlertTriangle,
  CheckCircle,
  XCircle,
  Search,
  RefreshCw,
  Eye,
  Shield,
} from "lucide-react";
import { useRefreshCountdown, fmtTime } from "@/lib/hooks";

const REFRESH_INTERVAL = 15_000;

/** Stable keys for loading skeletons — list is fixed length, never reordered (S6479). */
const INSIGHT_CARD_SKELETON_KEYS = [
  "insight-card-skel-a",
  "insight-card-skel-b",
  "insight-card-skel-c",
  "insight-card-skel-d",
  "insight-card-skel-e",
  "insight-card-skel-f",
] as const;

function severityIcon(s: string) {
  if (s === "critical") return <AlertTriangle size={14} style={{ color: "var(--er)" }} />;
  if (s === "warning") return <AlertTriangle size={14} style={{ color: "var(--wa)" }} />;
  return <Shield size={14} style={{ color: "var(--in)" }} />;
}

function severityBadge(s: string) {
  const colors: Record<string, string> = {
    critical: "bg-(--er) text-white",
    warning: "bg-(--wa) text-white",
    info: "bg-(--in)/20 text-(--in)",
  };
  return colors[s] ?? "bg-(--sl3) text-(--tx3)";
}

export default function InsightsPage() {
  const queryClient = useQueryClient();
  const [statusFilter, setStatusFilter] = useState("active");
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<InsightOut | null>(null);

  const { data: insights, isLoading, dataUpdatedAt } = useQuery<InsightOut[]>({
    queryKey: ["cognitive", "insights", statusFilter],
    queryFn: () => getInsights(`status=${statusFilter}&page_size=100`),
    refetchInterval: REFRESH_INTERVAL,
    staleTime: 10_000,
  });

  const { secsLeft, progress, lastRefreshed } = useRefreshCountdown(dataUpdatedAt, REFRESH_INTERVAL);

  const ackMutation = useMutation({
    mutationFn: (id: string) => ackInsight(id, "operator"),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["cognitive", "insights"] }),
  });

  const dismissMutation = useMutation({
    mutationFn: (id: string) => dismissInsight(id, "operator", "Manually dismissed"),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["cognitive", "insights"] }),
  });

  const filtered = insights?.filter(
    (ins) =>
      !search ||
      ins.title.toLowerCase().includes(search.toLowerCase()) ||
      ins.description.toLowerCase().includes(search.toLowerCase()) ||
      (ins.category ?? "").toLowerCase().includes(search.toLowerCase()),
  );

  const criticalCount = insights?.filter((i) => i.severity === "critical").length ?? 0;
  const warningCount = insights?.filter((i) => i.severity === "warning").length ?? 0;

  return (
    <div className="page-in" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
        <div>
          <h1 className="df-page-title" style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <AlertTriangle size={20} style={{ color: "var(--wa)" }} />
            Cognitive Insights
          </h1>
          <p className="df-page-sub">
            {insights?.length ?? 0} {statusFilter} insights
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
              placeholder="Filter insights…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="h-9 pl-8 w-48"
            />
          </div>
          <div className="flex gap-1">
            {["active", "acknowledged", "dismissed"].map((s) => (
              <Button
                key={s}
                size="sm"
                variant={statusFilter === s ? "default" : "outline"}
                onClick={() => setStatusFilter(s)}
              >
                {s}
              </Button>
            ))}
          </div>
          <div className="countdown-pill">
            <RefreshCw size={11} style={{ opacity: 0.55 }} />
            <span style={{ minWidth: 20, textAlign: "right" }}>{secsLeft}s</span>
            <div className="countdown-track">
              <div className="countdown-fill" style={{ transform: `scaleX(${progress})` }} />
            </div>
          </div>
        </div>
      </div>

      {/* Summary strip */}
      <div className="flex gap-3">
        <div className="rounded-md border border-border bg-(--sl2) px-3 py-2 text-center min-w-16">
          <p className="text-lg font-semibold">{insights?.length ?? 0}</p>
          <p className="text-xs text-(--tx3)">Total</p>
        </div>
        {criticalCount > 0 && (
          <div className="rounded-md border border-(--er)/30 bg-(--er)/10 px-3 py-2 text-center min-w-16">
            <p className="text-lg font-semibold text-(--er)">{criticalCount}</p>
            <p className="text-xs text-(--tx3)">Critical</p>
          </div>
        )}
        {warningCount > 0 && (
          <div className="rounded-md border border-(--wa)/30 bg-(--wa)/10 px-3 py-2 text-center min-w-16">
            <p className="text-lg font-semibold text-(--wa)">{warningCount}</p>
            <p className="text-xs text-(--tx3)">Warning</p>
          </div>
        )}
      </div>

      {/* Insight cards */}
      {isLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {INSIGHT_CARD_SKELETON_KEYS.map((skKey) => (
            <Skeleton key={skKey} className="h-40 w-full rounded-lg" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered?.map((ins) => (
            <Card
              key={ins.insight_id}
              className="hover:border-(--ac1)/40 transition-colors cursor-pointer"
              onClick={() => setSelected(ins)}
            >
              <CardHeader className="pb-2">
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-2 min-w-0">
                    {severityIcon(ins.severity)}
                    <CardTitle className="text-sm font-medium leading-tight truncate">
                      {ins.title || ins.description.slice(0, 60)}
                    </CardTitle>
                  </div>
                  <Badge className={`${severityBadge(ins.severity)} text-xs px-1.5 py-0 shrink-0`}>
                    {ins.severity}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent>
                <p className="text-xs text-(--tx3) leading-relaxed line-clamp-3 mb-3">
                  {ins.description}
                </p>
                <div className="flex items-center justify-between flex-wrap gap-2">
                  <div className="flex gap-1">
                    {ins.category && (
                      <Badge className="text-[10px] px-1.5 py-0 bg-(--sl3) text-(--tx3)">
                        {ins.category}
                      </Badge>
                    )}
                    {ins.entity_type && (
                      <Badge className="text-[10px] px-1.5 py-0 bg-(--sl3) text-(--tx3)">
                        {ins.entity_type}
                      </Badge>
                    )}
                  </div>
                  {statusFilter === "active" && (
                    <div className="flex gap-1">
                      <Button
                        size="sm"
                        variant="outline"
                        className="h-6 text-xs px-2"
                        onClick={(e) => {
                          e.stopPropagation();
                          ackMutation.mutate(ins.insight_id);
                        }}
                      >
                        <CheckCircle size={10} className="mr-0.5" />
                        Ack
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        className="h-6 text-xs px-2"
                        onClick={(e) => {
                          e.stopPropagation();
                          dismissMutation.mutate(ins.insight_id);
                        }}
                      >
                        <XCircle size={10} className="mr-0.5" />
                        Dismiss
                      </Button>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
          {filtered?.length === 0 && (
            <div className="col-span-full rounded-lg border border-dashed border-border p-12 text-center">
              <Eye size={32} className="mx-auto text-(--tx4) mb-3" />
              <p className="text-sm text-(--tx3)">No insights match the current filters.</p>
            </div>
          )}
        </div>
      )}

      {/* Detail dialog */}
      <Dialog open={!!selected} onOpenChange={(v) => !v && setSelected(null)}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              {selected && severityIcon(selected.severity)}
              {selected?.title || "Insight Detail"}
            </DialogTitle>
          </DialogHeader>
          {selected && (
            <div className="space-y-3 mt-2">
              <div className="flex gap-2 flex-wrap">
                <Badge className={`${severityBadge(selected.severity)} text-xs`}>{selected.severity}</Badge>
                {selected.category && (
                  <Badge className="bg-(--sl3) text-(--tx3) text-xs">{selected.category}</Badge>
                )}
                <Badge className="bg-(--sl3) text-(--tx3) text-xs">
                  {(selected.confidence * 100).toFixed(0)}% confidence
                </Badge>
              </div>
              <p className="text-sm leading-relaxed">{selected.description}</p>
              {selected.remediation && (
                <div className="rounded-md bg-(--ok)/10 border border-(--ok)/20 p-3">
                  <p className="text-xs font-medium text-(--ok) mb-1">Remediation</p>
                  <p className="text-sm">{selected.remediation}</p>
                </div>
              )}
              {selected.entity_id && (
                <p className="text-xs text-(--tx3)" style={{ fontFamily: "var(--fM)" }}>
                  Entity: {selected.entity_type} / {selected.entity_id}
                </p>
              )}
              {selected.created_at && (
                <p className="text-xs text-(--tx4)" style={{ fontFamily: "var(--fM)" }}>
                  Created: {new Date(selected.created_at).toLocaleString()}
                </p>
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
