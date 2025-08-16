import React from "react";
import { Cloud, CloudOff, Loader2, Check } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

export type AutoSaveStatus = "idle" | "saving" | "saved" | "error";

interface AutoSaveIndicatorProps {
  status: AutoSaveStatus;
  lastSaved?: Date;
  className?: string;
}

export function AutoSaveIndicator({ status, lastSaved, className }: AutoSaveIndicatorProps) {
  const getStatusConfig = () => {
    switch (status) {
      case "saving":
        return {
          icon: <Loader2 className="h-3 w-3 animate-spin" />,
          text: "Saving...",
          variant: "secondary" as const,
          className: "text-blue-600 bg-blue-50 border-blue-200"
        };
      case "saved":
        return {
          icon: <Check className="h-3 w-3" />,
          text: "Saved",
          variant: "secondary" as const,
          className: "text-success bg-success/10 border-success/20"
        };
      case "error":
        return {
          icon: <CloudOff className="h-3 w-3" />,
          text: "Save failed",
          variant: "destructive" as const,
          className: "text-destructive bg-destructive/10 border-destructive/20"
        };
      default:
        return {
          icon: <Cloud className="h-3 w-3" />,
          text: "Draft",
          variant: "outline" as const,
          className: "text-muted-foreground"
        };
    }
  };

  const config = getStatusConfig();

  return (
    <div className={cn("flex items-center space-x-2", className)}>
      <Badge variant={config.variant} className={cn("flex items-center space-x-1", config.className)}>
        {config.icon}
        <span className="text-xs">{config.text}</span>
      </Badge>
      {lastSaved && status === "saved" && (
        <span className="text-xs text-muted-foreground">
          {lastSaved.toLocaleTimeString()}
        </span>
      )}
    </div>
  );
}

// Hook for auto-save functionality
export function useAutoSave<T>(
  data: T,
  saveFunction: (data: T) => Promise<void>,
  delay: number = 2000
) {
  const [status, setStatus] = React.useState<AutoSaveStatus>("idle");
  const [lastSaved, setLastSaved] = React.useState<Date>();
  const timeoutRef = React.useRef<NodeJS.Timeout>();

  React.useEffect(() => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }

    timeoutRef.current = setTimeout(async () => {
      if (status !== "saving") {
        setStatus("saving");
        try {
          await saveFunction(data);
          setStatus("saved");
          setLastSaved(new Date());
        } catch (error) {
          setStatus("error");
          console.error("Auto-save failed:", error);
        }
      }
    }, delay);

    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, [data, saveFunction, delay, status]);

  return { status, lastSaved };
}