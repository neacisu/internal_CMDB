"use client";

import { useState, type ReactNode } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getHITLQueue,
  getHITLStats,
  getHITLHistory,
  approveHITLItem,
  rejectHITLItem,
  bulkApproveHITL,
  bulkRejectHITL,
  type HITLItem,
  type HITLStats,
} from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  ShieldCheck,
  CheckCircle,
  XCircle,
  Clock,
  RefreshCw,
  ArrowUpCircle,
  Target,
  BarChart3,
  ChevronDown,
  Brain,
} from "lucide-react";
import { useRefreshCountdown, fmtTime } from "@/lib/hooks";
import { timeAgo } from "@/lib/utils";

const REFRESH_INTERVAL = 6_000;

const HITL_KPI_SKELETON_KEYS = [
  "hitl-kpi-sk-a",
  "hitl-kpi-sk-b",
  "hitl-kpi-sk-c",
  "hitl-kpi-sk-d",
  "hitl-kpi-sk-e",
] as const;

const HITL_QUEUE_ROW_SKELETON_KEYS = [
  "hitl-queue-row-sk-a",
  "hitl-queue-row-sk-b",
  "hitl-queue-row-sk-c",
  "hitl-queue-row-sk-d",
  "hitl-queue-row-sk-e",
] as const;

function priorityBadge(p: string) {
  const map: Record<string, string> = {
    critical: "bg-(--er) text-white",
    high: "bg-(--wa) text-white",
    medium: "bg-(--in)/20 text-(--in)",
    low: "bg-(--sl3) text-(--tx3)",
  };
  return map[p] ?? "bg-(--sl3) text-(--tx3)";
}

function riskBadge(rc: string) {
  if (rc === "RC-4" || rc === "RC-5") return "bg-(--er)/15 text-(--er) border-(--er)/30";
  if (rc === "RC-3") return "bg-(--wa)/15 text-(--wa) border-(--wa)/30";
  return "bg-(--sl3) text-(--tx3)";
}

