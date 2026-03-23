"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  ScrollText,
  Search,
  RefreshCw,
  ChevronLeft,
  ChevronRight,
  Shield,
  AlertTriangle,
} from "lucide-react";
import { useRefreshCountdown, fmtTime } from "@/lib/hooks";
import { timeAgo } from "@/lib/utils";

const BASE = "/api/v1";

interface AuditEvent {
  event_id: string;
  event_type: string;
  actor: string;
  action: string;
  entity_type: string | null;
  entity_id: string | null;
  risk_level: string | null;
  status_code: number | null;
  method: string | null;
  path: string | null;
  ip_address: string | null;
  details: Record<string, unknown> | null;
  created_at: string;
}

async function fetchAuditEvents(params: string): Promise<AuditEvent[]> {
  const res = await fetch(`${BASE}/governance/changelog?${params}`, {
    headers: { "Content-Type": "application/json" },
  });
  if (!res.ok) return [];
  const data = await res.json();
  return (data.items ?? data) as AuditEvent[];
}

const REFRESH_INTERVAL = 15_000;

const AUDIT_TABLE_SKELETON_ROW_KEYS = [
  "audit-tbl-sk-r1",
  "audit-tbl-sk-r2",
  "audit-tbl-sk-r3",
  "audit-tbl-sk-r4",
  "audit-tbl-sk-r5",
  "audit-tbl-sk-r6",
  "audit-tbl-sk-r7",
  "audit-tbl-sk-r8",
  "audit-tbl-sk-r9",
  "audit-tbl-sk-r10",
] as const;

const AUDIT_TABLE_SKELETON_COLUMN_KEYS = [
  "time",
  "actor",
  "action",
  "entity",
  "risk",
  "status",
  "details",
] as const;

function riskColor(r: string | null) {
  if (r === "critical" || r === "high") return "bg-(--er)/15 text-(--er) border-(--er)/30";
  if (r === "medium") return "bg-(--wa)/15 text-(--wa) border-(--wa)/30";
  return "bg-(--sl3) text-(--tx3)";
}

