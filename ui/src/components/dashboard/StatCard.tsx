import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { LucideIcon, Loader2, TrendingUp, TrendingDown, Minus } from "lucide-react";
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

const getVariantStyles = (variant: string) => {
  switch (variant) {
    case 'success':
      return 'border-l-4 border-l-success bg-success/5 hover:bg-success/10';
    case 'warning':
      return 'border-l-4 border-l-warning bg-warning/5 hover:bg-warning/10';
    case 'destructive':
      return 'border-l-4 border-l-destructive bg-destructive/5 hover:bg-destructive/10';
    default:
      return 'border-l-4 border-l-primary bg-primary/5 hover:bg-primary/10';
  }
};

const getIconColor = (variant: string) => {
  switch (variant) {
    case 'success': return 'text-success';
    case 'warning': return 'text-warning';
    case 'destructive': return 'text-destructive';
    default: return 'text-primary';
  }
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
  
  return (
    <Card className={cn(
      "group transition-all duration-300 hover:shadow-lg hover:scale-[1.02]",
      getVariantStyles(variant),
      onClick && "cursor-pointer"
    )}
    onClick={onClick}
    >
      <CardHeader className="flex flex-row items-center justify-between pb-3">
        <CardTitle className="text-sm font-medium text-muted-foreground group-hover:text-foreground transition-colors">
          {title}
        </CardTitle>
        <div className={cn(
          "p-2 rounded-lg transition-all duration-300",
          variant === 'success' ? 'bg-success/10 group-hover:bg-success/20' :
          variant === 'warning' ? 'bg-warning/10 group-hover:bg-warning/20' :
          variant === 'destructive' ? 'bg-destructive/10 group-hover:bg-destructive/20' :
          'bg-primary/10 group-hover:bg-primary/20'
        )}>
          {loading ? (
            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
          ) : (
            <Icon className={cn("h-5 w-5 transition-colors", getIconColor(variant))} />
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {loading ? (
          <div className="space-y-2">
            <div className="h-8 w-32 bg-muted animate-pulse rounded" />
            <div className="h-3 w-24 bg-muted animate-pulse rounded" />
            <div className="flex items-center gap-2 pt-1">
              <div className="h-5 w-16 bg-muted animate-pulse rounded-full" />
              <div className="h-3 w-20 bg-muted animate-pulse rounded" />
            </div>
          </div>
        ) : (
          <>
            <div className="text-3xl font-bold tracking-tight">{value}</div>
            {description && (
              <p className="text-sm text-muted-foreground leading-relaxed">{description}</p>
            )}
            {trend && (
              <div className="flex items-center gap-2 pt-1">
                <div className={cn(
                  "flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium",
                  trend.isPositive ? 'bg-success/10 text-success' :
                  trend.value === 0 ? 'bg-muted text-muted-foreground' :
                  'bg-destructive/10 text-destructive'
                )}>
                  <TrendIcon className="h-3 w-3" />
                  {trend.value === 0 ? '0' : `${trend.isPositive ? '+' : ''}${trend.value}`}%
                </div>
                <span className="text-xs text-muted-foreground">vs last month</span>
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}