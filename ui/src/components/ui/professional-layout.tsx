import * as React from "react";
import { cn } from "@/lib/utils";
import { ChevronRight, Home } from "lucide-react";
import { Link } from "react-router-dom";

// Page Header Component
interface PageHeaderProps extends Omit<React.HTMLAttributes<HTMLDivElement>, 'title'> {
  title: React.ReactNode;
  description?: React.ReactNode;
  actions?: React.ReactNode;
  breadcrumbs?: Array<{
    label: string;
    href?: string;
  }>;
  alert?: React.ReactNode;
}

const PageHeader = React.forwardRef<HTMLDivElement, PageHeaderProps>(
  ({ className, title, description, actions, breadcrumbs, alert, ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={cn("space-y-4", className)}
        {...props}
      >
        {alert && (
          <div className="w-full">
            {alert}
          </div>
        )}
        
        <div
          className="bg-gradient-to-r from-primary/10 via-primary/5 to-transparent rounded-2xl border border-primary/20 p-8 backdrop-blur-sm space-y-4"
        >
          {breadcrumbs && breadcrumbs.length > 0 && (
            <nav className="flex items-center space-x-1 text-sm text-muted-foreground">
              <Home className="h-4 w-4" />
              {breadcrumbs.map((crumb, index) => (
                <React.Fragment key={index}>
                  <ChevronRight className="h-4 w-4" />
                  {crumb.href ? (
                    <Link
                      to={crumb.href}
                      className="hover:text-foreground transition-colors"
                    >
                      {crumb.label}
                    </Link>
                  ) : (
                    <span className="text-foreground font-medium">{crumb.label}</span>
                  )}
                </React.Fragment>
              ))}
            </nav>
          )}
          
          <div className="flex items-center justify-between gap-4">
            <div className="space-y-2 flex-1">
              <h1 className="text-4xl font-bold tracking-tight">{title}</h1>
              {description && (
                <p className="text-muted-foreground text-base">{description}</p>
              )}
            </div>
            
            {actions && (
              <div className="flex items-center gap-2 flex-shrink-0">
                {actions}
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }
);
PageHeader.displayName = "PageHeader";

// Content Section Component
interface ContentSectionProps extends React.HTMLAttributes<HTMLDivElement> {
  title?: string;
  description?: string;
  actions?: React.ReactNode;
  variant?: 'default' | 'card' | 'minimal';
  headerClassName?: string;
  titleClassName?: string;
  descriptionClassName?: string;
}

const ContentSection = React.forwardRef<HTMLDivElement, ContentSectionProps>(
  ({
    className,
    title,
    description,
    actions,
    variant = 'default',
    children,
    headerClassName,
    titleClassName,
    descriptionClassName,
    ...props
  }, ref) => {
    const variants = {
      default: "space-y-6",
      card: "bg-card border border-border/50 rounded-xl p-6 shadow-sm space-y-6",
      minimal: "space-y-4"
    };

    return (
      <div
        ref={ref}
        className={cn(variants[variant], className)}
        {...props}
      >
        {(title || description || actions) && (
          <div className={cn("flex items-start justify-between", headerClassName)}>
            <div className="space-y-1">
              {title && (
                <h2 className={cn("text-xl font-semibold tracking-tight", titleClassName)}>{title}</h2>
              )}
              {description && (
                <p className={cn("text-muted-foreground", descriptionClassName)}>{description}</p>
              )}
            </div>
            
            {actions && (
              <div className="flex items-center gap-2">
                {actions}
              </div>
            )}
          </div>
        )}
        
        {children}
      </div>
    );
  }
);
ContentSection.displayName = "ContentSection";

// Grid Layout Component
interface GridLayoutProps extends React.HTMLAttributes<HTMLDivElement> {
  cols?: 1 | 2 | 3 | 4 | 5 | 6 | 12;
  gap?: 'sm' | 'md' | 'lg' | 'xl';
  responsive?: boolean;
}

const GridLayout = React.forwardRef<HTMLDivElement, GridLayoutProps>(
  ({ className, cols = 1, gap = 'md', responsive = true, ...props }, ref) => {
    const colsMap = {
      1: 'grid-cols-1',
      2: 'grid-cols-2',
      3: 'grid-cols-3',
      4: 'grid-cols-4',
      5: 'grid-cols-5',
      6: 'grid-cols-6',
      12: 'grid-cols-12'
    };

    const gapMap = {
      sm: 'gap-2',
      md: 'gap-4',
      lg: 'gap-6',
      xl: 'gap-8'
    };

    const responsiveClasses = responsive 
      ? 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4'
      : colsMap[cols];

    return (
      <div
        ref={ref}
        className={cn(
          "grid",
          responsive ? responsiveClasses : colsMap[cols],
          gapMap[gap],
          className
        )}
        {...props}
      />
    );
  }
);
GridLayout.displayName = "GridLayout";

// Stack Layout Component
interface StackLayoutProps extends React.HTMLAttributes<HTMLDivElement> {
  direction?: 'vertical' | 'horizontal';
  spacing?: 'sm' | 'md' | 'lg' | 'xl';
  align?: 'start' | 'center' | 'end' | 'stretch';
  justify?: 'start' | 'center' | 'end' | 'between' | 'around' | 'evenly';
}

const StackLayout = React.forwardRef<HTMLDivElement, StackLayoutProps>(
  ({ 
    className, 
    direction = 'vertical', 
    spacing = 'md', 
    align = 'stretch',
    justify = 'start',
    ...props 
  }, ref) => {
    const directionMap = {
      vertical: 'flex-col',
      horizontal: 'flex-row'
    };

    const spacingMap = {
      vertical: {
        sm: 'space-y-2',
        md: 'space-y-4',
        lg: 'space-y-6',
        xl: 'space-y-8'
      },
      horizontal: {
        sm: 'space-x-2',
        md: 'space-x-4',
        lg: 'space-x-6',
        xl: 'space-x-8'
      }
    };

    const alignMap = {
      start: 'items-start',
      center: 'items-center',
      end: 'items-end',
      stretch: 'items-stretch'
    };

    const justifyMap = {
      start: 'justify-start',
      center: 'justify-center',
      end: 'justify-end',
      between: 'justify-between',
      around: 'justify-around',
      evenly: 'justify-evenly'
    };

    return (
      <div
        ref={ref}
        className={cn(
          "flex",
          directionMap[direction],
          spacingMap[direction][spacing],
          alignMap[align],
          justifyMap[justify],
          className
        )}
        {...props}
      />
    );
  }
);
StackLayout.displayName = "StackLayout";

// Empty State Component
interface EmptyStateProps extends React.HTMLAttributes<HTMLDivElement> {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: React.ReactNode;
}

const EmptyState = React.forwardRef<HTMLDivElement, EmptyStateProps>(
  ({ className, icon, title, description, action, ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={cn(
          "flex flex-col items-center justify-center text-center py-12 px-4",
          className
        )}
        {...props}
      >
        {icon && (
          <div className="mb-4 p-3 rounded-full bg-muted/50 text-muted-foreground">
            {icon}
          </div>
        )}
        
        <h3 className="text-lg font-semibold mb-2">{title}</h3>
        
        {description && (
          <p className="text-muted-foreground mb-6 max-w-sm">{description}</p>
        )}
        
        {action}
      </div>
    );
  }
);
EmptyState.displayName = "EmptyState";

export {
  PageHeader,
  ContentSection,
  GridLayout,
  StackLayout,
  EmptyState,
};
