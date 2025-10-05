import React from 'react';
import { Badge } from '@/components/ui/badge';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { Progress } from '@/components/ui/progress';
import { 
  Clock, 
  CheckCircle, 
  XCircle, 
  AlertTriangle,
  User,
  Calendar
} from 'lucide-react';
import { format } from 'date-fns';
import type { ExpenseApproval } from '@/types';

interface ExpenseApprovalStatusProps {
  expense: {
    id: number;
    status: string;
    amount: number;
    currency?: string;
  };
  approvals?: ExpenseApproval[];
  className?: string;
}

export function ExpenseApprovalStatus({ expense, approvals = [], className }: ExpenseApprovalStatusProps) {
  // If expense is not in approval workflow, don't show approval status
  if (!expense.status.includes('approval') && !expense.status.includes('pending_approval') && !expense.status.includes('approved') && !expense.status.includes('rejected')) {
    return null;
  }

  const getStatusBadge = () => {
    switch (expense.status) {
      case 'pending_approval':
        return (
          <div className="flex items-center gap-1">
            <Clock className="w-3 h-3 text-amber-600" />
            <Badge variant="warning">Pending Approval</Badge>
          </div>
        );
      case 'approved':
        return (
          <div className="flex items-center gap-1">
            <CheckCircle className="w-3 h-3 text-green-600" />
            <Badge variant="success">Approved</Badge>
          </div>
        );
      case 'rejected':
        return (
          <div className="flex items-center gap-1">
            <XCircle className="w-3 h-3 text-red-600" />
            <Badge variant="destructive">Rejected</Badge>
          </div>
        );
      case 'resubmitted':
        return (
          <div className="flex items-center gap-1">
            <AlertTriangle className="w-3 h-3 text-blue-600" />
            <Badge variant="info">Resubmitted</Badge>
          </div>
        );
      default:
        return null;
    }
  };

  const getApprovalProgress = () => {
    if (!approvals.length) return null;

    const totalLevels = Math.max(...approvals.map(a => a.approval_level));
    const completedLevels = approvals.filter(a => a.status === 'approved').length;
    const progress = totalLevels > 0 ? (completedLevels / totalLevels) * 100 : 0;

    return (
      <div className="flex items-center gap-2 mt-1">
        <Progress value={progress} className="w-16 h-1" />
        <span className="text-xs text-muted-foreground">
          {completedLevels}/{totalLevels}
        </span>
      </div>
    );
  };

  const getCurrentApprover = () => {
    const currentApproval = approvals.find(a => a.is_current_level && a.status === 'pending');
    return currentApproval?.approver;
  };

  const getSubmissionTime = () => {
    const firstApproval = approvals.find(a => a.approval_level === 1);
    return firstApproval?.submitted_at;
  };

  const getTooltipContent = () => {
    const currentApprover = getCurrentApprover();
    const submissionTime = getSubmissionTime();
    const rejectedApproval = approvals.find(a => a.status === 'rejected');

    return (
      <div className="space-y-2 text-sm">
        {expense.status === 'pending_approval' && currentApprover && (
          <div className="flex items-center gap-2">
            <User className="w-3 h-3" />
            <span>Current approver: {currentApprover.name}</span>
          </div>
        )}
        
        {submissionTime && (
          <div className="flex items-center gap-2">
            <Calendar className="w-3 h-3" />
            <span>Submitted: {format(new Date(submissionTime), 'MMM d, yyyy HH:mm')}</span>
          </div>
        )}

        {expense.status === 'rejected' && rejectedApproval?.rejection_reason && (
          <div className="space-y-1">
            <div className="font-medium">Rejection reason:</div>
            <div className="text-muted-foreground">{rejectedApproval.rejection_reason}</div>
          </div>
        )}

        {approvals.length > 1 && (
          <div className="space-y-1">
            <div className="font-medium">Approval History:</div>
            {approvals.map((approval, index) => (
              <div key={approval.id} className="text-xs text-muted-foreground">
                Level {approval.approval_level}: {approval.status} 
                {approval.approver && ` by ${approval.approver.name}`}
                {approval.decided_at && ` on ${format(new Date(approval.decided_at), 'MMM d')}`}
              </div>
            ))}
          </div>
        )}
      </div>
    );
  };

  const statusBadge = getStatusBadge();
  if (!statusBadge) return null;

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <div className={`flex flex-col items-start gap-1 ${className}`}>
            {statusBadge}
            {getApprovalProgress()}
          </div>
        </TooltipTrigger>
        <TooltipContent side="top" className="max-w-xs">
          {getTooltipContent()}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}