import React, { useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { X, ChevronLeft, ChevronRight, SkipForward } from 'lucide-react';
import { useOnboarding } from './OnboardingProvider';

export function TourOverlay() {
  const { 
    isActive, 
    currentTour, 
    currentStep, 
    tours, 
    nextStep, 
    prevStep, 
    skipTour, 
    endTour,
    getLastVisibleStep
  } = useOnboarding();
  
  const [targetElement, setTargetElement] = useState<HTMLElement | null>(null);
  const [overlayStyle, setOverlayStyle] = useState<React.CSSProperties>({});

  const tour = tours.find(t => t.id === currentTour);
  const step = tour?.steps[currentStep];
  const lastVisibleStep = getLastVisibleStep();

  useEffect(() => {
    if (!isActive || !step) {
      setTargetElement(null);
      return;
    }

    // Add a small delay to ensure the element is fully rendered
    const timer = setTimeout(() => {
      const element = document.querySelector(step.target) as HTMLElement;
      
      if (element) {
        // For dashboard-revenue-chart, make sure we're getting the right one
        // by checking if it contains the InvoiceChart (which has a BarChart)
        let foundTarget = element;
        if (step.target === '[data-tour="dashboard-revenue-chart"]') {
          const hasChart = element.querySelector('svg') || element.querySelector('canvas');
          if (!hasChart) {
            const allElements = document.querySelectorAll(step.target);
            for (const el of allElements) {
              if (el.querySelector('svg') || el.querySelector('canvas')) {
                foundTarget = el as HTMLElement;
                break;
              }
            }
          }
        }

        setTargetElement(foundTarget);
        foundTarget.scrollIntoView({ behavior: 'auto', block: 'center' });

        // Also scroll the sidebar content if the element is inside it
        const sidebarContent = document.querySelector('[class*="SidebarContent"]');
        if (sidebarContent && sidebarContent.contains(foundTarget)) {
          const elementRect = foundTarget.getBoundingClientRect();
          const containerRect = sidebarContent.getBoundingClientRect();
          if (elementRect.top < containerRect.top || elementRect.bottom > containerRect.bottom) {
            const containerHeight = (sidebarContent as HTMLElement).clientHeight;
            (sidebarContent as HTMLElement).scrollTop = foundTarget.offsetTop - containerHeight / 2;
          }
        }
      }
    }, 100);

    return () => clearTimeout(timer);
  }, [isActive, step]);

  // Effect to handle overlay tracking
  useEffect(() => {
    if (!targetElement || !isActive) return;

    const updateOverlay = () => {
      const rect = targetElement.getBoundingClientRect();
      const padding = 8;

      setOverlayStyle({
        position: 'fixed',
        top: rect.top - padding,
        left: rect.left - padding,
        width: rect.width + padding * 2,
        height: rect.height + padding * 2,
        borderRadius: '8px',
        boxShadow: '0 0 0 4px rgba(59, 130, 246, 0.5), 0 0 0 9999px rgba(0, 0, 0, 0.5)',
        pointerEvents: 'none',
        zIndex: 9998,
        transition: 'all 0.1s ease'
      });
    };

    updateOverlay();

    window.addEventListener('resize', updateOverlay);
    window.addEventListener('scroll', updateOverlay, { capture: true });

    return () => {
      window.removeEventListener('resize', updateOverlay);
      window.removeEventListener('scroll', updateOverlay, { capture: true });
    };
  }, [targetElement, isActive]);

  if (!isActive || !tour || !step) {
    return null;
  }

  const progress = ((currentStep + 1) / (lastVisibleStep + 1)) * 100;

  const getTooltipPosition = () => {
    if (!targetElement) return { top: '50%', left: '50%', transform: 'translate(-50%, -50%)' };

    const rect = targetElement.getBoundingClientRect();
    const tooltipWidth = 320;
    const tooltipHeight = 200;
    const spacing = 16;

    let top = rect.bottom + spacing;
    let left = rect.left + (rect.width / 2) - (tooltipWidth / 2);

    // Adjust for placement
    switch (step.placement) {
      case 'top':
        top = rect.top - tooltipHeight - spacing;
        break;
      case 'left':
        top = rect.top + (rect.height / 2) - (tooltipHeight / 2);
        left = rect.left - tooltipWidth - spacing;
        break;
      case 'right':
        top = rect.top + (rect.height / 2) - (tooltipHeight / 2);
        left = rect.right + spacing;
        break;
      case 'bottom':
      default:
        top = rect.bottom + spacing;
        break;
    }

    // Keep tooltip in viewport
    if (left < 16) left = 16;
    if (left + tooltipWidth > window.innerWidth - 16) {
      left = window.innerWidth - tooltipWidth - 16;
    }
    if (top < 16) top = 16;
    if (top + tooltipHeight > window.innerHeight - 16) {
      top = window.innerHeight - tooltipHeight - 16;
    }

    return { top: `${top}px`, left: `${left}px` };
  };

  return (
    <>
      {/* Highlight overlay */}
      <div style={overlayStyle} />

      {/* Tooltip */}
      <Card 
        className="fixed w-80 z-[10000] shadow-2xl border-2 border-primary/20 pointer-events-auto"
        style={getTooltipPosition()}
      >
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-lg">{step.title}</CardTitle>
            <Button
              variant="ghost"
              size="sm"
              onClick={endTour}
              className="h-6 w-6 p-0"
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
          <Progress value={progress} className="h-2" />
          <p className="text-xs text-muted-foreground">
            Step {currentStep + 1} of {lastVisibleStep + 1}
          </p>
        </CardHeader>

        <CardContent className="pt-0">
          <p className="text-sm text-muted-foreground mb-4">
            {step.content}
          </p>

          <div className="flex items-center justify-between">
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={prevStep}
                disabled={currentStep === 0}
              >
                <ChevronLeft className="h-4 w-4 mr-1" />
                Back
              </Button>

              <Button
                variant="outline"
                size="sm"
                onClick={skipTour}
              >
                <SkipForward className="h-4 w-4 mr-1" />
                Skip
              </Button>
            </div>

            <Button
              size="sm"
              onClick={nextStep}
            >
              {currentStep === lastVisibleStep ? 'Finish' : 'Next'}
              {currentStep < lastVisibleStep && (
                <ChevronRight className="h-4 w-4 ml-1" />
              )}
            </Button>
          </div>
        </CardContent>
      </Card>
    </>
  );
}