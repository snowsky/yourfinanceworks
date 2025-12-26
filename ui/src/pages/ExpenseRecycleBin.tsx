import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Trash2, RotateCcw } from "lucide-react";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { formatDate } from '@/lib/utils';
import { useTranslation } from 'react-i18next';

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

  useEffect(() => {
    fetchDeletedExpenses();
  }, []);

  const fetchDeletedExpenses = async () => {
    try {
      setLoading(true);
      const data = await api.get<DeletedExpense[]>('/expenses/recycle-bin');
      setDeletedExpenses(data);
    } catch (error) {
      console.error('Failed to fetch deleted expenses:', error);
      toast.error(t('expenseRecycleBin.failed_to_load_deleted_expenses'));
    } finally {
      setLoading(false);
    }
  };

  const handleRestore = async (expenseId: number) => {
    try {
      await api.post(`/expenses/${expenseId}/restore`, { new_status: 'recorded' });
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
      await api.delete(`/expenses/${expenseToDelete}/permanent`);
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

  const confirmEmptyRecycleBin = async () => {
    try {
      await api.post('/expenses/recycle-bin/empty');
      toast.success(t('expenseRecycleBin.recycle_bin_emptied_successfully'));
      fetchDeletedExpenses();
    } catch (error) {
      console.error('Failed to empty recycle bin:', error);
      toast.error(t('expenseRecycleBin.failed_to_empty_recycle_bin'));
    } finally {
      setEmptyRecycleBinModalOpen(false);
    }
  };

  return (
    <>
      <div className="h-full space-y-6 fade-in">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold flex items-center gap-2">
              <Trash2 className="h-8 w-8" />
              {t('expenseRecycleBin.title')}
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

        <Card className="slide-in">
          <CardHeader className="pb-3">
            <CardTitle>{t('expenseRecycleBin.deleted_expenses')}</CardTitle>
          </CardHeader>
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
          </CardContent>
        </Card>
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
