"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getAgentSessions,
  startAgentSession,
  stopAgentSession,
  type AgentSessionOut,
} from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useRefreshCountdown, fmtTime } from "@/lib/hooks";
import { timeAgo } from "@/lib/utils";
import {
  Brain,
  RefreshCw,
  Play,
  Wrench,
  Eye,
  Lightbulb,
  CheckCircle,
  XCircle,
  Clock,
  Zap,
  Send,
  StopCircle,
} from "lucide-react";

const REFRESH_INTERVAL = 6_000;
const SKELETON_KEYS = ["sk-1", "sk-2", "sk-3", "sk-4", "sk-5"];

function statusBadge(status: string) {
  switch (status) {
    case "running":
      return <Badge className="bg-blue-500/20 text-blue-400 border-blue-500/30">Running</Badge>;
    case "completed":
      return <Badge className="bg-emerald-500/20 text-emerald-400 border-emerald-500/30">Completed</Badge>;
    case "failed":
      return <Badge className="bg-red-500/20 text-red-400 border-red-500/30">Failed</Badge>;
    case "timeout":
      return <Badge className="bg-amber-500/20 text-amber-400 border-amber-500/30">Timeout</Badge>;
    case "budget_exceeded":
      return <Badge className="bg-orange-500/20 text-orange-400 border-orange-500/30">Budget</Badge>;
    default:
      return <Badge variant="outline">{status}</Badge>;
  }
}

function phaseBadge(phase: string) {
  switch (phase) {
    case "think":
      return <Lightbulb className="h-4 w-4 text-amber-400" />;
    case "act":
      return <Wrench className="h-4 w-4 text-blue-400" />;
    case "observe":
      return <Eye className="h-4 w-4 text-emerald-400" />;
    default:
      return <Brain className="h-4 w-4 text-purple-400" />;
  }
}

