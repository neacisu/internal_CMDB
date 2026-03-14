"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getJobs, retryJob, cancelJob, type Job, type Page } from "@/lib/api";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { RotateCw, X, ChevronLeft, ChevronRight } from "lucide-react";
import { formatDate, timeAgo } from "@/lib/utils";
import { useState } from "react";
import { toast } from "sonner";

const statusColor: Record<string, "warning" | "blue" | "default" | "destructive" | "secondary"> = {
  pending: "warning",
  running: "blue",
  completed: "default",
  failed: "destructive",
  cancelled: "secondary",
};

export function JobTable() {
  const [page, setPage] = useState(1);
  const qc = useQueryClient();

  const { data, isLoading } = useQuery<Page<Job>>({
    queryKey: ["jobs", page],
    queryFn: () => getJobs(`page=${page}&page_size=20`),
  });

  const retry = useMutation({
    mutationFn: (id: string) => retryJob(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["jobs"] }); toast.success("Job re-queued"); },
    onError: (e: Error) => toast.error(e.message),
  });

  const cancel = useMutation({
    mutationFn: (id: string) => cancelJob(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["jobs"] }); toast.success("Job cancelled"); },
    onError: (e: Error) => toast.error(e.message),
  });

  if (isLoading)
    return (
      <div className="space-y-2">
        {Array.from({ length: 8 }).map((_, i) => (
          <Skeleton key={i} className="h-10 w-full" />
        ))}
      </div>
    );

  const total = data?.meta.total ?? 0;
  const totalPages = Math.ceil(total / 20);

  return (
    <div className="space-y-3">
      <div className="overflow-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Task</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Started</TableHead>
              <TableHead>Duration</TableHead>
              <TableHead>Exit</TableHead>
              <TableHead>Triggered by</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data?.items.map((job) => {
              const dur =
                job.started_at && job.finished_at
                  ? `${((new Date(job.finished_at).getTime() - new Date(job.started_at).getTime()) / 1000).toFixed(1)}s`
                  : job.started_at
                  ? "running…"
                  : "—";
              return (
                <TableRow key={job.job_id}>
                  <TableCell style={{ fontFamily: "var(--fM)", fontSize: 13 }}>{job.task_name}</TableCell>
                  <TableCell>
                    <Badge variant={statusColor[job.status] ?? "secondary"}>
                      {job.status}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-xs text-(--tx3) whitespace-nowrap">
                    {job.started_at ? timeAgo(job.started_at) : "—"}
                  </TableCell>
                  <TableCell style={{ fontFamily: "var(--fM)", fontSize: 13 }}>{dur}</TableCell>
                  <TableCell style={{ fontFamily: "var(--fM)", fontSize: 13 }}>
                    {job.exit_code !== null ? job.exit_code : "—"}
                  </TableCell>
                  <TableCell className="text-xs text-(--tx3)">{job.triggered_by}</TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-1">
                      {(job.status === "failed" || job.status === "completed") && (
                        <Button
                          size="sm"
                          variant="ghost"
                          className="h-7"
                          onClick={() => retry.mutate(job.job_id)}
                        >
                          <RotateCw size={13} />
                        </Button>
                      )}
                      {(job.status === "pending" || job.status === "running") && (
                        <Button
                          size="sm"
                          variant="ghost"
                          className="h-7 text-destructive"
                          onClick={() => cancel.mutate(job.job_id)}
                        >
                          <X size={13} />
                        </Button>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              );
            })}
            {!data?.items.length && (
              <TableRow>
                <TableCell colSpan={7} className="text-center text-(--tx3) py-8">
                  No jobs yet
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-between text-sm">
          <span className="text-(--tx3)">
            {total} jobs · page {page} / {totalPages}
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
              disabled={page === totalPages}
              onClick={() => setPage((p) => p + 1)}
            >
              <ChevronRight size={14} />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
