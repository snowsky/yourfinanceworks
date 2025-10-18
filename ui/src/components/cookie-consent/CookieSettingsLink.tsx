import React from 'react';
import { Settings } from 'lucide-react';

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
  const baseClasses = variant === 'button' 
    ? 'inline-flex items-center gap-2 px-3 py-2 text-sm font-medium rounded-md border border-gray-300 bg-white text-gray-700 hover:bg-gray-50 transition-colors cursor-pointer'
    : 'inline-flex items-center gap-1 text-sm text-blue-600 hover:text-blue-800 hover:underline transition-colors cursor-pointer';

  const handleClick = () => {
    // Dispatch custom event to open the preferences modal
    window.dispatchEvent(new CustomEvent('openCookiePreferences'));
  };

  return (
    <button 
      onClick={handleClick}
      className={`${baseClasses} ${className}`}
      title="Manage your cookie preferences"
    >
      {showIcon && <Settings className="w-4 h-4" />}
      Cookie Settings
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