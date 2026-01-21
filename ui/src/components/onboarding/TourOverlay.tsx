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
  const [tooltipStyle, setTooltipStyle] = useState<React.CSSProperties>({ opacity: 0, visibility: 'hidden', transform: 'translate3d(0, 0, 0)' });
  const [isReady, setIsReady] = useState(false);
  const tooltipRef = React.useRef<HTMLDivElement>(null);

  const tour = tours.find(t => t.id === currentTour);
  const step = tour?.steps[currentStep];
  const lastVisibleStep = getLastVisibleStep();

  const calculateTooltipPosition = (element: HTMLElement, placement: string = 'bottom') => {
    const rect = element.getBoundingClientRect();
    const tooltipWidth = 320;
    const tooltipHeight = tooltipRef.current?.offsetHeight || 280; 
    const spacing = 12;

    let top = rect.bottom + spacing;
    let left = rect.left + (rect.width / 2) - (tooltipWidth / 2);

    switch (placement) {
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
    }

    // Viewport safety
    if (left < 16) left = 16;
    if (left + tooltipWidth > window.innerWidth - 16) {
      left = window.innerWidth - tooltipWidth - 16;
    }
    if (top < 16) top = 16;
    if (top + tooltipHeight > window.innerHeight - 16) {
      top = window.innerHeight - tooltipHeight - 16;
    }

    // Ensure we don't show at 0,0
    const isActuallyPositioned = top !== 0 || left !== 0;

    return { 
      transform: `translate3d(${left}px, ${top}px, 0)`,
      opacity: isActuallyPositioned && isReady ? 1 : 0,
      visibility: isActuallyPositioned && isReady ? 'visible' : 'hidden',
      top: 0,
      left: 0
    } as React.CSSProperties;
  };

  // Effect to find and scroll to target
  useEffect(() => {
    if (!isActive || !step) {
      setTargetElement(null);
      setIsReady(false);
      setTooltipStyle({ opacity: 0, visibility: 'hidden', transform: 'translate3d(0, 0, 0)' });
      return;
    }

    // Immediately hide everything on step change
    setIsReady(false);
    setOverlayStyle(prev => ({ ...prev, opacity: 0 }));
    setTooltipStyle(prev => ({ ...prev, opacity: 0, visibility: 'hidden' }));

    const timer = setTimeout(() => {
      const element = document.querySelector(step.target) as HTMLElement;
      
      if (element) {
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
        foundTarget.scrollIntoView({ behavior: 'smooth', block: 'center' });

        // Update sidebar scroll
        const sidebarContent = document.querySelector('[class*="SidebarContent"]');
        if (sidebarContent && sidebarContent.contains(foundTarget)) {
          const containerHeight = (sidebarContent as HTMLElement).clientHeight;
          (sidebarContent as HTMLElement).scrollTop = foundTarget.offsetTop - containerHeight / 2;
        }
        
        // PRE-CALCULATE initial position while still invisible
        const initialStyle = calculateTooltipPosition(foundTarget, step.placement);
        // Force opacity 0 even in calculated style for now
        setTooltipStyle({ ...initialStyle, opacity: 0, visibility: 'hidden' });
        
        // Wait for smooth scroll/layout to settle then reveal
        setTimeout(() => {
          setIsReady(true);
        }, 300);
      }
    }, 400); 

    return () => clearTimeout(timer);
  }, [isActive, step]);

  // High-performance tracking loop
  useEffect(() => {
    if (!targetElement || !isActive || !isReady) return;

    let rafId: number;
    
    const update = () => {
      const rect = targetElement.getBoundingClientRect();
      const padding = 8;

      // Update overlay (the blue highlight)
      setOverlayStyle({
        position: 'fixed',
        top: rect.top - padding,
        left: rect.left - padding,
        width: rect.width + padding * 2,
        height: rect.height + padding * 2,
        borderRadius: '8px',
        boxShadow: '0 0 0 4px rgba(59, 130, 246, 0.5), 0 0 0 9999px rgba(0, 0, 0, 0.6)',
        pointerEvents: 'none',
        zIndex: 9998,
        transition: 'all 150ms cubic-bezier(0.4, 0, 0.2, 1)',
        opacity: 1,
        visibility: 'visible'
      });

      // Update tooltip (the card)
      if (step) {
        const newStyle = calculateTooltipPosition(targetElement, step.placement);
        // Triple check translation to prevent top-left flash
        if (newStyle.transform !== 'translate3d(0px, 0px, 0)') {
          setTooltipStyle(newStyle);
        }
      }

      rafId = requestAnimationFrame(update);
    };

    rafId = requestAnimationFrame(update);

    return () => cancelAnimationFrame(rafId);
  }, [targetElement, isActive, step, isReady]);

  if (!isActive || !tour || !step) {
    return null;
  }

  const progress = ((currentStep + 1) / (lastVisibleStep + 1)) * 100;

  return (
    <>
      <div 
        style={overlayStyle} 
        className="transition-opacity duration-300 ease-out animate-in fade-in"
      />

      <Card 
        ref={tooltipRef}
        className="fixed w-80 z-[10000] shadow-[0_25px_60px_rgba(0,0,0,0.4)] border-2 border-primary/20 pointer-events-auto backdrop-blur-lg bg-background/95 max-h-[calc(100vh-32px)] overflow-y-auto scrollbar-none transition-opacity duration-200 ease-in-out"
        style={tooltipStyle}
      >
        <CardHeader className="pb-3 space-y-1">
          <div className="flex items-center justify-between">
            <CardTitle className="text-lg font-bold tracking-tight bg-gradient-to-r from-primary to-primary/60 bg-clip-text text-transparent">
              {step.title}
            </CardTitle>
            <Button
              variant="ghost"
              size="sm"
              onClick={endTour}
              className="h-8 w-8 p-0 rounded-full hover:bg-destructive/10 hover:text-destructive transition-colors"
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
          <div className="space-y-1.5 pt-1">
            <Progress value={progress} className="h-1.5 bg-primary/10" />
            <div className="flex justify-between items-center">
              <span className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground/70">
                Tour Progress
              </span>
              <span className="text-[10px] font-bold text-primary">
                {currentStep + 1} / {lastVisibleStep + 1}
              </span>
            </div>
          </div>
        </CardHeader>

        <CardContent className="pt-0">
          <p className="text-sm leading-relaxed text-muted-foreground mb-6">
            {step.content}
          </p>

          <div className="flex items-center justify-between pt-2 border-t border-border/50">
            <div className="flex gap-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={prevStep}
                disabled={currentStep === 0}
                className="h-8 px-3 text-xs font-semibold"
              >
                <ChevronLeft className="h-3.5 w-3.5 mr-1" />
                Back
              </Button>

              <Button
                variant="ghost"
                size="sm"
                onClick={skipTour}
                className="h-8 px-3 text-xs font-semibold hover:bg-primary/5"
              >
                Skip
              </Button>
            </div>

            <Button
              size="sm"
              onClick={nextStep}
              className="h-8 px-4 text-xs font-bold shadow-lg shadow-primary/20 hover:shadow-primary/30 transition-all hover:-translate-y-0.5 active:scale-95"
            >
              {currentStep === lastVisibleStep ? 'Complete' : 'Continue'}
              {currentStep < lastVisibleStep && (
                <ChevronRight className="h-3.5 w-3.5 ml-1.5" />
              )}
            </Button>
          </div>
        </CardContent>
      </Card>
    </>
  );
}