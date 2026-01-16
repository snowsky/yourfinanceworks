import { useState, useEffect, useRef, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Plus, Search, Filter, FileText, Loader2, Pencil, Trash2, RotateCcw, ChevronDown, ChevronUp, Upload, Edit, Copy, Grid3X3, List, Eye, Package, X, Tag } from "lucide-react";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog";
import { Checkbox } from "@/components/ui/checkbox";
import { Collapsible, CollapsibleContent } from "@/components/ui/collapsible";
import { Link } from "react-router-dom";
import { invoiceApi, Invoice, api, INVOICE_STATUSES, formatStatus } from "@/lib/api";
import { useNavigate } from 'react-router-dom';
import { toast } from "sonner";
import { Minus } from "lucide-react";
import { CurrencyDisplay } from "@/components/ui/currency-display";
import { formatDate } from '@/lib/utils';
import { canPerformActions } from "@/utils/auth";
import { useTranslation } from 'react-i18next';
import { InvoiceCard } from "@/components/invoices/InvoiceCard";
import { FeatureGate } from "@/components/FeatureGate";
import { PageHeader } from "@/components/ui/professional-layout";
import { ProfessionalCard } from "@/components/ui/professional-card";
import { ProfessionalButton } from "@/components/ui/professional-button";
import { useQuery } from '@tanstack/react-query';
import { settingsApi } from '@/lib/api';

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
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
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
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [bulkDeleteModalOpen, setBulkDeleteModalOpen] = useState(false);

  // Check if user can perform actions (not a viewer)
  const canPerformAction = canPerformActions();
  const [statusFilter, setStatusFilter] = useState("all");
  const [labelFilter, setLabelFilter] = useState("");
  const [bulkLabel, setBulkLabel] = useState("");
  const [newLabelValueById, setNewLabelValueById] = useState<Record<number, string>>({});

  // Pagination
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [totalInvoices, setTotalInvoices] = useState(0);

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

  const fetchInvoices = useCallback(async () => {
    setLoading(true);
    try {
      const status = statusFilter !== "all" ? statusFilter : undefined;
      const skip = (page - 1) * pageSize;
      const data = await invoiceApi.getInvoices(status, labelFilter || undefined, skip, pageSize);
      setInvoices(data.items);
      setTotalInvoices(data.total);
    } catch (error) {
      console.error("Failed to fetch invoices:", error);
      toast.error(t('invoices.errors.load_failed'));
    } finally {
      setLoading(false);
    }
  }, [statusFilter, labelFilter, currentTenantId, page, pageSize, t]);

  useEffect(() => {
    fetchInvoices();
  }, [fetchInvoices]);

  const fetchDeletedInvoices = async () => {
    try {
      setRecycleBinLoading(true);
      const data = await api.get<DeletedInvoice[]>('/invoices/recycle-bin');
      setDeletedInvoices(data);
    } catch (error) {
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
      // Refresh the invoices list
      const status = statusFilter !== "all" ? statusFilter : undefined;
      const data = await invoiceApi.getInvoices(status, labelFilter || undefined, (page - 1) * pageSize, pageSize);
      setInvoices(data.items);
      setTotalInvoices(data.total);
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
      toast.success(`Successfully deleted ${selectedIds.length} invoice${selectedIds.length > 1 ? 's' : ''}`);
      setSelectedIds([]);
      // Refresh the invoices list
      const status = statusFilter !== "all" ? statusFilter : undefined;
      const data = await invoiceApi.getInvoices(status, labelFilter || undefined, (page - 1) * pageSize, pageSize);
      setInvoices(data.items);
      setTotalInvoices(data.total);
      // Refresh recycle bin if open
      if (showRecycleBin) {
        fetchDeletedInvoices();
      }
    } catch (error) {
      let errorMessage = error instanceof Error ? error.message : 'Failed to delete invoices';

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
      toast.success('Invoice restored successfully');
      fetchDeletedInvoices();
      // Refresh main invoices list
      const status = statusFilter !== "all" ? statusFilter : undefined;
      const data = await invoiceApi.getInvoices(status, labelFilter || undefined, (page - 1) * pageSize, pageSize);
      setInvoices(data.items);
      setTotalInvoices(data.total);
    } catch (error) {
      toast.error('Failed to restore invoice');
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
      toast.error('Failed to permanently delete invoice');
    } finally {
      setPermanentDeleteModalOpen(false);
      setInvoiceToPermanentlyDelete(null);
    }
  };

  const handleEmptyRecycleBin = () => {
    setEmptyRecycleBinModalOpen(true);
  };

  const confirmEmptyRecycleBin = async () => {
    try {
      const response = await api.post<{ message: string; deleted_count: number }>('/invoices/recycle-bin/empty', {});
      toast.success(response.message || t('recycleBin.recycle_bin_emptied_successfully'));
      fetchDeletedInvoices();
    } catch (error) {
      toast.error(t('recycleBin.failed_to_empty_recycle_bin'));
    } finally {
      setEmptyRecycleBinModalOpen(false);
    }
  };

  const handleCloneInvoice = async (invoiceId: number) => {
    try {
      const newInvoice = await invoiceApi.cloneInvoice(invoiceId);
      toast.success(`Cloned as ${newInvoice.number}`);
      // Refresh list
      const status = statusFilter !== "all" ? statusFilter : undefined;
      const data = await invoiceApi.getInvoices(status, labelFilter || undefined, (page - 1) * pageSize, pageSize);
      setInvoices(data.items);
      setTotalInvoices(data.total);
      // Redirect to edit
      navigate(`/invoices/edit/${newInvoice.id}`);
    } catch (error) {
      toast.error('Failed to clone invoice');
    }
  };

  const handleToggleRecycleBin = () => {
    setShowRecycleBin(!showRecycleBin);
    if (!showRecycleBin) {
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
              <h1 className="text-4xl font-bold tracking-tight text-foreground">{t('invoices.title')}</h1>
              <p className="text-lg text-muted-foreground">{t('invoices.description')}</p>
            </div>
            {canPerformAction && (
              <div className="flex gap-3 items-center flex-wrap justify-end">
                <ProfessionalButton
                  variant="outline"
                  size="default"
                  onClick={fetchInvoices}
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
                            <span className="text-xs text-muted-foreground">Create manually</span>
                          </div>
                        </Link>
                      </DropdownMenuItem>
                      <FeatureGate feature="ai_invoice">
                        <DropdownMenuItem asChild>
                          <Link to="/invoices/new" className="flex items-center w-full cursor-pointer">
                            <Upload className="mr-2 h-4 w-4" />
                            <div className="flex flex-col">
                              <span>{t('invoices.import_from_pdf')}</span>
                              <span className="text-xs text-muted-foreground">Upload and extract from PDF</span>
                            </div>
                          </Link>
                        </DropdownMenuItem>
                      </FeatureGate>
                      <DropdownMenuItem asChild>
                        <Link to="/invoices/new-inventory" className="flex items-center w-full cursor-pointer">
                          <Package className="mr-2 h-4 w-4" />
                          <div className="flex flex-col">
                            <span>{t('invoices.create_with_inventory')}</span>
                            <span className="text-xs text-muted-foreground">From inventory catalog</span>
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
                      <p className="text-sm text-muted-foreground">Recover or permanently delete invoices</p>
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
                                  title="Restore invoice"
                                  className="hover:bg-success/10 hover:text-success"
                                >
                                  <RotateCcw className="h-4 w-4" />
                                </ProfessionalButton>
                                <ProfessionalButton
                                  variant="ghost"
                                  size="icon-sm"
                                  onClick={() => handlePermanentDelete(invoice.id)}
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
                              <p className="text-muted-foreground font-medium">{t('recycleBin.recycle_bin_empty')}</p>
                            </div>
                          </TableCell>
                        </TableRow>
                      )}
                    </TableBody>
                  </Table>
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
                          const data = await invoiceApi.getInvoices(statusFilter !== 'all' ? statusFilter : undefined, labelFilter || undefined);
                          setInvoices(data.items);
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
                          const data = await invoiceApi.getInvoices(statusFilter !== 'all' ? statusFilter : undefined, labelFilter || undefined);
                          setInvoices(data.items);
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
                        <TableHead className="font-bold text-foreground">ID</TableHead>
                        <TableHead className="font-bold text-foreground">{t('invoices.table.invoice')}</TableHead>
                        <TableHead className="font-bold text-foreground">{t('invoices.table.client')}</TableHead>
                        <TableHead className="font-bold text-foreground">Labels</TableHead>
                        <TableHead className="hidden md:table-cell font-bold text-foreground">{t('invoices.table.due_date')}</TableHead>
                        <TableHead className="text-right font-bold text-foreground">{t('invoices.table.total_paid')}</TableHead>
                        <TableHead className="text-right font-bold text-foreground">{t('invoices.table.outstanding_balance')}</TableHead>
                        <TableHead className="font-bold text-foreground">{t('invoices.table.status')}</TableHead>
                        <TableHead className="hidden lg:table-cell font-bold text-foreground">{t('invoices.table.created_at_by', { defaultValue: 'Created at / by' })}</TableHead>
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
                          <TableCell className="font-mono text-xs text-muted-foreground">{invoice.id}</TableCell>
                          <TableCell className="font-semibold text-foreground">
                            <span className="inline-flex items-center gap-2">
                              <FileText className="h-4 w-4 text-primary/60" />
                              <span>{invoice.number}</span>
                            </span>
                          </TableCell>
                          <TableCell className="text-foreground font-medium">{invoice.client_name}</TableCell>
                          <TableCell>
                            <div className="flex flex-wrap gap-1 items-center min-w-[200px]">
                              {invoice.labels && invoice.labels.map((label: string, idx: number) => (
                                <Badge
                                  key={idx}
                                  variant="secondary"
                                  className="text-[10px] px-1.5 py-0 h-5 bg-primary/10 text-primary border-primary/20 flex items-center gap-1 group/badge"
                                >
                                  {label}
                                  <button
                                    className="hover:text-destructive transition-colors"
                                    onClick={() => {
                                      const next = invoice.labels?.filter((_, i) => i !== idx) || [];
                                      invoiceApi.updateInvoice(invoice.id, { labels: next }).then(() => {
                                        setInvoices((prev) => prev.map((x) => (x.id === invoice.id ? { ...x, labels: next } : x)));
                                      }).catch((err: any) => {
                                        toast.error(err?.message || 'Failed to remove label');
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
                                      setInvoices((prev) => prev.map((x) => (x.id === invoice.id ? { ...x, labels: next } : x)));
                                      setNewLabelValueById((prev) => ({ ...prev, [invoice.id]: '' }));
                                    }).catch((err: any) => {
                                      toast.error(err?.message || 'Failed to add label');
                                    });
                                  }
                                }}
                              />
                            </div>
                          </TableCell>
                          <TableCell className="hidden md:table-cell text-muted-foreground text-sm">
                            {invoice.due_date ? new Date(invoice.due_date).toLocaleDateString(getLocale(), { 
                              timeZone: timezone,
                              year: 'numeric',
                              month: 'short',
                              day: 'numeric'
                            }) : 'N/A'}
                          </TableCell>
                          <TableCell className="text-right font-semibold text-foreground">
                            <CurrencyDisplay amount={invoice.paid_amount || 0} currency={invoice.currency} />
                          </TableCell>
                          <TableCell className="text-right">
                            <span className={(invoice.amount - (invoice.paid_amount || 0)) > 0 ? 'text-warning font-semibold' : 'text-success font-semibold'}>
                              <CurrencyDisplay amount={invoice.amount - (invoice.paid_amount || 0)} currency={invoice.currency} />
                            </span>
                          </TableCell>
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
                          <TableCell className="hidden lg:table-cell">
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
                          </TableCell>
                          <TableCell>
                            {canPerformAction && (
                              <div className="text-right flex gap-2 justify-end">
                                <Link to={`/invoices/view/${invoice.id}`}>
                                  <Button size="sm" variant="outline">
                                    <Eye className="h-4 w-4" />
                                  </Button>
                                </Link>
                                <Link to={`/invoices/edit/${invoice.id}`}>
                                  <Button size="sm" variant="outline">
                                    <Pencil className="h-4 w-4" />
                                  </Button>
                                </Link>
                                <Button size="sm" variant="outline" onClick={() => handleCloneInvoice(invoice.id)}>
                                  <Copy className="h-4 w-4" />
                                </Button>
                                <Button size="sm" variant="destructive" onClick={() => handleDeleteInvoice(invoice.id)}>
                                  <Trash2 className="h-4 w-4" />
                                </Button>
                              </div>
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
                Showing <span className="font-medium text-foreground">{invoices.length}</span> of <span className="font-medium text-foreground">{totalInvoices}</span> results
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
