"use client";

import { useQuery } from "@tanstack/react-query";
import { getResultTypes, getCurrentResult, type ResultTypeMeta } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { timeAgo } from "@/lib/utils";
import { CheckCircle2, XCircle, Shield, Network, Server, Key, Activity, Eye } from "lucide-react";

type AnyResult = Record<string, unknown>;

function SSHConnectivityView({ data }: Readonly<{ data: AnyResult }>) {
  const payload = (data.payload ?? {}) as AnyResult;
  const summary = (payload.summary ?? {}) as AnyResult;
  const results = (payload.results ?? []) as AnyResult[];
  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-3 gap-3">
        <Card>
          <CardContent className="py-3 px-4 text-center">
            <div className="text-2xl font-bold" style={{ fontFamily: "var(--fD)" }}>{String(summary.total ?? 0)}</div>
            <div className="text-xs" style={{ color: "var(--tx3)" }}>Total Hosts</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="py-3 px-4 text-center">
            <div className="text-2xl font-bold" style={{ fontFamily: "var(--fD)", color: "var(--g3)" }}>{String(summary.ok ?? 0)}</div>
            <div className="text-xs" style={{ color: "var(--tx3)" }}>Connected</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="py-3 px-4 text-center">
            <div className="text-2xl font-bold" style={{ fontFamily: "var(--fD)", color: Number(summary.fail) > 0 ? "var(--r3)" : "var(--tx3)" }}>{String(summary.fail ?? 0)}</div>
            <div className="text-xs" style={{ color: "var(--tx3)" }}>Failed</div>
          </CardContent>
        </Card>
      </div>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Host</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Detail</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {results.map((r) => (
            <TableRow key={String(r.host)}>
              <TableCell style={{ fontFamily: "var(--fM)", fontSize: 13 }}>{String(r.host)}</TableCell>
              <TableCell>
                {r.ok
                  ? <span className="flex items-center gap-1 text-xs" style={{ color: "var(--g3)" }}><CheckCircle2 size={13} /> OK</span>
                  : <span className="flex items-center gap-1 text-xs" style={{ color: "var(--r3)" }}><XCircle size={13} /> FAIL</span>}
              </TableCell>
              <TableCell className="text-xs" style={{ color: "var(--tx3)" }}>{String(r.detail)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

function FullClusterAuditView({ data }: Readonly<{ data: AnyResult }>) {
  const payload = (data.payload ?? {}) as AnyResult;
  const nodes = (payload.nodes ?? []) as AnyResult[];
  return (
    <div className="flex flex-col gap-4">
      <div className="text-xs" style={{ color: "var(--tx3)" }}>{nodes.length} nodes audited</div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        {nodes.map((node) => {
          const system = (node.system ?? {}) as AnyResult;
          const hardware = (node.hardware ?? {}) as AnyResult;
          const docker = (node.docker ?? {}) as AnyResult;
          const security = (node.security ?? {}) as AnyResult;
          const diskObj = (node.disk ?? {}) as AnyResult;
          const partitions = (diskObj.partitions ?? []) as AnyResult[];
          const ramTotalGb = Number(hardware.ram_total_gb ?? 0);
          const ramUsedGb = Number(hardware.ram_used_gb ?? 0);
          const ramPct = Number(hardware.ram_used_pct ?? 0);
          return (
            <Card key={String(node.alias)}>
              <CardHeader>
                <div className="flex items-center justify-between w-full">
                  <CardTitle className="text-sm flex items-center gap-1.5">
                    <Server size={14} style={{ color: "var(--tx3)" }} />
                    {String(node.alias)}
                  </CardTitle>
                  <Badge variant="secondary" className="text-xs">{String(system.os ?? "—")}</Badge>
                </div>
              </CardHeader>
              <CardContent className="flex flex-col gap-2 text-xs">
                <div className="grid grid-cols-2 gap-x-4 gap-y-1">
                  <span style={{ color: "var(--tx3)" }}>Hostname</span>
                  <span style={{ fontFamily: "var(--fM)" }}>{String(system.hostname ?? "—")}</span>
                  <span style={{ color: "var(--tx3)" }}>Kernel</span>
                  <span style={{ fontFamily: "var(--fM)" }}>{String(system.kernel ?? "—")}</span>
                  <span style={{ color: "var(--tx3)" }}>CPU</span>
                  <span style={{ fontFamily: "var(--fM)" }}>{String(hardware.cpu_model ?? "—")}</span>
                  <span style={{ color: "var(--tx3)" }}>Cores</span>
                  <span style={{ fontFamily: "var(--fM)" }}>{String(hardware.cpu_cores ?? "—")}</span>
                  <span style={{ color: "var(--tx3)" }}>RAM</span>
                  <span style={{ fontFamily: "var(--fM)" }}>{ramTotalGb > 0 ? `${ramUsedGb.toFixed(1)} / ${ramTotalGb.toFixed(1)} GB` : "—"}</span>
                </div>
                {ramTotalGb > 0 && (
                  <div className="flex items-center gap-2">
                    <Progress value={ramPct} className="flex-1" />
                    <span style={{ fontFamily: "var(--fM)", color: ramPct > 85 ? "var(--r3)" : "var(--tx3)" }}>{ramPct.toFixed(0)}%</span>
                  </div>
                )}
                {partitions.length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-1">
                    {partitions.slice(0, 3).map((p) => (
                      <Badge key={String(p.mountpoint)} variant="secondary" className="text-[10px]">
                        {String(p.mountpoint)} {String(p.pct ?? "—")}
                      </Badge>
                    ))}
                  </div>
                )}
                <div className="flex items-center gap-3 mt-1">
                  {docker.present && docker.version ? (
                    <Badge variant="blue" className="text-[10px]">Docker {String(docker.version)}</Badge>
                  ) : null}
                  {Array.isArray(docker.containers_running) && (
                    <span style={{ fontFamily: "var(--fM)", color: "var(--tx3)" }}>{(docker.containers_running as unknown[]).length} running</span>
                  )}
                  {String(security.sec_permit_root) === "yes" && (
                    <Badge variant="default" className="text-[10px] bg-[oklch(0.35_0.12_25)]">Root Login</Badge>
                  )}
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}

function NetworkAuditView({ data }: Readonly<{ data: AnyResult }>) {
  const payload = (data.payload ?? {}) as AnyResult;
  const results = (payload.results ?? []) as AnyResult[];
  const summary = (payload.summary ?? {}) as AnyResult;
  return (
    <div className="flex flex-col gap-4">
      {summary && (
        <div className="flex items-center gap-3 text-xs" style={{ color: "var(--tx3)" }}>
          <span>{String(summary.total ?? results.length)} nodes</span>
          {summary.vswitch_count != null && <span>{String(summary.vswitch_count)} with vSwitch</span>}
        </div>
      )}
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Node</TableHead>
            <TableHead>Hostname</TableHead>
            <TableHead>OS</TableHead>
            <TableHead>Public IP</TableHead>
            <TableHead>Private IPs</TableHead>
            <TableHead>VLANs</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {results.map((r) => {
            const privateIps = (r.private_ips ?? []) as string[];
            const vlans = (r.vlan_ids ?? r.vlans ?? []) as string[];
            return (
              <TableRow key={String(r.alias)}>
                <TableCell style={{ fontFamily: "var(--fM)", fontSize: 13 }}>{String(r.alias)}</TableCell>
                <TableCell className="text-xs">{String(r.hostname ?? "—")}</TableCell>
                <TableCell className="text-xs max-w-[140px] truncate" style={{ color: "var(--tx3)" }}>{String(r.os ?? "—")}</TableCell>
                <TableCell className="text-xs" style={{ fontFamily: "var(--fM)" }}>{String(r.pub_ip ?? "—")}</TableCell>
                <TableCell className="text-xs">
                  <div className="flex flex-wrap gap-1">
                    {privateIps.slice(0, 4).map((ip) => (
                      <Badge key={ip} variant="secondary" className="text-[10px]">{ip}</Badge>
                    ))}
                    {privateIps.length > 4 && <Badge variant="secondary" className="text-[10px]">+{privateIps.length - 4}</Badge>}
                  </div>
                </TableCell>
                <TableCell className="text-xs" style={{ fontFamily: "var(--fM)" }}>
                  {vlans.length > 0 ? vlans.join(", ") : "—"}
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}

function RuntimePostureView({ data }: Readonly<{ data: AnyResult }>) {
  const payload = (data.payload ?? {}) as AnyResult;
  const results = (payload.results ?? []) as AnyResult[];
  return (
    <div className="flex flex-col gap-4">
      <div className="text-xs" style={{ color: "var(--tx3)" }}>{results.length} hosts scanned</div>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Host</TableHead>
            <TableHead>OS</TableHead>
            <TableHead>Docker</TableHead>
            <TableHead>Containers</TableHead>
            <TableHead>Timers</TableHead>
            <TableHead>Units</TableHead>
            <TableHead>Indicators</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {results.map((r) => {
            const d = (r.data ?? {}) as AnyResult;
            const containers = (d.containers ?? []) as unknown[];
            const containersAll = (d.containers_all ?? []) as unknown[];
            const timers = (d.systemd_timers ?? []) as unknown[];
            const units = (d.systemd_units ?? []) as unknown[];
            const indicators = (d.indicators ?? []) as unknown[];
            return (
              <TableRow key={String(r.alias)}>
                <TableCell style={{ fontFamily: "var(--fM)", fontSize: 13 }}>
                  <div className="flex items-center gap-1.5">
                    {r.ok
                      ? <CheckCircle2 size={12} style={{ color: "var(--g3)" }} />
                      : <XCircle size={12} style={{ color: "var(--r3)" }} />}
                    {String(r.alias)}
                  </div>
                </TableCell>
                <TableCell className="text-xs max-w-[140px] truncate" style={{ color: "var(--tx3)" }}>{String(d.os ?? "—")}</TableCell>
                <TableCell>
                  {d.docker_present
                    ? <Badge variant="blue" className="text-[10px]">v{String(d.docker_server ?? "?")}</Badge>
                    : <span className="text-xs" style={{ color: "var(--tx4)" }}>No</span>}
                </TableCell>
                <TableCell className="text-xs" style={{ fontFamily: "var(--fM)" }}>
                  {containers.length}/{containersAll.length}
                </TableCell>
                <TableCell className="text-xs" style={{ fontFamily: "var(--fM)" }}>{timers.length}</TableCell>
                <TableCell className="text-xs" style={{ fontFamily: "var(--fM)" }}>{units.length}</TableCell>
                <TableCell className="text-xs" style={{ fontFamily: "var(--fM)" }}>{indicators.length}</TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}

function TrustSurfaceView({ data }: Readonly<{ data: AnyResult }>) {
  const payload = (data.payload ?? {}) as AnyResult;
  const resultsObj = (payload.results ?? {}) as AnyResult;
  const hostResults = (resultsObj.hosts ?? []) as AnyResult[];
  const endpointResults = (resultsObj.endpoints ?? []) as AnyResult[];
  return (
    <div className="flex flex-col gap-4">
      <div className="text-xs" style={{ color: "var(--tx3)" }}>{hostResults.length} hosts, {endpointResults.length} TLS endpoints</div>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Host</TableHead>
            <TableHead>SSHD Config</TableHead>
            <TableHead>Secret Paths</TableHead>
            <TableHead>Certificates</TableHead>
            <TableHead>SSH Dirs</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {hostResults.map((r) => {
            const d = (r.data ?? {}) as AnyResult;
            const sshd = (d.sshd ?? []) as string[];
            const secrets = (d.secret_paths ?? []) as AnyResult[];
            const certs = (d.certs ?? []) as AnyResult[];
            const sshDirs = (d.ssh_dirs ?? []) as AnyResult[];
            const hasRootLogin = sshd.some((s) => s.toLowerCase().includes("permitrootlogin yes"));
            const hasPwdAuth = sshd.some((s) => s.toLowerCase().includes("passwordauthentication yes"));
            return (
              <TableRow key={String(r.alias)}>
                <TableCell style={{ fontFamily: "var(--fM)", fontSize: 13 }}>
                  <div className="flex items-center gap-1.5">
                    <Shield size={12} style={{ color: hasRootLogin ? "var(--r3)" : "var(--g3)" }} />
                    {String(r.alias)}
                  </div>
                </TableCell>
                <TableCell>
                  <div className="flex flex-wrap gap-1">
                    {hasRootLogin && <Badge variant="default" className="text-[10px] bg-[oklch(0.35_0.12_25)]">root</Badge>}
                    {hasPwdAuth && <Badge variant="default" className="text-[10px] bg-[oklch(0.40_0.10_55)]">pwd</Badge>}
                    <Badge variant="secondary" className="text-[10px]">port {sshd.find((s) => s.startsWith("port"))?.split(" ")[1] ?? "22"}</Badge>
                  </div>
                </TableCell>
                <TableCell className="text-xs" style={{ fontFamily: "var(--fM)" }}>{secrets.length}</TableCell>
                <TableCell className="text-xs" style={{ fontFamily: "var(--fM)" }}>{certs.length > 0 ? certs.length : "—"}</TableCell>
                <TableCell className="text-xs" style={{ fontFamily: "var(--fM)" }}>{sshDirs.length}</TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
      {endpointResults.length > 0 && (
        <>
          <h3 className="text-sm font-medium mt-2">TLS Endpoint Probes</h3>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Endpoint</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>TLS Version</TableHead>
                <TableHead>Expiry</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {endpointResults.map((p) => (
                <TableRow key={String(p.endpoint)}>
                  <TableCell className="text-xs" style={{ fontFamily: "var(--fM)" }}>{String(p.endpoint)}</TableCell>
                  <TableCell>
                    <Badge variant={p.ok ? "default" : "secondary"} className="text-[10px]">
                      {p.ok ? "OK" : "FAIL"}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-xs" style={{ fontFamily: "var(--fM)" }}>{String(p.version ?? "—")}</TableCell>
                  <TableCell className="text-xs">{String(p.notAfter ?? "—")}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </>
      )}
    </div>
  );
}

function KeyMeshView({ data }: Readonly<{ data: AnyResult }>) {
  const payload = (data.payload ?? {}) as AnyResult;
  const cluster = (payload.cluster ?? []) as AnyResult[];
  const distribution = (payload.distribution_results ?? []) as AnyResult[];
  const summary = (payload.summary ?? {}) as AnyResult;
  const totalAdded = Number(summary.total_added ?? 0);
  const totalErrors = Number(summary.total_errors ?? 0);
  const keyInventory = (payload.key_inventory ?? {}) as AnyResult;
  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Card>
          <CardContent className="py-3 px-4 text-center">
            <div className="text-2xl font-bold" style={{ fontFamily: "var(--fD)" }}>{cluster.length}</div>
            <div className="text-xs" style={{ color: "var(--tx3)" }}>Cluster Nodes</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="py-3 px-4 text-center">
            <div className="text-2xl font-bold" style={{ fontFamily: "var(--fD)" }}>{String(keyInventory.unique_key_count ?? "—")}</div>
            <div className="text-xs" style={{ color: "var(--tx3)" }}>Unique Keys</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="py-3 px-4 text-center">
            <div className="text-2xl font-bold" style={{ fontFamily: "var(--fD)", color: "var(--g3)" }}>{totalAdded}</div>
            <div className="text-xs" style={{ color: "var(--tx3)" }}>Keys Added</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="py-3 px-4 text-center">
            <div className="text-2xl font-bold" style={{ fontFamily: "var(--fD)", color: totalErrors > 0 ? "var(--r3)" : "var(--tx3)" }}>{totalErrors}</div>
            <div className="text-xs" style={{ color: "var(--tx3)" }}>Errors</div>
          </CardContent>
        </Card>
      </div>
      {distribution.length > 0 && (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Target</TableHead>
              <TableHead>Added</TableHead>
              <TableHead>Skipped</TableHead>
              <TableHead>Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {distribution.map((d) => {
              const errors = (d.errors ?? []) as string[];
              return (
                <TableRow key={String(d.alias)}>
                  <TableCell style={{ fontFamily: "var(--fM)", fontSize: 13 }}>{String(d.alias)}</TableCell>
                  <TableCell className="text-xs" style={{ fontFamily: "var(--fM)" }}>{String(d.added ?? 0)}</TableCell>
                  <TableCell className="text-xs" style={{ fontFamily: "var(--fM)" }}>{String(d.skipped ?? 0)}</TableCell>
                  <TableCell>
                    {errors.length > 0
                      ? <Badge variant="default" className="text-[10px] bg-[oklch(0.35_0.12_25)]">error</Badge>
                      : <Badge variant="default" className="text-[10px]">ok</Badge>}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      )}
    </div>
  );
}

function RawJsonView({ data }: Readonly<{ data: unknown }>) {
  return (
    <ScrollArea className="h-[60vh] rounded-[10px] border border-[oklch(0.25_0.01_240)] bg-sidebar-background">
      <pre className="p-4 text-xs text-sidebar-foreground whitespace-pre-wrap wrap-break-word" style={{ fontFamily: "var(--fM)" }}>
        {JSON.stringify(data, null, 2)}
      </pre>
    </ScrollArea>
  );
}

const RESULT_ICONS: Record<string, React.ElementType> = {
  ssh_connectivity: Network,
  network_audit: Network,
  full_cluster_audit: Server,
  runtime_posture: Activity,
  trust_surface: Shield,
  cluster_key_mesh_state: Key,
};

const STRUCTURED_VIEWS: Record<string, React.FC<Readonly<{ data: AnyResult }>>> = {
  ssh_connectivity: SSHConnectivityView,
  full_cluster_audit: FullClusterAuditView,
  network_audit: NetworkAuditView,
  runtime_posture: RuntimePostureView,
  trust_surface: TrustSurfaceView,
  cluster_key_mesh_state: KeyMeshView,
};

function ResultViewer({ type }: Readonly<{ type: string }>) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["results", "current", type],
    queryFn: () => getCurrentResult(type),
  });

  if (isLoading) return <Skeleton className="h-64 w-full" />;
  if (isError) return <p className="text-sm text-(--tx3) p-4">Failed to load result</p>;

  const StructuredView = STRUCTURED_VIEWS[type];
  const resultData = data as AnyResult;

  return (
    <div className="flex flex-col gap-3">
      {StructuredView && <StructuredView data={resultData} />}
      <details className="mt-2">
        <summary className="text-xs cursor-pointer" style={{ color: "var(--tx4)", fontFamily: "var(--fM)" }}>
          Raw JSON ({JSON.stringify(data).length.toLocaleString()} chars)
        </summary>
        <div className="mt-2">
          <RawJsonView data={data} />
        </div>
      </details>
    </div>
  );
}

export default function ResultsPage() {
  const { data: types, isLoading } = useQuery<ResultTypeMeta[]>({
    queryKey: ["result-types"],
    queryFn: getResultTypes,
  });

  if (isLoading) return (
    <div className="p-6 space-y-4">
      <Skeleton className="h-8 w-48" />
      <Skeleton className="h-64 w-full" />
    </div>
  );

  if (!types?.length) return (
    <div className="p-6">
      <h1 className="df-page-title" style={{ marginBottom: 16 }}>Results</h1>
      <p className="text-(--tx3)">No result types configured</p>
    </div>
  );

  const activeTypes = types.filter((t) => t.current_file);
  const defaultTab = activeTypes.length > 0 ? activeTypes[0].result_type : types[0].result_type;

  return (
    <div className="page-in" style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <div className="flex items-center justify-between">
        <h1 className="df-page-title">Audit Results</h1>
        <div className="flex items-center gap-3" style={{ fontFamily: "var(--fM)", fontSize: 12, color: "var(--tx3)" }}>
          <span className="flex items-center gap-1">
            <Eye size={12} />
            {activeTypes.length}/{types.length} active
          </span>
        </div>
      </div>

      <Tabs defaultValue={defaultTab}>
        <TabsList>
          {types.map((t) => {
            const Icon = RESULT_ICONS[t.result_type] ?? Server;
            return (
              <TabsTrigger key={t.result_type} value={t.result_type} className="flex items-center gap-1.5">
                <Icon size={13} />
                {t.display_name}
              </TabsTrigger>
            );
          })}
        </TabsList>
        {types.map((t) => (
          <TabsContent key={t.result_type} value={t.result_type} className="mt-4">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0">
                <CardTitle className="text-sm font-medium">{t.display_name}</CardTitle>
                <div className="flex items-center gap-2">
                  {t.last_modified && (
                    <Badge variant="secondary" className="text-xs">
                      {timeAgo(t.last_modified)}
                    </Badge>
                  )}
                  <Badge variant={t.current_file ? "default" : "secondary"} className="text-xs">
                    {t.current_file ? "active" : "no data"}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent>
                {t.current_file ? (
                  <ResultViewer type={t.result_type} />
                ) : (
                  <p className="text-sm text-(--tx3) py-8 text-center">
                    No result available — run the audit script to generate data
                  </p>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        ))}
      </Tabs>
    </div>
  );
}
