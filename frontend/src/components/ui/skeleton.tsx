import * as React from "react"
import { cn } from "@/lib/utils"

// One loading primitive (DESIGN.md §6): muted reading block, no pulse on the
// default variant (structural skeleton); pulse-live only on the segment the
// operator should watch. Reduced-motion is handled globally in index.css.
function Skeleton({
  className,
  live = false,
  ...props
}: React.HTMLAttributes<HTMLDivElement> & { live?: boolean }) {
  return (
    <div
      className={cn(
        "rounded-sm bg-muted",
        live && "pulse-live opacity-60",
        className
      )}
      {...props}
    />
  )
}

export { Skeleton }
