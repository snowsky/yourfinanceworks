import { useState, useEffect, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Plus, Search, Filter, FileText, Loader2, Pencil, Trash2, RotateCcw, ChevronDown, ChevronUp, Upload, Edit, Copy, Grid3X3, List, Eye, Package, X, Tag, MoreHorizontal } from "lucide-react";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog";
import { Checkbox } from "@/components/ui/checkbox";
import { Collapsible, CollapsibleContent } from "@/components/ui/collapsible";
import { Link } from "react-router-dom";
import { invoiceApi, Invoice, api, INVOICE_STATUSES, formatStatus } from "@/lib/api";
import { useNavigate } from 'react-router-dom';
import { toast } from "sonner";
import { Minus } from "lucide-react";
import { CurrencyDisplay } from "@/components/ui/currency-display";
import { formatDate, cn } from '@/lib/utils';
import { canPerformActions } from "@/utils/auth";
import { useTranslation } from 'react-i18next';
import { InvoiceCard } from "@/components/invoices/InvoiceCard";
import { FeatureGate } from "@/components/FeatureGate";
import { ProfessionalCard } from "@/components/ui/professional-card";
import { ProfessionalButton } from "@/components/ui/professional-button";
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { settingsApi } from '@/lib/api';
import { ReviewDiffModal } from "@/components/ReviewDiffModal";
import { Wand } from "lucide-react";
import { Pagination, PaginationContent, PaginationItem, PaginationLink, PaginationNext, PaginationPrevious } from "@/components/ui/pagination";
import { useColumnVisibility, type ColumnDef } from "@/hooks/useColumnVisibility";
import { ColumnPicker } from "@/components/ui/column-picker";

const INVOICE_COLUMNS: ColumnDef[] = [
  { key: 'select', label: 'Select', essential: true },
  { key: 'id', label: 'ID' },
  { key: 'invoice', label: 'Invoice', essential: true },
  { key: 'client', label: 'Client', essential: true },
  { key: 'labels', label: 'Labels' },
  { key: 'due_date', label: 'Due Date' },
  { key: 'total_paid', label: 'Total Paid' },
  { key: 'outstanding_balance', label: 'Outstanding Balance' },
  { key: 'status', label: 'Status', essential: true },
  { key: 'review', label: 'Review' },
  { key: 'created_at_by', label: 'Created at / by' },
  { key: 'actions', label: 'Actions', essential: true },
];

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

