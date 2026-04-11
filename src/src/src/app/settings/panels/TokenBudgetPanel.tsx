"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { getTokenBudgets, updateTokenBudget, type TokenBudgetConfig } from "@/lib/api";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Save, Coins } from "lucide-react";

type RowState = { tokens_per_hour: number; dirty: boolean };

export default function TokenBudgetPanel() {
  const queryClient = useQueryClient();
  // Sparse overrides: only callers the user has explicitly edited are stored
  // here. This eliminates the useEffect that called setRows synchronously
  // (react-hooks/set-state-in-effect violation).
  const [overrides, setOverrides] = useState<Record<string, RowState>>({});

  const { data, isLoading, error } = useQuery<TokenBudgetConfig[]>({
    queryKey: ["settings", "token-budgets"],
    queryFn: getTokenBudgets,
    staleTime: 30_000,
  });

  const saveMut = useMutation({
    mutationFn: ({ caller, tokens_per_hour }: { caller: string; tokens_per_hour: number }) =>
      updateTokenBudget(caller, { tokens_per_hour }),
    onSuccess: (_data, vars) => {
      queryClient.invalidateQueries({ queryKey: ["settings", "token-budgets"] });
      // Remove the override so the component shows the fresh API value after refetch
      setOverrides(r => { const next = { ...r }; delete next[vars.caller]; return next; });
      toast.success(`Saved budget for ${vars.caller}`);
    },
    onError: (e) => toast.error(String(e)),
  });

  if (isLoading) return (
    <div className="flex flex-col gap-2">
      {[1, 2, 3, 4].map(i => <Skeleton key={i} className="h-10 w-full rounded-lg" />)}
    </div>
  );

  if (error || !data) return (
    <p className="text-(--er) text-sm">Failed to load: {(error as Error)?.message ?? "Unknown error"}</p>
  );

  return (
    <Card className="bg-(--sl2) border-[oklch(0.24_0.012_255)]">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-[15px] font-(--fD)">
          <Coins className="h-4 w-4 text-(--tx3)" />
          Token Budgets
        </CardTitle>
        <CardDescription className="text-(--tx3) text-sm">
          Per-caller hourly token limits. Edit inline and save each row individually.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow className="border-[oklch(0.24_0.012_255)]">
              <TableHead className="text-(--tx3)">Caller</TableHead>
              <TableHead className="text-(--tx3)">Tokens / hour</TableHead>
              <TableHead className="text-(--tx3)">Spike multiplier</TableHead>
              <TableHead />
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.map(budget => {
              const row = overrides[budget.caller];
              return (
                <TableRow key={budget.caller} className="border-[oklch(0.24_0.012_255)]">
                  <TableCell className="font-(--fM) text-sm text-(--tx1)">{budget.caller}</TableCell>
                  <TableCell>
                    <Input
                      type="number"
                      min={0}
                      className="w-36"
                      value={row?.tokens_per_hour ?? budget.tokens_per_hour}
                      onChange={e =>
                        setOverrides(r => ({
                          ...r,
                          [budget.caller]: { tokens_per_hour: Number(e.target.value), dirty: true },
                        }))
                      }
                    />
                  </TableCell>
                  <TableCell className="text-(--tx3)">{budget.spike_multiplier}×</TableCell>
                  <TableCell className="text-right">
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={!row?.dirty || saveMut.isPending}
                      onClick={() =>
                        saveMut.mutate({ caller: budget.caller, tokens_per_hour: row?.tokens_per_hour ?? budget.tokens_per_hour })
                      }
                    >
                      <Save className="h-3.5 w-3.5" />
                      Save
                    </Button>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
        {data.length === 0 && (
          <p className="text-(--tx3) text-sm text-center py-6">No token budgets configured.</p>
        )}
      </CardContent>
    </Card>
  );
}
