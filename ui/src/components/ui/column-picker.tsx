import { Settings2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { ColumnDef } from "@/hooks/useColumnVisibility";

interface ColumnPickerProps {
  columns: ColumnDef[];
  isVisible: (key: string) => boolean;
  onToggle: (key: string) => void;
  onReset: () => void;
  hiddenCount?: number;
}

export function ColumnPicker({
  columns,
  isVisible,
  onToggle,
  onReset,
  hiddenCount = 0,
}: ColumnPickerProps) {
  const optionalColumns = columns.filter((c) => !c.essential);

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          className="relative h-9 gap-1.5 font-normal border-border/50 bg-muted/30 hover:bg-muted/50"
        >
          <Settings2 className="h-4 w-4" />
          Columns
          {hiddenCount > 0 && (
            <span className="absolute -top-1.5 -right-1.5 flex h-4 w-4 items-center justify-center rounded-full bg-primary text-[10px] font-bold text-primary-foreground leading-none">
              {hiddenCount}
            </span>
          )}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-52 p-2">
        <p className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wide px-2 pb-2">
          Toggle columns
        </p>
        <div className="space-y-0.5">
          {optionalColumns.map((col) => (
            <label
              key={col.key}
              className="flex items-center gap-2.5 rounded-md px-2 py-1.5 cursor-pointer hover:bg-muted/50 transition-colors"
            >
              <Checkbox
                checked={isVisible(col.key)}
                onCheckedChange={() => onToggle(col.key)}
                className="h-3.5 w-3.5"
              />
              <span className="text-sm">{col.label}</span>
            </label>
          ))}
        </div>
        {hiddenCount > 0 && (
          <>
            <DropdownMenuSeparator className="my-2" />
            <button
              onClick={onReset}
              className="w-full text-left text-xs text-muted-foreground hover:text-foreground px-2 py-1 rounded transition-colors hover:bg-muted/50"
            >
              Reset to defaults
            </button>
          </>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
