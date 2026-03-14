"use client";

import { useQuery } from "@tanstack/react-query";
import { getDiscoveryRuns, type CollectionRun, type Page } from "@/lib/api";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { formatDate, timeAgo } from "@/lib/utils";
import { useState } from "react";

export default function DiscoveryPage() {
  const [page, setPage] = useState(1);
  const { data, isLoading } = useQuery<Page<CollectionRun>>({
    queryKey: ["discovery-runs", page],
    queryFn: () => getDiscoveryRuns(`page=${page}&page_size=25`),
  });

  const total = data?.meta.total ?? 0;
  const totalPages = Math.ceil(total / 25);

  return (
    <div className="page-in" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <h1 className="df-page-title">Discovery Runs</h1>

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
              ? Array.from({ length: 10 }).map((_, i) => (
                  <TableRow key={i}>
                    {Array.from({ length: 6 }).map((__, j) => (
                      <TableCell key={j}><Skeleton className="h-4 w-full" /></TableCell>
                    ))}
                  </TableRow>
                ))
              : data?.items.map((run) => {
                  const dur =
                    run.finished_at
                      ? `${((new Date(run.finished_at).getTime() - new Date(run.started_at).getTime()) / 1000).toFixed(1)}s`
                      : "running…";
                  const isRunning = !run.finished_at;
                  return (
                    <TableRow key={run.collection_run_id}>
                      <TableCell style={{ fontFamily: "var(--fM)", fontSize: 13 }}>{run.run_code}</TableCell>
                      <TableCell className="text-xs text-(--tx3)" style={{ fontFamily: "var(--fM)" }}>
                        {run.discovery_source_id.slice(0, 8)}…
                      </TableCell>
                      <TableCell className="text-xs text-(--tx3)">{run.executor_identity}</TableCell>
                      <TableCell className="text-xs whitespace-nowrap">{timeAgo(run.started_at)}</TableCell>
                      <TableCell style={{ fontFamily: "var(--fM)", fontSize: 13 }}>{dur}</TableCell>
                      <TableCell>
                        <Badge
                          variant={isRunning ? "blue" : "default"}
                        >
                          {isRunning ? "running" : "done"}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  );
                })}
          </TableBody>
        </Table>
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-between text-sm">
          <span className="text-(--tx3)">{total} runs · page {page} / {totalPages}</span>
          <div className="flex gap-1">
            <Button size="sm" variant="outline" disabled={page === 1} onClick={() => setPage((p) => p - 1)}>
              <ChevronLeft size={14} />
            </Button>
            <Button size="sm" variant="outline" disabled={page === totalPages} onClick={() => setPage((p) => p + 1)}>
              <ChevronRight size={14} />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
