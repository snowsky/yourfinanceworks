import React, { useState } from 'react';
import { HelpCircle, X, ChevronLeft, ChevronRight } from 'lucide-react';
import { useTranslation } from 'react-i18next';

interface ApprovalHelpTooltipsProps {
  context: 'submission' | 'approval' | 'dashboard' | 'rules' | 'delegation';
  children: React.ReactNode;
}

const tooltipIds: Record<string, Array<{ id: string; position?: 'top' | 'bottom' | 'left' | 'right' }>> = {
  submission: [
    { id: 'submit_approval', position: 'top' },
    { id: 'approval_status', position: 'right' },
    { id: 'required_fields', position: 'bottom' }
  ],
  approval: [
    { id: 'approve_button', position: 'top' },
    { id: 'reject_button', position: 'top' },
    { id: 'expense_details', position: 'left' },
    { id: 'approval_history', position: 'right' }
  ],
  dashboard: [
    { id: 'pending_count', position: 'bottom' },
    { id: 'filter_options', position: 'left' },
    { id: 'bulk_actions', position: 'top' },
    { id: 'delegation_status', position: 'right' }
  ],
  rules: [
    { id: 'rule_priority', position: 'right' },
    { id: 'amount_ranges', position: 'top' },
    { id: 'category_filter', position: 'bottom' },
    { id: 'approval_levels', position: 'left' },
    { id: 'auto_approval', position: 'top' }
  ],
  delegation: [
    { id: 'delegate_selection', position: 'right' },
    { id: 'delegation_period', position: 'bottom' },
    { id: 'delegation_scope', position: 'left' },
    { id: 'notification_settings', position: 'top' }
  ]
};

const ApprovalHelpTooltips: React.FC<ApprovalHelpTooltipsProps> = ({ context, children }) => {
  const { t } = useTranslation();
  const [isHelpMode, setIsHelpMode] = useState(false);
  const [currentTooltip, setCurrentTooltip] = useState(0);
  const [showTour, setShowTour] = useState(false);

  const contextTooltips = tooltipIds[context] || [];

  const startTour = () => {
    setShowTour(true);
    setCurrentTooltip(0);
    setIsHelpMode(true);
  };

  const nextTooltip = () => {
    if (currentTooltip < contextTooltips.length - 1) {
      setCurrentTooltip(currentTooltip + 1);
    } else {
      endTour();
    }
  };

  const prevTooltip = () => {
    if (currentTooltip > 0) {
      setCurrentTooltip(currentTooltip - 1);
    }
  };

  const endTour = () => {
    setShowTour(false);
    setIsHelpMode(false);
    setCurrentTooltip(0);
  };

  const toggleHelpMode = () => {
    if (isHelpMode) {
      setIsHelpMode(false);
      setShowTour(false);
    } else {
      startTour();
    }
  };

  return (
    <div className="relative">
      {/* Help Toggle Button */}
      <button
        onClick={toggleHelpMode}
        className={`fixed top-4 right-4 z-50 p-2 rounded-full shadow-lg transition-colors ${
          isHelpMode 
            ? 'bg-blue-600 text-white' 
            : 'bg-white text-gray-600 hover:bg-gray-50'
        }`}
        title={isHelpMode ? t('approvalHelp.exit_help') : t('approvalHelp.show_help')}
      >
        <HelpCircle size={20} />
      </button>

      {/* Tour Navigation */}
      {showTour && (
        <div className="fixed bottom-4 left-1/2 transform -translate-x-1/2 z-50 bg-white rounded-lg shadow-xl border p-4 min-w-80">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-semibold text-gray-900">
              {t(`approvalHelp.${context}.${contextTooltips[currentTooltip]?.id}.title`)}
            </h3>
            <button
              onClick={endTour}
              className="text-gray-400 hover:text-gray-600"
            >
              <X size={16} />
            </button>
          </div>
          
          <p className="text-gray-700 mb-4">
            {t(`approvalHelp.${context}.${contextTooltips[currentTooltip]?.id}.content`)}
          </p>
          
          <div className="flex items-center justify-between">
            <div className="flex space-x-2">
              <button
                onClick={prevTooltip}
                disabled={currentTooltip === 0}
                className="flex items-center px-3 py-1 text-sm bg-gray-100 rounded disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-200"
              >
                <ChevronLeft size={16} className="mr-1" />
                {t('approvalHelp.previous')}
              </button>
              
              <button
                onClick={nextTooltip}
                className="flex items-center px-3 py-1 text-sm bg-blue-600 text-white rounded hover:bg-blue-700"
              >
                {currentTooltip === contextTooltips.length - 1 ? t('approvalHelp.finish') : t('approvalHelp.next')}
                {currentTooltip < contextTooltips.length - 1 && (
                  <ChevronRight size={16} className="ml-1" />
                )}
              </button>
            </div>
            
            <span className="text-sm text-gray-500">
              {currentTooltip + 1} of {contextTooltips.length}
            </span>
          </div>
        </div>
      )}

      {/* Help Mode Overlay */}
      {isHelpMode && (
        <div className="fixed inset-0 bg-black bg-opacity-20 z-40 pointer-events-none" />
      )}

      {children}
    </div>
  );
};

