import { useRef } from "react";
import { type LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { fmtTime } from "@/lib/hooks";

interface KpiCardProps {
  title: string;
  value: string | number;
  sub?: string;
  icon?: LucideIcon;
  color?: string;
  trend?: "up" | "down" | "neutral";
  lastRefreshed?: Date | null;
  /** epoch ms of last data update — used to trigger the value flash animation */
  dataUpdatedAt?: number;
  className?: string;
}

export function KpiCard({
  title,
  value,
  sub,
  icon: Icon,
  color = "var(--g3)",
  lastRefreshed,
  dataUpdatedAt,
  className,
}: KpiCardProps) {
  // Track previous dataUpdatedAt so we can re-key value to trigger flash
  const prevRef = useRef<number | undefined>(undefined);
  const isNew = dataUpdatedAt !== undefined && dataUpdatedAt !== prevRef.current && prevRef.current !== undefined;
  prevRef.current = dataUpdatedAt;

  return (
    <div className={cn("kpi", className)}>
      {Icon && (
        <div
          className="kpi-ic"
          style={{ background: `color-mix(in oklch, ${color} 13%, transparent)` }}
        >
          <Icon size={16} style={{ color }} />
        </div>
      )}
      <div className="kpi-l">{title}</div>
      <div
        key={dataUpdatedAt}
        className={cn("kpi-v", isNew && "kpi-v-flash")}
      >
        {value}
      </div>
      {sub && <div className="kpi-sub">{sub}</div>}
      {lastRefreshed !== undefined && (
        <div className="kpi-ts">
          ↻ {fmtTime(lastRefreshed)}
        </div>
      )}
    </div>
  );
}
