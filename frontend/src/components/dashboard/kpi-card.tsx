import { type LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

interface KpiCardProps {
  title: string;
  value: string | number;
  sub?: string;
  icon?: LucideIcon;
  color?: string;
  trend?: "up" | "down" | "neutral";
  className?: string;
}

export function KpiCard({
  title,
  value,
  sub,
  icon: Icon,
  color = "var(--g3)",
  className,
}: KpiCardProps) {
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
      <div className="kpi-v">{value}</div>
      {sub && <div className="kpi-sub">{sub}</div>}
    </div>
  );
}
