import * as React from "react";
import { cn } from "@/lib/utils";
import { ChevronDown, ChevronUp, MoreHorizontal, ArrowUpDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useListDensity } from "@/hooks/use-list-density";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

const ProfessionalTable = React.forwardRef<
  HTMLTableElement,
  React.HTMLAttributes<HTMLTableElement> & {
    variant?: 'default' | 'minimal' | 'striped';
  }
>(({ className, variant = 'default', ...props }, ref) => {
  const variants = {
    default: "border-collapse border-spacing-0 border border-border/50",
    minimal: "border-collapse border-spacing-0",
    striped: "border-collapse border-spacing-0 [&_tbody_tr:nth-child(even)]:bg-muted/30"
  };

  return (
    <div className="relative w-full overflow-auto">
      <table
        ref={ref}
        className={cn("w-full caption-bottom text-sm", variants[variant], className)}
        {...props}
      />
    </div>
  );
});
ProfessionalTable.displayName = "ProfessionalTable";

const ProfessionalTableHeader = React.forwardRef<
  HTMLTableSectionElement,
  React.HTMLAttributes<HTMLTableSectionElement>
>(({ className, ...props }, ref) => (
  <thead 
    ref={ref} 
    className={cn("bg-muted/50 [&_tr]:border-b [&_tr]:border-border/50", className)} 
    {...props} 
  />
));
ProfessionalTableHeader.displayName = "ProfessionalTableHeader";

const ProfessionalTableBody = React.forwardRef<
  HTMLTableSectionElement,
  React.HTMLAttributes<HTMLTableSectionElement>
>(({ className, ...props }, ref) => (
  <tbody
    ref={ref}
    className={cn("[&_tr:last-child]:border-0", className)}
    {...props}
  />
));
ProfessionalTableBody.displayName = "ProfessionalTableBody";

const ProfessionalTableFooter = React.forwardRef<
  HTMLTableSectionElement,
  React.HTMLAttributes<HTMLTableSectionElement>
>(({ className, ...props }, ref) => (
  <tfoot
    ref={ref}
    className={cn("border-t bg-muted/50 font-medium [&>tr]:last:border-b-0", className)}
    {...props}
  />
));
ProfessionalTableFooter.displayName = "ProfessionalTableFooter";

const ProfessionalTableRow = React.forwardRef<
  HTMLTableRowElement,
  React.HTMLAttributes<HTMLTableRowElement> & {
    interactive?: boolean;
  }
>(({ className, interactive = false, ...props }, ref) => (
  <tr
    ref={ref}
    className={cn(
      "border-b border-border/50 transition-colors",
      interactive && "hover:bg-muted/50 cursor-pointer",
      "data-[state=selected]:bg-muted",
      className
    )}
    {...props}
  />
));
ProfessionalTableRow.displayName = "ProfessionalTableRow";

interface SortableHeaderProps extends React.ThHTMLAttributes<HTMLTableCellElement> {
  sortable?: boolean;
  sortDirection?: 'asc' | 'desc' | null;
  onSort?: () => void;
}

const ProfessionalTableHead = React.forwardRef<
  HTMLTableCellElement,
  SortableHeaderProps
>(({ className, sortable = false, sortDirection, onSort, children, ...props }, ref) => {
  const { density } = useListDensity();
  const handleSort = () => {
    if (sortable && onSort) {
      onSort();
    }
  };

  const handleSortKeyDown = (event: React.KeyboardEvent<HTMLTableCellElement>) => {
    if (!sortable || !onSort) return;
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      onSort();
    }
  };

  const ariaSortValue =
    sortDirection === "asc"
      ? "ascending"
      : sortDirection === "desc"
        ? "descending"
        : sortable
          ? "none"
          : undefined;

  const densityClass = density === "compact" ? "h-10 px-3 text-[11px]" : "h-12 px-4 text-xs";

  return (
    <th
      ref={ref}
      className={cn(
        "text-left align-middle font-semibold text-muted-foreground [&:has([role=checkbox])]:pr-0",
        densityClass,
        sortable && "cursor-pointer hover:text-foreground transition-colors select-none",
        className
      )}
      onClick={handleSort}
      onKeyDown={handleSortKeyDown}
      tabIndex={sortable ? 0 : undefined}
      aria-sort={ariaSortValue as React.AriaAttributes["aria-sort"]}
      {...props}
    >
      <div className="flex items-center gap-2">
        {children}
        {sortable && (
          <div className="flex flex-col">
            {sortDirection === null && <ArrowUpDown className="h-3 w-3" />}
            {sortDirection === 'asc' && <ChevronUp className="h-3 w-3" />}
            {sortDirection === 'desc' && <ChevronDown className="h-3 w-3" />}
          </div>
        )}
      </div>
    </th>
  );
});
ProfessionalTableHead.displayName = "ProfessionalTableHead";

