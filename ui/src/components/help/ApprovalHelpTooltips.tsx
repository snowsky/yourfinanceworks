import React, { useState } from 'react';
import { HelpCircle, X, ChevronLeft, ChevronRight } from 'lucide-react';

interface TooltipContent {
  id: string;
  title: string;
  content: string;
  position?: 'top' | 'bottom' | 'left' | 'right';
}

interface ApprovalHelpTooltipsProps {
  context: 'submission' | 'approval' | 'dashboard' | 'rules' | 'delegation';
  children: React.ReactNode;
}

const tooltipContent: Record<string, TooltipContent[]> = {
  submission: [
    {
      id: 'submit-approval',
      title: 'Submit for Approval',
      content: 'Once you submit an expense for approval, you cannot edit it. Make sure all information is correct and receipts are uploaded before submitting.',
      position: 'top'
    },
    {
      id: 'approval-status',
      title: 'Approval Status',
      content: 'Track your expense through the approval process. Status shows: Pending (waiting for review), Approved (ready for reimbursement), or Rejected (needs corrections).',
      position: 'right'
    },
    {
      id: 'required-fields',
      title: 'Required Information',
      content: 'All fields marked with * are required for approval submission. Missing information will prevent submission and delay processing.',
      position: 'bottom'
    }
  ],
  approval: [
    {
      id: 'approve-button',
      title: 'Approve Expense',
      content: 'Click to approve this expense. You can add optional notes that will be sent to the employee. Approval cannot be undone.',
      position: 'top'
    },
    {
      id: 'reject-button',
      title: 'Reject Expense',
      content: 'Reject this expense with a required reason. The employee will receive your feedback and can resubmit after making corrections.',
      position: 'top'
    },
    {
      id: 'expense-details',
      title: 'Review Details',
      content: 'Carefully review all expense information, receipts, and documentation before making your decision. Check for policy compliance.',
      position: 'left'
    },
    {
      id: 'approval-history',
      title: 'Approval History',
      content: 'View the complete approval timeline. For multi-level approvals, see who has already approved and who needs to approve next.',
      position: 'right'
    }
  ],
  dashboard: [
    {
      id: 'pending-count',
      title: 'Pending Approvals',
      content: 'Number of expenses waiting for your approval. Click to see the full list and prioritize your reviews.',
      position: 'bottom'
    },
    {
      id: 'filter-options',
      title: 'Filter & Sort',
      content: 'Use filters to find specific expenses by amount, date, employee, or category. Sort by urgency or submission date.',
      position: 'left'
    },
    {
      id: 'bulk-actions',
      title: 'Bulk Actions',
      content: 'Select multiple expenses to approve similar items at once. Use carefully and only for routine, policy-compliant expenses.',
      position: 'top'
    },
    {
      id: 'delegation-status',
      title: 'Delegation Active',
      content: 'You have active delegation settings. Some approvals may be handled by your delegate during the specified period.',
      position: 'right'
    }
  ],
  rules: [
    {
      id: 'rule-priority',
      title: 'Rule Priority',
      content: 'Higher priority numbers are evaluated first. Use priority to ensure specific rules override general ones.',
      position: 'right'
    },
    {
      id: 'amount-ranges',
      title: 'Amount Ranges',
      content: 'Set minimum and maximum amounts for this rule. Avoid gaps between rules to ensure all expenses have an approver.',
      position: 'top'
    },
    {
      id: 'category-filter',
      title: 'Category Filter',
      content: 'Specify which expense categories this rule applies to. Leave empty to apply to all categories within the amount range.',
      position: 'bottom'
    },
    {
      id: 'approval-levels',
      title: 'Approval Levels',
      content: 'Level 1 is the first approver, Level 2 is second, etc. Create multiple rules with the same amount range for multi-level approval.',
      position: 'left'
    },
    {
      id: 'auto-approval',
      title: 'Auto-Approval',
      content: 'Expenses below this amount are automatically approved. Use for small, routine expenses to reduce approval workload.',
      position: 'top'
    }
  ],
  delegation: [
    {
      id: 'delegate-selection',
      title: 'Choose Delegate',
      content: 'Select a trusted team member to handle approvals in your absence. They must have appropriate permissions and knowledge of policies.',
      position: 'right'
    },
    {
      id: 'delegation-period',
      title: 'Delegation Period',
      content: 'Set specific start and end dates for delegation. Delegation automatically expires at the end date for security.',
      position: 'bottom'
    },
    {
      id: 'delegation-scope',
      title: 'Delegation Scope',
      content: 'Choose whether to delegate all approvals or only specific types (amount limits, categories). Partial delegation maintains control.',
      position: 'left'
    },
    {
      id: 'notification-settings',
      title: 'Delegation Notifications',
      content: 'Configure whether you receive copies of approval decisions made by your delegate. Recommended for audit purposes.',
      position: 'top'
    }
  ]
};

