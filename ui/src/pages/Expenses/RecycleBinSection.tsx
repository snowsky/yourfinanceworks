import { useTranslation } from 'react-i18next';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Pagination, PaginationContent, PaginationItem, PaginationLink, PaginationNext, PaginationPrevious } from '@/components/ui/pagination';
import { Loader2, Trash2, RotateCcw, Receipt } from 'lucide-react';
import { Collapsible, CollapsibleContent } from '@/components/ui/collapsible';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { CurrencyDisplay } from '@/components/ui/currency-display';
import { ProfessionalCard } from '@/components/ui/professional-card';
import { ProfessionalButton } from '@/components/ui/professional-button';
import { formatDate } from '@/lib/utils';
import type { DeletedExpense } from '@/lib/api';

interface RecycleBinSectionProps {
  showRecycleBin: boolean;
  setShowRecycleBin: (v: boolean) => void;
  recycleBinLoading: boolean;
  deletedExpenses: DeletedExpense[];
  recycleBinTotalCount: number;
  recycleBinCurrentPage: number;
  setRecycleBinCurrentPage: (fn: (prev: number) => number) => void;
  recycleBinPageSize: number;
  onRestore: (expenseId: number) => Promise<void>;
  onEmptyRecycleBin: () => void;
  onSetExpenseToPermanentlyDelete: (id: number) => void;
  expenseToPermanentlyDelete: number | null;
  onPermanentlyDelete: (expenseId: number) => Promise<void>;
  emptyRecycleBinModalOpen: boolean;
  setEmptyRecycleBinModalOpen: (v: boolean) => void;
  onConfirmEmptyRecycleBin: () => Promise<void>;
}

