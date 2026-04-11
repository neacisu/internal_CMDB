import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-[6px] whitespace-nowrap rounded-[7px] text-[15.6px] font-semibold ring-offset-background transition-all duration-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-45 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0 cursor-pointer",
  {
    variants: {
      variant: {
        default: "bg-[var(--g3)] text-[oklch(0.08_0.01_152)] border border-[var(--g3)] hover:bg-[var(--g2)] hover:shadow-[0_0_18px_oklch(0.55_0.22_152/30%)] hover:-translate-y-px",
        destructive:
          "bg-[oklch(0.62_0.22_27/12%)] text-[oklch(0.72_0.20_27)] border border-[oklch(0.62_0.22_27/25%)] hover:bg-[oklch(0.62_0.22_27/20%)]",
        outline:
          "bg-transparent text-[var(--tx2)] border border-[var(--sl4)] hover:bg-[var(--sl3)] hover:text-[var(--tx1)]",
        secondary:
          "bg-[var(--sl3)] text-[var(--tx2)] border border-transparent hover:bg-[var(--sl4)] hover:text-[var(--tx1)]",
        ghost: "bg-transparent text-[var(--tx3)] border border-transparent hover:bg-[var(--sl3)] hover:text-[var(--tx2)]",
        link: "text-[var(--g2)] underline-offset-4 hover:underline border-none",
      },
      size: {
        default: "h-10 px-[14px] py-[7px]",
        sm: "h-9 px-[10px] py-[5px] text-[14.4px] rounded-[6px]",
        xs: "h-7 px-2 py-[3px] text-[13.2px] rounded-[5px]",
        lg: "h-11 px-8 rounded-[8px]",
        icon: "h-[30px] w-[30px] p-[6px]",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button"
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    )
  }
)
Button.displayName = "Button"

export { Button, buttonVariants }
