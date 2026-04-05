"use client";

import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { getLLMConfig, updateLLMConfig, type LLMConfig } from "@/lib/api";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Save, Cpu } from "lucide-react";

type FlatForm = {
  reasoning_url: string;
  reasoning_model_id: string;
  reasoning_timeout_s: number;
  fast_url: string;
  fast_model_id: string;
  fast_timeout_s: number;
  embed_url: string;
  embed_model_id: string;
  embed_timeout_s: number;
  guard_url: string;
  guard_model_id: string;
  guard_timeout_s: number;
  guard_token: string;
  circuit_breaker_threshold: number;
  circuit_breaker_cooldown_s: number;
  max_connections: number;
  max_keepalive: number;
  max_retries: number;
};

function toFlat(d: LLMConfig): FlatForm {
  return {
    reasoning_url: d.reasoning.url,
    reasoning_model_id: d.reasoning.model_id,
    reasoning_timeout_s: d.reasoning.timeout_s,
    fast_url: d.fast.url,
    fast_model_id: d.fast.model_id,
    fast_timeout_s: d.fast.timeout_s,
    embed_url: d.embed.url,
    embed_model_id: d.embed.model_id,
    embed_timeout_s: d.embed.timeout_s,
    guard_url: d.guard.url,
    guard_model_id: d.guard.model_id,
    guard_timeout_s: d.guard.timeout_s,
    guard_token: "",
    circuit_breaker_threshold: d.circuit_breaker_threshold,
    circuit_breaker_cooldown_s: d.circuit_breaker_cooldown_s,
    max_connections: d.max_connections,
    max_keepalive: d.max_keepalive,
    max_retries: d.max_retries,
  };
}

const BACKEND_SECTIONS = [
  { key: "reasoning", label: "Reasoning" },
  { key: "fast", label: "Fast" },
  { key: "embed", label: "Embed" },
  { key: "guard", label: "Guard" },
] as const;

function FieldRow({ label, children }: Readonly<{ label: string; children: React.ReactNode }>) {
  return (
    <div className="grid grid-cols-[160px_1fr] items-center gap-3">
      <Label className="text-right text-(--tx3) text-sm">{label}</Label>
      {children}
    </div>
  );
}

