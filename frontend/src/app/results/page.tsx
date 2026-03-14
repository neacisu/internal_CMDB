"use client";

import { useQuery } from "@tanstack/react-query";
import { getResultTypes, getCurrentResult, type ResultTypeMeta } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { formatDate } from "@/lib/utils";

function ResultViewer({ type }: { type: string }) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["results", "current", type],
    queryFn: () => getCurrentResult(type),
  });

  if (isLoading) return <Skeleton className="h-64 w-full" />;
  if (isError) return <p className="text-sm text-(--tx3) p-4">Failed to load result</p>;

  return (
    <ScrollArea className="h-[60vh] rounded-[10px] border border-[oklch(0.25_0.01_240)] bg-sidebar-background">
      <pre className="p-4 text-xs text-sidebar-foreground whitespace-pre-wrap wrap-break-word" style={{ fontFamily: "var(--fM)" }}>
        {JSON.stringify(data, null, 2)}
      </pre>
    </ScrollArea>
  );
}

export default function ResultsPage() {
  const { data: types, isLoading } = useQuery<ResultTypeMeta[]>({
    queryKey: ["result-types"],
    queryFn: getResultTypes,
  });

  if (isLoading) return (
    <div className="p-6 space-y-4">
      <Skeleton className="h-8 w-48" />
      <Skeleton className="h-64 w-full" />
    </div>
  );

  if (!types?.length) return (
    <div className="p-6">
      <h1 className="df-page-title" style={{ marginBottom: 16 }}>Results</h1>
      <p className="text-(--tx3)">No result types configured</p>
    </div>
  );

  return (
    <div className="page-in" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <h1 className="df-page-title">Results</h1>

      <Tabs defaultValue={types[0].result_type}>
        <TabsList>
          {types.map((t) => (
            <TabsTrigger key={t.result_type} value={t.result_type}>
              {t.display_name}
            </TabsTrigger>
          ))}
        </TabsList>
        {types.map((t) => (
          <TabsContent key={t.result_type} value={t.result_type} className="mt-4">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0">
                <CardTitle className="text-sm font-medium">{t.display_name}</CardTitle>
                {t.last_modified && (
                  <Badge variant="secondary" className="text-xs">
                    Updated {formatDate(t.last_modified)}
                  </Badge>
                )}
              </CardHeader>
              <CardContent>
                {t.current_file ? (
                  <ResultViewer type={t.result_type} />
                ) : (
                  <p className="text-sm text-(--tx3)">No current result file found</p>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        ))}
      </Tabs>
    </div>
  );
}
