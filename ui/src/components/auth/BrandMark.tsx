import { TrendingUp } from "lucide-react";
import { cn } from "@/lib/utils";

/** The YourFinanceWORKS logo tile and wordmark, used on pages outside the app shell. */
export function BrandMark({ size = "md", className }: { size?: "sm" | "md"; className?: string }) {
  return (
    <div className={cn("flex items-center", size === "md" ? "gap-3" : "gap-2", className)}>
      <div
        className={cn(
          "bg-primary rounded-xl flex items-center justify-center flex-shrink-0",
          size === "md" ? "w-10 h-10" : "w-9 h-9",
        )}
      >
        <TrendingUp className="h-5 w-5 text-primary-foreground" aria-hidden="true" />
      </div>
      <span className="text-foreground text-lg font-bold tracking-tight leading-none">YourFinanceWORKS</span>
    </div>
  );
}
