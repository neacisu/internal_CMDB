"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  ScrollText, Search, RefreshCw, ChevronLeft, ChevronRight,
  Shield, AlertTriangle, Activity, Clock, Zap, BarChart3, Database,
} from "lucide-react";
import { useRefreshCountdown, fmtTime } from "@/lib/hooks";
import { timeAgo } from "@/lib/utils";

const BASE = "/api/v1";

interface AuditEvent {
  event_id: string;
  event_type: string;
  actor: string | null;
  action: string;
  target_entity: string | null;
  correlation_id: string | null;
  duration_ms: number | null;
  status: string | null;
  ip_address: string | null;
  risk_level: string | null;
  created_at: string;
}

interface AuditEventsResponse {
  items: AuditEvent[];
  meta: { page: number; page_size: number; total: number };
}

interface StatusBreakdown { status: string; count: number }
interface ActorBreakdown { actor: string; count: number }
interface EndpointBreakdown { path: string; count: number }

interface AuditStats {
  total_events: number;
  total_changelogs: number;
  total_policies: number;
  total_approvals: number;
  error_count: number;
  avg_duration_ms: number | null;
  status_breakdown: StatusBreakdown[];
  actor_breakdown: ActorBreakdown[];
  endpoint_breakdown: EndpointBreakdown[];
  latest_event_at: string | null;
}

async function fetchEvents(params: string): Promise<AuditEventsResponse> {
  const res = await fetch(`${BASE}/audit/events?${params}`, {
    headers: { "Content-Type": "application/json" },
  });
  if (!res.ok) return { items: [], meta: { page: 1, page_size: 50, total: 0 } };
  return res.json();
}

async function fetchStats(): Promise<AuditStats> {
  const res = await fetch(`${BASE}/audit/stats`, {
    headers: { "Content-Type": "application/json" },
  });
  if (!res.ok) throw new Error("Failed to load stats");
  return res.json();
}

const REFRESH_INTERVAL = 15_000;

const STATS_TAB_SKELETON_KEYS = [
  "stats-sk-total-events",
  "stats-sk-errors",
  "stats-sk-avg-duration",
  "stats-sk-changelogs",
  "stats-sk-policies",
  "stats-sk-approvals",
  "stats-sk-status-codes",
  "stats-sk-unique-actors",
] as const;

const EVENTS_TABLE_SKELETON_ROW_KEYS = [
  "ev-sk-r1", "ev-sk-r2", "ev-sk-r3", "ev-sk-r4", "ev-sk-r5",
  "ev-sk-r6", "ev-sk-r7", "ev-sk-r8", "ev-sk-r9", "ev-sk-r10",
] as const;

const EVENTS_TABLE_SKELETON_COL_KEYS = [
  "ev-sk-time",
  "ev-sk-actor",
  "ev-sk-action",
  "ev-sk-status",
  "ev-sk-duration",
  "ev-sk-ip",
] as const;

function statusColor(s: string | null): string {
  if (!s) return "";
  const code = Number.parseInt(s, 10);
  if (code >= 200 && code < 300) return "bg-[oklch(0.35_0.12_145)]/20 text-[oklch(0.65_0.15_145)]";
  if (code >= 300 && code < 400) return "bg-[oklch(0.35_0.1_220)]/20 text-[oklch(0.65_0.1_220)]";
  if (code >= 400) return "bg-[oklch(0.35_0.12_25)]/20 text-[oklch(0.65_0.15_25)]";
  return "";
}

function KpiCard({ label, value, icon: Icon, sub }: Readonly<{
  label: string; value: string | number; icon: React.ElementType; sub?: string;
}>) {
  return (
    <Card>
      <CardContent className="flex items-center gap-3 py-3 px-4">
        <div className="flex items-center justify-center w-9 h-9 rounded-lg" style={{ background: "var(--sl4)" }}>
          <Icon size={17} style={{ color: "var(--tx3)" }} />
        </div>
        <div className="flex flex-col min-w-0">
          <span className="text-[22px] font-bold leading-none" style={{ fontFamily: "var(--fD)" }}>{value}</span>
          <span className="text-[11px] mt-0.5" style={{ color: "var(--tx3)" }}>{label}</span>
          {sub && <span className="text-[10px] truncate" style={{ color: "var(--tx4)", fontFamily: "var(--fM)" }}>{sub}</span>}
        </div>
      </CardContent>
    </Card>
  );
}

