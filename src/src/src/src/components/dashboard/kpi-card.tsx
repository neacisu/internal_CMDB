import { useEffect, useRef, useState } from "react";
import { type LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { fmtTime } from "@/lib/hooks";

interface KpiCardProps {
  title: string;
  value: string | number;
  sub?: string;
  icon?: LucideIcon;
  color?: string;
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
}: Readonly<KpiCardProps>) {
  // Flash the value element whenever new data arrives, but skip the initial mount.
  // The ref is read/written exclusively inside the effect (never during render),
  // satisfying the react-hooks/refs rule.
  const [isFlashing, setIsFlashing] = useState(false);
  const isFirstUpdateRef = useRef(true);

  useEffect(() => {
    if (isFirstUpdateRef.current) {
      isFirstUpdateRef.current = false;
      return;
    }
    if (dataUpdatedAt === undefined) return;
    // Schedule via setTimeout so setState is not called synchronously in the
    // effect body, satisfying the react-hooks/set-state-in-effect rule.
    const showId = setTimeout(() => setIsFlashing(true), 0);
    const hideId = setTimeout(() => setIsFlashing(false), 650);
    return () => {
      clearTimeout(showId);
      clearTimeout(hideId);
    };
  }, [dataUpdatedAt]);

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
        className={cn("kpi-v", isFlashing && "kpi-v-flash")}
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
