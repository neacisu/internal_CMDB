"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  getNotificationChannels,
  createNotificationChannel,
  deleteNotificationChannel,
  testNotificationChannel,
  type NotificationChannel,
  type NotificationChannelCreate,
} from "@/lib/api";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
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
  DialogTrigger,
  DialogClose,
} from "@/components/ui/dialog";
import { Bell, Plus, Trash2, Zap } from "lucide-react";

const BLANK_FORM: NotificationChannelCreate = {
  name: "",
  target_url: "",
  hmac_secret: "",
  events: [],
  is_active: true,
};

const KNOWN_EVENTS = [
  "hitl.created",
  "hitl.resolved",
  "hitl.escalated",
  "job.failed",
  "job.completed",
  "alert.fired",
  "snapshot.done",
];

export default function NotificationsPanel() {
  const queryClient = useQueryClient();
  const [addOpen, setAddOpen] = useState(false);
  const [newForm, setNewForm] = useState<NotificationChannelCreate>({ ...BLANK_FORM });
  const [eventsInput, setEventsInput] = useState("");

  const { data, isLoading, error } = useQuery<NotificationChannel[]>({
    queryKey: ["settings", "notifications"],
    queryFn: getNotificationChannels,
    staleTime: 30_000,
  });

  const createMut = useMutation({
    mutationFn: (body: NotificationChannelCreate) => createNotificationChannel(body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["settings", "notifications"] });
      toast.success("Notification channel created");
      setAddOpen(false);
      setNewForm({ ...BLANK_FORM });
      setEventsInput("");
    },
    onError: (e) => toast.error(String(e)),
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => deleteNotificationChannel(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["settings", "notifications"] });
      toast.success("Channel deleted");
    },
    onError: (e) => toast.error(String(e)),
  });

  const testMut = useMutation({
    mutationFn: (id: string) => testNotificationChannel(id),
    onSuccess: (result) => {
      if (result.success) {
        toast.success(
          `Test passed — ${result.status_code ?? "2xx"} in ${result.latency_ms ?? "?"}ms`
        );
      } else {
        toast.error(`Test failed: ${result.error ?? "unknown error"}`);
      }
    },
    onError: (e) => toast.error(String(e)),
  });

  const handleCreate = () => {
    const events = eventsInput
      .split(",")
      .map(s => s.trim())
      .filter(Boolean);
    createMut.mutate({ ...newForm, events });
  };

  if (isLoading) return (
    <div className="flex flex-col gap-2">
      {[1, 2, 3].map(i => <Skeleton key={i} className="h-10 w-full rounded-[8px]" />)}
    </div>
  );

  if (error) return (
    <p className="text-(--er) text-sm">Failed to load: {(error as Error)?.message ?? "Unknown error"}</p>
  );

  return (
    <Card className="bg-(--sl2) border-[oklch(0.24_0.012_255)]">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2 text-[15px] font-(--fD)">
              <Bell className="h-4 w-4 text-(--tx3)" />
              Notification Channels
            </CardTitle>
            <CardDescription className="text-(--tx3) text-sm mt-0.5">
              Webhook channels that receive event notifications.
            </CardDescription>
          </div>
          <Dialog open={addOpen} onOpenChange={setAddOpen}>
            <DialogTrigger asChild>
              <Button size="sm" variant="outline">
                <Plus className="h-3.5 w-3.5" />
                Add Channel
              </Button>
            </DialogTrigger>
            <DialogContent className="bg-(--sl2) border-[oklch(0.24_0.012_255)] text-(--tx1)">
              <DialogHeader>
                <DialogTitle className="font-(--fD)">Add Notification Channel</DialogTitle>
              </DialogHeader>
              <div className="flex flex-col gap-4 pt-2">
                <div className="flex flex-col gap-1.5">
                  <Label className="text-(--tx3) text-sm">Name</Label>
                  <Input
                    value={newForm.name}
                    onChange={e => setNewForm(f => ({ ...f, name: e.target.value }))}
                    placeholder="Slack alerts"
                  />
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label className="text-(--tx3) text-sm">Webhook URL</Label>
                  <Input
                    value={newForm.target_url}
                    onChange={e => setNewForm(f => ({ ...f, target_url: e.target.value }))}
                    placeholder="https://hooks.slack.com/..."
                  />
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label className="text-(--tx3) text-sm">HMAC Secret (optional)</Label>
                  <Input
                    type="password"
                    value={newForm.hmac_secret ?? ""}
                    onChange={e => setNewForm(f => ({ ...f, hmac_secret: e.target.value }))}
                    placeholder="Leave blank to skip"
                  />
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label className="text-(--tx3) text-sm">
                    Events (comma-separated)
                  </Label>
                  <Input
                    value={eventsInput}
                    onChange={e => setEventsInput(e.target.value)}
                    placeholder="hitl.created, job.failed"
                  />
                  <div className="flex flex-wrap gap-1.5 mt-1">
                    {KNOWN_EVENTS.map(ev => (
                      <button
                        key={ev}
                        type="button"
                        onClick={() => setEventsInput(s => s ? `${s}, ${ev}` : ev)}
                        className="rounded-[5px] bg-(--sl3) border border-[oklch(0.24_0.012_255)] px-2 py-0.5 text-xs text-(--tx3) hover:text-(--tx1) cursor-pointer transition-colors"
                      >
                        {ev}
                      </button>
                    ))}
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <input
                    id="ch-active"
                    type="checkbox"
                    checked={newForm.is_active}
                    onChange={e => setNewForm(f => ({ ...f, is_active: e.target.checked }))}
                    className="h-4 w-4 rounded accent-[var(--ok)] cursor-pointer"
                  />
                  <Label htmlFor="ch-active" className="cursor-pointer text-sm">Active</Label>
                </div>
                <div className="flex justify-end gap-2 pt-1">
                  <DialogClose asChild>
                    <Button variant="ghost" size="sm">Cancel</Button>
                  </DialogClose>
                  <Button
                    size="sm"
                    onClick={handleCreate}
                    disabled={createMut.isPending || !newForm.name || !newForm.target_url}
                  >
                    {createMut.isPending ? "Creating…" : "Create Channel"}
                  </Button>
                </div>
              </div>
            </DialogContent>
          </Dialog>
        </div>
      </CardHeader>
      <CardContent>
        {!data || data.length === 0 ? (
          <p className="text-(--tx3) text-sm text-center py-6">
            No notification channels configured.
          </p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow className="border-[oklch(0.24_0.012_255)]">
                <TableHead className="text-(--tx3)">Name</TableHead>
                <TableHead className="text-(--tx3)">Target URL</TableHead>
                <TableHead className="text-(--tx3)">Events</TableHead>
                <TableHead className="text-(--tx3)">Status</TableHead>
                <TableHead className="text-(--tx3)">HMAC</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.map(ch => (
                <TableRow key={ch.channel_id} className="border-[oklch(0.24_0.012_255)]">
                  <TableCell className="font-medium text-sm">{ch.name}</TableCell>
                  <TableCell className="text-(--tx3) text-xs font-(--fM) max-w-[180px] truncate">
                    {ch.target_url ?? "—"}
                  </TableCell>
                  <TableCell>
                    <div className="flex flex-wrap gap-1">
                      {ch.events.map(ev => (
                        <span
                          key={ev}
                          className="rounded-[4px] bg-(--sl3) px-1.5 py-0.5 text-[11px] text-(--tx3) font-(--fM)"
                        >
                          {ev}
                        </span>
                      ))}
                    </div>
                  </TableCell>
                  <TableCell>
                    <span className={`text-xs font-medium ${ch.is_active ? "text-(--ok)" : "text-(--tx3)"}`}>
                      {ch.is_active ? "Active" : "Inactive"}
                    </span>
                  </TableCell>
                  <TableCell>
                    <span className={`text-xs ${ch.hmac_configured ? "text-(--ok)" : "text-(--tx3)"}`}>
                      {ch.hmac_configured ? "Configured" : "None"}
                    </span>
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-1.5 justify-end">
                      <Button
                        size="xs"
                        variant="ghost"
                        disabled={testMut.isPending}
                        onClick={() => testMut.mutate(ch.channel_id)}
                        title="Send test event"
                      >
                        <Zap className="h-3.5 w-3.5" />
                        Test
                      </Button>
                      <Button
                        size="xs"
                        variant="destructive"
                        disabled={deleteMut.isPending}
                        onClick={() => deleteMut.mutate(ch.channel_id)}
                        title="Delete channel"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}
