"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  getTimelinesAIConfig,
  saveTimelinesAIConfig,
  testTimelinesAIConnection,
  type TimelinesAIConfig,
} from "@/lib/api";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
  MessageSquare,
  Save,
  Zap,
  Webhook,
  ChevronDown,
  CheckCircle,
  XCircle,
  Eye,
  EyeOff,
  ExternalLink,
} from "lucide-react";

const WEBHOOK_EVENTS = [
  { value: "message:received:new", label: "Message received", description: "Incoming WhatsApp message" },
  { value: "message:sent:new", label: "Message sent", description: "Outgoing message processed" },
  { value: "chat:received:created", label: "New incoming chat", description: "Contact initiates conversation" },
  { value: "chat:sent:created", label: "New outgoing chat", description: "You start conversation" },
  { value: "chat:assigned", label: "Chat assigned", description: "Chat reassigned to team member" },
  { value: "chat:unassigned", label: "Chat unassigned", description: "Chat assignment removed" },
];

const BLANK: TimelinesAIConfig = {
  enabled: false,
  api_token: "",
  webhook_secret: "",
  subscribed_events: ["message:received:new"],
  auto_reply_enabled: false,
  auto_reply_template: "",
};

function MaskedInput({ value, onChange, placeholder, id }: Readonly<{
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  id?: string;
}>) {
  const [show, setShow] = useState(false);
  return (
    <div className="relative">
      <Input
        id={id}
        type={show ? "text" : "password"}
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
        className="pr-9"
        autoComplete="off"
      />
      <button
        type="button"
        onClick={() => setShow(s => !s)}
        className="absolute right-2.5 top-1/2 -translate-y-1/2 text-(--tx3) hover:text-(--tx1) transition-colors"
        aria-label={show ? "Hide" : "Show"}
      >
        {show ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
      </button>
    </div>
  );
}

export default function IntegrationsPanel() {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<TimelinesAIConfig | null>(null);
  const [webhookOpen, setWebhookOpen] = useState(false);

  const { isLoading } = useQuery<TimelinesAIConfig>({
    queryKey: ["settings", "integrations", "timelinesai"],
    queryFn: getTimelinesAIConfig,
    onSuccess: (data) => {
      if (!form) setForm(data);
    },
  } as Parameters<typeof useQuery>[0]);

  const saveMutation = useMutation({
    mutationFn: (cfg: TimelinesAIConfig) => saveTimelinesAIConfig(cfg),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["settings", "integrations", "timelinesai"] });
      toast.success("TimelinesAI configuration saved");
    },
    onError: (e: Error) => toast.error(`Save failed: ${e.message}`),
  });

  const testMutation = useMutation({
    mutationFn: testTimelinesAIConnection,
    onSuccess: (res) => {
      if (res.ok) {
        toast.success(`Connected — workspace: ${res.workspace_name ?? "OK"}`);
      } else {
        toast.error(`Connection failed: ${res.error ?? "Unknown error"}`);
      }
    },
    onError: (e: Error) => toast.error(`Test failed: ${e.message}`),
  });

  const set = <K extends keyof TimelinesAIConfig>(key: K, value: TimelinesAIConfig[K]) =>
    setForm(f => f ? { ...f, [key]: value } : f);

  const toggleEvent = (event: string) => {
    if (!form) return;
    const current = form.subscribed_events;
    const updated = current.includes(event)
      ? current.filter(e => e !== event)
      : [...current, event];
    set("subscribed_events", updated);
  };

  if (isLoading || !form) {
    return (
      <div className="flex flex-col gap-4">
        <Skeleton className="h-64 w-full rounded-[10px]" />
        <Skeleton className="h-40 w-full rounded-[10px]" />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-5">

      {/* TimelinesAI Card */}
      <Card className="bg-(--sl2) border-[oklch(0.24_0.012_255)]">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="h-8 w-8 rounded-lg bg-[oklch(0.22_0.04_255)] flex items-center justify-center">
                <MessageSquare className="h-4 w-4 text-[oklch(0.72_0.18_255)]" />
              </div>
              <div>
                <CardTitle className="text-[15px] font-(--fD) flex items-center gap-2">
                  TimelinesAI
                  <Badge
                    variant="outline"
                    className={form.enabled
                      ? "text-(--ok) border-(--ok) text-[10px] px-1.5 py-0"
                      : "text-(--tx3) text-[10px] px-1.5 py-0"
                    }
                  >
                    {form.enabled ? "Enabled" : "Disabled"}
                  </Badge>
                </CardTitle>
                <CardDescription className="text-(--tx3) text-xs mt-0.5">
                  WhatsApp communication via TimelinesAI Public API
                </CardDescription>
              </div>
            </div>
            <a
              href="https://timelinesai.mintlify.app/introduction"
              target="_blank"
              rel="noopener noreferrer"
              className="text-(--tx3) hover:text-(--tx1) transition-colors"
              title="TimelinesAI docs"
            >
              <ExternalLink className="h-3.5 w-3.5" />
            </a>
          </div>
        </CardHeader>

        <CardContent className="flex flex-col gap-5">

          {/* Enable toggle */}
          <div className="flex items-center justify-between py-2 border-b border-[oklch(0.24_0.012_255)]">
            <div>
              <Label className="text-sm font-(--fM)">Enable integration</Label>
              <p className="text-(--tx3) text-xs mt-0.5">Activate TimelinesAI WhatsApp messaging</p>
            </div>
            <Switch
              checked={form.enabled}
              onCheckedChange={v => set("enabled", v)}
            />
          </div>

          {/* API Token */}
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="tai-token" className="text-sm">API Token</Label>
            <MaskedInput
              id="tai-token"
              value={form.api_token}
              onChange={v => set("api_token", v)}
              placeholder="4d2d0239-e28c-4f4a-8a4d-3a3ca40056b8"
            />
            <p className="text-(--tx3) text-xs">
              Get yours at{" "}
              <a
                href="https://app.timelines.ai/integrations/api"
                target="_blank"
                rel="noopener noreferrer"
                className="text-[oklch(0.72_0.18_255)] hover:underline"
              >
                app.timelines.ai → Integrations → Public API
              </a>
            </p>
          </div>

          {/* Base URL (read-only info) */}
          <div className="flex flex-col gap-1.5">
            <Label className="text-sm">API Base URL</Label>
            <Input
              value="https://app.timelines.ai/integrations/api"
              readOnly
              className="bg-(--sl3) text-(--tx3) text-xs cursor-default"
            />
          </div>

          {/* Test connection */}
          <div className="flex items-center gap-3">
            <Button
              variant="outline"
              size="sm"
              onClick={() => testMutation.mutate()}
              disabled={!form.api_token || testMutation.isPending}
              className="gap-1.5"
            >
              <Zap className="h-3.5 w-3.5" />
              {testMutation.isPending ? "Testing…" : "Test connection"}
            </Button>
            {testMutation.isSuccess && (
              testMutation.data.ok
                ? <span className="flex items-center gap-1 text-(--ok) text-xs"><CheckCircle className="h-3.5 w-3.5" /> Connected</span>
                : <span className="flex items-center gap-1 text-(--er) text-xs"><XCircle className="h-3.5 w-3.5" /> {testMutation.data.error}</span>
            )}
          </div>

          {/* Webhook section */}
          <Collapsible open={webhookOpen} onOpenChange={setWebhookOpen}>
            <CollapsibleTrigger asChild>
              <button
                type="button"
                className="flex items-center gap-2 w-full py-2 border-t border-[oklch(0.24_0.012_255)] text-sm font-(--fM) text-sidebar-foreground hover:text-(--tx1) transition-colors"
              >
                <Webhook className="h-3.5 w-3.5" />
                Webhook configuration
                <ChevronDown className={`h-3.5 w-3.5 ml-auto transition-transform ${webhookOpen ? "rotate-180" : ""}`} />
              </button>
            </CollapsibleTrigger>
            <CollapsibleContent className="flex flex-col gap-4 pt-3">

              {/* Webhook Secret */}
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="tai-secret" className="text-sm">Webhook Secret</Label>
                <MaskedInput
                  id="tai-secret"
                  value={form.webhook_secret}
                  onChange={v => set("webhook_secret", v)}
                  placeholder="Optional — used to verify webhook signatures"
                />
                <p className="text-(--tx3) text-xs">
                  If set, TimelinesAI will include an HMAC-SHA256 signature in webhook headers.
                </p>
              </div>

              {/* Subscribed events */}
              <div className="flex flex-col gap-2">
                <Label className="text-sm">Subscribed events</Label>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {WEBHOOK_EVENTS.map(ev => (
                    <label
                      key={ev.value}
                      aria-label={ev.label}
                      className={`flex items-start gap-2.5 p-2.5 rounded-lg cursor-pointer border transition-colors ${
                        form.subscribed_events.includes(ev.value)
                          ? "bg-(--sl3) border-[oklch(0.32_0.04_255)]"
                          : "border-[oklch(0.24_0.012_255)] hover:bg-(--sl3)"
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={form.subscribed_events.includes(ev.value)}
                        onChange={() => toggleEvent(ev.value)}
                        className="mt-0.5 accent-[oklch(0.72_0.18_255)] shrink-0"
                      />
                      <div>
                        <p className="text-xs font-(--fM) text-(--tx1)">{ev.label}</p>
                        <p className="text-[11px] text-(--tx3)">{ev.description}</p>
                        <code className="text-[10px] text-(--tx3) font-mono">{ev.value}</code>
                      </div>
                    </label>
                  ))}
                </div>
              </div>

              {/* Webhook endpoint info */}
              <div className="flex flex-col gap-1.5">
                <Label className="text-sm">Inbound webhook endpoint</Label>
                <Input
                  value="https://infraq.app/api/v1/integrations/timelinesai/webhook"
                  readOnly
                  className="bg-(--sl3) text-(--tx3) text-xs cursor-default font-mono"
                />
                <p className="text-(--tx3) text-xs">
                  Register this URL in TimelinesAI →{" "}
                  <a
                    href="https://timelinesai.mintlify.app/guides/webhooks"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-[oklch(0.72_0.18_255)] hover:underline"
                  >
                    Webhooks guide
                  </a>
                </p>
              </div>

            </CollapsibleContent>
          </Collapsible>

          {/* Auto-reply section */}
          <div className="flex flex-col gap-3 pt-1 border-t border-[oklch(0.24_0.012_255)]">
            <div className="flex items-center justify-between">
              <div>
                <Label className="text-sm font-(--fM)">Auto-reply</Label>
                <p className="text-(--tx3) text-xs mt-0.5">Send automatic response on new incoming messages</p>
              </div>
              <Switch
                checked={form.auto_reply_enabled}
                onCheckedChange={v => set("auto_reply_enabled", v)}
              />
            </div>
            {form.auto_reply_enabled && (
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="tai-reply" className="text-sm">Reply template</Label>
                <textarea
                  id="tai-reply"
                  value={form.auto_reply_template}
                  onChange={e => set("auto_reply_template", e.target.value)}
                  placeholder="Hi! We received your message and will reply shortly."
                  rows={3}
                  className="w-full rounded-lg border border-[oklch(0.24_0.012_255)] bg-(--sl3) text-(--tx1) text-sm px-3 py-2 resize-none focus:outline-none focus:ring-1 focus:ring-[oklch(0.72_0.18_255)] placeholder:text-(--tx3)"8_255)] placeholder:text-(--tx3)"
                />
              </div>
            )}
          </div>

          {/* Save */}
          <div className="flex justify-end pt-1">
            <Button
              onClick={() => saveMutation.mutate(form)}
              disabled={saveMutation.isPending}
              className="gap-1.5"
            >
              <Save className="h-3.5 w-3.5" />
              {saveMutation.isPending ? "Saving…" : "Save configuration"}
            </Button>
          </div>

        </CardContent>
      </Card>

      {/* Placeholder for future integrations */}
      <Card className="bg-(--sl2) border-[oklch(0.24_0.012_255)] opacity-50">
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-[15px] font-(--fD) text-(--tx3)">
            <MessageSquare className="h-4 w-4" />
            More integrations coming soon
          </CardTitle>
          <CardDescription className="text-(--tx3) text-xs">
            Slack, Telegram, email, and more
          </CardDescription>
        </CardHeader>
      </Card>

    </div>
  );
}
