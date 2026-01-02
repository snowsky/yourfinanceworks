import * as React from "react";
import { useTranslation } from "react-i18next";
import { cn } from "@/lib/utils";
import { Eye, EyeOff, Search, X } from "lucide-react";

export interface ProfessionalInputProps
  extends React.InputHTMLAttributes<HTMLInputElement> {
  variant?: 'default' | 'filled' | 'minimal' | 'glass';
  inputSize?: 'sm' | 'md' | 'lg';
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
  clearable?: boolean;
  onClear?: () => void;
  error?: boolean;
  helperText?: string;
  label?: string;
}

const ProfessionalInput = React.forwardRef<HTMLInputElement, ProfessionalInputProps>(
  ({
    className,
    type,
    variant = 'default',
    inputSize = 'md',
    leftIcon,
    rightIcon,
    clearable = false,
    onClear,
    error = false,
    helperText,
    label,
    value,
    ...props
  }, ref) => {
    const [showPassword, setShowPassword] = React.useState(false);
    const [internalValue, setInternalValue] = React.useState((value ?? '') || '');
    
    const inputValue = value !== undefined ? (value ?? '') : internalValue;
    const isPassword = type === 'password';
    const actualType = isPassword && showPassword ? 'text' : type;

    const variants = {
      default: "border border-input bg-background hover:border-ring/50 focus:border-ring",
      filled: "border-0 bg-muted hover:bg-muted/80 focus:bg-background focus:ring-2 focus:ring-ring",
      minimal: "border-0 border-b-2 border-border bg-transparent rounded-none hover:border-ring/50 focus:border-ring",
      glass: "border border-white/10 bg-background/50 backdrop-blur-sm hover:bg-background/70 focus:bg-background/80"
    };

    const sizes = {
      sm: "h-8 px-3 text-xs",
      md: "h-10 px-3 text-sm",
      lg: "h-12 px-4 text-base"
    };

    const iconSizes = {
      sm: "h-3 w-3",
      md: "h-4 w-4", 
      lg: "h-5 w-5"
    };

    const handleClear = () => {
      if (onClear) {
        onClear();
      } else {
        setInternalValue('');
        // Trigger onChange if controlled
        if (props.onChange) {
          const event = {
            target: { value: '' }
          } as React.ChangeEvent<HTMLInputElement>;
          props.onChange(event);
        }
      }
    };

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      if (value === undefined) {
        setInternalValue(e.target.value);
      }
      if (props.onChange) {
        props.onChange(e);
      }
    };

    return (
      <div className="space-y-2">
        {label && (
          <label className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">
            {label}
          </label>
        )}
        
        <div className="relative">
          {leftIcon && (
            <div className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground">
              <div className={iconSizes[inputSize]}>
                {leftIcon}
              </div>
            </div>
          )}
          
          <input
            type={actualType}
            className={cn(
              "flex w-full rounded-lg font-normal transition-all duration-200 file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50",
              variants[variant],
              sizes[inputSize],
              leftIcon && "pl-10",
              (rightIcon || clearable || isPassword) && "pr-10",
              error && "border-destructive focus:border-destructive focus:ring-destructive",
              className
            )}
            ref={ref}
            value={inputValue}
            onChange={handleChange}
            {...props}
          />
          
          <div className="absolute right-3 top-1/2 -translate-y-1/2 flex items-center gap-1">
            {clearable && inputValue && (
              <button
                type="button"
                onClick={handleClear}
                className="text-muted-foreground hover:text-foreground transition-colors"
              >
                <X className={iconSizes[inputSize]} />
              </button>
            )}
            
            {isPassword && (
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="text-muted-foreground hover:text-foreground transition-colors"
              >
                {showPassword ? (
                  <EyeOff className={iconSizes[inputSize]} />
                ) : (
                  <Eye className={iconSizes[inputSize]} />
                )}
              </button>
            )}
            
            {rightIcon && !clearable && !isPassword && (
              <div className="text-muted-foreground">
                <div className={iconSizes[inputSize]}>
                  {rightIcon}
                </div>
              </div>
            )}
          </div>
        </div>
        
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

ProfessionalInput.displayName = "ProfessionalInput";

// Search Input Component
interface SearchInputProps extends Omit<ProfessionalInputProps, 'leftIcon' | 'type'> {
  onSearch?: (value: string) => void;
}

const SearchInput = React.forwardRef<HTMLInputElement, SearchInputProps>(
  ({ onSearch, ...props }, ref) => {
    const { t } = useTranslation();
    const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === 'Enter' && onSearch) {
        onSearch(e.currentTarget.value);
      }
      if (props.onKeyDown) {
        props.onKeyDown(e);
      }
    };

    return (
      <ProfessionalInput
        ref={ref}
        type="search"
        leftIcon={<Search />}
        placeholder={t('common.search', { defaultValue: 'Search...' })}
        clearable
        {...props}
        onKeyDown={handleKeyDown}
      />
    );
  }
);

SearchInput.displayName = "SearchInput";

export { ProfessionalInput, SearchInput };