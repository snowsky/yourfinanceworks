import React from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { api } from '@/lib/api';
import { toast } from 'sonner';

interface PortfolioArchiveDialogProps {
  portfolioId: number;
  portfolioName: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess?: () => void;
}

const PortfolioArchiveDialog: React.FC<PortfolioArchiveDialogProps> = ({
  portfolioId,
  portfolioName,
  open,
  onOpenChange,
  onSuccess,
}) => {
  const queryClient = useQueryClient();

  const archivePortfolioMutation = useMutation({
    mutationFn: async () => {
      await api.put(`/investments/portfolios/${portfolioId}`, {
        is_archived: true,
      });
    },
    onSuccess: () => {
      toast.success('Portfolio archived successfully');
      queryClient.invalidateQueries({ queryKey: ['portfolios'] });
      onOpenChange(false);
      onSuccess?.();
    },
    onError: (error: any) => {
      const errorMessage = error?.response?.data?.detail || 'Failed to archive portfolio';
      toast.error(errorMessage);
    },
  });

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Archive Portfolio</AlertDialogTitle>
          <AlertDialogDescription>
            Are you sure you want to archive "{portfolioName}"?
            <br />
            <br />
            The portfolio and all its holdings will be hidden from your main view, but all data will be preserved. You can unarchive it anytime.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <div className="flex gap-4">
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction
            onClick={() => archivePortfolioMutation.mutate()}
            disabled={archivePortfolioMutation.isPending}
            className="bg-warning hover:bg-warning/90"
          >
            {archivePortfolioMutation.isPending ? 'Archiving...' : 'Archive'}
          </AlertDialogAction>
        </div>
      </AlertDialogContent>
    </AlertDialog>
  );
};

export default PortfolioArchiveDialog;
