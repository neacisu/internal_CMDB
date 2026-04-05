"use client";

import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { getObservabilityConfig, updateObservabilityConfig, type ObservabilityConfig } from "@/lib/api";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Save, Activity, RotateCcw } from "lucide-react";

function RestartBadge() {
  return (
    <span className="inline-flex items-center rounded-[5px] bg-(--wa)/15 border border-(--wa)/30 px-1.5 py-0.5 text-[11px] text-(--wa) font-medium leading-none ml-1.5">
      requires restart
    </span>
  );
}

export default function ObservabilityPanel() {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<ObservabilityConfig | null>(null);

  const { data, isLoading, error } = useQuery<ObservabilityConfig>({
    queryKey: ["settings", "observability"],
    queryFn: getObservabilityConfig,
    staleTime: 30_000,
  });

  useEffect(() => {
    if (data && !form) setForm({ ...data });
  }, [data, form]);

  const saveMut = useMutation({
    mutationFn: (f: ObservabilityConfig) => updateObservabilityConfig({
      ...f,
      cors_origins: f.cors_origins,
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["settings"] });
      toast.success("Observability settings saved");
    },
    onError: (e) => toast.error(String(e)),
  });

  if (isLoading) return (
    <div className="flex flex-col gap-4">
      <Skeleton className="h-64 w-full rounded-[10px]" />
    </div>
  );

  if (error || !data) return (
    <p className="text-(--er) text-sm">Failed to load: {(error as Error)?.message ?? "Unknown error"}</p>
  );

  if (!form) return null;

  const corsOriginsText = form.cors_origins.join("\n");

  return (
    <div className="flex flex-col gap-5">
      <Card className="bg-(--sl2) border-[oklch(0.24_0.012_255)]">
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-[15px] font-(--fD)">
            <Activity className="h-4 w-4 text-(--tx3)" />
            OTLP / Tracing
          </CardTitle>
          <CardDescription className="text-(--tx3) text-sm">
            OpenTelemetry export configuration.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <Label className="text-(--tx3) text-sm">
              OTLP Endpoint
              <RestartBadge />
            </Label>
            <Input
              value={form.otlp_endpoint}
              onChange={e => setForm(f => f ? { ...f, otlp_endpoint: e.target.value } : f)}
              placeholder="http://localhost:4317"
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <Label className="text-(--tx3) text-sm">
              OTLP Protocol
              <RestartBadge />
            </Label>
            <Select
              value={form.otlp_protocol}
              onValueChange={v => setForm(f => f ? { ...f, otlp_protocol: v } : f)}
            >
              <SelectTrigger className="w-40 bg-(--sl2) border-[oklch(0.24_0.012_255)] text-(--tx1)">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="bg-(--sl2) border-[oklch(0.24_0.012_255)]">
                <SelectItem value="grpc">grpc</SelectItem>
                <SelectItem value="http">http</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="flex items-center gap-3">
            <input
              id="otlp-insecure"
              type="checkbox"
              checked={form.otlp_insecure}
              onChange={e => setForm(f => f ? { ...f, otlp_insecure: e.target.checked } : f)}
              className="h-4 w-4 rounded border-[oklch(0.24_0.012_255)] accent-[var(--ok)] cursor-pointer"
            />
            <Label htmlFor="otlp-insecure" className="cursor-pointer text-sm">
              Allow insecure OTLP connection
            </Label>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label className="text-(--tx3) text-sm">Sample Rate (0.0–1.0)</Label>
            <Input
              type="number"
              min={0}
              max={1}
              step={0.01}
              className="w-28"
              value={form.sample_rate}
              onChange={e => setForm(f => f ? { ...f, sample_rate: Number(e.target.value) } : f)}
            />
          </div>
        </CardContent>
      </Card>

      <Card className="bg-(--sl2) border-[oklch(0.24_0.012_255)]">
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-[15px] font-(--fD)">
            <RotateCcw className="h-4 w-4 text-(--tx3)" />
            Runtime
          </CardTitle>
          <CardDescription className="text-(--tx3) text-sm">
            Log level, debug mode, and CORS configuration.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <Label className="text-(--tx3) text-sm">
              Log Level
              <RestartBadge />
            </Label>
            <Select
              value={form.log_level}
              onValueChange={v => setForm(f => f ? { ...f, log_level: v } : f)}
            >
              <SelectTrigger className="w-44 bg-(--sl2) border-[oklch(0.24_0.012_255)] text-(--tx1)">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="bg-(--sl2) border-[oklch(0.24_0.012_255)]">
                {["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"].map(l => (
                  <SelectItem key={l} value={l}>{l}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="flex items-center gap-3">
            <input
              id="debug-enabled"
              type="checkbox"
              checked={form.debug_enabled}
              onChange={e => setForm(f => f ? { ...f, debug_enabled: e.target.checked } : f)}
              className="h-4 w-4 rounded border-[oklch(0.24_0.012_255)] accent-[var(--ok)] cursor-pointer"
            />
            <Label htmlFor="debug-enabled" className="cursor-pointer text-sm">
              Enable debug mode
              <RestartBadge />
            </Label>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label className="text-(--tx3) text-sm">
              CORS Origins
              <RestartBadge />
            </Label>
            <p className="text-(--tx3) text-xs">One origin per line, e.g. https://example.com</p>
            <textarea
              rows={4}
              className="flex w-full rounded-[7px] border border-[oklch(0.24_0.012_255)] bg-(--sl2) px-2.75 py-2 text-[14px] text-(--tx1) font-(--fM) placeholder:text-(--tx4) outline-none focus:border-(--g3) focus:shadow-[0_0_0_3px_oklch(0.55_0.22_152/15%)] resize-y"
              placeholder="https://app.example.com"
              value={corsOriginsText}
              onChange={e =>
                setForm(f =>
                  f ? {
                    ...f,
                    cors_origins: e.target.value
                      .split("\n")
                      .map(s => s.trim())
                      .filter(Boolean),
                  } : f
                )
              }
            />
          </div>
        </CardContent>
      </Card>

      <div className="flex justify-end">
        <Button onClick={() => form && saveMut.mutate(form)} disabled={saveMut.isPending}>
          <Save className="h-4 w-4" />
          {saveMut.isPending ? "Saving…" : "Save Observability Settings"}
        </Button>
      </div>
    </div>
  );
}
