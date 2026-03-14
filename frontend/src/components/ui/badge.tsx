import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded-[5px] border px-2 py-[2px] text-[12px] font-semibold tracking-[0.06em] uppercase whitespace-nowrap transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
  {
    variants: {
      variant: {
        default:
          "bg-[oklch(0.68_0.22_152/12%)] text-[oklch(0.75_0.22_152)] border-[oklch(0.68_0.22_152/25%)]",
        secondary:
          "bg-[var(--sl3)] text-[var(--tx3)] border-[var(--sl4)]",
        destructive:
          "bg-[oklch(0.62_0.22_27/12%)] text-[oklch(0.72_0.20_27)] border-[oklch(0.62_0.22_27/25%)]",
        outline: "text-[var(--tx2)] border-[var(--sl4)]",
        warning:
          "bg-[oklch(0.78_0.18_74/12%)] text-[oklch(0.85_0.16_74)] border-[oklch(0.78_0.18_74/25%)]",
        blue:
          "bg-[oklch(0.62_0.18_240/12%)] text-[oklch(0.72_0.16_240)] border-[oklch(0.62_0.18_240/25%)]",
        purple:
          "bg-[oklch(0.62_0.18_295/12%)] text-[oklch(0.72_0.16_295)] border-[oklch(0.62_0.18_295/25%)]",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  )
}

export { Badge, badgeVariants }
