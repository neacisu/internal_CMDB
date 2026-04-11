"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  getUserPreferences,
  updateUserPreference,
  deleteUserPreference,
  type UserPreference,
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
import { Save, Trash2, SlidersHorizontal } from "lucide-react";
import { timeAgo } from "@/lib/utils";

function safeJson(v: unknown): string {
  try {
    return JSON.stringify(v, null, 2);
  } catch {
    return String(v);
  }
}

function parseJsonSafe(s: string): { ok: true; value: unknown } | { ok: false; error: string } {
  try {
    return { ok: true, value: JSON.parse(s) };
  } catch (e) {
    return { ok: false, error: (e as Error).message };
  }
}

export default function PreferencesPanel() {
  const queryClient = useQueryClient();
  const [newKey, setNewKey] = useState("");
  const [newValue, setNewValue] = useState("");
  const [newValueError, setNewValueError] = useState<string | null>(null);

  const { data, isLoading, error } = useQuery<UserPreference[]>({
    queryKey: ["settings", "preferences"],
    queryFn: getUserPreferences,
    staleTime: 30_000,
  });

  const saveMut = useMutation({
    mutationFn: ({ key, value }: { key: string; value: unknown }) =>
      updateUserPreference(key, value),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["settings", "preferences"] });
      toast.success("Preference saved");
      setNewKey("");
      setNewValue("");
      setNewValueError(null);
    },
    onError: (e) => toast.error(String(e)),
  });

  const deleteMut = useMutation({
    mutationFn: (key: string) => deleteUserPreference(key),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["settings", "preferences"] });
      toast.success("Preference deleted");
    },
    onError: (e) => toast.error(String(e)),
  });

  const handleAdd = () => {
    if (!newKey.trim()) {
      toast.error("Key is required");
      return;
    }
    const parsed = parseJsonSafe(newValue || "null");
    if (!parsed.ok) {
      setNewValueError(`Invalid JSON: ${parsed.error}`);
      return;
    }
    setNewValueError(null);
    saveMut.mutate({ key: newKey.trim(), value: parsed.value });
  };

  if (isLoading) return (
    <div className="flex flex-col gap-3">
      {[1, 2, 3].map(i => <Skeleton key={i} className="h-10 w-full rounded-[8px]" />)}
    </div>
  );

  if (error) return (
    <p className="text-(--er) text-sm">Failed to load: {(error as Error)?.message ?? "Unknown error"}</p>
  );

  return (
    <div className="flex flex-col gap-5">
      <Card className="bg-(--sl2) border-[oklch(0.24_0.012_255)]">
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-[15px] font-(--fD)">
            <SlidersHorizontal className="h-4 w-4 text-(--tx3)" />
            Your Preferences
          </CardTitle>
          <CardDescription className="text-(--tx3) text-sm">
            Per-user key-value preferences. Values must be valid JSON.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {!data || data.length === 0 ? (
            <p className="text-(--tx3) text-sm text-center py-6">No preferences set yet.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow className="border-[oklch(0.24_0.012_255)]">
                  <TableHead className="text-(--tx3)">Key</TableHead>
                  <TableHead className="text-(--tx3)">Value (JSON)</TableHead>
                  <TableHead className="text-(--tx3)">Updated</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.map(pref => (
                  <TableRow key={pref.preference_key} className="border-[oklch(0.24_0.012_255)]">
                    <TableCell className="font-(--fM) text-sm text-(--tx1)">{pref.preference_key}</TableCell>
                    <TableCell>
                      <pre className="text-xs font-(--fM) text-(--tx3) max-w-[240px] truncate">
                        {safeJson(pref.value)}
                      </pre>
                    </TableCell>
                    <TableCell className="text-(--tx3) text-xs">
                      {pref.updated_at ? timeAgo(pref.updated_at) : "—"}
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        size="xs"
                        variant="destructive"
                        disabled={deleteMut.isPending}
                        onClick={() => deleteMut.mutate(pref.preference_key)}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Card className="bg-(--sl2) border-[oklch(0.24_0.012_255)]">
        <CardHeader className="pb-3">
          <CardTitle className="text-[15px] font-(--fD)">Add / Update Preference</CardTitle>
          <CardDescription className="text-(--tx3) text-sm">
            Setting an existing key will overwrite its value.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="pref-key" className="text-(--tx3) text-sm">Key</Label>
            <Input
              id="pref-key"
              value={newKey}
              onChange={e => setNewKey(e.target.value)}
              placeholder="ui.theme"
              className="w-64"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="pref-value" className="text-(--tx3) text-sm">Value (JSON)</Label>
            <textarea
              id="pref-value"
              rows={3}
              className="flex w-full rounded-[7px] border border-[oklch(0.24_0.012_255)] bg-(--sl2) px-2.75 py-2 text-[14px] text-(--tx1) font-(--fM) placeholder:text-(--tx4) outline-none focus:border-(--g3) focus:shadow-[0_0_0_3px_oklch(0.55_0.22_152/15%)] resize-y"
              placeholder={`"dark"`}
              value={newValue}
              onChange={e => { setNewValue(e.target.value); setNewValueError(null); }}
            />
            {newValueError && (
              <p className="text-(--er) text-xs">{newValueError}</p>
            )}
          </div>
          <div className="flex justify-end">
            <Button onClick={handleAdd} disabled={saveMut.isPending || !newKey.trim()}>
              <Save className="h-4 w-4" />
              {saveMut.isPending ? "Saving…" : "Save Preference"}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