export default function LLMPanel() {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<FlatForm | null>(null);

  const { data, isLoading, error } = useQuery<LLMConfig>({
    queryKey: ["settings", "llm"],
    queryFn: getLLMConfig,
    staleTime: 30_000,
  });

  useEffect(() => {
    if (data && !form) setForm(toFlat(data));
  }, [data, form]);

  const saveMut = useMutation({
    mutationFn: (f: FlatForm) => {
      const body: Parameters<typeof updateLLMConfig>[0] = {
        reasoning_url: f.reasoning_url,
        reasoning_model_id: f.reasoning_model_id,
        reasoning_timeout_s: f.reasoning_timeout_s,
        fast_url: f.fast_url,
        fast_model_id: f.fast_model_id,
        fast_timeout_s: f.fast_timeout_s,
        embed_url: f.embed_url,
        embed_model_id: f.embed_model_id,
        embed_timeout_s: f.embed_timeout_s,
        guard_url: f.guard_url,
        guard_model_id: f.guard_model_id,
        guard_timeout_s: f.guard_timeout_s,
        circuit_breaker_threshold: f.circuit_breaker_threshold,
        circuit_breaker_cooldown_s: f.circuit_breaker_cooldown_s,
        max_connections: f.max_connections,
        max_keepalive: f.max_keepalive,
        max_retries: f.max_retries,
      };
      if (f.guard_token.trim()) body.guard_token = f.guard_token;
      return updateLLMConfig(body);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["settings"] });
      setForm(f => f ? { ...f, guard_token: "" } : f);
      toast.success("LLM settings saved");
    },
    onError: (e) => toast.error(String(e)),
  });

  if (isLoading) return (
    <div className="flex flex-col gap-4">
      {[1, 2, 3].map(i => <Skeleton key={i} className="h-32 w-full rounded-[10px]" />)}
    </div>
  );

  if (error || !data) return (
    <p className="text-(--er) text-sm">Failed to load: {(error as Error)?.message ?? "Unknown error"}</p>
  );

  if (!form) return null;

  const set = <K extends keyof FlatForm>(key: K, val: FlatForm[K]) =>
    setForm(f => f ? { ...f, [key]: val } : f);

  return (
    <div className="flex flex-col gap-5">
      {BACKEND_SECTIONS.map(({ key, label }) => {
        let sectionDescription: React.ReactNode;
        if (label === "Guard") {
          sectionDescription = data.guard_token_set ? (
            <span className="inline-flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-(--ok) inline-block" />
              <span className="text-(--ok) text-xs font-medium">Token configured</span>
            </span>
          ) : (
            <span className="inline-flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-(--wa) inline-block" />
              <span className="text-(--wa) text-xs font-medium">Token not configured</span>
            </span>
          );
        } else {
          sectionDescription = `Configure the ${label.toLowerCase()} LLM endpoint`;
        }
        return (
        <Card key={key} className="bg-(--sl2) border-[oklch(0.24_0.012_255)]">
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-[15px] font-(--fD)">
              <Cpu className="h-4 w-4 text-(--tx3)" />
              {label} Backend
            </CardTitle>
            <CardDescription className="text-(--tx3) text-sm">
              {sectionDescription}
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            <FieldRow label="URL">
              <Input
                value={form[`${key}_url` as keyof FlatForm] as string}
                onChange={e => set(`${key}_url` as keyof FlatForm, e.target.value as FlatForm[keyof FlatForm])}
                placeholder="http://localhost:11434"
              />
            </FieldRow>
            <FieldRow label="Model ID">
              <Input
                value={form[`${key}_model_id` as keyof FlatForm] as string}
                onChange={e => set(`${key}_model_id` as keyof FlatForm, e.target.value as FlatForm[keyof FlatForm])}
                placeholder="llama3.2"
              />
            </FieldRow>
            <FieldRow label="Timeout (s)">
              <Input
                type="number"
                min={1}
                max={300}
                value={form[`${key}_timeout_s` as keyof FlatForm] as number}
                onChange={e => set(`${key}_timeout_s` as keyof FlatForm, Number(e.target.value) as FlatForm[keyof FlatForm])}
              />
            </FieldRow>
            {key === "guard" && (
              <FieldRow label="Guard Token">
                <Input
                  type="password"
                  value={form.guard_token}
                  onChange={e => set("guard_token", e.target.value)}
                  placeholder="•••••••• (enter new value to change)"
                />
              </FieldRow>
            )}
          </CardContent>
        </Card>
        );
      })}

      <Card className="bg-(--sl2) border-[oklch(0.24_0.012_255)]">
        <CardHeader className="pb-3">
          <CardTitle className="text-[15px] font-(--fD)">Circuit Breaker &amp; Connections</CardTitle>
          <CardDescription className="text-(--tx3) text-sm">Resilience and connection pool limits</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <FieldRow label="CB Threshold">
            <Input type="number" min={1} max={100} value={form.circuit_breaker_threshold}
              onChange={e => set("circuit_breaker_threshold", Number(e.target.value))} />
          </FieldRow>
          <FieldRow label="CB Cooldown (s)">
            <Input type="number" min={1} max={3600} value={form.circuit_breaker_cooldown_s}
              onChange={e => set("circuit_breaker_cooldown_s", Number(e.target.value))} />
          </FieldRow>
          <FieldRow label="Max Connections">
            <Input type="number" min={1} max={500} value={form.max_connections}
              onChange={e => set("max_connections", Number(e.target.value))} />
          </FieldRow>
          <FieldRow label="Max Keepalive">
            <Input type="number" min={1} max={500} value={form.max_keepalive}
              onChange={e => set("max_keepalive", Number(e.target.value))} />
          </FieldRow>
          <FieldRow label="Max Retries">
            <Input type="number" min={0} max={10} value={form.max_retries}
              onChange={e => set("max_retries", Number(e.target.value))} />
          </FieldRow>
        </CardContent>
      </Card>

      <div className="flex justify-end">
        <Button onClick={() => form && saveMut.mutate(form)} disabled={saveMut.isPending}>
          <Save className="h-4 w-4" />
          {saveMut.isPending ? "Saving…" : "Save LLM Settings"}
        </Button>
      </div>
    </div>
  );
}
