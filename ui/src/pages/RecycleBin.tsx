import { useState, useEffect } from "react";
import { AppLayout } from "@/components/layout/AppLayout";
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

interface DeletedInvoice {
  id: number;
  number: string;
  amount: number;
  currency: string;
  due_date: string;
  status: string;
  client_id: number;
  deleted_at: string;
  deleted_by_username: string;
}

const RecycleBin = () => {
  const { t } = useTranslation();
  const [deletedInvoices, setDeletedInvoices] = useState<DeletedInvoice[]>([]);
  const [loading, setLoading] = useState(true);
  const [permanentDeleteModalOpen, setPermanentDeleteModalOpen] = useState(false);
  const [invoiceToDelete, setInvoiceToDelete] = useState<number | null>(null);
  const [emptyRecycleBinModalOpen, setEmptyRecycleBinModalOpen] = useState(false);

  useEffect(() => {
    fetchDeletedInvoices();
  }, []);

  const fetchDeletedInvoices = async () => {
    try {
      setLoading(true);
      const data = await api.get<DeletedInvoice[]>('/invoices/recycle-bin');
      setDeletedInvoices(data);
    } catch (error) {
      console.error('Failed to fetch deleted invoices:', error);
      toast.error(t('recycleBin.failed_to_load_deleted_invoices'));
    } finally {
      setLoading(false);
    }
  };

  const handleRestore = async (invoiceId: number) => {
    try {
      await api.post(`/invoices/${invoiceId}/restore`, { new_status: 'draft' });
      toast.success(t('recycleBin.invoice_restored_successfully'));
      fetchDeletedInvoices();
    } catch (error) {
      console.error('Failed to restore invoice:', error);
      toast.error(t('recycleBin.failed_to_restore_invoice'));
    }
  };

  const handlePermanentDelete = (invoiceId: number) => {
    console.log('🗑️ RECYCLE BIN handlePermanentDelete called with invoiceId:', invoiceId);
    console.log('🗑️ RECYCLE BIN Setting modal state to true');
    setInvoiceToDelete(invoiceId);
    setPermanentDeleteModalOpen(true);
    console.log('🗑️ RECYCLE BIN Modal state set, invoiceToDelete:', invoiceId, 'modalOpen:', true);
  };

  const confirmPermanentDelete = async () => {
    if (!invoiceToDelete) return;

    try {
      await api.delete(`/invoices/${invoiceToDelete}/permanent`);
      toast.success(t('recycleBin.invoice_permanently_deleted'));
      fetchDeletedInvoices();
    } catch (error) {
      console.error('Failed to permanently delete invoice:', error);
      // Extract specific error message from API response
      let errorMessage = error instanceof Error ? error.message : t('recycleBin.failed_to_permanently_delete_invoice');

      // Check if it's the linked expenses error and use translated version
      if (errorMessage.includes('linked expenses')) {
        errorMessage = t('invoices.delete_error_linked_expenses');
      }

      toast.error(errorMessage);
    } finally {
      setPermanentDeleteModalOpen(false);
      setInvoiceToDelete(null);
    }
  };

  const handleEmptyRecycleBin = () => {
    setEmptyRecycleBinModalOpen(true);
  };

  const confirmEmptyRecycleBin = async () => {
    try {
      await api.post('/invoices/recycle-bin/empty');
      toast.success(t('recycleBin.recycle_bin_emptied_successfully'));
      fetchDeletedInvoices();
    } catch (error) {
      console.error('Failed to empty recycle bin:', error);
      toast.error(t('recycleBin.failed_to_empty_recycle_bin'));
    } finally {
      setEmptyRecycleBinModalOpen(false);
    }
  };

  return (
    <AppLayout>
      <div className="h-full space-y-6 fade-in">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold flex items-center gap-2">
              <Trash2 className="h-8 w-8" />
              {t('recycleBin.title')}
            </h1>
            <p className="text-muted-foreground">{t('recycleBin.description')}</p>
          </div>
          {deletedInvoices.length > 0 && (
            <Button
              variant="destructive"
              onClick={handleEmptyRecycleBin}
              className="sm:self-end whitespace-nowrap"
            >
              <Trash2 className="mr-2 h-4 w-4" />
              {t('recycleBin.empty_recycle_bin')}
            </Button>
          )}
        </div>

        <Card className="slide-in">
          <CardHeader className="pb-3">
            <CardTitle>{t('recycleBin.deleted_invoices')}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t('recycleBin.invoice')}</TableHead>
                    <TableHead>{t('recycleBin.amount')}</TableHead>
                    <TableHead>{t('recycleBin.status')}</TableHead>
                    <TableHead>{t('recycleBin.deleted_at')}</TableHead>
                    <TableHead>{t('recycleBin.deleted_by')}</TableHead>
                    <TableHead className="w-[150px]">{t('recycleBin.actions')}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {loading ? (
                    <TableRow>
                      <TableCell colSpan={6} className="h-24 text-center">
                        {t('recycleBin.loading_deleted_invoices')}
                      </TableCell>
                    </TableRow>
                  ) : deletedInvoices.length > 0 ? (
                    deletedInvoices.map((invoice) => (
                      <TableRow key={invoice.id} className="hover:bg-muted/50">
                        <TableCell className="font-medium">
                          {invoice.number}
                        </TableCell>
                        <TableCell>
                          {invoice.currency} {invoice.amount}
                        </TableCell>
                        <TableCell>
                          <Badge variant="outline">
                            {invoice.status}
                          </Badge>
                        </TableCell>
                        <TableCell>{formatDate(invoice.deleted_at)}</TableCell>
                        <TableCell>{invoice.deleted_by_username || t('recycleBin.unknown')}</TableCell>
                        <TableCell>
                          <div className="flex gap-1">
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => handleRestore(invoice.id)}
                              className="text-green-600 hover:text-green-700 hover:bg-green-50"
                              title={t('recycleBin.restore_invoice')}
                            >
                              <RotateCcw className="h-4 w-4" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => handlePermanentDelete(invoice.id)}
                              className="text-red-600 hover:text-red-700 hover:bg-red-50"
                              title={t('recycleBin.permanently_delete')}
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))
                  ) : (
                    <TableRow>
                      <TableCell colSpan={6} className="h-24 text-center">
                        <div className="flex flex-col items-center gap-2">
                          <Trash2 className="h-8 w-8 text-muted-foreground" />
                          <p>{t('recycleBin.recycle_bin_empty')}</p>
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
            <AlertDialogTitle>{t('invoices.permanent_delete_confirm_title', 'Permanently Delete Invoice')}</AlertDialogTitle>
            <AlertDialogDescription>
              {t('invoices.permanent_delete_confirm_description', 'Are you sure you want to permanently delete this invoice? This action cannot be undone and the invoice will be completely removed from the system.')}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t('common.cancel', 'Cancel')}</AlertDialogCancel>
            <AlertDialogAction onClick={confirmPermanentDelete} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">
              {t('invoices.permanent_delete', 'Permanently Delete')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Empty Recycle Bin Modal */}
      <AlertDialog open={emptyRecycleBinModalOpen} onOpenChange={setEmptyRecycleBinModalOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('recycleBin.empty_recycle_bin_confirm_title', 'Empty Recycle Bin')}</AlertDialogTitle>
            <AlertDialogDescription>
              {t('recycleBin.empty_recycle_bin_confirm_description', 'Are you sure you want to permanently delete all invoices in the recycle bin? This action cannot be undone and all deleted invoices will be completely removed from the system.')}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t('common.cancel', 'Cancel')}</AlertDialogCancel>
            <AlertDialogAction onClick={confirmEmptyRecycleBin} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">
              <Trash2 className="mr-2 h-4 w-4" />
              {t('recycleBin.empty_recycle_bin', 'Empty Recycle Bin')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </AppLayout>
  );
};

export default RecycleBin;