const ProfessionalTableCell = React.forwardRef<
  HTMLTableCellElement,
  React.TdHTMLAttributes<HTMLTableCellElement>
>(({ className, ...props }, ref) => (
>(({ className, ...props }, ref) => {
  const { density } = useListDensity();
  const densityClass = density === "compact" ? "px-3 py-2.5" : "px-4 py-3";
  return (
    <td
      ref={ref}
      className={cn("align-middle [&:has([role=checkbox])]:pr-0", densityClass, className)}
      {...props}
    />
  );
});
ProfessionalTableCell.displayName = "ProfessionalTableCell";

// Status Badge Component for Tables
interface StatusBadgeProps {
  status: 'success' | 'warning' | 'danger' | 'info' | 'neutral';
  children: React.ReactNode;
  variant?: 'solid' | 'soft' | 'outline';
}

const StatusBadge = React.forwardRef<HTMLSpanElement, StatusBadgeProps>(
  ({ status, children, variant = 'soft' }, ref) => {
    const statusStyles = {
      success: {
        solid: "bg-success text-success-foreground",
        soft: "bg-success/10 text-success border-success/20",
        outline: "border-success text-success bg-transparent"
      },
      warning: {
        solid: "bg-warning text-warning-foreground",
        soft: "bg-warning/10 text-warning border-warning/20",
        outline: "border-warning text-warning bg-transparent"
      },
      danger: {
        solid: "bg-destructive text-destructive-foreground",
        soft: "bg-destructive/10 text-destructive border-destructive/20",
        outline: "border-destructive text-destructive bg-transparent"
      },
      info: {
        solid: "bg-primary text-primary-foreground",
        soft: "bg-primary/10 text-primary border-primary/20",
        outline: "border-primary text-primary bg-transparent"
      },
      neutral: {
        solid: "bg-muted text-muted-foreground",
        soft: "bg-muted/50 text-muted-foreground border-muted",
        outline: "border-muted-foreground text-muted-foreground bg-transparent"
      }
    };

    return (
      <span
        ref={ref}
        className={cn(
          "inline-flex items-center px-2 py-1 rounded-full text-xs font-medium border transition-colors",
          statusStyles[status][variant]
        )}
      >
        {children}
      </span>
    );
  }
);
StatusBadge.displayName = "StatusBadge";

// Action Menu Component for Table Rows
interface TableActionMenuProps {
  actions: Array<{
    label: string;
    onClick: () => void;
    variant?: 'default' | 'destructive';
    disabled?: boolean;
  }>;
}

const TableActionMenu = ({ actions }: TableActionMenuProps) => {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" className="h-8 w-8 p-0">
          <span className="sr-only">Open menu</span>
          <MoreHorizontal className="h-4 w-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-48">
        {actions.map((action, index) => (
          <DropdownMenuItem
            key={index}
            onClick={action.onClick}
            disabled={action.disabled}
            className={cn(
              action.variant === 'destructive' && "text-destructive focus:text-destructive"
            )}
          >
            {action.label}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
};

export {
  ProfessionalTable,
  ProfessionalTableHeader,
  ProfessionalTableBody,
  ProfessionalTableFooter,
  ProfessionalTableHead,
  ProfessionalTableRow,
  ProfessionalTableCell,
  StatusBadge,
  TableActionMenu,
};