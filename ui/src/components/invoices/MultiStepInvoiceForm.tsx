import React, { useState, useEffect } from "react";
import { ChevronLeft, ChevronRight, Check, FileText, User, Calculator, Settings } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

interface Step {
  id: string;
  title: string;
  description: string;
  icon: React.ReactNode;
  isComplete: boolean;
  isActive: boolean;
}

interface MultiStepInvoiceFormProps {
  currentStep: number;
  totalSteps: number;
  onStepChange: (step: number) => void;
  onNext: () => void;
  onPrevious: () => void;
  canProceed: boolean;
  children: React.ReactNode;
  steps: Omit<Step, 'isComplete' | 'isActive'>[];
  completedSteps: number[];
}

export function MultiStepInvoiceForm({
  currentStep,
  totalSteps,
  onStepChange,
  onNext,
  onPrevious,
  canProceed,
  children,
  steps,
  completedSteps
}: MultiStepInvoiceFormProps) {
  const progress = ((currentStep - 1) / (totalSteps - 1)) * 100;

  const stepItems: Step[] = steps.map((step, index) => ({
    ...step,
    isComplete: completedSteps.includes(index + 1),
    isActive: currentStep === index + 1
  }));

  return (
    <div className="space-y-6">
      {/* Progress Header */}
      <Card>
        <CardHeader className="pb-4">
          <div className="flex items-center justify-between mb-4">
            <CardTitle className="text-xl">Create Invoice</CardTitle>
            <Badge variant="outline" className="text-sm">
              Step {currentStep} of {totalSteps}
            </Badge>
          </div>
          <Progress value={progress} className="h-2" />
        </CardHeader>
      </Card>

      {/* Step Navigation */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {stepItems.map((step, index) => (
          <Card
            key={step.id}
            className={cn(
              "cursor-pointer transition-all duration-200 hover:shadow-md",
              step.isActive && "ring-2 ring-primary border-primary",
              step.isComplete && "bg-success/5 border-success"
            )}
            onClick={() => onStepChange(index + 1)}
          >
            <CardContent className="p-4">
              <div className="flex items-center space-x-3">
                <div
                  className={cn(
                    "flex h-8 w-8 items-center justify-center rounded-full text-sm font-medium",
                    step.isComplete
                      ? "bg-success text-success-foreground"
                      : step.isActive
                      ? "bg-primary text-primary-foreground"
                      : "bg-muted text-muted-foreground"
                  )}
                >
                  {step.isComplete ? (
                    <Check className="h-4 w-4" />
                  ) : (
                    step.icon
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <p className={cn(
                    "text-sm font-medium truncate",
                    step.isActive && "text-primary"
                  )}>
                    {step.title}
                  </p>
                  <p className="text-xs text-muted-foreground truncate">
                    {step.description}
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Form Content */}
      <Card>
        <CardContent className="p-6">
          {children}
        </CardContent>
      </Card>

      {/* Navigation Buttons */}
      <div className="flex justify-between">
        <Button
          variant="outline"
          onClick={onPrevious}
          disabled={currentStep === 1}
          className="flex items-center space-x-2"
        >
          <ChevronLeft className="h-4 w-4" />
          <span>Previous</span>
        </Button>

        <Button
          onClick={onNext}
          disabled={!canProceed}
          className="flex items-center space-x-2"
        >
          <span>{currentStep === totalSteps ? "Create Invoice" : "Next"}</span>
          {currentStep !== totalSteps && <ChevronRight className="h-4 w-4" />}
        </Button>
      </div>
    </div>
  );
}