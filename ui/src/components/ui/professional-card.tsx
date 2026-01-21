import * as React from "react";
import { cn } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle, CardFooter } from "@/components/ui/card";
import { LucideIcon } from "lucide-react";

interface ProfessionalCardProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: 'default' | 'elevated' | 'glass' | 'gradient' | 'minimal';
  size?: 'sm' | 'md' | 'lg';
  interactive?: boolean;
}

const ProfessionalCard = React.forwardRef<HTMLDivElement, ProfessionalCardProps>(
  ({ className, variant = 'default', size = 'md', interactive = false, ...props }, ref) => {
    const variants = {
      default: "bg-card border border-border/50 shadow-sm",
      elevated: "bg-card border-0 shadow-lg shadow-black/5 ring-1 ring-border/10",
      glass: "bg-card/80 backdrop-blur-xl border border-white/10 shadow-xl",
      gradient: "bg-gradient-to-br from-card via-card to-muted/20 border border-border/30 shadow-md",
      minimal: "bg-transparent border-0 shadow-none"
    };

    const sizes = {
      sm: "p-4",
      md: "p-6",
      lg: "p-8"
    };

    const interactiveStyles = interactive
      ? "transition-all duration-200 hover:shadow-lg hover:shadow-black/10 hover:-translate-y-0.5 cursor-pointer"
      : "";

    return (
      <div
        className={cn(
          "rounded-xl transition-colors",
          variants[variant],
          sizes[size],
          interactiveStyles,
          className
        )}
        ref={ref}
        {...props}
      />
    );
  }
);

ProfessionalCard.displayName = "ProfessionalCard";

const ProfessionalCardHeader = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn("flex flex-col space-y-1.5 p-6", className)}
    {...props}
  />
))
ProfessionalCardHeader.displayName = "ProfessionalCardHeader"

const ProfessionalCardTitle = React.forwardRef<
  HTMLParagraphElement,
  React.HTMLAttributes<HTMLHeadingElement>
>(({ className, ...props }, ref) => (
  <h3
    ref={ref}
    className={cn(
      "text-2xl font-semibold leading-none tracking-tight",
      className
    )}
    {...props}
  />
))
ProfessionalCardTitle.displayName = "ProfessionalCardTitle"

const ProfessionalCardDescription = React.forwardRef<
  HTMLParagraphElement,
  React.HTMLAttributes<HTMLParagraphElement>
>(({ className, ...props }, ref) => (
  <p
    ref={ref}
    className={cn("text-sm text-muted-foreground", className)}
    {...props}
  />
))
ProfessionalCardDescription.displayName = "ProfessionalCardDescription"

const ProfessionalCardContent = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div ref={ref} className={cn("p-6 pt-0", className)} {...props} />
))
ProfessionalCardContent.displayName = "ProfessionalCardContent"

const ProfessionalCardFooter = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn("flex items-center p-6 pt-0", className)}
    {...props}
  />
))
ProfessionalCardFooter.displayName = "ProfessionalCardFooter"

interface MetricCardProps {
  title: string;
  value: React.ReactNode;
  change?: {
    value: number;
    type: 'increase' | 'decrease' | 'neutral';
  };
  icon?: LucideIcon;
  description?: string;
  variant?: 'default' | 'success' | 'warning' | 'danger';
  loading?: boolean;
  className?: string;
}

const MetricCard = React.forwardRef<HTMLDivElement, MetricCardProps>(
  ({ title, value, change, icon: Icon, description, variant = 'default', loading = false, className }, ref) => {
    const variantStyles = {
      default: "border-l-4 border-l-primary bg-primary/5",
      success: "border-l-4 border-l-success bg-success/5",
      warning: "border-l-4 border-l-warning bg-warning/5",
      danger: "border-l-4 border-l-destructive bg-destructive/5"
    };

    const changeColors = {
      increase: "text-success bg-success/10",
      decrease: "text-destructive bg-destructive/10",
      neutral: "text-muted-foreground bg-muted"
    };

    if (loading) {
      return (
        <ProfessionalCard variant="elevated" className="animate-pulse">
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="h-4 bg-muted rounded w-24"></div>
              <div className="h-8 w-8 bg-muted rounded-lg"></div>
            </div>
            <div className="h-8 bg-muted rounded w-32"></div>
            <div className="h-3 bg-muted rounded w-40"></div>
          </div>
        </ProfessionalCard>
      );
    }

    return (
      <ProfessionalCard
        variant="elevated"
        className={cn("group hover:shadow-xl transition-all duration-300", variantStyles[variant], className)}
        interactive
        ref={ref}
      >
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-medium text-muted-foreground group-hover:text-foreground transition-colors">
              {title}
            </h3>
            {Icon && (
              <div className="p-2 rounded-lg bg-background/50 group-hover:bg-background transition-colors">
                <Icon className="h-4 w-4 text-muted-foreground" />
              </div>
            )}
          </div>

          <div className="space-y-2">
            <div className="text-2xl font-bold tracking-tight">{value}</div>

            {change && (
              <div className={cn(
                "inline-flex items-center px-2 py-1 rounded-full text-xs font-medium",
                changeColors[change.type]
              )}>
                {change.type === 'increase' ? '↗' : change.type === 'decrease' ? '↘' : '→'}
                {Math.abs(change.value)}%
              </div>
            )}

            {description && (
              <p className="text-xs text-muted-foreground leading-relaxed">{description}</p>
            )}
          </div>
        </div>
      </ProfessionalCard>
    );
  }
);

MetricCard.displayName = "MetricCard";

export {
  ProfessionalCard,
  ProfessionalCardHeader,
  ProfessionalCardTitle,
  ProfessionalCardDescription,
  ProfessionalCardContent,
  ProfessionalCardFooter,
  MetricCard
};