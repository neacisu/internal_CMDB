"use client";

import { useQuery } from "@tanstack/react-query";
import { getScripts, type ScriptMeta } from "@/lib/api";
import { ScriptCard } from "@/components/workers/script-card";
import { JobTable } from "@/components/workers/job-table";
import { SchedulerPanel } from "@/components/workers/scheduler-panel";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

export default function WorkersPage() {
  const { data: scripts, isLoading } = useQuery<ScriptMeta[]>({
    queryKey: ["scripts"],
    queryFn: getScripts,
  });

  return (
    <div className="page-in" style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <h1 className="df-page-title">Workers</h1>

      <Tabs defaultValue="scripts">
        <TabsList>
          <TabsTrigger value="scripts">Scripts</TabsTrigger>
          <TabsTrigger value="jobs">Job History</TabsTrigger>
          <TabsTrigger value="schedules">Schedules</TabsTrigger>
        </TabsList>

        <TabsContent value="scripts" className="mt-4">
          {isLoading ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {Array.from({ length: 6 }).map((_, i) => (
                <Skeleton key={i} className="h-48 w-full" />
              ))}
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {scripts?.map((s) => <ScriptCard key={s.task_name} script={s} />)}
            </div>
          )}
        </TabsContent>

        <TabsContent value="jobs" className="mt-4">
          <JobTable />
        </TabsContent>

        <TabsContent value="schedules" className="mt-4">
          <SchedulerPanel />
        </TabsContent>
      </Tabs>
    </div>
  );
}