const Invoices = () => {
  const { t } = useTranslation();
  const { isVisible, toggle, reset, hiddenCount } = useColumnVisibility('invoices', INVOICE_COLUMNS);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [searchQuery, setSearchQuery] = useState("");
  const [currentTenantId, setCurrentTenantId] = useState<string | null>(null);
  const [showRecycleBin, setShowRecycleBin] = useState(false);
  const [deletedInvoices, setDeletedInvoices] = useState<DeletedInvoice[]>([]);
  const [recycleBinLoading, setRecycleBinLoading] = useState(false);
  const prevDeletedCount = useRef<number>(0);
  const [viewMode, setViewMode] = useState<'cards' | 'table'>('table');
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [invoiceToDelete, setInvoiceToDelete] = useState<number | null>(null);
  const [permanentDeleteModalOpen, setPermanentDeleteModalOpen] = useState(false);
  const [invoiceToPermanentlyDelete, setInvoiceToPermanentlyDelete] = useState<number | null>(null);
  const [emptyRecycleBinModalOpen, setEmptyRecycleBinModalOpen] = useState(false);

  // Recycle bin pagination
  const [recycleBinCurrentPage, setRecycleBinCurrentPage] = useState(1);
  const [recycleBinPageSize] = useState(10);
  const [recycleBinTotalCount, setRecycleBinTotalCount] = useState(0);

  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [bulkDeleteModalOpen, setBulkDeleteModalOpen] = useState(false);

  // Review Mode State
  const [reviewModalOpen, setReviewModalOpen] = useState(false);
  const [selectedReviewInvoice, setSelectedReviewInvoice] = useState<Invoice | null>(null);
  const [isAcceptingReview, setIsAcceptingReview] = useState(false);
  const [isRejectingReview, setIsRejectingReview] = useState(false);
  const [isRetriggeringReview, setIsRetriggeringReview] = useState(false);

  const handleReviewClick = (invoice: Invoice) => {
    setSelectedReviewInvoice(invoice);
    setReviewModalOpen(true);
  };

  const handleAcceptReview = async () => {
    if (!selectedReviewInvoice) return;

    try {
      setIsAcceptingReview(true);
      await invoiceApi.acceptReview(selectedReviewInvoice.id);
      toast.success(t('invoices.review.accepted_success', { defaultValue: 'Review accepted successfully' }));
      setReviewModalOpen(false);
      invalidateInvoices();
    } catch (error) {
      toast.error(t('invoices.review.accept_failed', { defaultValue: 'Failed to accept review' }));
    } finally {
      setIsAcceptingReview(false);
    }
  };

  const handleRejectReview = async () => {
    if (!selectedReviewInvoice) return;

    try {
      setIsRejectingReview(true);
      await invoiceApi.rejectReview(selectedReviewInvoice.id);
      toast.success(t('invoices.review.dismissed_success', { defaultValue: 'Review dismissed' }));
      setReviewModalOpen(false);
      invalidateInvoices();
    } catch (error) {
      toast.error(t('invoices.review.dismiss_failed', { defaultValue: 'Failed to dismiss review' }));
    } finally {
      setIsRejectingReview(false);
    }
  };

  const handleRetriggerReview = async () => {
    if (!selectedReviewInvoice) return;

    try {
      setIsRetriggeringReview(true);
      await invoiceApi.reReview(selectedReviewInvoice.id);
      toast.success(t('invoices.review.retriggered_success', { defaultValue: 'Review re-triggered' }));
      setReviewModalOpen(false);
      invalidateInvoices();
    } catch (error) {
      toast.error(t('invoices.review.retrigger_failed', { defaultValue: 'Failed to re-trigger review' }));
    } finally {
      setIsRetriggeringReview(false);
    }
  };

  // Check if user can perform actions (not a viewer)
  const canPerformAction = canPerformActions();
  const [statusFilter, setStatusFilter] = useState("all");
  const [labelFilter, setLabelFilter] = useState("");
  const [bulkLabel, setBulkLabel] = useState("");
  const [newLabelValueById, setNewLabelValueById] = useState<Record<number, string>>({});

  // Pagination
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);

  // Fetch invoices via TanStack Query — eliminates N+1 manual refetches
  const { data: invoicesData, isLoading: loading } = useQuery({
    queryKey: ['invoices', statusFilter, labelFilter, page, pageSize, currentTenantId],
    queryFn: () => {
      const status = statusFilter !== "all" ? statusFilter : undefined;
      const skip = (page - 1) * pageSize;
      return invoiceApi.getInvoices(status, labelFilter || undefined, skip, pageSize);
    },
  });
  const invoices = invoicesData?.items ?? [];
  const totalInvoices = invoicesData?.total ?? 0;

  // Fetch settings to get timezone
  const { data: settings } = useQuery({
    queryKey: ['settings'],
    queryFn: () => settingsApi.getSettings(),
    staleTime: 5 * 60 * 1000, // 5 minutes
    refetchOnWindowFocus: false,
  });

  // Get timezone from settings, default to UTC
  const timezone = settings?.timezone || 'UTC';

  // Helper function to get locale for date formatting
  const getLocale = () => {
    const language = t('language', { defaultValue: 'en' });
    switch (language) {
      case 'es':
        return 'es-ES';
      case 'fr':
        return 'fr-FR';
      case 'de':
        return 'de-DE';
      default:
        return 'en-US';
    }
  };

  // Get current tenant ID to trigger refetch when organization switches
  const getCurrentTenantId = () => {
    try {
      const selectedTenantId = localStorage.getItem('selected_tenant_id');
      if (selectedTenantId) {
        return selectedTenantId;
      }
      const userStr = localStorage.getItem('user');
      if (userStr) {
        const user = JSON.parse(userStr);
        return user?.tenant_id?.toString();
      }
    } catch (e) {
      console.error('Error getting tenant ID:', e);
    }
    return null;
  };

  // Update tenant ID when it changes
  useEffect(() => {
    const updateTenantId = () => {
      const tenantId = getCurrentTenantId();
      if (tenantId !== currentTenantId) {
        console.log(`🔄 Invoices: Tenant ID changed from ${currentTenantId} to ${tenantId}`);
        setCurrentTenantId(tenantId);
      }
    };

    updateTenantId();

    // Listen for storage changes
    const handleStorageChange = () => {
      updateTenantId();
    };

    window.addEventListener('storage', handleStorageChange);
    return () => window.removeEventListener('storage', handleStorageChange);
  }, [currentTenantId]);

  useEffect(() => {
    if (!recycleBinLoading && deletedInvoices.length === 0 && showRecycleBin && prevDeletedCount.current > 0) {
      setShowRecycleBin(false);
    }
    prevDeletedCount.current = deletedInvoices.length;
  }, [deletedInvoices.length, recycleBinLoading, showRecycleBin]);

  useEffect(() => {
    if (showRecycleBin) {
      fetchDeletedInvoices();
    }
  }, [showRecycleBin, recycleBinCurrentPage]);

  const [isBulkLoading, setIsBulkLoading] = useState(false);
  const invalidateInvoices = () => queryClient.invalidateQueries({ queryKey: ['invoices'] });

  const fetchDeletedInvoices = async () => {
    try {
      setRecycleBinLoading(true);
      const skip = (recycleBinCurrentPage - 1) * recycleBinPageSize;
      const response = await invoiceApi.getDeletedInvoices(skip, recycleBinPageSize);
      setDeletedInvoices(response.items);
      setRecycleBinTotalCount(response.total);
    } catch (error) {
      console.error('Failed to fetch deleted invoices:', error);
      toast.error(t('recycleBin.failed_to_load_deleted_invoices'));
    } finally {
      setRecycleBinLoading(false);
    }
  };

  const handleDeleteInvoice = (invoiceId: number) => {
    setInvoiceToDelete(invoiceId);
    setDeleteModalOpen(true);
  };

  const confirmDeleteInvoice = async () => {
    if (!invoiceToDelete) return;

    try {
      await invoiceApi.deleteInvoice(invoiceToDelete);
      toast.success(t('invoices.delete_success'));
      invalidateInvoices();
      // Refresh recycle bin if open
      if (showRecycleBin) {
        fetchDeletedInvoices();
      }
    } catch (error) {
      // Extract specific error message from API response
      let errorMessage = error instanceof Error ? error.message : t('invoices.delete_error');

      // Check if it's the linked expenses error and use translated version
      if (errorMessage.includes('linked expenses')) {
        errorMessage = t('invoices.delete_error_linked_expenses');
      }

      toast.error(errorMessage);
    } finally {
      setDeleteModalOpen(false);
      setInvoiceToDelete(null);
    }
  };

  const handleBulkDelete = () => {
    setBulkDeleteModalOpen(true);
  };

  const confirmBulkDelete = async () => {
    try {
      await invoiceApi.bulkDelete(selectedIds);
      toast.success(t('invoices.bulk_delete_success', {
        count: selectedIds.length,
        defaultValue: 'Successfully deleted {{count}} invoice'
      }) + (selectedIds.length > 1 ? 's' : ''));
      setSelectedIds([]);
      invalidateInvoices();
      // Refresh recycle bin if open
      if (showRecycleBin) {
        console.log('🔄 Invoices bulk delete: Refreshing recycle bin, showRecycleBin:', showRecycleBin);
        // Reset to first page since total count may have changed
        setRecycleBinCurrentPage(1);
        await fetchDeletedInvoices();
        console.log('✅ Invoices bulk delete: Recycle bin refreshed');
      } else {
        console.log('ℹ️ Invoices bulk delete: Recycle bin not open, skipping refresh');
      }
    } catch (error) {
      let errorMessage = error instanceof Error
        ? error.message
        : t('invoices.bulk_delete_failed', { defaultValue: 'Failed to delete invoices' });

      // Check if it's the linked expenses error and use translated version
      if (errorMessage.includes('linked expenses')) {
        errorMessage = t('invoices.delete_error_linked_expenses');
      }

      toast.error(errorMessage);
    } finally {
      setBulkDeleteModalOpen(false);
    }
  };

  const handleRestoreInvoice = async (invoiceId: number) => {
    try {
      await api.post(`/invoices/${invoiceId}/restore`, { new_status: 'draft' });
      toast.success(t('invoices.restore_success', { defaultValue: 'Invoice restored successfully' }));
      fetchDeletedInvoices();
      invalidateInvoices();
    } catch (error) {
      toast.error(t('invoices.restore_failed', { defaultValue: 'Failed to restore invoice' }));
    }
  };

  const handlePermanentDelete = (invoiceId: number) => {
    console.log('📄 INVOICES PAGE handlePermanentDelete called with invoiceId:', invoiceId);
    setInvoiceToPermanentlyDelete(invoiceId);
    setPermanentDeleteModalOpen(true);
  };

  const confirmPermanentDelete = async () => {
    if (!invoiceToPermanentlyDelete) return;

    try {
      await api.delete(`/invoices/${invoiceToPermanentlyDelete}/permanent`);
      toast.success(t('recycleBin.invoice_permanently_deleted'));
      fetchDeletedInvoices();
    } catch (error) {
      toast.error(t('invoices.permanent_delete_failed', { defaultValue: 'Failed to permanently delete invoice' }));
    } finally {
      setPermanentDeleteModalOpen(false);
      setInvoiceToPermanentlyDelete(null);
    }
  };

  const handleEmptyRecycleBin = () => {
    setEmptyRecycleBinModalOpen(true);
  };

  const confirmEmptyRecycleBin = async () => {
    const addNotification = (window as any).addAINotification;
    try {
      const response = await api.post<{ message: string; deleted_count: number; status?: string }>('/invoices/recycle-bin/empty', {});

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

  const handleCloneInvoice = async (invoiceId: number) => {
    try {
      const newInvoice = await invoiceApi.cloneInvoice(invoiceId);
      toast.success(t('invoices.clone_success', { number: newInvoice.number, defaultValue: 'Cloned as {{number}}' }));
      invalidateInvoices();
      // Redirect to edit
      navigate(`/invoices/edit/${newInvoice.id}`);
    } catch (error) {
      toast.error(t('invoices.clone_failed', { defaultValue: 'Failed to clone invoice' }));
    }
  };

  const handleRunReview = async (invoiceId: number) => {
    try {
      await invoiceApi.reReview(invoiceId);
      toast.success(t('invoices.review.triggered', { defaultValue: 'Review triggered. The agent will process it shortly.' }));
      invalidateInvoices();
    } catch (error: any) {
      toast.error(error?.message || t('invoices.review.trigger_failed', { defaultValue: 'Failed to trigger review' }));
    }
  };

  const handleCancelReview = async (invoiceId: number) => {
    try {
      await invoiceApi.cancelReview(invoiceId);
      toast.success(t('invoices.review.cancelled', { defaultValue: 'Review cancelled.' }));
      invalidateInvoices();
    } catch (error: any) {
      toast.error(error?.message || t('invoices.review.cancel_failed', { defaultValue: 'Failed to cancel review' }));
    }
  };

  const handleBulkRunReview = async () => {
    if (selectedIds.length === 0) return;

    try {
      setIsBulkLoading(true);
      await Promise.all(selectedIds.map(id => invoiceApi.reReview(id)));
      toast.success(t('invoices.review.bulk_triggered', {
        count: selectedIds.length,
        defaultValue: 'Review triggered for {{count}} invoices.'
      }));
      setSelectedIds([]);
      invalidateInvoices();
    } catch (error: any) {
      toast.error(error?.message || t('invoices.review.bulk_trigger_failed', { defaultValue: 'Failed to trigger bulk review' }));
    } finally {
      setIsBulkLoading(false);
    }
  };

  const handleToggleRecycleBin = () => {
    const willShow = !showRecycleBin;
    setShowRecycleBin(willShow);
    if (willShow) {
      setRecycleBinCurrentPage(1); // Reset to first page when opening
      fetchDeletedInvoices();
    }
  };

  const filteredInvoices = (invoices || []).filter(invoice => {
    const matchesSearch =
      invoice.number.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (invoice.client_name && invoice.client_name.toLowerCase().includes(searchQuery.toLowerCase()));

    return matchesSearch;
  });

  return (
    <>
      <div className="h-full space-y-8 fade-in">
        {/* Hero Header */}
        <div className="bg-gradient-to-r from-primary/10 via-primary/5 to-transparent rounded-2xl border border-primary/20 p-8 backdrop-blur-sm">
          <div className="flex items-center justify-between gap-6">
            <div className="space-y-2">
              <h1 className="text-4xl font-bold tracking-tight">{t('invoices.title')}</h1>
              <p className="text-lg text-muted-foreground">{t('invoices.description')}</p>
            </div>
            {canPerformAction && (
              <div className="flex gap-3 items-center flex-wrap justify-end">
                <ProfessionalButton
                  variant="outline"
                  size="default"
                  onClick={invalidateInvoices}
                  className="whitespace-nowrap"
                  disabled={loading}
                >
                  <RotateCcw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
                  {t('common.refresh', { defaultValue: 'Refresh' })}
                </ProfessionalButton>
                <ProfessionalButton
                  variant="outline"
                  size="default"
                  onClick={handleToggleRecycleBin}
                  className="whitespace-nowrap"
                >
                  <Trash2 className="h-4 w-4" />
                  {t('recycleBin.title')}
                  {showRecycleBin ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                </ProfessionalButton>
                <div className="flex gap-1">
                  <Link to="/invoices/new">
                    <ProfessionalButton variant="default" size="default" className="shadow-lg">
                      <Plus className="h-4 w-4 mr-2" />
                      {t('invoices.new_invoice')}
                    </ProfessionalButton>
                  </Link>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <ProfessionalButton variant="default" size="icon" className="shadow-lg">
                        <ChevronDown className="h-4 w-4" />
                      </ProfessionalButton>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" className="w-56">
                      <DropdownMenuItem asChild>
                        <Link to="/invoices/new-manual" className="flex items-center w-full cursor-pointer">
                          <FileText className="mr-2 h-4 w-4" />
                          <div className="flex flex-col">
                            <span>{t('invoices.create_manually')}</span>
                            <span className="text-xs text-muted-foreground">
                              {t('invoices.create_manually_hint', { defaultValue: 'Create manually' })}
                            </span>
                          </div>
                        </Link>
                      </DropdownMenuItem>
                      <FeatureGate feature="ai_invoice">
                        <DropdownMenuItem asChild>
                          <Link to="/invoices/new" className="flex items-center w-full cursor-pointer">
                            <Upload className="mr-2 h-4 w-4" />
                            <div className="flex flex-col">
                              <span>{t('invoices.import_from_pdf')}</span>
                              <span className="text-xs text-muted-foreground">
                                {t('invoices.import_from_pdf_hint', { defaultValue: 'Upload and extract from PDF' })}
                              </span>
                            </div>
                          </Link>
                        </DropdownMenuItem>
                      </FeatureGate>
                      <DropdownMenuItem asChild>
                        <Link to="/invoices/new-inventory" className="flex items-center w-full cursor-pointer">
                          <Package className="mr-2 h-4 w-4" />
                          <div className="flex flex-col">
                            <span>{t('invoices.create_with_inventory')}</span>
                            <span className="text-xs text-muted-foreground">
                              {t('invoices.create_with_inventory_hint', { defaultValue: 'From inventory catalog' })}
                            </span>
                          </div>
                        </Link>
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
              </div>
            )}
          </div>
        </div>

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
                      <h3 className="font-bold text-xl text-foreground">{t('recycleBin.title')}</h3>
                      <p className="text-sm text-muted-foreground">
                        {recycleBinTotalCount} {t('recycleBin.items', 'items')} • Recover or permanently delete invoices
                      </p>
                    </div>
                  </div>
                  {deletedInvoices.length > 0 && canPerformAction && (
                    <ProfessionalButton
                      variant="destructive"
                      size="default"
                      onClick={handleEmptyRecycleBin}
                    >
                      <Trash2 className="h-4 w-4" />
                      {t('recycleBin.empty_recycle_bin')}
                    </ProfessionalButton>
                  )}
                </div>
                <div className="rounded-xl border border-border/50 overflow-hidden shadow-sm">
                  <Table>
                    <TableHeader>
                      <TableRow className="bg-gradient-to-r from-muted/50 to-muted/30 hover:bg-gradient-to-r hover:from-muted/50 hover:to-muted/30">
                        <TableHead className="font-bold text-foreground">{t('recycleBin.invoice')}</TableHead>
                        <TableHead className="font-bold text-foreground">{t('recycleBin.amount')}</TableHead>
                        <TableHead className="font-bold text-foreground">{t('recycleBin.status')}</TableHead>
                        <TableHead className="font-bold text-foreground">{t('recycleBin.deleted_at')}</TableHead>
                        <TableHead className="font-bold text-foreground">{t('recycleBin.deleted_by')}</TableHead>
                        <TableHead className="w-[100px] font-bold text-foreground text-right">{t('recycleBin.actions')}</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {recycleBinLoading ? (
                        <TableRow>
                          <TableCell colSpan={6} className="h-24 text-center">
                            <div className="flex justify-center items-center gap-2">
                              <Loader2 className="h-5 w-5 animate-spin text-primary" />
                              <span className="text-muted-foreground">{t('recycleBin.loading_deleted_invoices')}</span>
                            </div>
                          </TableCell>
                        </TableRow>
                      ) : deletedInvoices.length > 0 ? (
                        deletedInvoices.map((invoice) => (
                          <TableRow key={invoice.id} className="hover:bg-muted/60 transition-all duration-200 border-b border-border/30">
                            <TableCell className="font-semibold text-foreground">
                              <span className="inline-flex items-center gap-2">
                                <FileText className="h-4 w-4 text-primary/60" />
                                {invoice.number}
                              </span>
                            </TableCell>
                            <TableCell className="font-semibold text-foreground">
                              <CurrencyDisplay amount={invoice.amount} currency={invoice.currency} />
                            </TableCell>
                            <TableCell>
                              <Badge variant="outline" className="capitalize font-medium">
                                {invoice.status}
                              </Badge>
                            </TableCell>
                            <TableCell className="text-muted-foreground text-sm">{formatDate(invoice.deleted_at)}</TableCell>
                            <TableCell className="text-muted-foreground text-sm">{invoice.deleted_by_username || t('recycleBin.unknown')}</TableCell>
                            <TableCell>
                              <div className="flex gap-2 justify-end">
                                <ProfessionalButton
                                  variant="ghost"
                                  size="icon-sm"
                                  onClick={() => handleRestoreInvoice(invoice.id)}
                                  title={t('recycleBin.restore_invoice', { defaultValue: 'Restore invoice' })}
                                  aria-label={t('recycleBin.restore_invoice', { defaultValue: 'Restore invoice' })}
                                  className="hover:bg-success/10 hover:text-success"
                                >
                                  <RotateCcw className="h-4 w-4" />
                                </ProfessionalButton>
                                <ProfessionalButton
                                  variant="ghost"
                                  size="icon-sm"
                                  onClick={() => handlePermanentDelete(invoice.id)}
                                  title={t('recycleBin.permanently_delete', { defaultValue: 'Permanently delete' })}
                                  aria-label={t('recycleBin.permanently_delete', { defaultValue: 'Permanently delete' })}
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
                              <p className="text-muted-foreground font-medium">{t('recycleBin.recycle_bin_empty')}</p>
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
                                  onClick={() => setRecycleBinCurrentPage(pageNum)}
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

        <ProfessionalCard className="slide-in" variant="elevated">
          <div className="space-y-6">
            {/* Header with filters */}
            <div className="flex flex-col lg:flex-row justify-between gap-6 pb-6 border-b border-border/50">
              <div>
                <h2 className="text-2xl font-bold text-foreground">{t('invoices.invoice_list')}</h2>
              </div>
              <div className="flex flex-col sm:flex-row gap-3 items-start sm:items-center">
                {/* Search */}
                <div className="relative w-full sm:w-auto">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <Input
                    placeholder={t('invoices.search_placeholder')}
                    className="pl-9 w-full sm:w-[240px] h-10 rounded-lg border-border/50 bg-muted/30 focus:bg-background transition-colors"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                  />
                </div>

                {/* Status Filter */}
                <div className="flex items-center gap-2">
                  <Filter className="h-4 w-4 text-muted-foreground" />
                  <Select value={statusFilter} onValueChange={setStatusFilter}>
                    <SelectTrigger className="w-full sm:w-[170px] h-10 rounded-lg border-border/50 bg-muted/30">
                      <SelectValue placeholder={t('invoices.filter_by_status')} />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">{t('invoices.all_statuses')}</SelectItem>
                      {INVOICE_STATUSES.map((status) => (
                        <SelectItem key={status} value={status}>
                          {t(`invoices.status.${status}`)}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                {/* Label Filter */}
                <div className="relative">
                  <Tag className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <Input
                    placeholder={t('invoices.filter_by_label', { defaultValue: 'Filter by label' })}
                    className="pl-9 w-full sm:w-[150px] h-10 rounded-lg border-border/50 bg-muted/30 focus:bg-background transition-colors"
                    value={labelFilter}
                    onChange={(e) => setLabelFilter(e.target.value)}
                  />
                  {labelFilter && (
                    <button
                      aria-label="Clear label filter"
                      className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                      onClick={() => setLabelFilter('')}
                    >
                      <X className="w-4 h-4" />
                    </button>
                  )}
                </div>

                {/* Page Size */}
                <div className="flex items-center gap-2">
                  <span className="text-sm text-muted-foreground">{t('common.page_size', { defaultValue: 'Page Size' })}</span>
                  <Select value={String(pageSize)} onValueChange={(v) => { setPageSize(Number(v)); setPage(1); }}>
                    <SelectTrigger className="w-[100px] h-10 rounded-lg border-border/50 bg-muted/30">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {[10, 20, 50, 100].map(n => (
                        <SelectItem key={n} value={String(n)}>{n}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                {/* View Mode Toggle */}
                <div className="flex border border-border/50 rounded-lg p-1 bg-muted/30 shadow-sm">
                  <ProfessionalButton
                    variant={viewMode === 'cards' ? 'default' : 'ghost'}
                    size="icon-sm"
                    onClick={() => setViewMode('cards')}
                    className="rounded-md"
                  >
                    <Grid3X3 className="h-4 w-4" />
                  </ProfessionalButton>
                  <ProfessionalButton
                    variant={viewMode === 'table' ? 'default' : 'ghost'}
                    size="icon-sm"
                    onClick={() => setViewMode('table')}
                    className="rounded-md"
                  >
                    <List className="h-4 w-4" />
                  </ProfessionalButton>
                </div>
                {viewMode === 'table' && (
                  <ColumnPicker columns={INVOICE_COLUMNS} isVisible={isVisible} onToggle={toggle} onReset={reset} hiddenCount={hiddenCount} />
                )}
              </div>
            </div>

            {/* Bulk actions bar */}
            {selectedIds.length > 0 && (
              <div className="flex flex-col md:flex-row items-center justify-between p-4 bg-gradient-to-r from-primary/10 to-primary/5 border border-primary/30 rounded-xl shadow-sm gap-4 slide-in">
                <div className="flex items-center gap-3">
                  <div className="h-2 w-2 rounded-full bg-primary animate-pulse shadow-[0_0_8px_rgba(var(--primary),0.5)]"></div>
                  <span className="text-sm font-bold text-foreground">
                    {selectedIds.length} invoice{selectedIds.length !== 1 ? 's' : ''} selected
                  </span>
                  <ProfessionalButton
                    variant="ghost"
                    size="sm"
                    onClick={() => setSelectedIds([])}
                    className="h-8 text-xs hover:bg-primary/10 transition-colors"
                  >
                    Clear
                  </ProfessionalButton>
                </div>

                <div className="flex flex-wrap items-center gap-3 w-full md:w-auto justify-end">
                  <div className="relative group flex-1 md:flex-initial min-w-[200px]">
                    <Tag className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
                    <Input
                      placeholder={t('invoices.bulk_label_placeholder', { defaultValue: 'Add or remove label' })}
                      value={bulkLabel}
                      onChange={(e) => setBulkLabel(e.target.value)}
                      className="pl-8 h-9 text-sm border-primary/20 focus:border-primary/40 bg-background/50"
                    />
                  </div>

                  <div className="flex items-center gap-1.5">
                    <ProfessionalButton
                      variant="outline"
                      size="sm"
                      disabled={!canPerformAction || !bulkLabel.trim()}
                      onClick={async () => {
                        try {
                          await invoiceApi.bulkLabels(selectedIds, 'add', bulkLabel.trim());
                          invalidateInvoices();
                          setSelectedIds([]);
                          setBulkLabel('');
                          toast.success('Labels added');
                        } catch (e: any) {
                          toast.error(e?.message || 'Failed to add label');
                        }
                      }}
                      className="h-9 px-3 gap-1.5"
                    >
                      <Plus className="h-3.5 w-3.5" />
                      Add
                    </ProfessionalButton>

                    <ProfessionalButton
                      variant="outline"
                      size="sm"
                      disabled={!canPerformAction || !bulkLabel.trim()}
                      onClick={async () => {
                        try {
                          await invoiceApi.bulkLabels(selectedIds, 'remove', bulkLabel.trim());
                          invalidateInvoices();
                          setSelectedIds([]);
                          setBulkLabel('');
                          toast.success('Labels removed');
                        } catch (e: any) {
                          toast.error(e?.message || 'Failed to remove label');
                        }
                      }}
                      className="h-9 px-3 gap-1.5"
                    >
                      <Minus className="h-3.5 w-3.5" />
                      Remove
                    </ProfessionalButton>
                  </div>

                  <div className="w-px h-6 bg-primary/10 hidden md:block mx-1"></div>

                  <ProfessionalButton
                    variant="outline"
                    size="sm"
                    onClick={handleBulkRunReview}
                    disabled={!canPerformAction || loading}
                    className="h-9 px-3 gap-1.5 shadow-sm border-primary/20 bg-primary/5 hover:bg-primary/10 text-primary"
                  >
                    <Wand className="w-3.5 h-3.5" />
                    Run Review
                  </ProfessionalButton>

                  <ProfessionalButton
                    variant="destructive"
                    size="sm"
                    onClick={handleBulkDelete}
                    disabled={!canPerformAction}
                    className="h-9 px-3 gap-1.5 shadow-sm"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                    Delete Selected
                  </ProfessionalButton>
                </div>
              </div>
            )}

            {/* Content */}
            {loading ? (
              <div className="flex justify-center items-center h-40">
                <div className="flex flex-col items-center gap-4">
                  <div className="relative w-12 h-12">
                    <Loader2 className="h-12 w-12 animate-spin text-primary/60" />
                  </div>
                  <p className="text-muted-foreground font-medium">{t('invoices.loading')}</p>
                </div>
              </div>
            ) : filteredInvoices.length > 0 ? (
              viewMode === 'cards' ? (
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
                  {filteredInvoices.map((invoice) => {
                    const cardProps = {
                      invoice,
                      onClone: handleCloneInvoice,
                      onDelete: handleDeleteInvoice,
                      canPerformActions: canPerformAction,
                      selected: selectedIds.includes(invoice.id),
                      onSelectionChange: (selected: boolean) => {
                        if (selected) {
                          setSelectedIds(prev => Array.from(new Set([...prev, invoice.id])));
                        } else {
                          setSelectedIds(prev => prev.filter(x => x !== invoice.id));
                        }
                      }
                    };
                    return (
                      <InvoiceCard
                        key={invoice.id}
                        invoice={invoice}
                        onClone={handleCloneInvoice}
                        onDelete={handleDeleteInvoice}
                        canPerformActions={canPerformAction}
                        selected={selectedIds.includes(invoice.id)}
                        onSelectionChange={(selected) => {
                          if (selected) {
                            setSelectedIds(prev => Array.from(new Set([...prev, invoice.id])));
                          } else {
                            setSelectedIds(prev => prev.filter(x => x !== invoice.id));
                          }
                        }}
                      />
                    );
                  })}
                </div>
              ) : (
                <div className="rounded-xl border border-border/50 overflow-hidden shadow-sm">
                  <Table>
                    <TableHeader>
                      <TableRow className="bg-gradient-to-r from-muted/50 to-muted/30 hover:bg-gradient-to-r hover:from-muted/50 hover:to-muted/30 border-b border-border/50">
                        <TableHead className="w-[40px]">
                          <Checkbox
                            checked={selectedIds.length > 0 && selectedIds.length === filteredInvoices.length}
                            onCheckedChange={(v) => {
                              if (v) setSelectedIds(filteredInvoices.map(x => x.id));
                              else setSelectedIds([]);
                            }}
                            aria-label="Select all"
                          />
                        </TableHead>
                        {isVisible('id') && <TableHead className="font-bold text-foreground">{t('common.id', { defaultValue: 'ID' })}</TableHead>}
                        <TableHead className="font-bold text-foreground">{t('invoices.table.invoice')}</TableHead>
                        <TableHead className="font-bold text-foreground">{t('invoices.table.client')}</TableHead>
                        {isVisible('labels') && <TableHead className="font-bold text-foreground">{t('common.labels', { defaultValue: 'Labels' })}</TableHead>}
                        {isVisible('due_date') && <TableHead className="font-bold text-foreground">{t('invoices.table.due_date')}</TableHead>}
                        {isVisible('total_paid') && <TableHead className="text-right font-bold text-foreground">{t('invoices.table.total_paid')}</TableHead>}
                        {isVisible('outstanding_balance') && <TableHead className="text-right font-bold text-foreground">{t('invoices.table.outstanding_balance')}</TableHead>}
                        <TableHead className="font-bold text-foreground">{t('invoices.table.status')}</TableHead>
                        {isVisible('review') && <TableHead className="font-bold text-foreground">{t('invoices.review.title', { defaultValue: 'Review' })}</TableHead>}
                        {isVisible('created_at_by') && <TableHead className="font-bold text-foreground">{t('invoices.table.created_at_by', { defaultValue: 'Created at / by' })}</TableHead>}
                        <TableHead className="w-[100px] text-right font-bold text-foreground">{t('invoices.table.actions')}</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {filteredInvoices.map((invoice) => (
                        <TableRow key={invoice.id} className="hover:bg-muted/50 transition-all duration-200 border-b border-border/30">
                          <TableCell>
                            <Checkbox
                              checked={selectedIds.includes(invoice.id)}
                              onCheckedChange={(v) => {
                                if (v) setSelectedIds(prev => Array.from(new Set([...prev, invoice.id])));
                                else setSelectedIds(prev => prev.filter(x => x !== invoice.id));
                              }}
                              aria-label={`Select invoice ${invoice.id}`}
                            />
                          </TableCell>
                          {isVisible('id') && <TableCell className="font-mono text-xs text-muted-foreground">{invoice.id}</TableCell>}
                          <TableCell className="font-semibold text-foreground">
                            <span className="inline-flex items-center gap-2">
                              <FileText className="h-4 w-4 text-primary/60" />
                              <span>{invoice.number}</span>
                            </span>
                          </TableCell>
                          <TableCell className="text-foreground font-medium">{invoice.client_name}</TableCell>
                          {isVisible('labels') && <TableCell>
                            <div className="flex flex-wrap gap-1 items-center min-w-[200px]">
                              {invoice.labels && invoice.labels.map((label: string, idx: number) => (
                                <Badge
                                  key={idx}
                                  variant="secondary"
                                  className="text-[10px] px-1.5 py-0 h-5 bg-primary/10 text-primary border-primary/20 flex items-center gap-1 group/badge"
                                >
                                  {label}
                                  <button
                                    aria-label={t('invoices.remove_label', { defaultValue: 'Remove label' })}
                                    className="hover:text-destructive transition-colors"
                                    onClick={() => {
                                      const next = invoice.labels?.filter((_, i) => i !== idx) || [];
                                      invoiceApi.updateInvoice(invoice.id, { labels: next }).then(() => {
                                        invalidateInvoices();
                                      }).catch((err: any) => {
                                        toast.error(err?.message || t('invoices.labels.remove_failed', { defaultValue: 'Failed to remove label' }));
                                      });
                                    }}
                                  >
                                    <X className="h-2.5 w-2.5" />
                                  </button>
                                </Badge>
                              ))}
                              <Input
                                placeholder={t('expenses.labels.label_placeholder', { defaultValue: 'Add label...' })}
                                className="w-[100px] h-7 text-[10px] px-2 bg-muted/20 border-border/40 focus:bg-background transition-all"
                                value={newLabelValueById[invoice.id] || ''}
                                onChange={(ev) => setNewLabelValueById((prev) => ({ ...prev, [invoice.id]: ev.target.value }))}
                                onKeyDown={(ev) => {
                                  if (ev.key === 'Enter' && newLabelValueById[invoice.id]?.trim()) {
                                    const raw = newLabelValueById[invoice.id].trim();
                                    const existing = invoice.labels || [];
                                    if (existing.includes(raw)) { 
                                      setNewLabelValueById((prev) => ({ ...prev, [invoice.id]: '' })); 
                                      return; 
                                    }
                                    const next = [...existing, raw].slice(0, 10);
                                    invoiceApi.updateInvoice(invoice.id, { labels: next }).then(() => {
                                      invalidateInvoices();
                                      setNewLabelValueById((prev) => ({ ...prev, [invoice.id]: '' }));
                                    }).catch((err: any) => {
                                      toast.error(err?.message || t('invoices.labels.add_failed', { defaultValue: 'Failed to add label' }));
                                    });
                                  }
                                }}
                              />
                            </div>
                          </TableCell>}
                          {isVisible('due_date') && <TableCell className="text-muted-foreground text-sm">
                            {invoice.due_date ? new Date(invoice.due_date).toLocaleDateString(getLocale(), {
                              timeZone: timezone,
                              year: 'numeric',
                              month: 'short',
                              day: 'numeric'
                            }) : 'N/A'}
                          </TableCell>}
                          {isVisible('total_paid') && <TableCell className="text-right font-semibold text-foreground">
                            <CurrencyDisplay amount={invoice.paid_amount || 0} currency={invoice.currency} />
                          </TableCell>}
                          {isVisible('outstanding_balance') && <TableCell className="text-right">
                            <span className={(invoice.amount - (invoice.paid_amount || 0)) > 0 ? 'text-warning font-semibold' : 'text-success font-semibold'}>
                              <CurrencyDisplay amount={invoice.amount - (invoice.paid_amount || 0)} currency={invoice.currency} />
                            </span>
                          </TableCell>}
                          <TableCell>
                            <Badge
                              className={
                                invoice.status === 'paid' ? 'status-paid' :
                                  invoice.status === 'pending' ? 'status-pending' :
                                    invoice.status === 'overdue' ? 'status-overdue' :
                                      invoice.status === 'partially_paid' ? 'status-partially-paid' :
                                        'bg-muted/50 text-muted-foreground'
                              }
                            >
                              {formatStatus(invoice.status)}
                            </Badge>
                          </TableCell>
                          {isVisible('review') && <TableCell>
                            {invoice.review_status === 'diff_found' ? (
                              <Button 
                                size="sm" 
                                variant="outline" 
                                className="h-7 text-xs border-amber-500/50 text-amber-600 hover:bg-amber-50"
                                onClick={() => handleReviewClick(invoice)}
                              >
                                <Wand className="h-3 w-3 mr-1" />
                                Review Diff
                              </Button>
                            ) : (invoice.review_status === 'reviewed' || invoice.review_status === 'no_diff') ? (
                              <div className="flex flex-col gap-1 items-start">
                                <Badge variant="outline" className={cn(
                                  "font-medium shadow-none",
                                  invoice.review_status === 'reviewed' ? "bg-green-50 text-green-700 border-green-200" : "bg-blue-50 text-blue-700 border-blue-200"
                                )}>
                                  {invoice.review_status === 'reviewed'
                                    ? t('invoices.review.reviewed', { defaultValue: 'Reviewed' })
                                    : t('invoices.review.verified', { defaultValue: 'Verified' })}
                                </Badge>
                                <Button
                                  size="sm"
                                  variant="ghost"
                                  className="h-6 text-[10px] px-2 text-muted-foreground hover:text-foreground"
                                  onClick={() => handleReviewClick(invoice)}
                                >
                                  <Eye className="w-3 h-3 mr-1" />
                                  {t('invoices.review.view_report', { defaultValue: 'View Report' })}
                                </Button>
                              </div>
                            ) : (
                                <div className="flex flex-col gap-1 items-start">
                                <Badge variant="outline" className={cn(
                                  "font-medium shadow-none",
                                  invoice.review_status === 'pending'
                                    ? "bg-blue-50 text-blue-700 border-blue-200"
                                    : invoice.review_status === 'rejected'
                                    ? "bg-amber-50 text-amber-700 border-amber-200"
                                    : invoice.review_status === 'failed'
                                    ? "bg-red-50 text-red-700 border-red-200"
                                    : "bg-muted/50 text-muted-foreground border-transparent"
                                )}>
                                  {invoice.review_status === 'pending' ? t('invoices.review.pending', { defaultValue: 'Review Pending' }) :
                                   invoice.review_status === 'rejected' ? t('invoices.review.dismissed', { defaultValue: 'Review Dismissed' }) :
                                   invoice.review_status === 'failed' ? t('invoices.review.failed', { defaultValue: 'Review Failed' }) :
                                   t('common.not_started', { defaultValue: 'Not Started' })}
                                </Badge>
                                {(!invoice.review_status || invoice.review_status === 'not_started' || invoice.review_status === 'failed' || invoice.review_status === 'rejected') && (
                                  <Button 
                                    size="sm" 
                                    variant="ghost" 
                                    className="h-6 text-[10px] text-primary hover:bg-primary/5 p-0 px-1"
                                    onClick={() => handleRunReview(invoice.id)}
                                  >
                                    <RotateCcw className="h-2.5 w-2.5 mr-1" />
                                    {t('invoices.review.trigger', { defaultValue: 'Trigger Review' })}
                                  </Button>
                                )}
                                {(invoice.review_status === 'pending' || invoice.review_status === 'rejected' || invoice.review_status === 'failed') && (
                                  <Button
                                    size="sm"
                                    variant="ghost"
                                    className="h-6 text-[10px] text-destructive hover:bg-destructive/5 p-0 px-1"
                                    onClick={() => handleCancelReview(invoice.id)}
                                  >
                                    <X className="h-2.5 w-2.5 mr-1" />
                                    {invoice.review_status === 'pending'
                                      ? t('invoices.review.cancel', { defaultValue: 'Cancel Review' })
                                      : t('invoices.review.clear_status', { defaultValue: 'Clear Status' })}
                                  </Button>
                                )}
                                </div>
                            )}
                          </TableCell>}
                          {isVisible('created_at_by') && <TableCell>
                            <div className="text-sm">
                              <div className="text-muted-foreground">
                                {invoice.created_at ? new Date(invoice.created_at).toLocaleString(getLocale(), { 
                                  timeZone: timezone,
                                  year: 'numeric',
                                  month: 'short',
                                  day: 'numeric',
                                  hour: '2-digit',
                                  minute: '2-digit'
                                }) : 'N/A'}
                              </div>
                              <div className="text-xs text-muted-foreground">
                                {invoice.created_by_username || invoice.created_by_email || t('common.unknown')}
                              </div>
                            </div>
                          </TableCell>}
                          <TableCell className="text-right">
                            {canPerformAction && (
                              <DropdownMenu>
                                <DropdownMenuTrigger asChild>
                                  <Button variant="ghost" size="icon">
                                    <MoreHorizontal className="h-4 w-4" />
                                  </Button>
                                </DropdownMenuTrigger>
                                <DropdownMenuContent align="end">
                                  <DropdownMenuItem asChild>
                                    <Link to={`/invoices/view/${invoice.id}`} className="flex items-center">
                                      <Eye className="mr-2 h-4 w-4" /> {t('common.view', 'View')}
                                    </Link>
                                  </DropdownMenuItem>
                                  <DropdownMenuItem asChild>
                                    <Link to={`/invoices/edit/${invoice.id}`} className="flex items-center">
                                      <Pencil className="mr-2 h-4 w-4" /> {t('common.edit', 'Edit')}
                                    </Link>
                                  </DropdownMenuItem>
                                  <DropdownMenuItem onClick={() => handleCloneInvoice(invoice.id)}>
                                    <Copy className="mr-2 h-4 w-4" /> {t('invoices.clone', 'Clone')}
                                  </DropdownMenuItem>
                                  <DropdownMenuSeparator />
                                  <DropdownMenuItem className="text-destructive focus:text-destructive" onClick={() => handleDeleteInvoice(invoice.id)}>
                                    <Trash2 className="mr-2 h-4 w-4" /> {t('common.delete', 'Delete')}
                                  </DropdownMenuItem>
                                </DropdownMenuContent>
                              </DropdownMenu>
                            )}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )
            ) : (
              <div className="text-center py-20 bg-gradient-to-br from-muted/30 to-muted/10 rounded-2xl border-2 border-dashed border-muted-foreground/20">
                <div className="bg-gradient-to-br from-primary/20 to-primary/10 w-20 h-20 rounded-full flex items-center justify-center mx-auto mb-6">
                  <FileText className="h-10 w-10 text-primary/60" />
                </div>
                <h3 className="text-2xl font-bold text-foreground mb-2">{t('invoices.no_invoices', 'No invoices yet')}</h3>
                <p className="text-muted-foreground max-w-sm mx-auto mb-8">
                  {t('invoices.no_invoices_description', 'Get started by creating your first professional invoice. You can also import one from a PDF.')}
                </p>
                {canPerformAction && (
                  <Link to="/invoices/new">
                    <ProfessionalButton variant="default" size="lg" className="shadow-lg">
                      <Plus className="h-4 w-4" />
                      {t('invoices.create_your_first_invoice', { defaultValue: 'Create Your First Invoice' })}
                    </ProfessionalButton>
                  </Link>
                )}
              </div>
            )}
            {/* Pagination */}
            <div className="flex flex-col sm:flex-row items-center justify-between gap-4 mt-6 pt-6 border-t border-border/50">
              <div className="text-sm text-muted-foreground">
                {t('common.showing_results', {
                  shown: invoices.length,
                  total: totalInvoices,
                  defaultValue: 'Showing {{shown}} of {{total}} results'
                })}
              </div>
              <div className="flex items-center gap-2">
                <ProfessionalButton
                  variant="outline"
                  size="sm"
                  onClick={() => setPage(prev => Math.max(1, prev - 1))}
                  disabled={page === 1}
                  className="h-9 px-4"
                >
                  {t('common.previous')}
                </ProfessionalButton>
                <div className="flex items-center gap-1">
                  {Array.from({ length: Math.ceil(totalInvoices / pageSize) }, (_, i) => i + 1)
                    .filter(p => p === 1 || p === Math.ceil(totalInvoices / pageSize) || Math.abs(p - page) <= 1)
                    .map((p, i, arr) => (
                      <div key={p} className="flex items-center">
                        {i > 0 && arr[i - 1] !== p - 1 && <span className="text-muted-foreground px-1">...</span>}
                        <ProfessionalButton
                          variant={page === p ? "default" : "outline"}
                          size="sm"
                          onClick={() => setPage(p)}
                          className={`h-9 w-9 p-0 ${page === p ? 'shadow-md shadow-primary/20' : ''}`}
                        >
                          {p}
                        </ProfessionalButton>
                      </div>
                    ))}
                </div>
                <ProfessionalButton
                  variant="outline"
                  size="sm"
                  onClick={() => setPage(prev => Math.min(Math.ceil(totalInvoices / pageSize), prev + 1))}
                  disabled={page >= Math.ceil(totalInvoices / pageSize)}
                  className="h-9 px-4"
                >
                  {t('common.next')}
                </ProfessionalButton>
              </div>
            </div>
          </div>
        </ProfessionalCard >
      </div >

      {/* Review Diff Modal */}
      {selectedReviewInvoice && (
        <ReviewDiffModal
          isOpen={reviewModalOpen}
          onClose={() => setReviewModalOpen(false)}
          originalData={{
            amount: selectedReviewInvoice.amount,
            date: selectedReviewInvoice.date,
            vendor: selectedReviewInvoice.client_name, // Using client name as vendor proxy
            category: '', // Invoice doesn't have simple category field
            notes: selectedReviewInvoice.notes,
            tax_amount: 0 // Not in basic invoice list
          }}
          reviewResult={selectedReviewInvoice.review_result || {}}
          onAccept={handleAcceptReview}
          onReject={handleRejectReview}
          onRetrigger={handleRetriggerReview}
          isAccepting={isAcceptingReview}
          isRejecting={isRejectingReview}
          isRetriggering={isRetriggeringReview}
          type="invoice"
          readOnly={selectedReviewInvoice?.review_status === 'reviewed' || selectedReviewInvoice?.review_status === 'no_diff'}
        />
      )}

      {/* Permanent Delete Modal */}
      < AlertDialog open={permanentDeleteModalOpen} onOpenChange={setPermanentDeleteModalOpen} >
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
              <Trash2 className="mr-2 h-4 w-4" />
              {t('invoices.permanent_delete', 'Permanently Delete')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog >

      {/* Delete Invoice Modal */}
      < AlertDialog open={deleteModalOpen} onOpenChange={setDeleteModalOpen} >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('invoices.delete_confirm_title', 'Delete Invoice')}</AlertDialogTitle>
            <AlertDialogDescription>
              {t('invoices.delete_confirm_description', 'This will move the invoice to the recycle bin where it can be restored or permanently deleted later.')}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t('common.cancel', 'Cancel')}</AlertDialogCancel>
            <AlertDialogAction onClick={confirmDeleteInvoice} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">
              {t('invoices.delete', 'Delete')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog >

      {/* Bulk Delete Modal */}
      < AlertDialog open={bulkDeleteModalOpen} onOpenChange={setBulkDeleteModalOpen} >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {selectedIds.length === 1
                ? t('invoices.delete_single_title', 'Move 1 Invoice to Recycle Bin')
                : t('invoices.delete_multiple_title', 'Move {{count}} Invoices to Recycle Bin', { count: selectedIds.length })
              }
            </AlertDialogTitle>
            <AlertDialogDescription>
              {selectedIds.length === 1
                ? t('invoices.delete_single_description', 'Are you sure you want to move this invoice to the recycle bin? You can restore it later if needed.')
                : t('invoices.delete_multiple_description', 'Are you sure you want to move {{count}} invoices to the recycle bin? You can restore them later if needed.', { count: selectedIds.length })
              }
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t('common.cancel', 'Cancel')}</AlertDialogCancel>
            <AlertDialogAction
              onClick={confirmBulkDelete}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              <Trash2 className="mr-2 h-4 w-4" />
              {selectedIds.length === 1
                ? t('invoices.move_to_recycle_bin', 'Move to Recycle Bin')
                : t('invoices.move_multiple_to_recycle_bin', 'Move All to Recycle Bin')
              }
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog >

      {/* Empty Recycle Bin Modal */}
      < AlertDialog open={emptyRecycleBinModalOpen} onOpenChange={setEmptyRecycleBinModalOpen} >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('recycleBin.empty_recycle_bin_confirm_title')}</AlertDialogTitle>
            <AlertDialogDescription>
              {t('recycleBin.empty_recycle_bin_confirm_description')}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t('common.cancel', 'Cancel')}</AlertDialogCancel>
            <AlertDialogAction onClick={confirmEmptyRecycleBin} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">
              <Trash2 className="mr-2 h-4 w-4" />
              {t('recycleBin.empty_recycle_bin')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog >
    </>
  );
};

export default Invoices;
