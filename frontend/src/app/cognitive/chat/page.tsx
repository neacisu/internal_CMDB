"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Brain, Send, User, Sparkles, FileText } from "lucide-react";
import { cognitiveQuery, type NLQueryResponse } from "@/lib/api";

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: NLQueryResponse["sources"];
  confidence?: number;
  tokens_used?: number;
  timestamp: Date;
}

export default function CognitiveChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
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
      <div>
        <h1 className="df-page-title" style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <Brain size={22} style={{ color: "var(--pu)" }} />
          Infrastructure Chat
        </h1>
        <p className="df-page-sub">Ask questions about your infrastructure using natural language</p>
      </div>

      {/* Chat area */}
      <Card className="flex-1 flex flex-col overflow-hidden">
        <ScrollArea className="flex-1 p-4" ref={scrollRef}>
          <div style={{ display: "flex", flexDirection: "column", gap: 16, minHeight: "100%" }}>
            {messages.length === 0 && (
              <div className="flex flex-col items-center justify-center flex-1 text-center py-16 gap-3">
                <Sparkles size={40} style={{ color: "var(--pu)", opacity: 0.5 }} />
                <p className="text-sm font-medium text-(--tx2)">Ask anything about your infrastructure</p>
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
                  <p className="text-sm leading-relaxed whitespace-pre-wrap">{msg.content}</p>

                  {msg.sources && msg.sources.length > 0 && (
                    <div className="mt-3 pt-2 border-t border-border/50">
                      <p className="text-xs text-(--tx3) mb-1.5 flex items-center gap-1">
                        <FileText size={10} /> {msg.sources.length} sources
                        {msg.confidence != null && (
                          <Badge className="ml-2 text-xs px-1 py-0 bg-(--sl3) text-(--tx3)">
                            {(msg.confidence * 100).toFixed(0)}% confidence
                          </Badge>
                        )}
                      </p>
                      <div className="flex flex-wrap gap-1">
                        {msg.sources.map((s, i) => (
                          <Badge
                            key={`${msg.id}:${s.chunk_id}`}
                            className="text-[10px] px-1.5 py-0 bg-(--sl3) text-(--tx3) border-border"
                            title={s.content.slice(0, 200)}
                          >
                            {s.section || `Source ${i + 1}`}
                          </Badge>
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
              placeholder="Ask about your infrastructure…"
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
