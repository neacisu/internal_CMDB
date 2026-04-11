"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { getSystemInfo, type SystemInfo } from "@/lib/api";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { RefreshCw, Server, Database, Brain, Clock } from "lucide-react";

function InfoRow({ label, value }: Readonly<{ label: string; value: React.ReactNode }>) {
  return (
    <div className="flex items-center gap-3 py-1.5 border-b border-[oklch(0.24_0.012_255)] last:border-0">
      <span className="w-36 shrink-0 text-(--tx3) text-sm">{label}</span>
      <span className="text-(--tx1) text-sm font-(--fM)">{value}</span>
    </div>
  );
}

export default function SystemInfoPanel() {
  const queryClient = useQueryClient();

  const { data, isLoading, error, dataUpdatedAt } = useQuery<SystemInfo>({
    queryKey: ["settings", "system-info"],
    queryFn: getSystemInfo,
    staleTime: 60_000,
    refetchInterval: 60_000,
  });

  const handleRefresh = () => {
    queryClient.invalidateQueries({ queryKey: ["settings", "system-info"] });
  };

  if (isLoading) return (
    <div className="flex flex-col gap-4">
      <Skeleton className="h-48 w-full rounded-[10px]" />
      <Skeleton className="h-40 w-full rounded-[10px]" />
    </div>
  );

  if (error || !data) return (
    <p className="text-(--er) text-sm">Failed to load: {(error as Error)?.message ?? "Unknown error"}</p>
  );

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center justify-between">
        <p className="text-(--tx3) text-xs">
          Last updated: {dataUpdatedAt ? new Date(dataUpdatedAt).toLocaleTimeString() : "—"}
          {" · Polls every 60s"}
        </p>
        <Button size="sm" variant="outline" onClick={handleRefresh}>
          <RefreshCw className="h-3.5 w-3.5" />
          Refresh
        </Button>
      </div>

      <Card className="bg-(--sl2) border-[oklch(0.24_0.012_255)]">
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-[15px] font-(--fD)">
            <Server className="h-4 w-4 text-(--tx3)" />
            Application
          </CardTitle>
        </CardHeader>
        <CardContent>
          <InfoRow label="App Version" value={data.app_version} />
          <InfoRow label="Python Version" value={data.python_version} />
          <InfoRow label="Debug Mode" value={data.debug_enabled ? (
            <span className="text-(--wa) font-medium">Enabled</span>
          ) : (
            <span className="text-(--ok)">Disabled</span>
          )} />
        </CardContent>
      </Card>

      <Card className="bg-(--sl2) border-[oklch(0.24_0.012_255)]">
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-[15px] font-(--fD)">
            <Database className="h-4 w-4 text-(--tx3)" />
            Data Stores
          </CardTitle>
        </CardHeader>
        <CardContent>
          <InfoRow label="DB Host" value={data.db_host} />
          <InfoRow label="DB Port" value={String(data.db_port)} />
          <InfoRow label="DB Name" value={data.db_name} />
          <InfoRow label="DB SSL Mode" value={data.db_ssl_mode} />
          <InfoRow label="Redis Host" value={data.redis_url_host} />
        </CardContent>
      </Card>

      <Card className="bg-(--sl2) border-[oklch(0.24_0.012_255)]">
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-[15px] font-(--fD)">
            <Brain className="h-4 w-4 text-(--tx3)" />
            LLM Backends
          </CardTitle>
          <CardDescription className="text-(--tx3) text-sm">
            Live reachability check for each configured backend.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow className="border-[oklch(0.24_0.012_255)]">
                <TableHead className="text-(--tx3)">Name</TableHead>
                <TableHead className="text-(--tx3)">Model</TableHead>
                <TableHead className="text-(--tx3)">URL</TableHead>
                <TableHead className="text-(--tx3)">Status</TableHead>
                <TableHead className="text-(--tx3)">Latency</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.llm_backends.map(b => (
                <TableRow key={b.name} className="border-[oklch(0.24_0.012_255)]">
                  <TableCell className="font-medium text-sm">{b.name}</TableCell>
                  <TableCell className="font-(--fM) text-xs text-(--tx3)">{b.model}</TableCell>
                  <TableCell className="font-(--fM) text-xs text-(--tx3) max-w-45 truncate">{b.url}</TableCell>
                  <TableCell>
                    <span className="inline-flex items-center gap-1.5">
                      <span className={`h-2 w-2 rounded-full shrink-0 ${b.reachable ? "bg-(--ok)" : "bg-(--er)"}`} />
                      <span className={`text-xs font-medium ${b.reachable ? "text-(--ok)" : "text-(--er)"}`}>
                        {b.reachable ? "OK" : "Unreachable"}
                      </span>
                    </span>
                    {b.error && (
                      <p className="text-(--er) text-xs mt-0.5 truncate max-w-40">{b.error}</p>
                    )}
                  </TableCell>
                  <TableCell className="text-(--tx3) text-sm">
                    {b.response_ms === undefined ? "—" : `${b.response_ms}ms`}
                  </TableCell>
                </TableRow>
              ))}
              {data.llm_backends.length === 0 && (
                <TableRow>
                  <TableCell colSpan={5} className="text-center text-(--tx3) text-sm py-4">
                    No backends configured.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
        <Card className="bg-(--sl2) border-[oklch(0.24_0.012_255)]">
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-[15px] font-(--fD)">
              <Brain className="h-4 w-4 text-(--tx3)" />
              Cognitive Tasks
            </CardTitle>
          </CardHeader>
          <CardContent>
            {data.cognitive_tasks.length === 0
              ? <p className="text-(--tx3) text-sm">None registered.</p>
              : (
                <ul className="flex flex-col gap-1">
                  {data.cognitive_tasks.map(t => (
                    <li key={t} className="text-sm font-(--fM) text-sidebar-foreground bg-(--sl3) rounded-[5px] px-2.5 py-1">
                      {t}
                    </li>
                  ))}
                </ul>
              )}
          </CardContent>
        </Card>

        <Card className="bg-(--sl2) border-[oklch(0.24_0.012_255)]">
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-[15px] font-(--fD)">
              <Clock className="h-4 w-4 text-(--tx3)" />
              Cron Jobs
            </CardTitle>
          </CardHeader>
          <CardContent>
            {data.cron_jobs.length === 0
              ? <p className="text-(--tx3) text-sm">None registered.</p>
              : (
                <ul className="flex flex-col gap-1">
                  {data.cron_jobs.map(j => (
                    <li key={j} className="text-sm font-(--fM) text-sidebar-foreground bg-(--sl3) rounded-[5px] px-2.5 py-1">
                      {j}
                    </li>
                  ))}
                </ul>
              )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