export function RecycleBinSection({
  showRecycleBin,
  setShowRecycleBin,
  recycleBinLoading,
  deletedExpenses,
  recycleBinTotalCount,
  recycleBinCurrentPage,
  setRecycleBinCurrentPage,
  recycleBinPageSize,
  onRestore,
  onEmptyRecycleBin,
  onSetExpenseToPermanentlyDelete,
  expenseToPermanentlyDelete,
  onPermanentlyDelete,
  emptyRecycleBinModalOpen,
  setEmptyRecycleBinModalOpen,
  onConfirmEmptyRecycleBin,
}: RecycleBinSectionProps) {
  const { t } = useTranslation();

  return (
    <>
      <Collapsible open={showRecycleBin} onOpenChange={setShowRecycleBin}>
        <CollapsibleContent>
          <ProfessionalCard className="slide-in mb-8 border-l-4 border-l-destructive overflow-hidden" variant="elevated">
            <div className="absolute top-0 right-0 w-40 h-40 bg-destructive/5 rounded-full -mr-20 -mt-20 blur-3xl"></div>
            <div className="relative space-y-6">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <div className="p-3 rounded-xl bg-destructive/10 border border-destructive/20">
                    <Trash2 className="h-6 w-6 text-destructive" />
                  </div>
                  <div>
                    <h3 className="font-bold text-xl text-foreground">{t('expenseRecycleBin.title', { defaultValue: 'Recycle Bin' })}</h3>
                    <p className="text-sm text-muted-foreground">
                      {recycleBinTotalCount} {t('expenseRecycleBin.items', 'items')} • Recover or permanently delete expenses
                    </p>
                  </div>
                </div>
                {deletedExpenses.length > 0 && (
                  <ProfessionalButton
                    variant="destructive"
                    size="default"
                    onClick={onEmptyRecycleBin}
                  >
                    <Trash2 className="h-4 w-4" />
                    {t('expenseRecycleBin.empty_recycle_bin', { defaultValue: 'Empty Recycle Bin' })}
                  </ProfessionalButton>
                )}
              </div>
              <div className="rounded-xl border border-border/50 overflow-hidden shadow-sm">
                <Table>
                  <TableHeader>
                    <TableRow className="bg-gradient-to-r from-muted/50 to-muted/30 hover:bg-gradient-to-r hover:from-muted/50 hover:to-muted/30">
                      <TableHead className="font-bold text-foreground">{t('expenseRecycleBin.expense')}</TableHead>
                      <TableHead className="font-bold text-foreground">{t('expenseRecycleBin.amount')}</TableHead>
                      <TableHead className="font-bold text-foreground">{t('expenseRecycleBin.category')}</TableHead>
                      <TableHead className="font-bold text-foreground">{t('expenseRecycleBin.deleted_at')}</TableHead>
                      <TableHead className="font-bold text-foreground">{t('expenseRecycleBin.deleted_by')}</TableHead>
                      <TableHead className="w-[100px] font-bold text-foreground text-right">{t('expenseRecycleBin.actions')}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {recycleBinLoading ? (
                      <TableRow>
                        <TableCell colSpan={6} className="h-24 text-center">
                          <div className="flex justify-center items-center gap-2">
                            <Loader2 className="h-5 w-5 animate-spin text-primary" />
                            <span className="text-muted-foreground">{t('expenseRecycleBin.loading', { defaultValue: 'Loading...' })}</span>
                          </div>
                        </TableCell>
                      </TableRow>
                    ) : deletedExpenses.length > 0 ? (
                      deletedExpenses.map((expense) => (
                        <TableRow key={expense.id} className="hover:bg-muted/60 transition-all duration-200 border-b border-border/30">
                          <TableCell className="font-semibold text-foreground">
                            <span className="inline-flex items-center gap-2">
                              <Receipt className="h-4 w-4 text-primary/60" />
                              #{expense.id}
                            </span>
                          </TableCell>
                          <TableCell className="font-semibold text-foreground">
                            <CurrencyDisplay amount={expense.amount} currency={expense.currency} />
                          </TableCell>
                          <TableCell className="text-foreground">{expense.category}</TableCell>
                          <TableCell className="text-muted-foreground text-sm">{formatDate(expense.deleted_at ?? undefined)}</TableCell>
                          <TableCell className="text-muted-foreground text-sm">{expense.deleted_by_username || t('expenseRecycleBin.unknown')}</TableCell>
                          <TableCell>
                            <div className="flex gap-2 justify-end">
                              <ProfessionalButton
                                variant="ghost"
                                size="icon-sm"
                                onClick={() => onRestore(expense.id)}
                                title="Restore expense"
                                className="hover:bg-success/10 hover:text-success"
                              >
                                <RotateCcw className="h-4 w-4" />
                              </ProfessionalButton>
                              <ProfessionalButton
                                variant="ghost"
                                size="icon-sm"
                                onClick={() => onSetExpenseToPermanentlyDelete(expense.id)}
                                title="Permanently delete"
                                className="hover:bg-destructive/10 hover:text-destructive"
                              >
                                <Trash2 className="h-4 w-4" />
                              </ProfessionalButton>
                            </div>
                          </TableCell>
                        </TableRow>
                      ))
                    ) : (
                      <TableRow>
                        <TableCell colSpan={6} className="h-32 text-center">
                          <div className="flex flex-col items-center justify-center gap-3">
                            <div className="p-4 rounded-full bg-muted/50">
                              <Trash2 className="h-8 w-8 text-muted-foreground/50" />
                            </div>
                            <p className="text-muted-foreground font-medium">{t('expenseRecycleBin.recycle_bin_empty', { defaultValue: 'Recycle bin is empty' })}</p>
                          </div>
                        </TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>
                {Math.ceil(recycleBinTotalCount / recycleBinPageSize) > 1 && (
                  <div className="mt-4">
                    <Pagination>
                      <PaginationContent>
                        <PaginationItem>
                          <PaginationPrevious
                            onClick={() => setRecycleBinCurrentPage(prev => Math.max(1, prev - 1))}
                            className={recycleBinCurrentPage === 1 ? 'pointer-events-none opacity-50' : 'cursor-pointer'}
                          />
                        </PaginationItem>
                        {Array.from({ length: Math.min(5, Math.ceil(recycleBinTotalCount / recycleBinPageSize)) }, (_, i) => {
                          let pageNum = recycleBinCurrentPage;
                          const totalPages = Math.ceil(recycleBinTotalCount / recycleBinPageSize);
                          if (totalPages <= 5) pageNum = i + 1;
                          else if (recycleBinCurrentPage <= 3) pageNum = i + 1;
                          else if (recycleBinCurrentPage >= totalPages - 2) pageNum = totalPages - 4 + i;
                          else pageNum = recycleBinCurrentPage - 2 + i;

                          return (
                            <PaginationItem key={pageNum}>
                              <PaginationLink
                                onClick={() => setRecycleBinCurrentPage(() => pageNum)}
                                isActive={recycleBinCurrentPage === pageNum}
                                className="cursor-pointer"
                              >
                                {pageNum}
                              </PaginationLink>
                            </PaginationItem>
                          );
                        })}
                        <PaginationItem>
                          <PaginationNext
                            onClick={() => setRecycleBinCurrentPage(prev => Math.min(Math.ceil(recycleBinTotalCount / recycleBinPageSize), prev + 1))}
                            className={recycleBinCurrentPage >= Math.ceil(recycleBinTotalCount / recycleBinPageSize) ? 'pointer-events-none opacity-50' : 'cursor-pointer'}
                          />
                        </PaginationItem>
                      </PaginationContent>
                    </Pagination>
                  </div>
                )}
              </div>
            </div>
          </ProfessionalCard>
        </CollapsibleContent>
      </Collapsible>

      {/* Permanent Delete Modal */}
      <AlertDialog open={!!expenseToPermanentlyDelete} onOpenChange={(open) => !open && onSetExpenseToPermanentlyDelete(null as any)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('expenseRecycleBin.permanent_delete_confirm_title', { defaultValue: 'Permanently Delete Expense?' })}</AlertDialogTitle>
            <AlertDialogDescription>
              {t('expenseRecycleBin.permanent_delete_confirm_description', { defaultValue: 'This action cannot be undone. This will permanently delete the expense and remove it from our servers.' })}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t('common.cancel')}</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={() => expenseToPermanentlyDelete && onPermanentlyDelete(expenseToPermanentlyDelete)}
            >
              {t('expenseRecycleBin.permanent_delete', { defaultValue: 'Permanently Delete' })}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Empty Recycle Bin Modal */}
      <AlertDialog open={emptyRecycleBinModalOpen} onOpenChange={setEmptyRecycleBinModalOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('expenseRecycleBin.empty_recycle_bin_confirm_title', { defaultValue: 'Empty Recycle Bin' })}</AlertDialogTitle>
            <AlertDialogDescription>
              {t('expenseRecycleBin.empty_recycle_bin_confirm_description', { defaultValue: 'Are you sure you want to permanently delete all expenses in the recycle bin? This action cannot be undone and all deleted expenses will be completely removed from the system.' })}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t('common.cancel')}</AlertDialogCancel>
            <AlertDialogAction onClick={onConfirmEmptyRecycleBin} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">
              <Trash2 className="mr-2 h-4 w-4" />
              {t('expenseRecycleBin.empty_recycle_bin', { defaultValue: 'Empty Recycle Bin' })}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
