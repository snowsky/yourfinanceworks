import React from 'react';
import { AlertCircle, Lock } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { useTranslation } from 'react-i18next';

interface LicenseAlertProps {
  message: string;
  feature?: string;
  compact?: boolean;
}

export const LicenseAlert: React.FC<LicenseAlertProps> = ({
  message,
  feature,
  compact = false,
}) => {
  const { t } = useTranslation();

  if (compact) {
    return (
      <div className="bg-amber-50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-800 rounded-lg p-3 flex items-start gap-3">
        <AlertCircle className="h-5 w-5 text-amber-600 dark:text-amber-500 flex-shrink-0 mt-0.5" />
        <div className="flex-1 min-w-0">
          <p className="text-sm text-amber-800 dark:text-amber-200">
            {message}
          </p>
        </div>
        <Button
          asChild
          size="sm"
          variant="outline"
          className="flex-shrink-0 ml-2"
        >
          <Link to="/settings?tab=license">
            {t('license.upgrade', 'Upgrade')}
          </Link>
        </Button>
      </div>
    );
  }

  return (
    <div className="bg-amber-50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-800 rounded-lg p-4 space-y-3">
      <div className="flex items-start gap-3">
        <Lock className="h-5 w-5 text-amber-600 dark:text-amber-500 flex-shrink-0 mt-0.5" />
        <div className="flex-1">
          <h3 className="font-semibold text-amber-900 dark:text-amber-100 mb-1">
            {t('license.required', 'License Required')}
          </h3>
          <p className="text-sm text-amber-800 dark:text-amber-200">
            {message}
          </p>
        </div>
      </div>
      <div className="flex gap-2 ml-8">
        <Button
          asChild
          size="sm"
          variant="default"
        >
          <Link to="/settings?tab=license">
            {t('license.upgrade', 'Upgrade License')}
          </Link>
        </Button>
      </div>
    </div>
  );
};
