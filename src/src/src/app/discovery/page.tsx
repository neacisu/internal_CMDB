"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  getDiscoveryStats,
  getDiscoverySources,
  getDiscoveryRuns,
  getDiscoveryFacts,
  getDiscoveryEvidence,
  type DiscoveryStats,
  type DiscoverySource,
  type CollectionRun,
  type ObservedFact,
  type EvidenceArtifact,
  type Page,
} from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  ChevronLeft, ChevronRight, Database, Eye, FileText,
  Activity, Layers, Radio, BarChart3, Clock,
} from "lucide-react";
import { formatDate, timeAgo } from "@/lib/utils";

const SKELETON_KEYS_8 = ["sk-a", "sk-b", "sk-c", "sk-d", "sk-e", "sk-f", "sk-g", "sk-h"] as const;
const SKELETON_KEYS_10 = ["sk-0", "sk-1", "sk-2", "sk-3", "sk-4", "sk-5", "sk-6", "sk-7", "sk-8", "sk-9"] as const;
const SKELETON_KEYS_5 = ["sk-v", "sk-w", "sk-x", "sk-y", "sk-z"] as const;
const SKELETON_KEYS_3 = ["sk-p", "sk-q", "sk-r"] as const;
const CELL_KEYS_6 = ["c-0", "c-1", "c-2", "c-3", "c-4", "c-5"] as const;
const CELL_KEYS_5 = ["c-a", "c-b", "c-c", "c-d", "c-e"] as const;

function KPICard({ label, value, icon: Icon, sub }: Readonly<{
  label: string; value: string | number; icon: React.ElementType; sub?: string;
}>) {
  return (
    <Card>
      <CardContent className="flex items-center gap-3 py-3 px-4">
        <div className="flex items-center justify-center w-9 h-9 rounded-lg" style={{ background: "var(--sl4)" }}>
          <Icon size={17} style={{ color: "var(--tx3)" }} />
        </div>
        <div className="flex flex-col min-w-0">
          <span className="text-[22px] font-bold leading-none" style={{ fontFamily: "var(--fD)" }}>
            {value}
          </span>
          <span className="text-[11px] mt-0.5" style={{ color: "var(--tx3)" }}>{label}</span>
          {sub && <span className="text-[10px] truncate" style={{ color: "var(--tx4)", fontFamily: "var(--fM)" }}>{sub}</span>}
        </div>
      </CardContent>
    </Card>
  );
}

function Paginator({ page, totalPages, total, label, onPrev, onNext }: Readonly<{
  page: number; totalPages: number; total: number; label: string;
  onPrev: () => void; onNext: () => void;
}>) {
  if (totalPages <= 1) return null;
  return (
    <div className="flex items-center justify-between text-sm">
      <span className="text-(--tx3)">{total} {label} &middot; page {page} / {totalPages}</span>
      <div className="flex gap-1">
        <Button size="sm" variant="outline" disabled={page === 1} onClick={onPrev}>
          <ChevronLeft size={14} />
        </Button>
        <Button size="sm" variant="outline" disabled={page === totalPages} onClick={onNext}>
          <ChevronRight size={14} />
        </Button>
      </div>
    </div>
  );
}

