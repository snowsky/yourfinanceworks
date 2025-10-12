import { CheckCircle2, Clock, User } from 'lucide-react';
import { Alert, AlertDescription } from '@/components/ui/alert';

interface ApprovalSuccessNotificationProps {
  expenseAmount: number;
  currency: string;
  approverName?: string;
  estimatedApprovalTime?: string;
}

export function ApprovalSuccessNotification({
  expenseAmount,
  currency,
  approverName,
  estimatedApprovalTime = '1-2 business days'
}: ApprovalSuccessNotificationProps) {
  return (
    <Alert className="border-green-200 bg-green-50">
      <CheckCircle2 className="h-4 w-4 text-green-600" />
      <AlertDescription className="text-green-800">
        <div className="space-y-2">
          <div className="font-medium">
            Expense submitted for approval successfully!
          </div>
          <div className="text-sm space-y-1">
            <div>Amount: {currency} {expenseAmount.toFixed(2)}</div>
            {approverName && (
              <div className="flex items-center gap-1">
                <User className="h-3 w-3" />
                Assigned to: {approverName}
              </div>
            )}
            <div className="flex items-center gap-1">
              <Clock className="h-3 w-3" />
              Expected approval time: {estimatedApprovalTime}
            </div>
          </div>
        </div>
      </AlertDescription>
    </Alert>
  );
}