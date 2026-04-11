"use client";

import React, { useState, useRef, useEffect, useCallback } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Brain, Send, User, Sparkles, FileText, Wrench, Bot, ChevronDown, ChevronUp } from "lucide-react";
import { cognitiveQuery, startAgentSession, streamAgentSession, type NLQueryResponse } from "@/lib/api";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";

interface ToolCallDisplay {
  tool: string;
  args: Record<string, unknown>;
  result: unknown;
  success: boolean;
}

interface AgentStreamStep {
  phase: string;
  content: string;
  iteration: number;
  timestamp: string;
  tool_call?: { name: string; arguments: Record<string, unknown> } | null;
}

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: NLQueryResponse["sources"];
  confidence?: number;
  tokens_used?: number;
  tool_calls?: ToolCallDisplay[];
  agent_status?: string;
  agent_steps?: AgentStreamStep[];
  timestamp: Date;
}

type SetMessages = React.Dispatch<React.SetStateAction<ChatMessage[]>>;

/** Split <think>…</think> from the rest of the answer. */
function parseThinkBlock(content: string): { thinking: string | null; answer: string } {
  const match = /^<think>([\s\S]*?)<\/think>\s*/i.exec(content);
  if (!match) return { thinking: null, answer: content };
  return { thinking: match[1].trim(), answer: content.slice(match[0].length).trim() };
}