function SessionDetail({ session }: Readonly<{ session: AgentSessionOut }>) {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4 text-sm">
        <div>
          <span className="text-(--tx3)">Status:</span> {statusBadge(session.status)}
        </div>
        <div>
          <span className="text-(--tx3)">Model:</span>{" "}
          <Badge variant="outline">{session.model_used}</Badge>
        </div>
        <div>
          <span className="text-(--tx3)">Iterations:</span> {session.iterations}
        </div>
        <div>
          <span className="text-(--tx3)">Tokens:</span>{" "}
          {session.tokens_used.toLocaleString()}
        </div>
      </div>

      {session.final_answer && (
        <Card className="bg-emerald-500/5 border-emerald-500/20">
          <CardHeader className="p-3">
            <CardTitle className="text-sm text-emerald-400">Final Answer</CardTitle>
          </CardHeader>
          <CardContent className="p-3 pt-0 text-sm whitespace-pre-wrap">
            {session.final_answer}
          </CardContent>
        </Card>
      )}

      {session.error && (
        <Card className="bg-red-500/5 border-red-500/20">
          <CardHeader className="p-3">
            <CardTitle className="text-sm text-red-400">Error</CardTitle>
          </CardHeader>
          <CardContent className="p-3 pt-0 text-sm">{session.error}</CardContent>
        </Card>
      )}

      <div>
        <h4 className="text-sm font-medium mb-2 text-sidebar-foreground">ReAct Loop Steps</h4>
        <ScrollArea className="h-75">
          <div className="space-y-2">
            {session.conversation.map((step) => (
              <div
                key={`step-${step.iteration}-${step.phase}`}
                className="flex items-start gap-2 p-2 rounded bg-(--sl2)"
              >
                <div className="flex items-center gap-1 min-w-20">
                  {phaseBadge(step.phase)}
                  <span className="text-xs text-(--tx3) capitalize">{step.phase}</span>
                </div>
                <span className="text-xs text-sidebar-foreground line-clamp-3">{step.content}</span>
              </div>
            ))}
          </div>
        </ScrollArea>
      </div>

      {session.tool_calls.length > 0 && (
        <div>
          <h4 className="text-sm font-medium mb-2 text-sidebar-foreground">Tool Calls</h4>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Tool</TableHead>
                <TableHead>Success</TableHead>
                <TableHead>Result</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {session.tool_calls.map((tc) => (
                <TableRow key={`tc-${tc.tool}-${String(tc.success)}`}>
                  <TableCell className="font-mono text-xs">{tc.tool}</TableCell>
                  <TableCell>
                    {tc.success ? (
                      <CheckCircle className="h-4 w-4 text-emerald-400" />
                    ) : (
                      <XCircle className="h-4 w-4 text-red-400" />
                    )}
                  </TableCell>
                  <TableCell className="text-xs max-w-75 truncate">
                    {JSON.stringify(tc.result).slice(0, 100)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}

export default function AgentDashboardPage() {
  const queryClient = useQueryClient();
  const [goal, setGoal] = useState("");
  const [selectedSession, setSelectedSession] = useState<AgentSessionOut | null>(null);

  // useQuery must be declared before useRefreshCountdown so that
  // dataUpdatedAt (epoch-ms of the last successful fetch) is available.
  const { data: sessions, isLoading, dataUpdatedAt } = useQuery({
    queryKey: ["agent-sessions"],
    queryFn: () => getAgentSessions("limit=20"),
    refetchInterval: REFRESH_INTERVAL,
  });

  const countdown = useRefreshCountdown(dataUpdatedAt, REFRESH_INTERVAL);

  const startMutation = useMutation({
    mutationFn: (g: string) => startAgentSession({ goal: g }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["agent-sessions"] });
      setGoal("");
    },
  });

  const stopMutation = useMutation({
    mutationFn: (sessionId: string) => stopAgentSession(sessionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["agent-sessions"] });
      setSelectedSession(null);
    },
  });

  const handleStart = () => {
    if (goal.trim()) {
      startMutation.mutate(goal.trim());
    }
  };

  const runningCount = sessions?.filter((s) => s.status === "running").length ?? 0;
  const completedCount = sessions?.filter((s) => s.status === "completed").length ?? 0;
  const totalTokens = sessions?.reduce((sum, s) => sum + s.tokens_used, 0) ?? 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Brain className="h-6 w-6 text-purple-400" />
          <h1 className="text-xl font-semibold">Cognitive Agent</h1>
          <Badge variant="outline" className="text-emerald-400 border-emerald-500/30">
            LIVE
          </Badge>
          <span className="text-xs text-(--tx3)">{fmtTime(countdown.lastRefreshed)}</span>
        </div>
        <Button
          size="sm"
          variant="outline"
          onClick={() => queryClient.invalidateQueries({ queryKey: ["agent-sessions"] })}
        >
          <RefreshCw className="h-3.5 w-3.5 mr-1.5" /> Refresh
        </Button>
      </div>

      {/* Start new session */}
      <Card>
        <CardHeader className="p-4">
          <CardTitle className="text-sm">Start Agent Session</CardTitle>
        </CardHeader>
        <CardContent className="p-4 pt-0">
          <form
            className="flex gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              handleStart();
            }}
          >
            <Input
              placeholder="Describe a goal (e.g. 'investigate disk usage on hz.223')"
              value={goal}
              onChange={(e) => setGoal(e.target.value)}
              className="flex-1"
            />
            <Button
              type="submit"
              disabled={!goal.trim() || startMutation.isPending}
              className="bg-purple-600 hover:bg-purple-700"
            >
              {startMutation.isPending ? (
                <Clock className="h-4 w-4 mr-1 animate-spin" />
              ) : (
                <Play className="h-4 w-4 mr-1" />
              )}
              Start
            </Button>
          </form>
        </CardContent>
      </Card>

      {/* KPI Strip */}
      <div className="grid grid-cols-4 gap-4">
        <Card className="p-3">
          <div className="flex items-center gap-2 text-sm text-(--tx3)">
            <Zap className="h-4 w-4 text-blue-400" />
            Running
          </div>
          <div className="text-2xl font-bold">{runningCount}</div>
        </Card>
        <Card className="p-3">
          <div className="flex items-center gap-2 text-sm text-(--tx3)">
            <CheckCircle className="h-4 w-4 text-emerald-400" />
            Completed
          </div>
          <div className="text-2xl font-bold">{completedCount}</div>
        </Card>
        <Card className="p-3">
          <div className="flex items-center gap-2 text-sm text-(--tx3)">
            <Brain className="h-4 w-4 text-purple-400" />
            Total Sessions
          </div>
          <div className="text-2xl font-bold">{sessions?.length ?? 0}</div>
        </Card>
        <Card className="p-3">
          <div className="flex items-center gap-2 text-sm text-(--tx3)">
            <Send className="h-4 w-4 text-amber-400" />
            Tokens Used
          </div>
          <div className="text-2xl font-bold">{totalTokens.toLocaleString()}</div>
        </Card>
      </div>

      {/* Sessions table */}
      <Card>
        <CardHeader className="p-4">
          <CardTitle className="text-sm">Recent Agent Sessions</CardTitle>
        </CardHeader>
        <CardContent className="p-4 pt-0">
          {isLoading && (
            <div className="space-y-2">
              {SKELETON_KEYS.map((k) => (
                <Skeleton key={k} className="h-10 w-full" />
              ))}
            </div>
          )}
          {!isLoading && sessions && sessions.length > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Goal</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Model</TableHead>
                  <TableHead>Iterations</TableHead>
                  <TableHead>Tokens</TableHead>
                  <TableHead>Tools</TableHead>
                  <TableHead>Started</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {sessions.map((s) => (
                  <TableRow
                    key={s.session_id}
                    className="cursor-pointer hover:bg-(--sl2)"
                    onClick={() => setSelectedSession(s)}
                  >
                    <TableCell className="max-w-62.5 truncate font-medium">
                      {s.goal}
                    </TableCell>
                    <TableCell>{statusBadge(s.status)}</TableCell>
                    <TableCell>
                      <Badge variant="outline" className="text-xs">
                        {s.model_used}
                      </Badge>
                    </TableCell>
                    <TableCell>{s.iterations}</TableCell>
                    <TableCell>{s.tokens_used.toLocaleString()}</TableCell>
                    <TableCell>{s.tool_calls.length}</TableCell>
                    <TableCell className="text-xs text-(--tx3)">
                      {timeAgo(s.created_at)}
                    </TableCell>
                    <TableCell>
                      <Button size="sm" variant="ghost">
                        <Eye className="h-3.5 w-3.5" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
          {!isLoading && (!sessions || sessions.length === 0) && (
            <div className="flex flex-col items-center justify-center py-12 text-(--tx3)">
              <Brain className="h-12 w-12 mb-3 opacity-20" />
              <p className="text-sm">No agent sessions yet</p>
              <p className="text-xs mt-1">Start a session above to investigate an issue</p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Session detail dialog */}
      <Dialog open={!!selectedSession} onOpenChange={() => setSelectedSession(null)}>
        <DialogContent className="max-w-3xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Brain className="h-5 w-5 text-purple-400" />
              Agent Session
            </DialogTitle>
          </DialogHeader>
          {selectedSession && (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <p className="text-sm font-medium">{selectedSession.goal}</p>
                {selectedSession.status === "running" && (
                  <Button
                    size="sm"
                    variant="destructive"
                    disabled={stopMutation.isPending}
                    onClick={() => stopMutation.mutate(selectedSession.session_id)}
                  >
                    <StopCircle className="h-3.5 w-3.5 mr-1" />
                    {stopMutation.isPending ? "Stopping…" : "Force Stop"}
                  </Button>
                )}
              </div>
              <SessionDetail session={selectedSession} />
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