export default function AuditPage() {
  const [search, setSearch] = useState("");
  const [riskFilter, setRiskFilter] = useState("all");
  const [page, setPage] = useState(1);
  const pageSize = 50;

  const params = [`page=${page}`, `page_size=${pageSize}`].join("&");

  const { data: events, isLoading, dataUpdatedAt } = useQuery<AuditEvent[]>({
    queryKey: ["audit", "events", page],
    queryFn: () => fetchAuditEvents(params),
    refetchInterval: REFRESH_INTERVAL,
    staleTime: 10_000,
  });

  const { secsLeft, progress, lastRefreshed } = useRefreshCountdown(dataUpdatedAt, REFRESH_INTERVAL);

  const filtered = events?.filter((e) => {
    if (riskFilter !== "all" && e.risk_level !== riskFilter) return false;
    if (!search) return true;
    const q = search.toLowerCase();
    return (
      (e.actor ?? "").toLowerCase().includes(q) ||
      (e.action ?? "").toLowerCase().includes(q) ||
      (e.entity_type ?? "").toLowerCase().includes(q) ||
      (e.entity_id ?? "").toLowerCase().includes(q) ||
      (e.event_type ?? "").toLowerCase().includes(q) ||
      (e.path ?? "").toLowerCase().includes(q)
    );
  });

  return (
    <div className="page-in" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
        <div>
          <h1 className="df-page-title" style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <ScrollText size={22} style={{ color: "var(--in)" }} />
            Audit Trail
          </h1>
          <p className="df-page-sub">
            Full governance and change audit log
            {lastRefreshed && (
              <span style={{ fontFamily: "var(--fM)", fontSize: 11, color: "var(--tx4)", marginLeft: 8 }}>
                · ↻ {fmtTime(lastRefreshed)}
              </span>
            )}
          </p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <div className="relative">
            <Search size={14} className="absolute left-2.5 top-2.5 text-(--tx3)" />
            <Input
              placeholder="Search actor, action, entity…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="h-9 pl-8 w-56"
            />
          </div>
          <Select value={riskFilter} onValueChange={setRiskFilter}>
            <SelectTrigger className="h-9 w-32">
              <SelectValue placeholder="Risk level" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All risks</SelectItem>
              <SelectItem value="critical">Critical</SelectItem>
              <SelectItem value="high">High</SelectItem>
              <SelectItem value="medium">Medium</SelectItem>
              <SelectItem value="low">Low</SelectItem>
            </SelectContent>
          </Select>
          <div className="countdown-pill">
            <RefreshCw size={11} style={{ opacity: 0.55 }} />
            <span style={{ minWidth: 20, textAlign: "right" }}>{secsLeft}s</span>
            <div className="countdown-track">
              <div className="countdown-fill" style={{ transform: `scaleX(${progress})` }} />
            </div>
          </div>
        </div>
      </div>

      {/* Table */}
      <Card>
        <CardContent className="p-0">
          <div className="overflow-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-32">Time</TableHead>
                  <TableHead>Actor</TableHead>
                  <TableHead>Action</TableHead>
                  <TableHead>Entity</TableHead>
                  <TableHead>Risk</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Details</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {isLoading
                  ? AUDIT_TABLE_SKELETON_ROW_KEYS.map((rowKey) => (
                      <TableRow key={rowKey}>
                        {AUDIT_TABLE_SKELETON_COLUMN_KEYS.map((colKey) => (
                          <TableCell key={`${rowKey}-${colKey}`}>
                            <Skeleton className="h-4 w-full" />
                          </TableCell>
                        ))}
                      </TableRow>
                    ))
                  : filtered?.map((e) => (
                      <TableRow key={e.event_id ?? e.created_at + e.action}>
                        <TableCell className="text-xs" style={{ fontFamily: "var(--fM)" }}>
                          {timeAgo(e.created_at)}
                        </TableCell>
                        <TableCell className="text-sm font-medium">{e.actor ?? "system"}</TableCell>
                        <TableCell className="text-sm">{e.action ?? e.event_type}</TableCell>
                        <TableCell className="text-xs text-(--tx3)" style={{ fontFamily: "var(--fM)" }}>
                          {e.entity_type ? `${e.entity_type}` : "—"}
                          {e.entity_id && (
                            <span className="ml-1">{String(e.entity_id).slice(0, 8)}…</span>
                          )}
                        </TableCell>
                        <TableCell>
                          {e.risk_level ? (
                            <Badge className={`${riskColor(e.risk_level)} text-xs px-1.5 py-0`}>
                              {e.risk_level === "critical" || e.risk_level === "high" ? (
                                <AlertTriangle size={9} className="mr-0.5" />
                              ) : (
                                <Shield size={9} className="mr-0.5" />
                              )}
                              {e.risk_level}
                            </Badge>
                          ) : (
                            <span className="text-xs text-(--tx4)">—</span>
                          )}
                        </TableCell>
                        <TableCell>
                          {e.status_code ? (
                            <Badge
                              className={`text-xs px-1 py-0 ${
                                e.status_code < 400
                                  ? "bg-(--ok)/15 text-(--ok)"
                                  : "bg-(--er)/15 text-(--er)"
                              }`}
                            >
                              {e.status_code}
                            </Badge>
                          ) : (
                            "—"
                          )}
                        </TableCell>
                        <TableCell className="text-xs text-(--tx3) max-w-40 truncate">
                          {e.method && e.path ? `${e.method} ${e.path}` : "—"}
                        </TableCell>
                      </TableRow>
                    ))}
                {!isLoading && (!filtered || filtered.length === 0) && (
                  <TableRow>
                    <TableCell colSpan={7} className="text-center text-sm text-(--tx3) py-8">
                      No audit events match the current filters.
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      {/* Pagination */}
      <div className="flex items-center justify-between text-sm">
        <span className="text-(--tx3)">
          {filtered?.length ?? 0} events · page {page}
        </span>
        <div className="flex gap-1">
          <Button
            size="sm"
            variant="outline"
            disabled={page === 1}
            onClick={() => setPage((p) => p - 1)}
          >
            <ChevronLeft size={14} />
          </Button>
          <Button
            size="sm"
            variant="outline"
            disabled={(events?.length ?? 0) < pageSize}
            onClick={() => setPage((p) => p + 1)}
          >
            <ChevronRight size={14} />
          </Button>
        </div>
      </div>
    </div>
  );
}
