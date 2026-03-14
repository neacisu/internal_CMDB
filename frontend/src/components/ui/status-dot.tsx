import { cn } from "@/lib/utils";

type DotVariant = "ok" | "warning" | "error" | "info" | "purple" | "neutral";

const variantMap: Record<DotVariant, string> = {
  ok: "dot-ok",
  warning: "dot-wa",
  error: "dot-er",
  info: "dot-in",
  purple: "dot-pu",
  neutral: "dot-nt",
};

export function StatusDot({
  variant = "ok",
  className,
  pulse,
}: {
  variant?: DotVariant;
  className?: string;
  pulse?: boolean;
}) {
  return (
    <div
      className={cn("dot", variantMap[variant], pulse && "blink", className)}
    />
  );
}
