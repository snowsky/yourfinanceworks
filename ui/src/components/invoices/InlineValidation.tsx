import React from "react";
import { AlertCircle, CheckCircle2, Info } from "lucide-react";
import { cn } from "@/lib/utils";

interface ValidationMessage {
  type: "error" | "warning" | "success" | "info";
  message: string;
}

interface InlineValidationProps {
  messages: ValidationMessage[];
  className?: string;
}

export function InlineValidation({ messages, className }: InlineValidationProps) {
  if (messages.length === 0) return null;

  return (
    <div className={cn("space-y-2", className)}>
      {messages.map((msg, index) => (
        <div
          key={index}
          className={cn(
            "flex items-start space-x-2 text-sm p-2 rounded-md",
            {
              "text-destructive bg-destructive/10 border border-destructive/20": msg.type === "error",
              "text-warning bg-warning/10 border border-warning/20": msg.type === "warning",
              "text-success bg-success/10 border border-success/20": msg.type === "success",
              "text-info bg-info/10 border border-info/20": msg.type === "info",
            }
          )}
        >
          {msg.type === "error" && <AlertCircle className="h-4 w-4 mt-0.5 flex-shrink-0" />}
          {msg.type === "warning" && <AlertCircle className="h-4 w-4 mt-0.5 flex-shrink-0" />}
          {msg.type === "success" && <CheckCircle2 className="h-4 w-4 mt-0.5 flex-shrink-0" />}
          {msg.type === "info" && <Info className="h-4 w-4 mt-0.5 flex-shrink-0" />}
          <span className="flex-1">{msg.message}</span>
        </div>
      ))}
    </div>
  );
}

// Hook for real-time validation
export function useInlineValidation() {
  const [validationMessages, setValidationMessages] = React.useState<ValidationMessage[]>([]);

  const addValidation = React.useCallback((message: ValidationMessage) => {
    setValidationMessages(prev => [...prev, message]);
  }, []);

  const clearValidations = React.useCallback(() => {
    setValidationMessages([]);
  }, []);

  const removeValidation = React.useCallback((index: number) => {
    setValidationMessages(prev => prev.filter((_, i) => i !== index));
  }, []);

  return {
    validationMessages,
    addValidation,
    clearValidations,
    removeValidation,
    setValidationMessages
  };
}