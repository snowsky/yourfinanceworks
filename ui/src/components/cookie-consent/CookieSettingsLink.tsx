import React from 'react';
import { Settings } from 'lucide-react';
import { useTranslation } from 'react-i18next';

interface CookieSettingsLinkProps {
  className?: string;
  showIcon?: boolean;
  variant?: 'link' | 'button';
}

export const CookieSettingsLink: React.FC<CookieSettingsLinkProps> = ({ 
  className = '', 
  showIcon = true,
  variant = 'link'
}) => {
  const { t } = useTranslation();
  const baseClasses = variant === 'button' 
    ? 'inline-flex items-center gap-2 px-3 py-2 text-sm font-medium rounded-md border border-border bg-card text-muted-foreground hover:bg-muted transition-colors cursor-pointer'
    : 'inline-flex items-center gap-1 text-sm text-primary hover:text-primary hover:underline transition-colors cursor-pointer';

  const handleClick = () => {
    // Dispatch custom event to open the preferences modal
    window.dispatchEvent(new CustomEvent('openCookiePreferences'));
  };

  return (
    <button 
      onClick={handleClick}
      className={`${baseClasses} ${className}`}
      title={t('cookieConsent.banner.managePreferences')}
    >
      {showIcon && <Settings className="w-4 h-4" />}
      {t('settings.tabs.cookies')}
    </button>
  );
};

// Hook to programmatically open cookie preferences modal
export const useCookiePreferences = () => {
  const openPreferences = () => {
    // Dispatch custom event to open the preferences modal
    window.dispatchEvent(new CustomEvent('openCookiePreferences'));
  };

  return { openPreferences };
};

export default CookieSettingsLink;