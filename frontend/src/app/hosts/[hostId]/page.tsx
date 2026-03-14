"use client";

import { use } from "react";
import { useQuery } from "@tanstack/react-query";
import { getHost, type HostDetail } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { formatBytes, formatDate } from "@/lib/utils";
import Link from "next/link";
import { ArrowLeft, Cpu, Container, Network } from "lucide-react";

function InfoRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex justify-between py-1 text-sm">
      <span className="text-(--tx3)">{label}</span>
      <span className="font-medium text-right max-w-[60%] truncate">{value ?? "—"}</span>
    </div>
  );
}

export default function HostDetailPage({ params }: { params: Promise<{ hostId: string }> }) {
  const { hostId } = use(params);

  const { data: host, isLoading } = useQuery<HostDetail>({
    queryKey: ["host", hostId],
    queryFn: () => getHost(hostId),
  });

  if (isLoading)
    return (
      <div className="page-in" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-64 w-full" />
      </div>
    );

  if (!host) return <div className="page-in text-(--tx3)">Host not found</div>;

  const snap = host.latest_snapshot;

  return (
    <div className="page-in" style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      {/* Back + header */}
      <div>
        <Link href="/hosts" className="flex items-center gap-1 text-sm text-(--tx3) hover:text-(--tx1) mb-3">
          <ArrowLeft size={14} /> Hosts
        </Link>
        <div className="flex items-start gap-3">
          <div>
            <h1 className="df-page-title">{host.hostname}</h1>
            {host.fqdn && <p className="df-page-sub">{host.fqdn}</p>}
          </div>
          <div className="flex gap-1.5 mt-1">
            {host.is_gpu_capable && <Badge variant="purple"><Cpu size={12} className="mr-1" />GPU</Badge>}
            {host.is_docker_host && <Badge variant="blue"><Container size={12} className="mr-1" />Docker</Badge>}
            {host.is_hypervisor && <Badge variant="warning">Hypervisor</Badge>}
          </div>
        </div>
      </div>

      <Tabs defaultValue="overview">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="hardware">Hardware</TabsTrigger>
          <TabsTrigger value="gpu">
            GPU ({host.gpu_devices.length})
          </TabsTrigger>
          <TabsTrigger value="network">
            Network ({host.network_interfaces.length})
          </TabsTrigger>
        </TabsList>

        {/* Overview */}
        <TabsContent value="overview" className="mt-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Card>
              <CardHeader><CardTitle className="text-sm">Identity</CardTitle></CardHeader>
              <CardContent>
                <InfoRow label="Host code" value={<code style={{ fontFamily: "var(--fM)", fontSize: 13 }}>{host.host_code}</code>} />
                <InfoRow label="SSH alias" value={host.ssh_alias} />
                <InfoRow label="Private IP" value={host.primary_private_ipv4} />
                <InfoRow label="Public IP" value={host.primary_public_ipv4} />
                <InfoRow label="Observed hostname" value={host.observed_hostname} />
                <InfoRow label="Confidence" value={host.confidence_score != null ? `${(host.confidence_score * 100).toFixed(0)}%` : null} />
              </CardContent>
            </Card>
            <Card>
              <CardHeader><CardTitle className="text-sm">System</CardTitle></CardHeader>
              <CardContent>
                <InfoRow label="OS" value={host.os_version_text} />
                <InfoRow label="Kernel" value={host.kernel_version_text} />
                <InfoRow label="Architecture" value={host.architecture_text} />
                <Separator className="my-2" />
                <InfoRow label="Created" value={formatDate(host.created_at)} />
                <InfoRow label="Updated" value={formatDate(host.updated_at)} />
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Hardware */}
        <TabsContent value="hardware" className="mt-4">
          {snap ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Card>
                <CardHeader><CardTitle className="text-sm">CPU</CardTitle></CardHeader>
                <CardContent>
                  <InfoRow label="Model" value={snap.cpu_model} />
                  <InfoRow label="Sockets" value={snap.cpu_socket_count} />
                  <InfoRow label="Cores" value={snap.cpu_core_count} />
                </CardContent>
              </Card>
              <Card>
                <CardHeader><CardTitle className="text-sm">Memory</CardTitle></CardHeader>
                <CardContent>
                  <InfoRow label="Total RAM" value={snap.ram_total_bytes != null ? formatBytes(snap.ram_total_bytes) : null} />
                  <InfoRow label="Used RAM" value={snap.ram_used_bytes != null ? formatBytes(snap.ram_used_bytes) : null} />
                  <InfoRow label="Free RAM" value={snap.ram_free_bytes != null ? formatBytes(snap.ram_free_bytes) : null} />
                  <InfoRow label="Swap total" value={snap.swap_total_bytes != null ? formatBytes(snap.swap_total_bytes) : null} />
                  <InfoRow label="GPU count" value={snap.gpu_count} />
                  <InfoRow label="Observed at" value={formatDate(snap.observed_at)} />
                </CardContent>
              </Card>
            </div>
          ) : (
            <p className="text-sm text-(--tx3)">No hardware snapshot available</p>
          )}
        </TabsContent>

        {/* GPU */}
        <TabsContent value="gpu" className="mt-4">
          {host.gpu_devices.length === 0 ? (
            <p className="text-sm text-(--tx3)">No GPU devices</p>
          ) : (
            <div className="overflow-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>#</TableHead>
                    <TableHead>Model</TableHead>
                    <TableHead>UUID</TableHead>
                    <TableHead className="text-right">Mem (MB)</TableHead>
                    <TableHead className="text-right">Util %</TableHead>
                    <TableHead className="text-right">Temp °C</TableHead>
                    <TableHead className="text-right">Power W</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {host.gpu_devices.map((g) => (
                    <TableRow key={g.gpu_device_id}>
                      <TableCell>{g.gpu_index}</TableCell>
                      <TableCell>{g.model_name ?? "—"}</TableCell>
                      <TableCell style={{ fontFamily: "var(--fM)", fontSize: 13 }} className="text-(--tx3)">{g.uuid_text ?? "—"}</TableCell>
                      <TableCell className="text-right" style={{ fontFamily: "var(--fM)", fontSize: 13 }}>{g.memory_used_mb ?? "—"} / {g.memory_total_mb ?? "—"}</TableCell>
                      <TableCell className="text-right">{g.utilization_gpu_pct ?? "—"}</TableCell>
                      <TableCell className="text-right">{g.temperature_celsius ?? "—"}</TableCell>
                      <TableCell className="text-right">{g.power_draw_watts ?? "—"}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </TabsContent>

        {/* Network */}
        <TabsContent value="network" className="mt-4">
          {host.network_interfaces.length === 0 ? (
            <p className="text-sm text-(--tx3)">No network interfaces</p>
          ) : (
            <div className="overflow-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Interface</TableHead>
                    <TableHead>State</TableHead>
                    <TableHead>MAC</TableHead>
                    <TableHead className="text-right">MTU</TableHead>
                    <TableHead>Virtual</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {host.network_interfaces.map((nic) => (
                    <TableRow key={nic.network_interface_id}>
                      <TableCell style={{ fontFamily: "var(--fM)", fontSize: 14 }}>{nic.interface_name}</TableCell>
                      <TableCell>
                        <Badge variant={nic.state_text === "UP" ? "default" : "secondary"} className="text-xs">
                          {nic.state_text ?? "unknown"}
                        </Badge>
                      </TableCell>
                      <TableCell style={{ fontFamily: "var(--fM)", fontSize: 13 }} className="text-(--tx3)">{nic.mac_address ?? "—"}</TableCell>
                      <TableCell className="text-right" style={{ fontFamily: "var(--fM)", fontSize: 13 }}>{nic.mtu ?? "—"}</TableCell>
                      <TableCell>{nic.is_virtual ? "yes" : "no"}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