function OverviewTab({ stats, isLoading }: Readonly<{ stats?: DiscoveryStats; isLoading: boolean }>) {
  if (isLoading) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {SKELETON_KEYS_8.map((k) => <Skeleton key={k} className="h-20 w-full" />)}
      </div>
    );
  }
  if (!stats) return null;

  const topKinds = stats.snapshot_kinds.slice(0, 8);
  const maxKindCount = topKinds.length > 0 ? topKinds[0].count : 1;

  return (
    <div className="flex flex-col gap-5">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <KPICard icon={Radio} label="Discovery Sources" value={stats.sources} />
        <KPICard icon={Layers} label="Collection Runs" value={stats.collection_runs}
          sub={stats.latest_run_at ? `last: ${timeAgo(stats.latest_run_at)}` : undefined} />
        <KPICard icon={Eye} label="Observed Facts" value={stats.observed_facts} />
        <KPICard icon={FileText} label="Evidence Artifacts" value={stats.evidence_artifacts} />
        <KPICard icon={Activity} label="Active Agents" value={stats.active_agents} />
        <KPICard icon={Database} label="Total Snapshots" value={stats.total_snapshots.toLocaleString()}
          sub={stats.latest_snapshot_at ? `last: ${timeAgo(stats.latest_snapshot_at)}` : undefined} />
        <KPICard icon={BarChart3} label="Snapshot Kinds" value={stats.snapshot_kinds.length} />
        <KPICard icon={Clock} label="Fact Namespaces" value={stats.fact_namespaces.length} />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Snapshot Kinds Distribution</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-2">
            {topKinds.map((k) => (
              <div key={k.kind} className="flex items-center gap-2">
                <span className="text-xs w-32 truncate" style={{ fontFamily: "var(--fM)", color: "var(--tx3)" }}>{k.kind}</span>
                <div className="flex-1">
                  <Progress value={(k.count / maxKindCount) * 100} />
                </div>
                <span className="text-xs w-14 text-right" style={{ fontFamily: "var(--fM)" }}>{k.count.toLocaleString()}</span>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Fact Namespaces</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-2">
            {stats.fact_namespaces.length === 0 ? (
              <span className="text-xs" style={{ color: "var(--tx4)" }}>No facts recorded yet</span>
            ) : (
              stats.fact_namespaces.map((ns) => (
                <div key={ns.namespace} className="flex items-center justify-between">
                  <Badge variant="secondary" className="text-xs">{ns.namespace}</Badge>
                  <span className="text-xs" style={{ fontFamily: "var(--fM)" }}>{ns.count} facts</span>
                </div>
              ))
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function SourcesTab() {
  const { data, isLoading } = useQuery<DiscoverySource[]>({
    queryKey: ["discovery-sources"],
    queryFn: getDiscoverySources,
  });

  return (
    <div className="overflow-auto">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Code</TableHead>
            <TableHead>Name</TableHead>
            <TableHead>Tool</TableHead>
            <TableHead>Read-Only</TableHead>
            <TableHead>Description</TableHead>
            <TableHead>Created</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {isLoading
            ? SKELETON_KEYS_3.map((rk) => (
              <TableRow key={rk}>
                {CELL_KEYS_6.map((ck) => (
                  <TableCell key={`${rk}-${ck}`}><Skeleton className="h-4 w-full" /></TableCell>
                ))}
              </TableRow>
            ))
            : data?.map((s) => (
              <TableRow key={s.discovery_source_id}>
                <TableCell style={{ fontFamily: "var(--fM)", fontSize: 13 }}>
                  <Badge variant="secondary">{s.source_code}</Badge>
                </TableCell>
                <TableCell className="font-medium text-sm">{s.name}</TableCell>
                <TableCell className="text-xs" style={{ fontFamily: "var(--fM)", color: "var(--tx3)" }}>
                  {s.tool_path ?? "—"}
                </TableCell>
                <TableCell>
                  <Badge variant={s.is_read_only ? "default" : "blue"}>
                    {s.is_read_only ? "read-only" : "read-write"}
                  </Badge>
                </TableCell>
                <TableCell className="text-xs max-w-[240px] truncate" style={{ color: "var(--tx3)" }}>
                  {s.description ?? "—"}
                </TableCell>
                <TableCell className="text-xs whitespace-nowrap">{formatDate(s.created_at)}</TableCell>
              </TableRow>
            ))
          }
        </TableBody>
      </Table>
    </div>
  );
}

function RunsTab() {
  const [page, setPage] = useState(1);
  const pageSize = 25;
  const { data, isLoading } = useQuery<Page<CollectionRun>>({
    queryKey: ["discovery-runs", page],
    queryFn: () => getDiscoveryRuns(`page=${page}&page_size=${pageSize}`),
  });

  const total = data?.meta.total ?? 0;
  const totalPages = Math.ceil(total / pageSize);

  return (
    <div className="flex flex-col gap-3">
      <div className="overflow-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Run</TableHead>
              <TableHead>Source</TableHead>
              <TableHead>Executor</TableHead>
              <TableHead>Started</TableHead>
              <TableHead>Duration</TableHead>
              <TableHead>Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading
              ? SKELETON_KEYS_10.map((rk) => (
                <TableRow key={rk}>
                  {CELL_KEYS_6.map((ck) => (
                    <TableCell key={`${rk}-${ck}`}><Skeleton className="h-4 w-full" /></TableCell>
                  ))}
                </TableRow>
              ))
              : data?.items.map((run) => {
                const dur = run.finished_at
                  ? `${((new Date(run.finished_at).getTime() - new Date(run.started_at).getTime()) / 1000).toFixed(1)}s`
                  : "running\u2026";
                const isRunning = !run.finished_at;
                return (
                  <TableRow key={run.collection_run_id}>
                    <TableCell style={{ fontFamily: "var(--fM)", fontSize: 13 }}>{run.run_code}</TableCell>
                    <TableCell className="text-xs text-(--tx3)" style={{ fontFamily: "var(--fM)" }}>
                      {run.discovery_source_id.slice(0, 8)}&hellip;
                    </TableCell>
                    <TableCell className="text-xs text-(--tx3)">{run.executor_identity}</TableCell>
                    <TableCell className="text-xs whitespace-nowrap">{timeAgo(run.started_at)}</TableCell>
                    <TableCell style={{ fontFamily: "var(--fM)", fontSize: 13 }}>{dur}</TableCell>
                    <TableCell>
                      <Badge variant={isRunning ? "blue" : "default"}>
                        {isRunning ? "running" : "done"}
                      </Badge>
                    </TableCell>
                  </TableRow>
                );
              })}
          </TableBody>
        </Table>
      </div>
      <Paginator page={page} totalPages={totalPages} total={total} label="runs"
        onPrev={() => setPage((p) => p - 1)} onNext={() => setPage((p) => p + 1)} />
    </div>
  );
}

function FactsTab() {
  const [page, setPage] = useState(1);
  const pageSize = 30;
  const { data, isLoading } = useQuery<Page<ObservedFact>>({
    queryKey: ["discovery-facts", page],
    queryFn: () => getDiscoveryFacts(`page=${page}&page_size=${pageSize}`),
  });

  const total = data?.meta.total ?? 0;
  const totalPages = Math.ceil(total / pageSize);

  return (
    <div className="flex flex-col gap-3">
      <div className="overflow-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Namespace</TableHead>
              <TableHead>Key</TableHead>
              <TableHead>Entity</TableHead>
              <TableHead>Value</TableHead>
              <TableHead>Confidence</TableHead>
              <TableHead>Observed</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading
              ? SKELETON_KEYS_10.map((rk) => (
                <TableRow key={rk}>
                  {CELL_KEYS_6.map((ck) => (
                    <TableCell key={`${rk}-${ck}`}><Skeleton className="h-4 w-full" /></TableCell>
                  ))}
                </TableRow>
              ))
              : data?.items.map((f) => (
                <TableRow key={f.observed_fact_id}>
                  <TableCell>
                    <Badge variant="secondary" className="text-xs">{f.fact_namespace}</Badge>
                  </TableCell>
                  <TableCell className="text-xs font-medium" style={{ fontFamily: "var(--fM)" }}>{f.fact_key}</TableCell>
                  <TableCell className="text-xs" style={{ fontFamily: "var(--fM)", color: "var(--tx3)" }}>
                    {f.entity_id.slice(0, 8)}&hellip;
                  </TableCell>
                  <TableCell className="text-xs max-w-[220px] truncate" style={{ fontFamily: "var(--fM)", color: "var(--tx3)" }}>
                    {f.fact_value_jsonb ? JSON.stringify(f.fact_value_jsonb).slice(0, 80) : "—"}
                  </TableCell>
                  <TableCell>
                    {f.confidence_score == null ? (
                      <span className="text-xs" style={{ color: "var(--tx4)" }}>—</span>
                    ) : (
                      <span className="text-xs" style={{ fontFamily: "var(--fM)" }}>
                        {(f.confidence_score * 100).toFixed(0)}%
                      </span>
                    )}
                  </TableCell>
                  <TableCell className="text-xs whitespace-nowrap">{timeAgo(f.observed_at)}</TableCell>
                </TableRow>
              ))}
          </TableBody>
        </Table>
      </div>
      <Paginator page={page} totalPages={totalPages} total={total} label="facts"
        onPrev={() => setPage((p) => p - 1)} onNext={() => setPage((p) => p + 1)} />
    </div>
  );
}

function EvidenceTab() {
  const [page, setPage] = useState(1);
  const pageSize = 30;
  const { data, isLoading } = useQuery<Page<EvidenceArtifact>>({
    queryKey: ["discovery-evidence", page],
    queryFn: () => getDiscoveryEvidence(`page=${page}&page_size=${pageSize}`),
  });

  const total = data?.meta.total ?? 0;
  const totalPages = Math.ceil(total / pageSize);

  let evidenceTableBody;
  if (isLoading) {
    evidenceTableBody = SKELETON_KEYS_5.map((rk) => (
      <TableRow key={rk}>
        {CELL_KEYS_5.map((ck) => (
          <TableCell key={`${rk}-${ck}`}><Skeleton className="h-4 w-full" /></TableCell>
        ))}
      </TableRow>
    ));
  } else if (data?.items.length === 0) {
    evidenceTableBody = (
      <TableRow>
        <TableCell colSpan={5} className="text-center text-xs py-8" style={{ color: "var(--tx4)" }}>
          No evidence artifacts recorded yet
        </TableCell>
      </TableRow>
    );
  } else {
    evidenceTableBody = data?.items.map((e) => (
      <TableRow key={e.evidence_artifact_id}>
        <TableCell className="text-xs max-w-[200px] truncate" style={{ fontFamily: "var(--fM)" }}>
          {e.artifact_path ?? "—"}
        </TableCell>
        <TableCell>
          <Badge variant="secondary" className="text-xs">{e.mime_type ?? "unknown"}</Badge>
        </TableCell>
        <TableCell className="text-xs" style={{ fontFamily: "var(--fM)", color: "var(--tx3)" }}>
          {e.artifact_hash ? `${e.artifact_hash.slice(0, 12)}\u2026` : "—"}
        </TableCell>
        <TableCell className="text-xs max-w-[240px] truncate" style={{ color: "var(--tx3)" }}>
          {e.content_excerpt_text ?? "—"}
        </TableCell>
        <TableCell className="text-xs whitespace-nowrap">{timeAgo(e.created_at)}</TableCell>
      </TableRow>
    ));
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="overflow-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Artifact Path</TableHead>
              <TableHead>MIME Type</TableHead>
              <TableHead>Hash</TableHead>
              <TableHead>Excerpt</TableHead>
              <TableHead>Created</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {evidenceTableBody}
          </TableBody>
        </Table>
      </div>
      <Paginator page={page} totalPages={totalPages} total={total} label="artifacts"
        onPrev={() => setPage((p) => p - 1)} onNext={() => setPage((p) => p + 1)} />
    </div>
  );
}

export default function DiscoveryPage() {
  const { data: stats, isLoading: statsLoading } = useQuery<DiscoveryStats>({
    queryKey: ["discovery-stats"],
    queryFn: getDiscoveryStats,
    refetchInterval: 30_000,
  });

  return (
    <div className="page-in" style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <div className="flex items-center justify-between">
        <h1 className="df-page-title">Discovery</h1>
        <div className="flex items-center gap-3" style={{ fontFamily: "var(--fM)", fontSize: 12, color: "var(--tx3)" }}>
          {stats && (
            <>
              <span className="flex items-center gap-1">
                <Database size={12} />
                {stats.total_snapshots.toLocaleString()} snapshots
              </span>
              <span className="flex items-center gap-1">
                <Eye size={12} />
                {stats.observed_facts} facts
              </span>
              <span className="flex items-center gap-1">
                <Activity size={12} />
                {stats.active_agents} agents
              </span>
            </>
          )}
        </div>
      </div>

      <Tabs defaultValue="overview">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="sources">Sources ({stats?.sources ?? 0})</TabsTrigger>
          <TabsTrigger value="runs">Runs ({stats?.collection_runs ?? 0})</TabsTrigger>
          <TabsTrigger value="facts">Facts ({stats?.observed_facts ?? 0})</TabsTrigger>
          <TabsTrigger value="evidence">Evidence ({stats?.evidence_artifacts ?? 0})</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="mt-4">
          <OverviewTab stats={stats} isLoading={statsLoading} />
        </TabsContent>

        <TabsContent value="sources" className="mt-4">
          <SourcesTab />
        </TabsContent>

        <TabsContent value="runs" className="mt-4">
          <RunsTab />
        </TabsContent>

        <TabsContent value="facts" className="mt-4">
          <FactsTab />
        </TabsContent>

        <TabsContent value="evidence" className="mt-4">
          <EvidenceTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}
