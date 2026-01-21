import * as React from "react";
import { cn } from "@/lib/utils";

export interface ProfessionalTextareaProps
    extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
    variant?: 'default' | 'filled' | 'minimal' | 'glass';
    error?: boolean;
    helperText?: string;
    label?: string;
}

const ProfessionalTextarea = React.forwardRef<HTMLTextAreaElement, ProfessionalTextareaProps>(
    ({
        className,
        variant = 'default',
        error = false,
        helperText,
        label,
        ...props
    }, ref) => {

        const variants = {
            default: "border border-input bg-background hover:border-ring/50 focus:border-ring",
            filled: "border-0 bg-muted hover:bg-muted/80 focus:bg-background focus:ring-2 focus:ring-ring",
            minimal: "border-0 border-b-2 border-border bg-transparent rounded-none hover:border-ring/50 focus:border-ring",
            glass: "border border-white/10 bg-background/50 backdrop-blur-sm hover:bg-background/70 focus:bg-background/80"
        };

        return (
            <div className="space-y-2">
                {label && (
                    <label className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">
                        {label}
                    </label>
                )}

                <textarea
                    className={cn(
                        "flex min-h-[80px] w-full rounded-lg font-normal transition-all duration-200 px-3 py-2 text-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50",
                        variants[variant],
                        error && "border-destructive focus:border-destructive focus:ring-destructive",
                        className
                    )}
                    ref={ref}
                    {...props}
                />

                {helperText && (
                    <p className={cn(
                        "text-xs",
                        error ? "text-destructive" : "text-muted-foreground"
                    )}>
                        {helperText}
                    </p>
                )}
            </div>
        );
    }
);

ProfessionalTextarea.displayName = "ProfessionalTextarea";

export { ProfessionalTextarea };
