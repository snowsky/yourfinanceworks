import React from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Play, BookOpen, X, ChevronRight } from 'lucide-react';
import { useOnboarding } from './OnboardingProvider';
import { useTranslation } from 'react-i18next';
import onboardingWelcomeImg from '../../assets/onboarding_welcome.png';

interface OnboardingWelcomeProps {
  open: boolean;
  onClose: () => void;
}

export function OnboardingWelcome({ open, onClose }: OnboardingWelcomeProps) {
  const { startTour, tours } = useOnboarding();
  const { t } = useTranslation();

  const handleStartTour = (tourId: string) => {
    onClose();
    startTour(tourId);
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-3xl overflow-hidden p-0 border-none shadow-2xl">
        <div className="relative h-48 bg-gradient-to-br from-primary/95 via-primary/80 to-primary/60 flex items-center justify-center overflow-hidden">
          <div className="absolute inset-0 opacity-20 bg-[url('https://www.transparenttextures.com/patterns/cubes.png')] animate-pulse" />
          <div className="relative z-10 text-center px-6">
            <DialogTitle className="text-3xl font-extrabold text-white tracking-tight mb-2">
              Your Finance Command Center 🎉
            </DialogTitle>
            <p className="text-primary-foreground/90 font-medium">
              Take complete control of your business's financial health
            </p>
          </div>
          {/* Decorative elements */}
          <div className="absolute -bottom-12 -left-12 w-48 h-48 bg-white/10 rounded-full blur-3xl" />
          <div className="absolute -top-12 -right-12 w-48 h-48 bg-primary-foreground/10 rounded-full blur-3xl" />
        </div>

        <div className="p-8 space-y-8">
          <div className="flex flex-col md:flex-row gap-8 items-center">
            <div className="w-full md:w-2/5 flex justify-center">
              <div className="relative group">
                <div className="absolute -inset-1 bg-gradient-to-r from-primary/50 to-primary/20 rounded-2xl blur opacity-25 group-hover:opacity-50 transition duration-1000 group-hover:duration-200"></div>
                <img 
                  src={onboardingWelcomeImg} 
                  alt="Finance Management" 
                  className="relative rounded-xl w-full max-w-[240px] shadow-xl transform transition-transform duration-500 group-hover:scale-105"
                />
              </div>
            </div>
            
            <div className="w-full md:w-3/5 space-y-4">
              <h3 className="text-xl font-bold text-foreground">
                Quick Start Guides
              </h3>
              <p className="text-muted-foreground text-sm leading-relaxed">
                Choose a personalized walkthrough to discover how our integrated platform can streamline your financial operations and accelerate growth.
              </p>
              
              <div className="grid gap-3 pt-2">
                {tours.map((tour) => (
                  <button 
                    key={tour.id} 
                    onClick={() => handleStartTour(tour.id)}
                    className="group flex items-center justify-between p-4 bg-muted/30 hover:bg-primary/5 border border-border/50 hover:border-primary/30 rounded-xl transition-all duration-300 text-left"
                  >
                    <div className="flex items-center gap-4">
                      <div className="p-2.5 bg-background rounded-lg shadow-sm group-hover:bg-primary/10 transition-colors">
                        <Play className="h-4 w-4 text-primary group-hover:scale-110 transition-transform" />
                      </div>
                      <div>
                        <h4 className="font-bold text-sm text-foreground group-hover:text-primary transition-colors">{tour.name}</h4>
                        <p className="text-xs text-muted-foreground">
                          {tour.steps.length} interactive steps
                        </p>
                      </div>
                    </div>
                    <ChevronRight className="h-4 w-4 text-muted-foreground opacity-0 group-hover:opacity-100 transform translate-x-[-10px] group-hover:translate-x-0 transition-all" />
                  </button>
                ))}
              </div>
            </div>
          </div>
          
          <div className="flex justify-between items-center pt-4 border-t border-border/50">
            <p className="text-xs text-muted-foreground font-medium">
              You can always restart these tours from the Help Center.
            </p>
            <Button 
              variant="ghost" 
              onClick={onClose}
              className="text-sm font-semibold hover:bg-destructive/5 hover:text-destructive transition-colors"
            >
              Skip for now
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}