import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog';
import { Tag, Plus, Minus, Wand, Trash2 } from 'lucide-react';
import { ProfessionalButton } from '@/components/ui/professional-button';
import { expenseApi, type Expense } from '@/lib/api';
import { toast } from 'sonner';

interface BulkActionsToolbarProps {
  selectedIds: number[];
  setSelectedIds: (ids: number[]) => void;
  bulkLabel: string;
  setBulkLabel: (v: string) => void;
  canPerformActionsResult: boolean;
  categoryFilter: string;
  labelFilter: string;
  unlinkedOnly: boolean;
  page: number;
  pageSize: number;
  onExpensesChange: (expenses: Expense[], total: number) => void;
  showRecycleBin: boolean;
  onRecycleBinRefresh: () => void;
  onBulkRunReview: () => void;
  loading: boolean;
  onDuplicatesInvalidate?: () => void;
}

export function BulkActionsToolbar({
  selectedIds,
  setSelectedIds,
  bulkLabel,
  setBulkLabel,
  canPerformActionsResult,
  categoryFilter,
  labelFilter,
  unlinkedOnly,
  page,
  pageSize,
  onExpensesChange,
  showRecycleBin,
  onRecycleBinRefresh,
  onBulkRunReview,
  loading,
  onDuplicatesInvalidate,
}: BulkActionsToolbarProps) {
  const { t } = useTranslation();

  if (selectedIds.length === 0) return null;

  return (
    <div className="flex flex-col md:flex-row items-center justify-between p-4 bg-gradient-to-r from-primary/10 to-primary/5 border border-primary/20 rounded-xl shadow-sm gap-4 slide-in">
      <div className="flex items-center gap-3">
        <div className="h-2 w-2 rounded-full bg-primary animate-pulse shadow-[0_0_8px_rgba(var(--primary),0.5)]"></div>
        <span className="text-sm font-bold text-foreground">
          {selectedIds.length} {t('expenses.selected', { defaultValue: 'selected' })}
        </span>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setSelectedIds([])}
          className="h-8 text-xs hover:bg-primary/10 transition-colors"
        >
          {t('common.clear', { defaultValue: 'Clear' })}
        </Button>
      </div>

      <div className="flex flex-wrap items-center gap-3 w-full md:w-auto justify-end">
        <div className="relative group flex-1 md:flex-initial min-w-[200px]">
          <Tag className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
          <Input
            placeholder={t('expenses.bulk_label_placeholder', { defaultValue: 'Add or remove label' })}
            value={bulkLabel}
            onChange={(e) => setBulkLabel(e.target.value)}
            className="pl-8 h-9 text-sm border-primary/20 focus:border-primary/40 bg-background/50"
          />
        </div>

        <div className="flex items-center gap-1.5">
          <ProfessionalButton
            variant="outline"
            size="sm"
            disabled={!canPerformActionsResult || !bulkLabel.trim()}
            onClick={async () => {
              try {
                const skip = (page - 1) * pageSize;
                await expenseApi.bulkLabels(selectedIds, 'add', bulkLabel.trim());
                const result = await expenseApi.getExpensesPaginated({ category: categoryFilter, label: labelFilter || undefined, unlinkedOnly, skip, limit: pageSize, excludeStatus: 'pending_approval' });
                onExpensesChange(result.expenses, result.total);
                setSelectedIds([]);
                setBulkLabel('');
                toast.success(t('expenses.labels.added', { defaultValue: 'Labels added' }));
              } catch (e: any) {
                toast.error(e?.message || t('expenses.labels.add_failed', { defaultValue: 'Failed to add label' }));
              }
            }}
            className="h-9 px-3 gap-1.5"
          >
            <Plus className="h-3.5 w-3.5" />
            {t('expenses.add')}
          </ProfessionalButton>

          <ProfessionalButton
            variant="outline"
            size="sm"
            disabled={!canPerformActionsResult || !bulkLabel.trim()}
            onClick={async () => {
              try {
                const skip = (page - 1) * pageSize;
                await expenseApi.bulkLabels(selectedIds, 'remove', bulkLabel.trim());
                const result = await expenseApi.getExpensesPaginated({ category: categoryFilter, label: labelFilter || undefined, unlinkedOnly, skip, limit: pageSize, excludeStatus: 'pending_approval' });
                onExpensesChange(result.expenses, result.total);
                setSelectedIds([]);
                setBulkLabel('');
                toast.success(t('expenses.labels.removed', { defaultValue: 'Labels removed' }));
              } catch (e: any) {
                toast.error(e?.message || t('expenses.labels.remove_failed', { defaultValue: 'Failed to remove label' }));
              }
            }}
            className="h-9 px-3 gap-1.5"
          >
            <Minus className="h-3.5 w-3.5" />
            {t('expenses.remove')}
          </ProfessionalButton>
        </div>

        <div className="flex items-center gap-1.5 ml-2">
          <ProfessionalButton
            variant="outline"
            size="sm"
            onClick={onBulkRunReview}
            disabled={!canPerformActionsResult || loading}
            className="h-9 px-3 gap-1.5 shadow-sm border-primary/20 bg-primary/5 hover:bg-primary/10 text-primary whitespace-nowrap"
          >
            <Wand className="w-3.5 h-3.5" />
            Run Review
          </ProfessionalButton>
        </div>

        <div className="w-px h-6 bg-primary/10 hidden md:block mx-1"></div>

        <AlertDialog>
          <AlertDialogTrigger asChild>
            <ProfessionalButton
              variant="destructive"
              size="sm"
              disabled={!canPerformActionsResult}
              className="h-9 px-3 gap-1.5 shadow-sm"
            >
              <Trash2 className="h-3.5 w-3.5" />
              {t('expenses.delete_selected', { defaultValue: 'Delete' })}
            </ProfessionalButton>
          </AlertDialogTrigger>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>
                {selectedIds.length === 1
                  ? t('expenses.delete_single_title', 'Delete 1 Expense')
                  : t('expenses.delete_multiple_title', 'Delete {{count}} Expenses', { count: selectedIds.length })}
              </AlertDialogTitle>
              <AlertDialogDescription>
                {selectedIds.length === 1
                  ? t('expenses.delete_single_description', 'Are you sure you want to delete 1 expense? This will move it to the recycle bin.')
                  : t('expenses.delete_multiple_description', 'Are you sure you want to delete {{count}} expenses? They will be moved to the recycle bin.', { count: selectedIds.length })}
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>{t('common.cancel')}</AlertDialogCancel>
              <AlertDialogAction
                className="bg-destructive text-white hover:bg-destructive/90"
                onClick={async () => {
                  try {
                    await expenseApi.bulkDelete(selectedIds);
                    const result = await expenseApi.getExpensesPaginated({ category: categoryFilter, label: labelFilter || undefined, unlinkedOnly, skip: (page - 1) * pageSize, limit: pageSize, excludeStatus: 'pending_approval' });
                    onExpensesChange(result.expenses, result.total);
                    // Refresh recycle bin if it's currently open
                    if (showRecycleBin) {
                      console.log('🔄 Expenses bulk delete: Refreshing recycle bin, showRecycleBin:', showRecycleBin);
                      onRecycleBinRefresh();
                      console.log('✅ Expenses bulk delete: Recycle bin refreshed');
                    } else {
                      console.log('ℹ️ Expenses bulk delete: Recycle bin not open, skipping refresh');
                    }
                    setSelectedIds([]);
                    onDuplicatesInvalidate?.();
                    toast.success(`Successfully deleted ${selectedIds.length} expense${selectedIds.length > 1 ? 's' : ''}`);
                  } catch (e: any) {
                    toast.error(e?.message || t('expenses.bulk_delete_failed', { defaultValue: 'Failed to delete expenses' }));
                  }
                }}
              >
                {t('common.delete', { defaultValue: 'Delete' })}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>
    </div>
  );
}