const ApprovalHelpTooltips: React.FC<ApprovalHelpTooltipsProps> = ({ context, children }) => {
  const [isHelpMode, setIsHelpMode] = useState(false);
  const [currentTooltip, setCurrentTooltip] = useState(0);
  const [showTour, setShowTour] = useState(false);

  const contextTooltips = tooltipContent[context] || [];

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
        title={isHelpMode ? 'Exit Help Mode' : 'Show Help'}
      >
        <HelpCircle size={20} />
      </button>

      {/* Tour Navigation */}
      {showTour && (
        <div className="fixed bottom-4 left-1/2 transform -translate-x-1/2 z-50 bg-white rounded-lg shadow-xl border p-4 min-w-80">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-semibold text-gray-900">
              {contextTooltips[currentTooltip]?.title}
            </h3>
            <button
              onClick={endTour}
              className="text-gray-400 hover:text-gray-600"
            >
              <X size={16} />
            </button>
          </div>
          
          <p className="text-gray-700 mb-4">
            {contextTooltips[currentTooltip]?.content}
          </p>
          
          <div className="flex items-center justify-between">
            <div className="flex space-x-2">
              <button
                onClick={prevTooltip}
                disabled={currentTooltip === 0}
                className="flex items-center px-3 py-1 text-sm bg-gray-100 rounded disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-200"
              >
                <ChevronLeft size={16} className="mr-1" />
                Previous
              </button>
              
              <button
                onClick={nextTooltip}
                className="flex items-center px-3 py-1 text-sm bg-blue-600 text-white rounded hover:bg-blue-700"
              >
                {currentTooltip === contextTooltips.length - 1 ? 'Finish' : 'Next'}
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
  const [showTooltip, setShowTooltip] = useState(false);
  
  const tooltipData = tooltipContent[context]?.find(t => t.id === id);
  
  if (!tooltipData) return <>{children}</>;

  return (
    <div 
      className={`relative inline-block ${className}`}
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
          <div className="font-medium mb-1">{tooltipData.title}</div>
          <div className="text-xs">{tooltipData.content}</div>
          
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
  const [isOpen, setIsOpen] = useState(false);
  
  const contextTips = {
    submission: [
      'Ensure all required fields are completed before submitting',
      'Upload clear, legible receipts for all expenses',
      'Provide detailed business justification in descriptions',
      'Review expense policy limits before submission'
    ],
    approval: [
      'Review all expense details and supporting documentation',
      'Check expense compliance with company policies',
      'Provide clear feedback when rejecting expenses',
      'Use delegation when you will be unavailable'
    ],
    dashboard: [
      'Use filters to prioritize urgent approvals',
      'Set up notifications for timely approval processing',
      'Review approval analytics to identify bottlenecks',
      'Configure delegation before planned absences'
    ],
    rules: [
      'Test new rules before activating them',
      'Avoid gaps in amount ranges between rules',
      'Use priority to handle rule conflicts',
      'Document rule changes for audit purposes'
    ],
    delegation: [
      'Choose delegates with appropriate knowledge and permissions',
      'Set specific start and end dates for security',
      'Configure notification preferences for oversight',
      'Review delegation effectiveness regularly'
    ]
  };

  const tips = contextTips[context] || [];

  return (
    <div className={`relative ${className}`}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center text-sm text-blue-600 hover:text-blue-800"
      >
        <HelpCircle size={16} className="mr-1" />
        Quick Help
      </button>
      
      {isOpen && (
        <div className="absolute top-full mt-2 right-0 bg-white border rounded-lg shadow-lg p-4 w-80 z-50">
          <div className="flex items-center justify-between mb-3">
            <h4 className="font-medium text-gray-900">Quick Tips</h4>
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