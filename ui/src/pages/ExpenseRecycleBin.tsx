import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Trash2, RotateCcw, ChevronDown } from "lucide-react";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { expenseApi } from "@/lib/api";
import { toast } from "sonner";
import { formatDate } from '@/lib/utils';
import { useTranslation } from 'react-i18next';
import { Pagination, PaginationContent, PaginationEllipsis, PaginationItem, PaginationLink, PaginationNext, PaginationPrevious } from "@/components/ui/pagination";

interface DeletedExpense {
  id: number;
  amount: number;
  currency: string;
  expense_date: string;
  category: string;
  vendor: string;
  status: string;
  deleted_at: string;
  deleted_by_username: string;
  created_by_username: string;
}

const ExpenseRecycleBin = () => {
  const { t } = useTranslation();
  const [deletedExpenses, setDeletedExpenses] = useState<DeletedExpense[]>([]);
  const [loading, setLoading] = useState(true);
  const [permanentDeleteModalOpen, setPermanentDeleteModalOpen] = useState(false);
  const [expenseToDelete, setExpenseToDelete] = useState<number | null>(null);
  const [emptyRecycleBinModalOpen, setEmptyRecycleBinModalOpen] = useState(false);
  const [isBinCollapsed, setIsBinCollapsed] = useState(true);
  const [userInteracted, setUserInteracted] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize] = useState(10);
  const [totalCount, setTotalCount] = useState(0);

  const totalPages = Math.ceil(totalCount / pageSize);

  useEffect(() => {
    fetchDeletedExpenses();
  }, [currentPage]);

  useEffect(() => {
    // Auto-collapse when bin is empty and not loading, but only if user hasn't interacted
    if (!loading && deletedExpenses.length === 0 && !userInteracted) {
      setIsBinCollapsed(true);
    }
  }, [deletedExpenses, loading, userInteracted]);

  const fetchDeletedExpenses = async () => {
    try {
      setLoading(true);
      const skip = (currentPage - 1) * pageSize;
      const response = await expenseApi.getDeletedExpenses(skip, pageSize);
      setDeletedExpenses(response.items);
      setTotalCount(response.total);
    } catch (error) {
      console.error('Failed to fetch deleted expenses:', error);
      toast.error(t('expenseRecycleBin.failed_to_load_deleted_expenses'));
    } finally {
      setLoading(false);
    }
  };

  const handleRestore = async (expenseId: number) => {
    try {
      await expenseApi.restoreExpense(expenseId, 'recorded');
      toast.success(t('expenseRecycleBin.expense_restored_successfully'));
      fetchDeletedExpenses();
    } catch (error) {
      console.error('Failed to restore expense:', error);
      toast.error(t('expenseRecycleBin.failed_to_restore_expense'));
    }
  };

  const handlePermanentDelete = (expenseId: number) => {
    setExpenseToDelete(expenseId);
    setPermanentDeleteModalOpen(true);
  };

  const confirmPermanentDelete = async () => {
    if (!expenseToDelete) return;

    try {
      await expenseApi.permanentlyDeleteExpense(expenseToDelete);
      toast.success(t('expenseRecycleBin.expense_permanently_deleted'));
      fetchDeletedExpenses();
    } catch (error) {
      console.error('Failed to permanently delete expense:', error);
      let errorMessage = error instanceof Error ? error.message : t('expenseRecycleBin.failed_to_permanently_delete_expense');
      toast.error(errorMessage);
    } finally {
      setPermanentDeleteModalOpen(false);
      setExpenseToDelete(null);
    }
  };

  const handleEmptyRecycleBin = () => {
    setEmptyRecycleBinModalOpen(true);
  };

  const handleUserInteraction = () => {
    setUserInteracted(true);
  };

  const confirmEmptyRecycleBin = async () => {
    const addNotification = (window as any).addAINotification;
    try {
      const response = await expenseApi.emptyRecycleBin() as { message: string; deleted_count: number; status?: string };

      // Show immediate notification
      toast.success(response.message || t('expenseRecycleBin.deletion_initiated', { count: response.deleted_count }));

      // Add bell notification for completion
      if (addNotification && response.status === 'processing') {
        addNotification(
          'info', 
          t('expenseRecycleBin.deletion_title'), 
          t('expenseRecycleBin.deletion_processing', { count: response.deleted_count })
        );

        // Show completion notification and refresh after background task completes
        setTimeout(() => {
          addNotification(
            'success', 
            t('expenseRecycleBin.deletion_completed_title'), 
            t('expenseRecycleBin.deletion_completed', { count: response.deleted_count })
          );
          // Refresh the list after deletion completes
          fetchDeletedExpenses();
        }, 2000);
      } else {
        // If not async, refresh immediately
        fetchDeletedExpenses();
      }
    } catch (error) {
      console.error('Failed to empty recycle bin:', error);
      toast.error(t('expenseRecycleBin.failed_to_empty_recycle_bin'));
    } finally {
      setEmptyRecycleBinModalOpen(false);
    }
  };

  const handlePageChange = (newPage: number) => {
    if (newPage >= 1 && newPage <= totalPages) {
      setCurrentPage(newPage);
    }
  };

  return (
    <>
      <div className="h-full space-y-6 fade-in">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold flex items-center gap-2">
              <Trash2 className="h-8 w-8" />
              {t('recycleBin.title')}
            </h1>
            <p className="text-muted-foreground">{t('expenseRecycleBin.description')}</p>
          </div>
          {deletedExpenses.length > 0 && (
            <Button
              variant="destructive"
              onClick={handleEmptyRecycleBin}
              className="sm:self-end whitespace-nowrap"
            >
              <Trash2 className="mr-2 h-4 w-4" />
              {t('expenseRecycleBin.empty_recycle_bin')}
            </Button>
          )}
        </div>

        <Collapsible open={!isBinCollapsed} onOpenChange={(open) => {
      setIsBinCollapsed(!open);
      handleUserInteraction();
    }}>
          <Card className="slide-in">
            <CollapsibleTrigger asChild>
              <CardHeader className="pb-3 cursor-pointer hover:bg-muted/50 transition-colors">
                <div className="flex items-center justify-between">
                  <CardTitle>{t('expenseRecycleBin.deleted_expenses')}</CardTitle>
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-muted-foreground">
                      {totalCount} {t('expenseRecycleBin.items', 'items')}
                    </span>
                    <ChevronDown className={`h-4 w-4 transition-transform ${isBinCollapsed ? '' : 'rotate-180'}`} />
                  </div>
                </div>
              </CardHeader>
            </CollapsibleTrigger>
            <CollapsibleContent>
              <CardContent>
            <div className="rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t('expenseRecycleBin.expense')}</TableHead>
                    <TableHead>{t('expenseRecycleBin.amount')}</TableHead>
                    <TableHead>{t('expenseRecycleBin.category')}</TableHead>
                    <TableHead>{t('expenseRecycleBin.status')}</TableHead>
                    <TableHead>{t('expenseRecycleBin.deleted_at')}</TableHead>
                    <TableHead>{t('expenseRecycleBin.deleted_by')}</TableHead>
                    <TableHead className="w-[150px]">{t('expenseRecycleBin.actions')}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {loading ? (
                    <TableRow>
                      <TableCell colSpan={7} className="h-24 text-center">
                        {t('expenseRecycleBin.loading_deleted_expenses')}
                      </TableCell>
                    </TableRow>
                  ) : deletedExpenses.length > 0 ? (
                    deletedExpenses.map((expense) => (
                      <TableRow key={expense.id} className="hover:bg-muted/50">
                        <TableCell className="font-medium">
                          <div>
                            <div className="font-medium">{expense.vendor || t('expenseRecycleBin.unknown_vendor')}</div>
                            <div className="text-sm text-muted-foreground">
                              {formatDate(expense.expense_date)}
                            </div>
                          </div>
                        </TableCell>
                        <TableCell>
                          {expense.currency} {expense.amount}
                        </TableCell>
                        <TableCell>
                          <Badge variant="outline">
                            {expense.category}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <Badge variant="outline">
                            {expense.status}
                          </Badge>
                        </TableCell>
                        <TableCell>{formatDate(expense.deleted_at)}</TableCell>
                        <TableCell>{expense.deleted_by_username || t('expenseRecycleBin.unknown')}</TableCell>
                        <TableCell>
                          <div className="flex gap-1">
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => handleRestore(expense.id)}
                              className="text-green-600 hover:text-green-700 hover:bg-green-50"
                              title={t('expenseRecycleBin.restore_expense')}
                            >
                              <RotateCcw className="h-4 w-4" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => handlePermanentDelete(expense.id)}
                              className="text-red-600 hover:text-red-700 hover:bg-red-50"
                              title={t('expenseRecycleBin.permanently_delete')}
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))
                  ) : (
                    <TableRow>
                      <TableCell colSpan={7} className="h-24 text-center">
                        <div className="flex flex-col items-center gap-2">
                          <Trash2 className="h-8 w-8 text-muted-foreground" />
                          <p>{t('expenseRecycleBin.recycle_bin_empty')}</p>
                        </div>
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </div>
            {totalPages > 1 && (
              <div className="mt-4">
                <Pagination>
                  <PaginationContent>
                    <PaginationItem>
                      <PaginationPrevious
                        onClick={() => handlePageChange(currentPage - 1)}
                        className={currentPage === 1 ? 'pointer-events-none opacity-50' : 'cursor-pointer'}
                      />
                    </PaginationItem>
                    {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                      let pageNum = currentPage;
                      if (totalPages <= 5) pageNum = i + 1;
                      else if (currentPage <= 3) pageNum = i + 1;
                      else if (currentPage >= totalPages - 2) pageNum = totalPages - 4 + i;
                      else pageNum = currentPage - 2 + i;

                      return (
                        <PaginationItem key={pageNum}>
                          <PaginationLink
                            onClick={() => handlePageChange(pageNum)}
                            isActive={currentPage === pageNum}
                            className="cursor-pointer"
                          >
                            {pageNum}
                          </PaginationLink>
                        </PaginationItem>
                      );
                    })}
                    <PaginationItem>
                      <PaginationNext
                        onClick={() => handlePageChange(currentPage + 1)}
                        className={currentPage === totalPages ? 'pointer-events-none opacity-50' : 'cursor-pointer'}
                      />
                    </PaginationItem>
                  </PaginationContent>
                </Pagination>
              </div>
            )}
              </CardContent>
            </CollapsibleContent>
          </Card>
        </Collapsible>
      </div>

      {/* Permanent Delete Modal */}
      <AlertDialog open={permanentDeleteModalOpen} onOpenChange={setPermanentDeleteModalOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('expenseRecycleBin.permanent_delete_confirm_title')}</AlertDialogTitle>
            <AlertDialogDescription>
              {t('expenseRecycleBin.permanent_delete_confirm_description')}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t('common.cancel')}</AlertDialogCancel>
            <AlertDialogAction onClick={confirmPermanentDelete} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">
              {t('expenseRecycleBin.permanent_delete')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Empty Recycle Bin Modal */}
      <AlertDialog open={emptyRecycleBinModalOpen} onOpenChange={setEmptyRecycleBinModalOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('expenseRecycleBin.empty_recycle_bin_confirm_title')}</AlertDialogTitle>
            <AlertDialogDescription>
              {t('expenseRecycleBin.empty_recycle_bin_confirm_description')}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t('common.cancel')}</AlertDialogCancel>
            <AlertDialogAction onClick={confirmEmptyRecycleBin} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">
              <Trash2 className="mr-2 h-4 w-4" />
              {t('expenseRecycleBin.empty_recycle_bin')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
};

export default ExpenseRecycleBin;