function StatsTab() {
  const { data: stats, isLoading } = useQuery<AuditStats>({
    queryKey: ["audit-stats"],
    queryFn: fetchStats,
    refetchInterval: 30_000,
  });

  if (isLoading) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {STATS_TAB_SKELETON_KEYS.map((skKey) => (
          <Skeleton key={skKey} className="h-20 w-full" />
        ))}
      </div>
    );
  }
  if (!stats) return null;

  const maxEndpoint = stats.endpoint_breakdown.length > 0 ? stats.endpoint_breakdown[0].count : 1;

  return (
    <div className="flex flex-col gap-5">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <KpiCard icon={Activity} label="Total Events" value={stats.total_events.toLocaleString()}
          sub={stats.latest_event_at ? `last: ${timeAgo(stats.latest_event_at)}` : undefined} />
        <KpiCard icon={AlertTriangle} label="Errors (4xx/5xx)" value={stats.error_count.toLocaleString()} />
        <KpiCard icon={Zap} label="Avg Duration" value={stats.avg_duration_ms ? `${stats.avg_duration_ms}ms` : "—"} />
        <KpiCard icon={Database} label="Changelogs" value={stats.total_changelogs} />
        <KpiCard icon={Shield} label="Policies" value={stats.total_policies} />
        <KpiCard icon={ScrollText} label="Approvals" value={stats.total_approvals} />
        <KpiCard icon={BarChart3} label="Status Codes" value={stats.status_breakdown.length} />
        <KpiCard icon={Clock} label="Unique Actors" value={stats.actor_breakdown.length} />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">HTTP Status Distribution</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-2">
            {stats.status_breakdown.map((s) => (
              <div key={s.status} className="flex items-center justify-between">
                <Badge className={`${statusColor(s.status)} text-xs`}>{s.status}</Badge>
                <span className="text-xs" style={{ fontFamily: "var(--fM)" }}>{s.count.toLocaleString()}</span>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Top Actors</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-2">
            {stats.actor_breakdown.map((a) => (
              <div key={a.actor} className="flex items-center justify-between">
                <span className="text-xs truncate max-w-[180px]" style={{ fontFamily: "var(--fM)" }}>{a.actor ?? "anonymous"}</span>
                <span className="text-xs" style={{ fontFamily: "var(--fM)" }}>{a.count.toLocaleString()}</span>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Top Endpoints</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-2">
          {stats.endpoint_breakdown.slice(0, 12).map((e) => (
            <div key={e.path} className="flex items-center gap-2">
              <span className="text-xs w-56 truncate" style={{ fontFamily: "var(--fM)", color: "var(--tx3)" }}>{e.path}</span>
              <div className="flex-1">
                <Progress value={(e.count / maxEndpoint) * 100} />
              </div>
              <span className="text-xs w-14 text-right" style={{ fontFamily: "var(--fM)" }}>{e.count.toLocaleString()}</span>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}

function EventsTab() {
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [page, setPage] = useState(1);
  const pageSize = 50;

  const params = [`page=${page}`, `page_size=${pageSize}`].join("&");
  const { data, isLoading, dataUpdatedAt } = useQuery<AuditEventsResponse>({
    queryKey: ["audit", "events", page],
    queryFn: () => fetchEvents(params),
    refetchInterval: REFRESH_INTERVAL,
    staleTime: 10_000,
  });

  const { secsLeft, progress, lastRefreshed } = useRefreshCountdown(dataUpdatedAt, REFRESH_INTERVAL);
  const total = data?.meta.total ?? 0;
  const totalPages = Math.ceil(total / pageSize);

  const filtered = data?.items.filter((e) => {
    if (statusFilter !== "all") {
      const code = Number.parseInt(e.status ?? "0", 10);
      if (statusFilter === "success" && (code < 200 || code >= 300)) return false;
      if (statusFilter === "error" && code < 400) return false;
    }
    if (!search) return true;
    const q = search.toLowerCase();
    return (
      (e.actor ?? "").toLowerCase().includes(q) ||
      (e.action ?? "").toLowerCase().includes(q) ||
      (e.target_entity ?? "").toLowerCase().includes(q) ||
      (e.ip_address ?? "").toLowerCase().includes(q)
    );
  });

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-2 flex-wrap">
        <div className="relative">
          <Search size={14} className="absolute left-2.5 top-2.5 text-(--tx3)" />
          <Input placeholder="Search actor, action, IP…" value={search}
            onChange={(ev) => setSearch(ev.target.value)} className="h-9 pl-8 w-56" />
        </div>
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="h-9 w-32">
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All</SelectItem>
            <SelectItem value="success">2xx OK</SelectItem>
            <SelectItem value="error">4xx/5xx</SelectItem>
          </SelectContent>
        </Select>
        <div className="countdown-pill ml-auto">
          <RefreshCw size={11} style={{ opacity: 0.55 }} />
          <span style={{ minWidth: 20, textAlign: "right" }}>{secsLeft}s</span>
          <div className="countdown-track">
            <div className="countdown-fill" style={{ transform: `scaleX(${progress})` }} />
          </div>
        </div>
        {lastRefreshed && (
          <span className="text-[10px]" style={{ color: "var(--tx4)", fontFamily: "var(--fM)" }}>
            {fmtTime(lastRefreshed)}
          </span>
        )}
      </div>

      <Card>
        <CardContent className="p-0">
          <div className="overflow-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-24">Time</TableHead>
                  <TableHead>Actor</TableHead>
                  <TableHead>Action</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Duration</TableHead>
                  <TableHead>IP</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {isLoading
                  ? EVENTS_TABLE_SKELETON_ROW_KEYS.map((rowKey) => (
                    <TableRow key={rowKey}>
                      {EVENTS_TABLE_SKELETON_COL_KEYS.map((colKey) => (
                        <TableCell key={`${rowKey}-${colKey}`}><Skeleton className="h-4 w-full" /></TableCell>
                      ))}
                    </TableRow>
                  ))
                  : filtered?.map((e) => (
                    <TableRow key={e.event_id}>
                      <TableCell className="text-xs whitespace-nowrap" style={{ fontFamily: "var(--fM)" }}>
                        {timeAgo(e.created_at)}
                      </TableCell>
                      <TableCell className="text-xs">{e.actor ?? "anonymous"}</TableCell>
                      <TableCell className="text-xs max-w-[260px] truncate" style={{ fontFamily: "var(--fM)" }}>
                        {e.action}
                      </TableCell>
                      <TableCell>
                        <Badge className={`${statusColor(e.status)} text-xs px-1.5 py-0`}>
                          {e.status ?? "—"}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-xs" style={{ fontFamily: "var(--fM)", color: "var(--tx3)" }}>
                        {e.duration_ms == null ? "—" : `${e.duration_ms}ms`}
                      </TableCell>
                      <TableCell className="text-xs" style={{ fontFamily: "var(--fM)", color: "var(--tx3)" }}>
                        {e.ip_address ?? "—"}
                      </TableCell>
                    </TableRow>
                  ))}
                {!isLoading && (!filtered || filtered.length === 0) && (
                  <TableRow>
                    <TableCell colSpan={6} className="text-center text-sm text-(--tx3) py-8">
                      No audit events match the current filters.
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      <div className="flex items-center justify-between text-sm">
        <span className="text-(--tx3)">{total.toLocaleString()} events &middot; page {page} / {totalPages || 1}</span>
        <div className="flex gap-1">
          <Button size="sm" variant="outline" disabled={page === 1} onClick={() => setPage((p) => p - 1)}>
            <ChevronLeft size={14} />
          </Button>
          <Button size="sm" variant="outline" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>
            <ChevronRight size={14} />
          </Button>
        </div>
      </div>
    </div>
  );
}

export default function AuditPage() {
  const { data: stats } = useQuery<AuditStats>({
    queryKey: ["audit-stats-header"],
    queryFn: fetchStats,
    refetchInterval: 30_000,
  });

  return (
    <div className="page-in" style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <div className="flex items-center justify-between">
        <div>
          <h1 className="df-page-title" style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <ScrollText size={22} style={{ color: "var(--in)" }} />
            Audit Trail
          </h1>
          <p className="df-page-sub">Full HTTP request audit log and governance trail</p>
        </div>
        <div className="flex items-center gap-3" style={{ fontFamily: "var(--fM)", fontSize: 12, color: "var(--tx3)" }}>
          {stats && (
            <>
              <span className="flex items-center gap-1">
                <Activity size={12} />
                {stats.total_events.toLocaleString()} events
              </span>
              <span className="flex items-center gap-1">
                <AlertTriangle size={12} />
                {stats.error_count} errors
              </span>
            </>
          )}
        </div>
      </div>

      <Tabs defaultValue="events">
        <TabsList>
          <TabsTrigger value="events">Events</TabsTrigger>
          <TabsTrigger value="stats">Statistics</TabsTrigger>
        </TabsList>

        <TabsContent value="events" className="mt-4">
          <EventsTab />
        </TabsContent>

        <TabsContent value="stats" className="mt-4">
          <StatsTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}
