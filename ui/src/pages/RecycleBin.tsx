import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Trash2, RotateCcw, ChevronDown } from "lucide-react";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { invoiceApi } from "@/lib/api";
import { toast } from "sonner";
import { formatDate } from '@/lib/utils';
import { useTranslation } from 'react-i18next';
import { Pagination, PaginationContent, PaginationEllipsis, PaginationItem, PaginationLink, PaginationNext, PaginationPrevious } from "@/components/ui/pagination";

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
  const [isBinCollapsed, setIsBinCollapsed] = useState(true);
  const [userInteracted, setUserInteracted] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize] = useState(10);
  const [totalCount, setTotalCount] = useState(0);

  const totalPages = Math.ceil(totalCount / pageSize);

  useEffect(() => {
    fetchDeletedInvoices();
  }, [currentPage]);

  useEffect(() => {
    // Auto-collapse when bin is empty and not loading, but only if user hasn't interacted
    if (!loading && deletedInvoices.length === 0 && !userInteracted) {
      setIsBinCollapsed(true);
    }
  }, [deletedInvoices, loading, userInteracted]);

  const fetchDeletedInvoices = async () => {
    try {
      setLoading(true);
      const skip = (currentPage - 1) * pageSize;
      const response = await invoiceApi.getDeletedInvoices(skip, pageSize);
      setDeletedInvoices(response.items);
      setTotalCount(response.total);
    } catch (error) {
      console.error('Failed to fetch deleted invoices:', error);
      toast.error(t('recycleBin.failed_to_load_deleted_invoices'));
    } finally {
      setLoading(false);
    }
  };

  const handleRestore = async (invoiceId: number) => {
    try {
      await invoiceApi.restoreInvoice(invoiceId, 'draft');
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
      await invoiceApi.permanentlyDeleteInvoice(invoiceToDelete);
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

  const handleUserInteraction = () => {
    setUserInteracted(true);
  };

  const confirmEmptyRecycleBin = async () => {
    const addNotification = (window as any).addAINotification;
    try {
      const response = await invoiceApi.emptyRecycleBin() as { message: string; deleted_count: number; status?: string };

      // Show immediate notification
      toast.success(response.message || t('recycleBin.deletion_initiated', { count: response.deleted_count }));

      // Add bell notification for completion
      if (addNotification && response.status === 'processing') {
        addNotification(
          'info', 
          t('recycleBin.deletion_title'), 
          t('recycleBin.deletion_processing', { count: response.deleted_count })
        );

        // Show completion notification and refresh after background task completes
        setTimeout(() => {
          addNotification(
            'success', 
            t('recycleBin.deletion_completed_title'), 
            t('recycleBin.deletion_completed', { count: response.deleted_count })
          );
          // Refresh the list after deletion completes
          fetchDeletedInvoices();
        }, 2000);
      } else {
        // If not async, refresh immediately
        fetchDeletedInvoices();
      }
    } catch (error) {
      console.error('Failed to empty recycle bin:', error);
      toast.error(t('recycleBin.failed_to_empty_recycle_bin'));
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

        <Collapsible open={!isBinCollapsed} onOpenChange={(open) => {
      setIsBinCollapsed(!open);
      handleUserInteraction();
    }}>
          <Card className="slide-in">
            <CollapsibleTrigger asChild>
              <CardHeader className="pb-3 cursor-pointer hover:bg-muted/50 transition-colors">
                <div className="flex items-center justify-between">
                  <CardTitle>{t('recycleBin.deleted_invoices')}</CardTitle>
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-muted-foreground">
                      {totalCount} {t('recycleBin.items', 'items')}
                    </span>
                    <ChevronDown className={`h-4 w-4 transition-transform ${isBinCollapsed ? '' : 'rotate-180'}`} />
                  </div>
                </div>
              </CardHeader>
            </CollapsibleTrigger>
            <CollapsibleContent>
              <CardContent>
            <div className="rounded-xl border border-border/50 overflow-hidden shadow-sm">
              <Table>
                <TableHeader>
                  <TableRow className="bg-gradient-to-r from-muted/50 to-muted/30 hover:bg-gradient-to-r hover:from-muted/50 hover:to-muted/30 border-b border-border/50">
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
                      <TableRow key={invoice.id} className="hover:bg-muted/50 transition-all duration-200 border-b border-border/30">
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
            <AlertDialogTitle>{t('recycleBin.permanent_delete_confirm_title')}</AlertDialogTitle>
            <AlertDialogDescription>
              {t('recycleBin.permanent_delete_confirm_description')}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t('common.cancel')}</AlertDialogCancel>
            <AlertDialogAction onClick={confirmPermanentDelete} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">
              {t('recycleBin.permanent_delete')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Empty Recycle Bin Modal */}
      <AlertDialog open={emptyRecycleBinModalOpen} onOpenChange={setEmptyRecycleBinModalOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('recycleBin.empty_recycle_bin_confirm_title')}</AlertDialogTitle>
            <AlertDialogDescription>
              {t('recycleBin.empty_recycle_bin_confirm_description')}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t('common.cancel')}</AlertDialogCancel>
            <AlertDialogAction onClick={confirmEmptyRecycleBin} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">
              <Trash2 className="mr-2 h-4 w-4" />
              {t('recycleBin.empty_recycle_bin')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
};

export default RecycleBin;
