import React from 'react';
import { HelpCircle } from 'lucide-react';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { Button } from '@/components/ui/button';

interface HelpTooltipProps {
  content: string;
  title?: string;
  side?: 'top' | 'bottom' | 'left' | 'right';
  className?: string;
}

export function HelpTooltip({ content, title, side = 'top', className }: HelpTooltipProps) {
  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            variant="ghost"
            size="sm"
            className={`h-5 w-5 p-0 text-muted-foreground hover:text-foreground ${className}`}
          >
            <HelpCircle className="h-4 w-4" />
          </Button>
        </TooltipTrigger>
        <TooltipContent side={side} className="max-w-xs">
          {title && <div className="font-semibold mb-1">{title}</div>}
          <div className="text-sm">{content}</div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}