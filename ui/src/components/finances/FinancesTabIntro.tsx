import React, { useState } from 'react';
import { Info, X } from 'lucide-react';

import {
  ProfessionalCard,
  ProfessionalCardContent,
} from '@/components/ui/professional-card';
import { Button } from '@/components/ui/button';

interface FinancesTabIntroProps {
  /** localStorage key used to persist dismissal of this card. */
  storageKey: string;
  title: string;
  description: string;
  /** Data sources that feed this tab. */
  sources: string[];
  /** The outcome the tab produces (rendered after a ⇒). */
  output: string;
}

export const FinancesTabIntro: React.FC<FinancesTabIntroProps> = ({
  storageKey,
  title,
  description,
  sources,
  output,
}) => {
  const [dismissed, setDismissed] = useState(
    () => localStorage.getItem(storageKey) === 'true',
  );

  if (dismissed) return null;

  const dismiss = () => {
    localStorage.setItem(storageKey, 'true');
    setDismissed(true);
  };

  return (
    <ProfessionalCard className="mb-4 border-primary/20 bg-primary/5">
      <ProfessionalCardContent className="flex items-start gap-3 py-3">
        <Info className="mt-0.5 h-4 w-4 flex-shrink-0 text-primary" />
        <div className="min-w-0 flex-1">
          <div className="text-sm font-medium">{title}</div>
          <div className="text-xs text-muted-foreground">{description}</div>
          <div className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
            {sources.map((source, i) => (
              <span key={source} className="flex items-center gap-2">
                {i > 0 ? (
                  <span aria-hidden className="text-muted-foreground/50">
                    ·
                  </span>
                ) : null}
                {source}
              </span>
            ))}
          </div>
          <div className="mt-1 text-xs font-medium text-primary">
            ⇒ {output}
          </div>
        </div>
        <Button
          size="sm"
          variant="ghost"
          className="h-6 w-6 flex-shrink-0 p-0"
          aria-label="Dismiss"
          onClick={dismiss}
        >
          <X className="h-4 w-4" />
        </Button>
      </ProfessionalCardContent>
    </ProfessionalCard>
  );
};
