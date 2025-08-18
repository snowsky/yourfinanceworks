import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { ChevronDown, ChevronRight, Lightbulb, Zap } from 'lucide-react';

interface AdvancedFeature {
  id: string;
  title: string;
  description: string;
  category: 'automation' | 'analytics' | 'integration' | 'customization';
  difficulty: 'beginner' | 'intermediate' | 'advanced';
  component?: React.ReactNode;
  action?: () => void;
}

interface ProgressiveDisclosureProps {
  features: AdvancedFeature[];
  title?: string;
  description?: string;
  className?: string;
}

export function ProgressiveDisclosure({ 
  features, 
  title = "Advanced Features", 
  description = "Unlock powerful features as you get comfortable with the basics",
  className 
}: ProgressiveDisclosureProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [userLevel, setUserLevel] = useState<'beginner' | 'intermediate' | 'advanced'>('beginner');
  const [dismissedFeatures, setDismissedFeatures] = useState<string[]>([]);

  useEffect(() => {
    const level = localStorage.getItem('user-experience-level') as any || 'beginner';
    const dismissed = JSON.parse(localStorage.getItem('dismissed-features') || '[]');
    setUserLevel(level);
    setDismissedFeatures(dismissed);
  }, []);

  const filteredFeatures = features.filter(feature => {
    if (dismissedFeatures.includes(feature.id)) return false;
    
    const levelOrder = { beginner: 0, intermediate: 1, advanced: 2 };
    return levelOrder[feature.difficulty] <= levelOrder[userLevel];
  });

  const dismissFeature = (featureId: string) => {
    const updated = [...dismissedFeatures, featureId];
    setDismissedFeatures(updated);
    localStorage.setItem('dismissed-features', JSON.stringify(updated));
  };

  const getCategoryColor = (category: string) => {
    const colors = {
      automation: 'bg-blue-100 text-blue-800',
      analytics: 'bg-green-100 text-green-800',
      integration: 'bg-purple-100 text-purple-800',
      customization: 'bg-orange-100 text-orange-800'
    };
    return colors[category as keyof typeof colors] || 'bg-gray-100 text-gray-800';
  };

  const getDifficultyColor = (difficulty: string) => {
    const colors = {
      beginner: 'bg-green-100 text-green-800',
      intermediate: 'bg-yellow-100 text-yellow-800',
      advanced: 'bg-red-100 text-red-800'
    };
    return colors[difficulty as keyof typeof colors] || 'bg-gray-100 text-gray-800';
  };

  if (filteredFeatures.length === 0) return null;

  return (
    <Card className={className}>
      <Collapsible open={isOpen} onOpenChange={setIsOpen}>
        <CollapsibleTrigger asChild>
          <CardHeader className="cursor-pointer hover:bg-muted/50 transition-colors">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Lightbulb className="h-5 w-5 text-primary" />
                <CardTitle className="text-lg">{title}</CardTitle>
                <Badge variant="secondary" className="ml-2">
                  {filteredFeatures.length} available
                </Badge>
              </div>
              {isOpen ? (
                <ChevronDown className="h-4 w-4" />
              ) : (
                <ChevronRight className="h-4 w-4" />
              )}
            </div>
            <p className="text-sm text-muted-foreground text-left">
              {description}
            </p>
          </CardHeader>
        </CollapsibleTrigger>
        
        <CollapsibleContent>
          <CardContent className="pt-0">
            <div className="space-y-4">
              {filteredFeatures.map((feature) => (
                <div
                  key={feature.id}
                  className="border rounded-lg p-4 hover:shadow-md transition-shadow"
                >
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <Zap className="h-4 w-4 text-primary" />
                      <h3 className="font-semibold">{feature.title}</h3>
                    </div>
                    <div className="flex gap-2">
                      <Badge 
                        variant="outline" 
                        className={getCategoryColor(feature.category)}
                      >
                        {feature.category}
                      </Badge>
                      <Badge 
                        variant="outline"
                        className={getDifficultyColor(feature.difficulty)}
                      >
                        {feature.difficulty}
                      </Badge>
                    </div>
                  </div>
                  
                  <p className="text-sm text-muted-foreground mb-3">
                    {feature.description}
                  </p>
                  
                  {feature.component && (
                    <div className="mb-3">
                      {feature.component}
                    </div>
                  )}
                  
                  <div className="flex items-center justify-between">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => dismissFeature(feature.id)}
                    >
                      Not interested
                    </Button>
                    
                    {feature.action && (
                      <Button
                        size="sm"
                        onClick={feature.action}
                      >
                        Try it now
                      </Button>
                    )}
                  </div>
                </div>
              ))}
              
              <div className="pt-4 border-t">
                <div className="flex items-center justify-between">
                  <p className="text-sm text-muted-foreground">
                    Experience level: <span className="font-medium">{userLevel}</span>
                  </p>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      const levels = ['beginner', 'intermediate', 'advanced'];
                      const currentIndex = levels.indexOf(userLevel);
                      const nextLevel = levels[(currentIndex + 1) % levels.length];
                      setUserLevel(nextLevel as any);
                      localStorage.setItem('user-experience-level', nextLevel);
                    }}
                  >
                    Change level
                  </Button>
                </div>
              </div>
            </div>
          </CardContent>
        </CollapsibleContent>
      </Collapsible>
    </Card>
  );
}