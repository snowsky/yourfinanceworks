import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Play, BookOpen, Users, FileText, Settings } from 'lucide-react';
import { useOnboarding } from './OnboardingProvider';

export function OnboardingWelcome() {
  const { startTour, isFirstTime } = useOnboarding();

  if (!isFirstTime) return null;

  const tourOptions = [
    {
      id: 'dashboard',
      title: 'Dashboard Overview',
      description: 'Learn about your financial metrics and key insights',
      icon: BookOpen,
      duration: '2 min',
      color: 'bg-blue-500'
    },
    {
      id: 'navigation',
      title: 'Navigation Tour',
      description: 'Discover all the features and sections available',
      icon: Users,
      duration: '3 min',
      color: 'bg-green-500'
    }
  ];

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <Card className="w-full max-w-2xl">
        <CardHeader className="text-center">
          <CardTitle className="text-2xl mb-2">
            Welcome to Invoice Manager! 🎉
          </CardTitle>
          <p className="text-muted-foreground">
            Let's get you started with a quick tour of your new invoice management system.
            Choose a tour below or explore on your own.
          </p>
        </CardHeader>
        
        <CardContent className="space-y-4">
          <div className="grid gap-4">
            {tourOptions.map((tour) => (
              <div
                key={tour.id}
                className="flex items-center gap-4 p-4 border rounded-lg hover:bg-muted/50 transition-colors"
              >
                <div className={`p-2 rounded-lg ${tour.color} text-white`}>
                  <tour.icon className="h-5 w-5" />
                </div>
                
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <h3 className="font-semibold">{tour.title}</h3>
                    <Badge variant="secondary" className="text-xs">
                      {tour.duration}
                    </Badge>
                  </div>
                  <p className="text-sm text-muted-foreground">
                    {tour.description}
                  </p>
                </div>
                
                <Button
                  onClick={() => startTour(tour.id)}
                  size="sm"
                  className="shrink-0"
                >
                  <Play className="h-4 w-4 mr-1" />
                  Start Tour
                </Button>
              </div>
            ))}
          </div>
          
          <div className="flex items-center justify-between pt-4 border-t">
            <p className="text-sm text-muted-foreground">
              You can always access these tours later from the help menu
            </p>
            
            <Button
              variant="outline"
              onClick={() => {
                localStorage.setItem('first-time-user', 'true');
                window.location.reload();
              }}
            >
              Skip for now
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}