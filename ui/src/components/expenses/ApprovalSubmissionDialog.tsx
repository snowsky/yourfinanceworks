import { useState } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { AlertCircle, CheckCircle2 } from 'lucide-react';
import { Alert, AlertDescription } from '@/components/ui/alert';

interface ApprovalSubmissionDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: (notes?: string) => Promise<void>;
  expenseAmount: number;
  currency: string;
  category: string;
  selectedApproverName?: string;
  loading?: boolean;
}

export function ApprovalSubmissionDialog({
  open,
  onOpenChange,
  onConfirm,
  expenseAmount,
  currency,
  category,
  selectedApproverName,
  loading = false
}: ApprovalSubmissionDialogProps) {
  const [notes, setNotes] = useState('');

  const handleConfirm = async () => {
    try {
      await onConfirm(notes.trim() || undefined);
      setNotes(''); // Clear notes after successful submission
    } catch (error) {
      // Error handling is done in the parent component
    }
  };

  const handleCancel = () => {
    setNotes('');
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <CheckCircle2 className="h-5 w-5 text-green-600" />
            Submit for Approval
          </DialogTitle>
        </DialogHeader>
        
        <div className="space-y-4">
          <Alert>
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>
              Confirm submission for approval. The selected approver will be notified to review your expense.
            </AlertDescription>
          </Alert>

          <div className="space-y-2">
            <div className="text-sm">
              <span className="font-medium">Amount:</span> {currency} {expenseAmount.toFixed(2)}
            </div>
            <div className="text-sm">
              <span className="font-medium">Category:</span> {category}
            </div>
            {selectedApproverName && (
              <div className="text-sm">
                <span className="font-medium">Approver:</span> {selectedApproverName}
              </div>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="approval-notes">Additional Notes (Optional)</Label>
            <Textarea
              id="approval-notes"
              placeholder="Add any additional context for the approver..."
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={3}
              disabled={loading}
            />
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={handleCancel} disabled={loading}>
            Cancel
          </Button>
          <Button onClick={handleConfirm} disabled={loading}>
            {loading ? 'Submitting...' : 'Submit for Approval'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}