// Individual Tooltip Component for specific elements
interface TooltipProps {
  id: string;
  context: string;
  children: React.ReactNode;
  className?: string;
}

export const HelpTooltip: React.FC<TooltipProps> = ({ id, context, children, className = '' }) => {
  const { t } = useTranslation();
  const [showTooltip, setShowTooltip] = useState(false);
  
  const tooltipData = tooltipIds[context]?.find(t => t.id === id);
  
  if (!tooltipData) return <>{children}</>;

  return (
    <div 
      className={`relative ${className}`}
      onMouseEnter={() => setShowTooltip(true)}
      onMouseLeave={() => setShowTooltip(false)}
    >
      {children}
      
      {showTooltip && (
        <div className={`absolute z-50 px-3 py-2 text-sm bg-gray-900 text-white rounded-lg shadow-lg max-w-xs ${
          tooltipData.position === 'top' ? 'bottom-full mb-2 left-1/2 transform -translate-x-1/2' :
          tooltipData.position === 'bottom' ? 'top-full mt-2 left-1/2 transform -translate-x-1/2' :
          tooltipData.position === 'left' ? 'right-full mr-2 top-1/2 transform -translate-y-1/2' :
          'left-full ml-2 top-1/2 transform -translate-y-1/2'
        }`}>
          <div className="font-medium mb-1">{t(`approvalHelp.${context}.${tooltipData.id}.title`)}</div>
          <div className="text-xs">{t(`approvalHelp.${context}.${tooltipData.id}.content`)}</div>
          
          {/* Tooltip Arrow */}
          <div className={`absolute w-2 h-2 bg-gray-900 transform rotate-45 ${
            tooltipData.position === 'top' ? 'top-full left-1/2 -translate-x-1/2 -mt-1' :
            tooltipData.position === 'bottom' ? 'bottom-full left-1/2 -translate-x-1/2 -mb-1' :
            tooltipData.position === 'left' ? 'left-full top-1/2 -translate-y-1/2 -ml-1' :
            'right-full top-1/2 -translate-y-1/2 -mr-1'
          }`} />
        </div>
      )}
    </div>
  );
};

// Quick Help Component for contextual help
interface QuickHelpProps {
  context: 'submission' | 'approval' | 'dashboard' | 'rules' | 'delegation';
  className?: string;
}

export const QuickHelp: React.FC<QuickHelpProps> = ({ context, className = '' }) => {
  const { t } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);
  
  const tips = t(`approvalHelp.${context}.tips`, { returnObjects: true }) as string[];

  return (
    <div className={`relative ${className}`}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center text-sm text-blue-600 hover:text-blue-800"
      >
        <HelpCircle size={16} className="mr-1" />
        {t('approvalHelp.quick_help')}
      </button>
      
      {isOpen && (
        <div className="absolute top-full mt-2 right-0 bg-white border rounded-lg shadow-lg p-4 w-80 z-50">
          <div className="flex items-center justify-between mb-3">
            <h4 className="font-medium text-gray-900">{t('approvalHelp.quick_tips')}</h4>
            <button
              onClick={() => setIsOpen(false)}
              className="text-gray-400 hover:text-gray-600"
            >
              <X size={16} />
            </button>
          </div>
          
          <ul className="space-y-2">
            {tips.map((tip, index) => (
              <li key={index} className="flex items-start text-sm text-gray-700">
                <span className="w-2 h-2 bg-blue-500 rounded-full mt-2 mr-3 flex-shrink-0" />
                {tip}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};

export default ApprovalHelpTooltips;