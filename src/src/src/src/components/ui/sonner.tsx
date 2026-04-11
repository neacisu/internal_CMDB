"use client"

import {
  CircleCheck,
  Info,
  LoaderCircle,
  OctagonX,
  TriangleAlert,
} from "lucide-react"
import { useTheme } from "next-themes"
import { Toaster as Sonner } from "sonner"

type ToasterProps = React.ComponentProps<typeof Sonner>

const Toaster = ({ ...props }: ToasterProps) => {
  const { theme = "system" } = useTheme()

  return (
    <Sonner
      theme={theme as ToasterProps["theme"]}
      className="toaster group"
      icons={{
        success: <CircleCheck className="h-4 w-4" />,
        info: <Info className="h-4 w-4" />,
        warning: <TriangleAlert className="h-4 w-4" />,
        error: <OctagonX className="h-4 w-4" />,
        loading: <LoaderCircle className="h-4 w-4 animate-spin" />,
      }}
      toastOptions={{
        classNames: {
          toast:
            "group toast group-[.toaster]:bg-[var(--sl3)] group-[.toaster]:text-[var(--tx1)] group-[.toaster]:border-[oklch(0.28_0.012_255)] group-[.toaster]:shadow-[0_8px_24px_oklch(0_0_0/40%)] group-[.toaster]:rounded-[9px] group-[.toaster]:text-[15.6px]",
          description: "group-[.toast]:text-[var(--tx3)]",
          actionButton:
            "group-[.toast]:bg-[var(--g3)] group-[.toast]:text-[oklch(0.08_0.01_152)]",
          cancelButton:
            "group-[.toast]:bg-[var(--sl4)] group-[.toast]:text-[var(--tx3)]",
          success: "group-[.toaster]:border-[oklch(0.55_0.22_152/40%)]",
          error: "group-[.toaster]:border-[oklch(0.62_0.22_27/40%)]",
          warning: "group-[.toaster]:border-[oklch(0.78_0.18_74/40%)]",
        },
      }}
      {...props}
    />
  )
}

export { Toaster }
