"use client";

import { useQuery } from "@tanstack/react-query";
import { getScripts, getCognitiveTasks, type ScriptMeta, type CognitiveTask } from "@/lib/api";
import { ScriptCard } from "@/components/workers/script-card";
import { JobTable } from "@/components/workers/job-table";
import { SchedulerPanel } from "@/components/workers/scheduler-panel";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Brain, Wrench, Zap } from "lucide-react";

const cogCategoryColors: Record<string, string> = {
  cognitive: "purple",
  maintenance: "blue",
};

export default function WorkersPage() {
  const { data: scripts, isLoading } = useQuery<ScriptMeta[]>({
    queryKey: ["scripts"],
    queryFn: getScripts,
  });

  const { data: cogTasks, isLoading: cogLoading } = useQuery<CognitiveTask[]>({
    queryKey: ["cognitive-tasks"],
    queryFn: getCognitiveTasks,
  });

  return (
    <div className="page-in" style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <div className="flex items-center justify-between">
        <h1 className="df-page-title">Workers</h1>
        <div className="flex items-center gap-3" style={{ fontFamily: "var(--fM)", fontSize: 12, color: "var(--tx3)" }}>
          <span className="flex items-center gap-1">
            <Wrench size={12} />
            {scripts?.length ?? "—"} scripts
          </span>
          <span className="flex items-center gap-1">
            <Brain size={12} />
            {cogTasks?.length ?? "—"} async tasks
          </span>
        </div>
      </div>

      <Tabs defaultValue="scripts">
        <TabsList>
          <TabsTrigger value="scripts">Scripts ({scripts?.length ?? 0})</TabsTrigger>
          <TabsTrigger value="cognitive">Async Tasks ({cogTasks?.length ?? 0})</TabsTrigger>
          <TabsTrigger value="jobs">Job History</TabsTrigger>
          <TabsTrigger value="schedules">Schedules</TabsTrigger>
        </TabsList>

        <TabsContent value="scripts" className="mt-4">
          {isLoading ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {["wk-sk-1", "wk-sk-2", "wk-sk-3", "wk-sk-4", "wk-sk-5", "wk-sk-6"].map((k) => (
                <Skeleton key={k} className="h-48 w-full" />
              ))}
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {scripts?.map((s) => <ScriptCard key={s.task_name} script={s} />)}
            </div>
          )}
        </TabsContent>

        <TabsContent value="cognitive" className="mt-4">
          {cogLoading ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {["cg-sk-1", "cg-sk-2", "cg-sk-3", "cg-sk-4", "cg-sk-5", "cg-sk-6"].map((k) => (
                <Skeleton key={k} className="h-36 w-full" />
              ))}
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {cogTasks?.map((t) => (
                <Card key={t.task_name} className="flex flex-col">
                  <CardHeader className="pb-2">
                    <div className="flex items-start justify-between gap-2">
                      <CardTitle className="text-sm font-medium leading-snug flex items-center gap-1.5">
                        <Zap size={13} style={{ color: "var(--pu)", flexShrink: 0 }} />
                        {t.display_name}
                      </CardTitle>
                      <Badge variant={(cogCategoryColors[t.category] ?? "secondary") as "default" | "secondary" | "blue" | "purple"}>
                        {t.category}
                      </Badge>
                    </div>
                  </CardHeader>
                  <CardContent className="flex flex-col gap-3 flex-1">
                    <p className="text-xs text-(--tx3) flex-1">{t.description}</p>
                    <div className="flex items-center justify-between">
                      <Badge variant="secondary" className="text-xs px-1.5 py-0">
                        {t.runtime.toUpperCase()}
                      </Badge>
                    </div>
                  </CardContent>
                </Card>
              ))}
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