function ThinkingBlock({ thinking }: Readonly<{ thinking: string }>) {
  const [open, setOpen] = useState(false);
  return (
    <div className="mt-2 mb-1">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1 text-xs text-(--tx3) hover:text-sidebar-foreground transition-colors"
      >
        {open ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
        {open ? "Ascunde procesul de gândire" : "Arată procesul de gândire"}
      </button>
      {open && (
        <pre className="mt-1.5 text-xs text-(--tx4) bg-(--sl3) border border-border rounded p-2 whitespace-pre-wrap overflow-auto max-h-64 leading-relaxed">
          {thinking}
        </pre>
      )}
    </div>
  );
}

function stepPhaseColor(phase: string): string {
  if (phase === "act") return "text-amber-500 bg-amber-500/5";
  if (phase === "observe") return "text-emerald-500 bg-emerald-500/5";
  if (phase === "think") return "text-(--tx3)";
  return "text-(--tx4)";
}

function truncateThinkContent(step: AgentStreamStep): string {
  if (step.phase !== "think") return step.content;
  return step.content.length > 300 ? step.content.slice(0, 300) + "…" : step.content;
}

function attachAgentStream(
  es: EventSource,
  placeholderId: string,
  setMessages: SetMessages,
  setLoading: (v: boolean) => void,
  focusInput: () => void,
): void {
  es.onmessage = (evt) => {
    let data: Record<string, unknown>;
    try {
      data = JSON.parse(evt.data) as Record<string, unknown>;
    } catch {
      return;
    }
    if (data.ping) return;

    const step: AgentStreamStep = {
      phase: String(data.phase ?? ""),
      content: String(data.content ?? ""),
      iteration: Number(data.iteration ?? 0),
      timestamp: String(data.timestamp ?? new Date().toISOString()),
      tool_call: (data.tool_call as AgentStreamStep["tool_call"]) ?? null,
    };

    if (data.phase === "done") {
      es.close();
      setLoading(false);
      focusInput();
      setMessages((prev) =>
        prev.map((m) => {
          if (m.id !== placeholderId) return m;
          return {
            ...m,
            content: step.content || "Agent completed.",
            agent_status: "completed",
            agent_steps: [...(m.agent_steps ?? []), step],
          };
        }),
      );
    } else {
      setMessages((prev) =>
        prev.map((m) => {
          if (m.id !== placeholderId) return m;
          return {
            ...m,
            content: step.phase === "think" ? truncateThinkContent(step) : m.content,
            agent_steps: [...(m.agent_steps ?? []), step],
          };
        }),
      );
    }
  };

  es.onerror = () => {
    es.close();
    setLoading(false);
    focusInput();
    setMessages((prev) =>
      prev.map((m) => {
        if (m.id !== placeholderId) return m;
        return { ...m, content: "Agent stream disconnected.", agent_status: "failed" };
      }),
    );
  };
}

export default function CognitiveChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [agentMode, setAgentMode] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const scrollToBottom = useCallback(() => {
    setTimeout(() => {
      scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
    }, 50);
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  const sendMessage = async () => {
    const q = input.trim();
    if (!q || loading) return;

    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: q,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    // Agent mode: background run + SSE streaming (does not use the try/finally below)
    if (agentMode) {
      try {
        const started = await startAgentSession({ goal: q });
        const sessionId = started.session_id;
        const placeholderId = crypto.randomUUID();

        setMessages((prev) => [
          ...prev,
          {
            id: placeholderId,
            role: "assistant",
            content: "Agent is thinking…",
            agent_status: "running",
            agent_steps: [],
            timestamp: new Date(),
          },
        ]);

        const es = streamAgentSession(sessionId);
        attachAgentStream(es, placeholderId, setMessages, setLoading, () => inputRef.current?.focus());
      } catch (err) {
        setLoading(false);
        inputRef.current?.focus();
        setMessages((prev) => [
          ...prev,
          {
            id: crypto.randomUUID(),
            role: "assistant",
            content: `Agent error: ${err instanceof Error ? err.message : "Unknown error"}`,
            timestamp: new Date(),
          },
        ]);
      }
      return;
    }

    // RAG mode
    try {
      const result = await cognitiveQuery(q);
      const assistantMsg: ChatMessage = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: result.answer,
        sources: result.sources,
        confidence: result.confidence,
        tokens_used: result.tokens_used,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: `Error: ${err instanceof Error ? err.message : "Unknown error"}`,
          timestamp: new Date(),
        },
      ]);
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  };

  return (
    <div className="page-in" style={{ display: "flex", flexDirection: "column", gap: 16, height: "calc(100vh - 8rem)" }}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="df-page-title" style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <Brain size={22} style={{ color: "var(--pu)" }} />
            Infrastructure Chat
          </h1>
          <p className="df-page-sub">Ask questions about your infrastructure using natural language</p>
        </div>
        <div className="flex items-center gap-2">
          <Switch id="agent-mode" checked={agentMode} onCheckedChange={setAgentMode} />
          <Label htmlFor="agent-mode" className="text-xs flex items-center gap-1 cursor-pointer">
            <Bot size={14} /> Agent Mode
          </Label>
        </div>
      </div>

      {/* Chat area */}
      <Card className="flex-1 flex flex-col overflow-hidden">
        <ScrollArea className="flex-1 p-4" ref={scrollRef}>
          <div style={{ display: "flex", flexDirection: "column", gap: 16, minHeight: "100%" }}>
            {messages.length === 0 && (
              <div className="flex flex-col items-center justify-center flex-1 text-center py-16 gap-3">
                <Sparkles size={40} style={{ color: "var(--pu)", opacity: 0.5 }} />
                <p className="text-sm font-medium text-sidebar-foreground">Ask anything about your infrastructure</p>
                <div className="flex flex-wrap gap-2 justify-center mt-2">
                  {[
                    "Which hosts have high CPU usage?",
                    "Show GPU utilization across the fleet",
                    "What services are running on production?",
                  ].map((suggestion) => (
                    <button
                      key={suggestion}
                      type="button"
                      className="text-xs px-3 py-1.5 rounded-full border border-border bg-(--sl2) text-(--tx3) hover:border-(--pu)/40 hover:text-(--tx1) transition-colors cursor-pointer"
                      onClick={() => {
                        setInput(suggestion);
                        inputRef.current?.focus();
                      }}
                    >
                      {suggestion}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((msg) => (
              <div key={msg.id} className={`flex gap-3 ${msg.role === "user" ? "justify-end" : ""}`}>
                {msg.role === "assistant" && (
                  <div
                    className="shrink-0 w-7 h-7 rounded-full flex items-center justify-center"
                    style={{ background: "var(--pu)", opacity: 0.9 }}
                  >
                    <Brain size={14} style={{ color: "#fff" }} />
                  </div>
                )}
                <div
                  className={`rounded-lg p-3 max-w-[75%] ${
                    msg.role === "user"
                      ? "bg-primary/15 border border-primary/20"
                      : "bg-(--sl2) border border-border"
                  }`}
                >
                  {(() => {
                    const { thinking, answer } = parseThinkBlock(msg.content);
                    return (
                      <>
                        {thinking && <ThinkingBlock thinking={thinking} />}
                        <p className="text-sm leading-relaxed whitespace-pre-wrap">{answer}</p>
                      </>
                    );
                  })()}

                  {msg.sources && msg.sources.length > 0 && (
                    <div className="mt-3 pt-2 border-t border-border/50">
                      <div className="text-xs text-(--tx3) mb-1.5 flex items-center gap-1">
                        <FileText size={10} /> {msg.sources.length} sources
                        {msg.confidence != null && (
                          <Badge className="ml-2 text-xs px-1 py-0 bg-(--sl3) text-(--tx3)">
                            {(msg.confidence * 100).toFixed(0)}% confidence
                          </Badge>
                        )}
                      </div>
                      <div className="flex flex-wrap gap-1">
                        {msg.sources.map((s, i) => (
                          <Badge
                            key={`${msg.id}:${s.chunk_id}`}
                            className="text-[10px] px-1.5 py-0 bg-(--sl3) text-(--tx3) border-border max-w-45 truncate"
                            title={s.content.slice(0, 200)}
                          >
                            {s.section || `#${i + 1}`}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Live agent steps (SSE streaming) */}
                  {msg.agent_steps && msg.agent_steps.length > 0 && (
                    <div className="mt-3 pt-2 border-t border-border/50">
                      <div className="text-xs text-(--tx3) mb-1.5 flex items-center gap-1">
                        <Bot size={10} /> {msg.agent_steps.length} steps
                        {msg.agent_status && (
                          <Badge className="ml-2 text-xs px-1 py-0 bg-(--sl3) text-(--tx3)">
                            {msg.agent_status}
                          </Badge>
                        )}
                      </div>
                      <div className="flex flex-col gap-0.5 max-h-48 overflow-y-auto">
                        {msg.agent_steps.map((s, i) => (
                          <div
                            key={`${msg.id}:step:${i}`}
                            className={`text-[10px] px-2 py-0.5 rounded font-mono truncate ${stepPhaseColor(s.phase)}`}
                          >
                            <span className="opacity-60">[{s.iteration}/{s.phase}]</span>{" "}
                            {s.content.slice(0, 120)}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Tool calls display (agent mode) */}
                  {msg.tool_calls && msg.tool_calls.length > 0 && (
                    <div className="mt-3 pt-2 border-t border-border/50">
                      <div className="text-xs text-(--tx3) mb-1.5 flex items-center gap-1">
                        <Wrench size={10} /> {msg.tool_calls.length} tool calls
                        {msg.agent_status && (
                          <Badge className="ml-2 text-xs px-1 py-0 bg-(--sl3) text-(--tx3)">
                            {msg.agent_status}
                          </Badge>
                        )}
                      </div>
                      <div className="flex flex-col gap-1">
                        {msg.tool_calls.map((tc, i) => (
                          <div
                            key={`${msg.id}:tool:${i}`}
                            className={`text-[11px] px-2 py-1 rounded border font-mono ${
                              tc.success
                                ? "border-emerald-500/30 bg-emerald-500/5"
                                : "border-red-500/30 bg-red-500/5"
                            }`}
                          >
                            <span className="font-semibold">{tc.tool}</span>
                            <span className="text-(--tx4) ml-1">
                              ({Object.keys(tc.args).join(", ")})
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  <p className="text-[10px] text-(--tx4) mt-1.5" style={{ fontFamily: "var(--fM)" }}>
                    {msg.timestamp.toLocaleTimeString()}
                    {msg.tokens_used ? ` · ${msg.tokens_used} tokens` : ""}
                  </p>
                </div>
                {msg.role === "user" && (
                  <div
                    className="shrink-0 w-7 h-7 rounded-full flex items-center justify-center"
                    style={{ background: "var(--sl3)" }}
                  >
                    <User size={14} style={{ color: "var(--tx2)" }} />
                  </div>
                )}
              </div>
            ))}

            {loading && (
              <div className="flex gap-3">
                <div
                  className="shrink-0 w-7 h-7 rounded-full flex items-center justify-center"
                  style={{ background: "var(--pu)", opacity: 0.9 }}
                >
                  <Brain size={14} style={{ color: "#fff" }} />
                </div>
                <div className="rounded-lg p-3 bg-(--sl2) border border-border">
                  <div className="flex gap-2">
                    <Skeleton className="h-3 w-24" />
                    <Skeleton className="h-3 w-16" />
                    <Skeleton className="h-3 w-20" />
                  </div>
                </div>
              </div>
            )}
          </div>
        </ScrollArea>

        {/* Input */}
        <CardContent className="p-3 border-t border-border shrink-0">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              sendMessage();
            }}
            className="flex gap-2"
          >
            <Input
              ref={inputRef}
              placeholder={agentMode ? "Describe a goal for the agent…" : "Ask about your infrastructure…"}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={loading}
              className="flex-1"
              autoFocus
            />
            <Button type="submit" disabled={loading || !input.trim()} size="sm">
              <Send size={14} />
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
