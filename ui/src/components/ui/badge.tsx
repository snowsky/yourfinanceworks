import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

const badgeVariants = cva(
  "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
  {
    variants: {
      variant: {
        default:
          "border-transparent bg-primary text-primary-foreground hover:bg-primary/80",
        secondary:
          "border-transparent bg-slate-700 text-white hover:bg-slate-600 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700",
        destructive:
          "border-transparent bg-destructive text-destructive-foreground hover:bg-destructive/80",
        outline: "text-foreground",
        success:
          "border-transparent bg-green-700 text-white hover:bg-green-600 dark:bg-green-900/30 dark:text-green-400 dark:hover:bg-green-900/50",
        warning:
          "border-transparent bg-amber-700 text-white hover:bg-amber-600 dark:bg-amber-900/30 dark:text-amber-400 dark:hover:bg-amber-900/50",
        info:
          "border-transparent bg-blue-700 text-white hover:bg-blue-600 dark:bg-blue-900/30 dark:text-blue-400 dark:hover:bg-blue-900/50",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
  VariantProps<typeof badgeVariants> {
  children?: React.ReactNode;
}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  )
}

export { Badge, badgeVariants }
