import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { ExpenseApproval } from '@/types';
import { CheckCircle, XCircle, Loader2 } from 'lucide-react';

interface ApprovalActionButtonsProps {
  approval: ExpenseApproval;
  onAction: (approvalId: number, action: 'approve' | 'reject', data?: any) => Promise<void>;
}

export function ApprovalActionButtons({ approval, onAction }: ApprovalActionButtonsProps) {
  const [approveDialogOpen, setApproveDialogOpen] = useState(false);
  const [rejectDialogOpen, setRejectDialogOpen] = useState(false);
  const [approveNotes, setApproveNotes] = useState('');
  const [rejectReason, setRejectReason] = useState('');
  const [rejectNotes, setRejectNotes] = useState('');
  const [loading, setLoading] = useState<'approve' | 'reject' | null>(null);

  const handleApprove = async () => {
    try {
      setLoading('approve');
      await onAction(approval.id, 'approve', { notes: approveNotes });
      setApproveDialogOpen(false);
      setApproveNotes('');
    } catch (error) {
      // Error handling is done in parent component
    } finally {
      setLoading(null);
    }
  };

  const handleReject = async () => {
    if (!rejectReason.trim()) {
      return; // Validation should prevent this
    }
    
    try {
      setLoading('reject');
      await onAction(approval.id, 'reject', { 
        reason: rejectReason, 
        notes: rejectNotes 
      });
      setRejectDialogOpen(false);
      setRejectReason('');
      setRejectNotes('');
    } catch (error) {
      // Error handling is done in parent component
    } finally {
      setLoading(null);
    }
  };

  return (
    <div className="flex gap-2">
      {/* Approve Button */}
      <Dialog open={approveDialogOpen} onOpenChange={setApproveDialogOpen}>
        <DialogTrigger asChild>
          <Button
            size="sm"
            className="bg-green-600 hover:bg-green-700 text-white"
            disabled={loading !== null}
          >
            {loading === 'approve' ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <CheckCircle className="h-4 w-4" />
            )}
            Approve
          </Button>
        </DialogTrigger>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Approve Expense</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="p-4 bg-muted rounded-lg">
              <div className="text-sm space-y-1">
                <div><strong>Amount:</strong> {approval.expense?.currency || 'USD'} {approval.expense?.amount?.toFixed(2)}</div>
                <div><strong>Category:</strong> {approval.expense?.category}</div>
                {approval.expense?.vendor && <div><strong>Vendor:</strong> {approval.expense.vendor}</div>}
                <div><strong>Date:</strong> {new Date(approval.expense?.expense_date || '').toLocaleDateString()}</div>
              </div>
            </div>
            
            <div className="space-y-2">
              <Label htmlFor="approve-notes">Notes (Optional)</Label>
              <Textarea
                id="approve-notes"
                placeholder="Add any notes about this approval..."
                value={approveNotes}
                onChange={(e) => setApproveNotes(e.target.value)}
                rows={3}
              />
            </div>
            
            <div className="flex justify-end gap-2">
              <Button
                variant="outline"
                onClick={() => setApproveDialogOpen(false)}
                disabled={loading === 'approve'}
              >
                Cancel
              </Button>
              <Button
                onClick={handleApprove}
                disabled={loading === 'approve'}
                className="bg-green-600 hover:bg-green-700"
              >
                {loading === 'approve' ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin mr-2" />
                    Approving...
                  </>
                ) : (
                  <>
                    <CheckCircle className="h-4 w-4 mr-2" />
                    Approve Expense
                  </>
                )}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Reject Button */}
      <Dialog open={rejectDialogOpen} onOpenChange={setRejectDialogOpen}>
        <DialogTrigger asChild>
          <Button
            variant="destructive"
            size="sm"
            disabled={loading !== null}
          >
            {loading === 'reject' ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <XCircle className="h-4 w-4" />
            )}
            Reject
          </Button>
        </DialogTrigger>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Reject Expense</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="p-4 bg-muted rounded-lg">
              <div className="text-sm space-y-1">
                <div><strong>Amount:</strong> {approval.expense?.currency || 'USD'} {approval.expense?.amount?.toFixed(2)}</div>
                <div><strong>Category:</strong> {approval.expense?.category}</div>
                {approval.expense?.vendor && <div><strong>Vendor:</strong> {approval.expense.vendor}</div>}
                <div><strong>Date:</strong> {new Date(approval.expense?.expense_date || '').toLocaleDateString()}</div>
              </div>
            </div>
            
            <div className="space-y-2">
              <Label htmlFor="reject-reason">Rejection Reason *</Label>
              <Textarea
                id="reject-reason"
                placeholder="Please provide a reason for rejecting this expense..."
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
                rows={3}
                required
              />
            </div>
            
            <div className="space-y-2">
              <Label htmlFor="reject-notes">Additional Notes (Optional)</Label>
              <Textarea
                id="reject-notes"
                placeholder="Add any additional notes..."
                value={rejectNotes}
                onChange={(e) => setRejectNotes(e.target.value)}
                rows={2}
              />
            </div>
            
            <div className="flex justify-end gap-2">
              <Button
                variant="outline"
                onClick={() => setRejectDialogOpen(false)}
                disabled={loading === 'reject'}
              >
                Cancel
              </Button>
              <Button
                variant="destructive"
                onClick={handleReject}
                disabled={loading === 'reject' || !rejectReason.trim()}
              >
                {loading === 'reject' ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin mr-2" />
                    Rejecting...
                  </>
                ) : (
                  <>
                    <XCircle className="h-4 w-4 mr-2" />
                    Reject Expense
                  </>
                )}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}