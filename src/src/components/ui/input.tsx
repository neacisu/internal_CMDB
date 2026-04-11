import * as React from "react"

import { cn } from "@/lib/utils"

const Input = React.forwardRef<HTMLInputElement, React.ComponentProps<"input">>(
  ({ className, type, ...props }, ref) => {
    return (
      <input
        type={type}
        className={cn(
          "flex h-9 w-full rounded-[7px] border border-[oklch(0.24_0.012_255)] bg-(--sl2) px-2.75 py-2 text-[15.6px] text-(--tx1) placeholder:text-(--tx4) transition-[border-color,box-shadow] duration-100 outline-none focus:border-(--g3) focus:shadow-[0_0_0_3px_oklch(0.55_0.22_152/15%)] disabled:cursor-not-allowed disabled:opacity-50 file:border-0 file:bg-transparent file:text-sm file:font-medium",
          className
        )}
        ref={ref}
        {...props}
      />
    )
  }
)
Input.displayName = "Input"

export { Input }