export default function HITLPage() {
  const queryClient = useQueryClient();
  const [page] = useState(1);
  const [expandedItems, setExpandedItems] = useState<Set<string>>(new Set());
  const [selectedItems, setSelectedItems] = useState<Set<string>>(new Set());

  const toggleExpand = (id: string) => {
    setExpandedItems((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const toggleSelect = (id: string) => {
    setSelectedItems((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (!queue) return;
    setSelectedItems((prev) =>
      prev.size === queue.length ? new Set() : new Set(queue.map((i) => i.item_id)),
    );
  };

  const { data: queue, isLoading, dataUpdatedAt } = useQuery<HITLItem[]>({
    queryKey: ["hitl", "queue", page],
    queryFn: () => getHITLQueue(`status=pending&page=${page}&page_size=50`),
    refetchInterval: REFRESH_INTERVAL,
    staleTime: 4_000,
  });

  const { data: stats } = useQuery<HITLStats>({
    queryKey: ["hitl", "stats"],
    queryFn: getHITLStats,
    refetchInterval: REFRESH_INTERVAL,
    staleTime: 4_000,
  });

  const { data: history } = useQuery<HITLItem[]>({
    queryKey: ["hitl", "history"],
    queryFn: () => getHITLHistory("page_size=20"),
    refetchInterval: 30_000,
    staleTime: 20_000,
  });

  const { secsLeft, progress, lastRefreshed } = useRefreshCountdown(dataUpdatedAt, REFRESH_INTERVAL);

  const approveMut = useMutation({
    mutationFn: (id: string) => approveHITLItem(id, "operator", "Approved via UI"),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["hitl"] });
    },
  });

  const rejectMut = useMutation({
    mutationFn: (id: string) => rejectHITLItem(id, "operator", "Rejected via UI"),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["hitl"] });
    },
  });

  const bulkApproveMut = useMutation({
    mutationFn: (ids: string[]) => bulkApproveHITL(ids, "operator", "Bulk approved via UI"),
    onSuccess: () => {
      setSelectedItems(new Set());
      queryClient.invalidateQueries({ queryKey: ["hitl"] });
    },
  });

  const bulkRejectMut = useMutation({
    mutationFn: (ids: string[]) => bulkRejectHITL(ids, "operator", "Bulk rejected via UI"),
    onSuccess: () => {
      setSelectedItems(new Set());
      queryClient.invalidateQueries({ queryKey: ["hitl"] });
    },
  });

  let queueTabBody: ReactNode;
  if (isLoading) {
    queueTabBody = (
      <div className="space-y-2">
        {HITL_QUEUE_ROW_SKELETON_KEYS.map((skKey) => (
          <Skeleton key={skKey} className="h-14 w-full" />
        ))}
      </div>
    );
  } else if (queue?.length === 0) {
    queueTabBody = (
      <Card>
        <CardContent className="p-12 text-center">
          <CheckCircle size={40} className="mx-auto text-(--ok) mb-3" />
          <p className="text-sm font-medium">All clear</p>
          <p className="text-xs text-(--tx3)">No pending items in the HITL queue.</p>
        </CardContent>
      </Card>
    );
  } else {
    queueTabBody = (
      <div className="space-y-3">
        {/* Bulk action bar */}
        {selectedItems.size > 0 && (
          <div className="flex items-center gap-3 p-2 rounded-md bg-(--sl2) border border-border/50">
            <span className="text-xs text-(--tx3)">
              {selectedItems.size} selected
            </span>
            <Button
              size="sm"
              variant="outline"
              className="h-7 text-xs border-(--ok)/40 text-(--ok) hover:bg-(--ok)/10"
              onClick={() => bulkApproveMut.mutate([...selectedItems])}
              disabled={bulkApproveMut.isPending}
            >
              <CheckCircle size={12} className="mr-1" />
              Approve All
            </Button>
            <Button
              size="sm"
              variant="outline"
              className="h-7 text-xs border-(--er)/40 text-(--er) hover:bg-(--er)/10"
              onClick={() => bulkRejectMut.mutate([...selectedItems])}
              disabled={bulkRejectMut.isPending}
            >
              <XCircle size={12} className="mr-1" />
              Reject All
            </Button>
            <Button
              size="sm"
              variant="ghost"
              className="h-7 text-xs"
              onClick={() => setSelectedItems(new Set())}
            >
              Clear
            </Button>
          </div>
        )}
        {/* Select all toggle */}
        {queue && queue.length > 1 && (
          <label className="flex items-center gap-2 text-xs text-(--tx3) cursor-pointer select-none">
            <input
              type="checkbox"
              checked={selectedItems.size === queue.length}
              onChange={toggleSelectAll}
              className="rounded border-border"
            />
            Select all ({queue.length})
          </label>
        )}
        {queue?.map((item) => (
          <Card key={item.item_id} className="hover:border-(--ac1)/30 transition-colors">
            <CardContent className="p-4">
              <div className="flex items-center gap-4">
              <input
                type="checkbox"
                checked={selectedItems.has(item.item_id)}
                onChange={() => toggleSelect(item.item_id)}
                className="rounded border-border shrink-0"
              />
              <div className="flex gap-2 shrink-0">
                <Badge className={`${priorityBadge(item.priority)} text-xs px-1.5 py-0`}>
                  {item.priority}
                </Badge>
                <Badge className={`${riskBadge(item.risk_class)} text-xs px-1.5 py-0`}>
                  {item.risk_class}
                </Badge>
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium">
                  {item.item_type}
                  <span className="text-(--tx3) font-normal ml-2" style={{ fontFamily: "var(--fM)", fontSize: 12 }}>
                    {item.item_id.slice(0, 8)}…
                  </span>
                </p>
                {item.llm_confidence != null && (
                  <p className="text-xs text-(--tx3)">
                    LLM confidence: {(item.llm_confidence * 100).toFixed(0)}%
                    {item.llm_model_used && ` · ${item.llm_model_used}`}
                  </p>
                )}
              </div>
              {item.expires_at && (
                <div className="text-right shrink-0">
                  <p className="text-xs text-(--tx3)" style={{ fontFamily: "var(--fM)" }}>
                    Expires {timeAgo(item.expires_at)}
                  </p>
                </div>
              )}
              {(item.llm_suggestion || item.context_jsonb) && (
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-7 w-7 p-0 shrink-0"
                  onClick={() => toggleExpand(item.item_id)}
                >
                  <ChevronDown
                    size={14}
                    className={`transition-transform ${expandedItems.has(item.item_id) ? "rotate-180" : ""}`}
                  />
                </Button>
              )}
              <div className="flex gap-1 shrink-0">
                <Button
                  size="sm"
                  variant="outline"
                  className="h-8 text-xs border-(--ok)/40 text-(--ok) hover:bg-(--ok)/10"
                  onClick={() => approveMut.mutate(item.item_id)}
                  disabled={approveMut.isPending}
                >
                  <CheckCircle size={12} className="mr-1" />
                  Approve
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  className="h-8 text-xs border-(--er)/40 text-(--er) hover:bg-(--er)/10"
                  onClick={() => rejectMut.mutate(item.item_id)}
                  disabled={rejectMut.isPending}
                >
                  <XCircle size={12} className="mr-1" />
                  Reject
                </Button>
              </div>
              </div>

              {/* Expandable LLM context panel */}
              {expandedItems.has(item.item_id) && (
                <div className="mt-3 pt-3 border-t border-border/50 space-y-2">
                  {item.llm_suggestion && (
                    <div className="rounded-md bg-(--sl2) p-3 border border-border/50">
                      <p className="text-xs font-medium flex items-center gap-1 mb-1.5 text-(--tx2)">
                        <Brain size={12} style={{ color: "var(--pu)" }} />
                        LLM Suggestion
                      </p>
                      <pre className="text-xs text-(--tx3) whitespace-pre-wrap" style={{ fontFamily: "var(--fM)" }}>
                        {JSON.stringify(item.llm_suggestion, null, 2)}
                      </pre>
                    </div>
                  )}
                  {item.context_jsonb && (
                    <div className="rounded-md bg-(--sl2) p-3 border border-border/50">
                      <p className="text-xs font-medium mb-1.5 text-(--tx2)">Evidence / Context</p>
                      <pre className="text-xs text-(--tx3) whitespace-pre-wrap max-h-48 overflow-auto" style={{ fontFamily: "var(--fM)" }}>
                        {JSON.stringify(item.context_jsonb, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        ))}
      </div>
    );
  }

  return (
    <div className="page-in" style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
        <div>
          <h1 className="df-page-title" style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <ShieldCheck size={22} style={{ color: "var(--in)" }} />
            HITL Command Center
          </h1>
          <p className="df-page-sub">
            Human-in-the-loop review queue
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
            onClick={() => queryClient.invalidateQueries({ queryKey: ["hitl"] })}
          >
            <RefreshCw size={13} />
            Refresh
          </Button>
        </div>
      </div>

      {/* KPI strip */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        {stats ? (
          <>
            <Card>
              <CardContent className="p-3 text-center">
                <Clock size={16} className="mx-auto mb-1" style={{ color: "var(--wa)" }} />
                <p className="text-2xl font-bold">{stats.pending_count}</p>
                <p className="text-xs text-(--tx3)">Pending</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-3 text-center">
                <ArrowUpCircle size={16} className="mx-auto mb-1" style={{ color: "var(--er)" }} />
                <p className="text-2xl font-bold">{stats.escalated_count}</p>
                <p className="text-xs text-(--tx3)">Escalated</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-3 text-center">
                <CheckCircle size={16} className="mx-auto mb-1" style={{ color: "var(--ok)" }} />
                <p className="text-2xl font-bold">{stats.approved_count}</p>
                <p className="text-xs text-(--tx3)">Approved</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-3 text-center">
                <XCircle size={16} className="mx-auto mb-1" style={{ color: "var(--er)" }} />
                <p className="text-2xl font-bold">{stats.rejected_count}</p>
                <p className="text-xs text-(--tx3)">Rejected</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-3 text-center">
                <Target size={16} className="mx-auto mb-1" style={{ color: "var(--pu)" }} />
                <p className="text-2xl font-bold">
                  {stats.accuracy == null ? "—" : `${(stats.accuracy * 100).toFixed(0)}%`}
                </p>
                <p className="text-xs text-(--tx3)">Accuracy</p>
              </CardContent>
            </Card>
          </>
        ) : (
          HITL_KPI_SKELETON_KEYS.map((skKey) => <Skeleton key={skKey} className="h-20 w-full" />)
        )}
      </div>

      {/* Tabs: Queue / History */}
      <Tabs defaultValue="queue">
        <TabsList>
          <TabsTrigger value="queue">
            Pending Queue
            {queue && queue.length > 0 && (
              <Badge className="ml-1.5 text-[10px] h-4 px-1 bg-(--wa)/20 text-(--wa)">
                {queue.length}
              </Badge>
            )}
          </TabsTrigger>
          <TabsTrigger value="history">
            <BarChart3 size={13} className="mr-1" />
            Decision History
          </TabsTrigger>
        </TabsList>

        <TabsContent value="queue" className="mt-4">
          {queueTabBody}
        </TabsContent>

        <TabsContent value="history" className="mt-4">
          <div className="overflow-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Type</TableHead>
                  <TableHead>Risk</TableHead>
                  <TableHead>Priority</TableHead>
                  <TableHead>Decision</TableHead>
                  <TableHead>Decided By</TableHead>
                  <TableHead>Reason</TableHead>
                  <TableHead className="text-right">When</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {history?.map((item) => (
                  <TableRow key={item.item_id}>
                    <TableCell className="text-sm">{item.item_type}</TableCell>
                    <TableCell>
                      <Badge className={`${riskBadge(item.risk_class)} text-xs px-1 py-0`}>
                        {item.risk_class}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Badge className={`${priorityBadge(item.priority)} text-xs px-1 py-0`}>
                        {item.priority}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Badge
                        className={`text-xs px-1.5 py-0 ${
                          item.decision === "approved"
                            ? "bg-(--ok)/15 text-(--ok)"
                            : "bg-(--er)/15 text-(--er)"
                        }`}
                      >
                        {item.decision ?? item.status}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-sm text-(--tx3)">{item.decided_by ?? "—"}</TableCell>
                    <TableCell className="text-xs text-(--tx3) max-w-40 truncate">
                      {item.decision_reason ?? "—"}
                    </TableCell>
                    <TableCell className="text-right text-xs text-(--tx3)" style={{ fontFamily: "var(--fM)" }}>
                      {item.decided_at ? timeAgo(item.decided_at) : "—"}
                    </TableCell>
                  </TableRow>
                ))}
                {(!history || history.length === 0) && (
                  <TableRow>
                    <TableCell colSpan={7} className="text-center text-sm text-(--tx3) py-8">
                      No decision history yet.
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
