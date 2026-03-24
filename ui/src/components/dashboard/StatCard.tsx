import { Card, CardContent } from "@/components/ui/card";
import { LucideIcon, TrendingUp, TrendingDown, Minus } from "lucide-react";
import { cn } from "@/lib/utils";

export interface StatCardProps {
  title: string;
  value: string;
  icon: LucideIcon;
  description?: string;
  trend?: {
    value: number;
    isPositive: boolean;
  };
  loading?: boolean;
  onClick?: () => void;
  variant?: 'default' | 'success' | 'warning' | 'destructive';
}

const variantConfig = {
  default: {
    iconBg: 'bg-primary/10',
    iconBgHover: 'group-hover:bg-primary/15',
    iconColor: 'text-primary',
    dot: 'bg-primary',
  },
  success: {
    iconBg: 'bg-success/10',
    iconBgHover: 'group-hover:bg-success/15',
    iconColor: 'text-success',
    dot: 'bg-success',
  },
  warning: {
    iconBg: 'bg-warning/10',
    iconBgHover: 'group-hover:bg-warning/15',
    iconColor: 'text-warning',
    dot: 'bg-warning',
  },
  destructive: {
    iconBg: 'bg-destructive/10',
    iconBgHover: 'group-hover:bg-destructive/15',
    iconColor: 'text-destructive',
    dot: 'bg-destructive',
  },
};

export function StatCard({
  title,
  value,
  icon: Icon,
  description,
  trend,
  loading = false,
  onClick,
  variant = 'default'
}: StatCardProps) {
  const TrendIcon = trend?.isPositive ? TrendingUp : trend?.value === 0 ? Minus : TrendingDown;
  const cfg = variantConfig[variant];

  return (
    <Card className={cn(
      "group transition-all duration-300 hover:shadow-md border-border/60",
      onClick && "cursor-pointer"
    )}
    onClick={onClick}
    >
      <CardContent className="p-5">
        {loading ? (
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="h-4 w-28 bg-muted animate-pulse rounded" />
              <div className="h-10 w-10 bg-muted animate-pulse rounded-xl" />
            </div>
            <div className="h-9 w-36 bg-muted animate-pulse rounded" />
            <div className="h-5 w-24 bg-muted animate-pulse rounded-full" />
          </div>
        ) : (
          <>
            <div className="flex items-start justify-between mb-3">
              <p className="text-sm font-medium text-muted-foreground leading-none">{title}</p>
              <div className={cn(
                "p-2.5 rounded-xl transition-colors duration-200",
                cfg.iconBg,
                cfg.iconBgHover
              )}>
                <Icon className={cn("h-5 w-5", cfg.iconColor)} />
              </div>
            </div>

            <div className="font-display text-3xl font-normal tracking-tight text-foreground mb-2 leading-none">
              {value}
            </div>

            {description && (
              <p className="text-xs text-muted-foreground mb-2">{description}</p>
            )}

            {trend && (
              <div className="flex items-center gap-1.5">
                <span className={cn(
                  "inline-flex items-center gap-1 text-xs font-semibold px-1.5 py-0.5 rounded",
                  trend.isPositive
                    ? 'text-success bg-success/10'
                    : trend.value === 0
                    ? 'text-muted-foreground bg-muted'
                    : 'text-destructive bg-destructive/10'
                )}>
                  <TrendIcon className="h-3 w-3" />
                  {trend.value === 0 ? '0' : `${trend.isPositive ? '+' : ''}${trend.value}`}%
                </span>
                <span className="text-xs text-muted-foreground">vs last month</span>
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}