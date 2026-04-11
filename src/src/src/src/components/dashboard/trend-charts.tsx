"use client";

import { useQuery } from "@tanstack/react-query";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";
import { getDashboardTrends, type TrendSeries } from "@/lib/api";
import { Skeleton } from "@/components/ui/skeleton";
import { format } from "date-fns";
import { RefreshCw } from "lucide-react";
import { useRefreshCountdown, fmtTime } from "@/lib/hooks";

const TRENDS_INTERVAL = 120_000;

export function TrendCharts() {
  const { data, isLoading, dataUpdatedAt } = useQuery<TrendSeries[]>({
    queryKey: ["dashboard", "trends"],
    queryFn: getDashboardTrends,
    refetchInterval: TRENDS_INTERVAL,
  });
  const { secsLeft, progress, lastRefreshed } = useRefreshCountdown(dataUpdatedAt, TRENDS_INTERVAL);

  if (isLoading) return <Skeleton className="h-64 w-full" />;
  if (!data?.length) return null;

  return (
    <div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      {data.map((series) => (
        <div key={series.series} className="rounded-[10px] border border-[oklch(0.22_0.012_255/70%)] bg-(--sl2) p-4">
          <p className="text-[12px] font-semibold text-(--tx3) mb-3 uppercase tracking-[0.08em]" style={{ fontFamily: "var(--fM)" }}>
            {series.series.replace(/_/g, " ")}
          </p>
          <ResponsiveContainer width="100%" height={180}>
            <AreaChart data={series.points}>
              <defs>
                <linearGradient id={`grad-${series.series}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="var(--g3)" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="var(--g3)" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--sl4)" />
              <XAxis
                dataKey="ts"
                tickFormatter={(v) => format(new Date(v), "MMM d")}
                tick={{ fontSize: 11, fill: "var(--tx3)", fontFamily: "var(--fM)" }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                tick={{ fontSize: 11, fill: "var(--tx3)", fontFamily: "var(--fM)" }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: "var(--sl2)",
                  border: "1px solid var(--sl4)",
                  borderRadius: "8px",
                  fontSize: 12,
                  color: "var(--tx1)",
                  fontFamily: "var(--fM)",
                }}
                labelFormatter={(v) => format(new Date(v), "MMM d, yyyy")}
              />
              <Area
                type="monotone"
                dataKey="value"
                stroke="var(--g3)"
                fill={`url(#grad-${series.series})`}
                strokeWidth={2}
                dot={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      ))}
      </div>
      <div className="panel-refresh-footer">
        <RefreshCw size={10} style={{ opacity: 0.5, flexShrink: 0 }} />
        <span>Last: {fmtTime(lastRefreshed)}</span>
        <span style={{ color: "var(--tx4)" }}>·</span>
        <span>Next: {secsLeft}s</span>
        <div className="countdown-track">
          <div className="countdown-fill" style={{ transform: `scaleX(${progress})` }} />
        </div>
      </div>
    </div>
  );
}
