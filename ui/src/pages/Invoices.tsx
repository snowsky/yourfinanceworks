import { useState, useEffect } from "react";
import { AppLayout } from "@/components/layout/AppLayout";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Plus, Search, Filter, FileText, Loader2, Pencil, Trash2, RotateCcw, ChevronDown, ChevronUp, Upload, Edit, Copy, Grid3X3, List, Send, Eye, CheckSquare } from "lucide-react";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from "@/components/ui/alert-dialog";
import { Checkbox } from "@/components/ui/checkbox";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Link } from "react-router-dom";
import { invoiceApi, Invoice, api, INVOICE_STATUSES, formatStatus } from "@/lib/api";
import { useNavigate } from 'react-router-dom';
import { toast } from "sonner";
import { CurrencyDisplay } from "@/components/ui/currency-display";
import { formatDate } from '@/lib/utils';
import { canPerformActions } from "@/utils/auth";
import { useTranslation } from 'react-i18next';
import { InvoiceCard } from "@/components/invoices/InvoiceCard";
import { FeatureGate } from "@/components/FeatureGate";
import { PageHeader, ContentSection } from "@/components/ui/professional-layout";
import { ProfessionalCard } from "@/components/ui/professional-card";
import { ProfessionalButton } from "@/components/ui/professional-button";

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
  const [viewMode, setViewMode] = useState<'cards' | 'table'>('cards');
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
    const fetchInvoices = async () => {
      setLoading(true);
      try {
        const status = statusFilter !== "all" ? statusFilter : undefined;
        const data = await invoiceApi.getInvoices(status);
        console.log("Invoices data received:", data);
        data.forEach(invoice => {
          console.log(`Invoice ${invoice.number}: amount=${invoice.amount}, paid_amount=${invoice.paid_amount}, outstanding=${invoice.amount - (invoice.paid_amount || 0)}`);
        });
        setInvoices(data);
      } catch (error) {
        console.error("Failed to fetch invoices:", error);
        toast.error(t('invoices.errors.load_failed'));
      } finally {
        setLoading(false);
      }
    };

    fetchInvoices();
  }, [statusFilter, currentTenantId]); // Use state variable as dependency

  const fetchDeletedInvoices = async () => {
    try {
      setRecycleBinLoading(true);
      const data = await api.get<DeletedInvoice[]>('/invoices/recycle-bin');
      setDeletedInvoices(data);
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
      // Refresh the invoices list
      const status = statusFilter !== "all" ? statusFilter : undefined;
      const data = await invoiceApi.getInvoices(status);
      setInvoices(data);
      // Refresh recycle bin if open
      if (showRecycleBin) {
        fetchDeletedInvoices();
      }
    } catch (error) {
      console.error('Failed to delete invoice:', error);
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
      const data = await invoiceApi.getInvoices(status);
      setInvoices(data);
      // Refresh recycle bin if open
      if (showRecycleBin) {
        fetchDeletedInvoices();
      }
    } catch (error) {
      console.error('Failed to bulk delete invoices:', error);
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
      const data = await invoiceApi.getInvoices(status);
      setInvoices(data);
    } catch (error) {
      console.error('Failed to restore invoice:', error);
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
      console.error('Failed to permanently delete invoice:', error);
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
      console.error('Failed to empty recycle bin:', error);
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
      const data = await invoiceApi.getInvoices(status);
      setInvoices(data);
      // Redirect to edit
      navigate(`/invoices/edit/${newInvoice.id}`);
    } catch (error) {
      console.error('Failed to clone invoice:', error);
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
    <AppLayout>
      <div className="h-full space-y-6 fade-in">
        <PageHeader
          title={t('invoices.title')}
          description={t('invoices.description')}
          actions={canPerformAction && (
            <div className="flex gap-2">
              <ProfessionalButton
                variant="outline"
                onClick={handleToggleRecycleBin}
                className="whitespace-nowrap"
              >
                <Trash2 className="mr-2 h-4 w-4" />
                {t('recycleBin.title')}
                {showRecycleBin ? <ChevronUp className="ml-2 h-4 w-4" /> : <ChevronDown className="ml-2 h-4 w-4" />}
              </ProfessionalButton>
              <div className="flex">
                <Button asChild className="rounded-r-none border-r-0 h-9" variant="default">
                  <Link to="/invoices/new">
                    <Plus className="mr-2 h-4 w-4" /> {t('invoices.new_invoice')}
                  </Link>
                </Button>
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button className="rounded-l-none px-2 h-9" variant="default">
                      <ChevronDown className="h-4 w-4" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    <FeatureGate feature="ai_invoice">
                      <DropdownMenuItem asChild>
                        <Link to="/invoices/new" className="flex items-center w-full">
                          <Upload className="mr-2 h-4 w-4" />
                          {t('invoices.import_from_pdf')}
                        </Link>
                      </DropdownMenuItem>
                    </FeatureGate>
                    <DropdownMenuItem asChild>
                      <Link to="/invoices/new-manual" className="flex items-center w-full">
                        <Edit className="mr-2 h-4 w-4" />
                        {t('invoices.enter_invoice_details_manually')}
                      </Link>
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
            </div>
          )}
        />

        <Collapsible open={showRecycleBin} onOpenChange={setShowRecycleBin}>
          <CollapsibleContent>
            <ProfessionalCard className="slide-in mb-6" variant="elevated">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2 font-semibold text-lg">
                  <Trash2 className="h-5 w-5" />
                  {t('recycleBin.title')}
                </div>
                {deletedInvoices.length > 0 && canPerformAction && (
                  <ProfessionalButton
                    variant="destructive"
                    size="sm"
                    onClick={handleEmptyRecycleBin}
                    className="gap-2"
                  >
                    <Trash2 className="h-4 w-4" />
                    {t('recycleBin.empty_recycle_bin')}
                  </ProfessionalButton>
                )}
              </div>
              <div className="rounded-md border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>{t('recycleBin.invoice')}</TableHead>
                      <TableHead>{t('recycleBin.amount')}</TableHead>
                      <TableHead>{t('recycleBin.status')}</TableHead>
                      <TableHead>{t('recycleBin.deleted_at')}</TableHead>
                      <TableHead>{t('recycleBin.deleted_by')}</TableHead>
                      <TableHead className="w-[100px]">{t('recycleBin.actions')}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {recycleBinLoading ? (
                      <TableRow>
                        <TableCell colSpan={6} className="h-24 text-center">
                          <div className="flex justify-center items-center">
                            <Loader2 className="h-6 w-6 animate-spin mr-2" />
                            {t('recycleBin.loading_deleted_invoices')}
                          </div>
                        </TableCell>
                      </TableRow>
                    ) : deletedInvoices.length > 0 ? (
                      deletedInvoices.map((invoice) => (
                        <TableRow key={invoice.id} className="hover:bg-muted/50">
                          <TableCell className="font-medium">
                            {invoice.number}
                          </TableCell>
                          <TableCell>
                            <CurrencyDisplay amount={invoice.amount} currency={invoice.currency} />
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
                                onClick={() => handleRestoreInvoice(invoice.id)}
                                className="text-green-600 hover:text-green-700 hover:bg-green-50"
                                title="Restore invoice"
                              >
                                <RotateCcw className="h-4 w-4" />
                              </Button>
                              <Button
                                variant="ghost"
                                size="icon"
                                onClick={() => handlePermanentDelete(invoice.id)}
                                className="text-red-600 hover:text-red-700 hover:bg-red-50"
                                title="Permanently delete"
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
            </ProfessionalCard>
          </CollapsibleContent>
        </Collapsible>

        <ProfessionalCard className="slide-in" variant="default">
          <div className="flex flex-col sm:flex-row justify-between gap-4 mb-6">
            <h2 className="text-xl font-semibold tracking-tight">{t('invoices.invoice_list')}</h2>
            <div className="flex flex-col sm:flex-row gap-4">
              <div className="relative">
                <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder={t('invoices.search_placeholder')}
                  className="pl-8 w-full sm:w-[200px]"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
              </div>
              <div className="flex gap-2 items-center">
                <Filter className="h-4 w-4 text-muted-foreground" />
                <Select value={statusFilter} onValueChange={setStatusFilter}>
                  <SelectTrigger className="w-full sm:w-[150px]">
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
                <div className="flex border rounded-md">
                  <Button
                    variant={viewMode === 'cards' ? 'default' : 'ghost'}
                    size="sm"
                    onClick={() => setViewMode('cards')}
                    className="rounded-r-none border-r-0"
                  >
                    <Grid3X3 className="h-4 w-4" />
                  </Button>
                  <Button
                    variant={viewMode === 'table' ? 'default' : 'ghost'}
                    size="sm"
                    onClick={() => setViewMode('table')}
                    className="rounded-l-none"
                  >
                    <List className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            </div>
          </div>

          {/* Bulk actions bar */}
          {selectedIds.length > 0 && (
            <div className="flex items-center justify-between p-3 bg-muted/50 rounded-md mb-4">
              <div className="text-sm text-muted-foreground">
                {selectedIds.length} selected
              </div>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setSelectedIds([])}
                >
                  Clear Selection
                </Button>
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={handleBulkDelete}
                  disabled={!canPerformAction}
                >
                  <Trash2 className="w-4 h-4 mr-2" />
                  Delete Selected
                </Button>
              </div>
            </div>
          )}

          {loading ? (
            <div className="flex justify-center items-center h-24">
              <Loader2 className="h-6 w-6 animate-spin mr-2" />
              {t('invoices.loading')}
            </div>
          ) : filteredInvoices.length > 0 ? (
            viewMode === 'cards' ? (
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
                {filteredInvoices.map((invoice) => (
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
                ))}
              </div>
            ) : (
              <div className="rounded-md border">
                <Table>
                  <TableHeader>
                    <TableRow>
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
                      <TableHead>{t('invoices.table.invoice')}</TableHead>
                      <TableHead>{t('invoices.table.client')}</TableHead>
                      <TableHead className="hidden sm:table-cell">{t('invoices.table.date')}</TableHead>
                      <TableHead className="hidden md:table-cell">{t('invoices.table.due_date')}</TableHead>
                      <TableHead className="text-right">{t('invoices.table.total_paid')}</TableHead>
                      <TableHead className="text-right">{t('invoices.table.outstanding_balance')}</TableHead>
                      <TableHead>{t('invoices.table.status')}</TableHead>
                      <TableHead className="hidden lg:table-cell">{t('common.created_by')}</TableHead>
                      <TableHead className="w-[100px]">{t('invoices.table.actions')}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filteredInvoices.map((invoice) => (
                      <TableRow key={invoice.id} className="hover:bg-muted/50">
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
                        <TableCell className="font-medium">
                          <span className="inline-flex items-center">
                            <FileText className="h-4 w-4 mr-2 text-muted-foreground" />
                            {invoice.number}
                          </span>
                        </TableCell>
                        <TableCell>{invoice.client_name}</TableCell>
                        <TableCell className="hidden sm:table-cell">{formatDate(invoice.created_at)}</TableCell>
                        <TableCell className="hidden md:table-cell">{formatDate(invoice.due_date)}</TableCell>
                        <TableCell className="text-right font-medium">
                          <CurrencyDisplay amount={invoice.paid_amount || 0} currency={invoice.currency} />
                        </TableCell>
                        <TableCell className="text-right">
                          <span className={(invoice.amount - (invoice.paid_amount || 0)) > 0 ? 'text-warning font-medium' : 'text-success font-medium'}>
                            <CurrencyDisplay amount={invoice.amount - (invoice.paid_amount || 0)} currency={invoice.currency} />
                          </span>
                        </TableCell>
                        <TableCell>
                          <Badge className={
                            invoice.status === 'paid' ? 'status-paid' :
                              invoice.status === 'pending' ? 'status-pending' :
                                invoice.status === 'overdue' ? 'status-overdue' :
                                  invoice.status === 'partially_paid' ? 'status-partially-paid' :
                                    'bg-muted/50 text-muted-foreground'
                          }>
                            {formatStatus(invoice.status)}
                          </Badge>
                        </TableCell>
                        <TableCell className="hidden lg:table-cell text-sm text-muted-foreground">
                          {invoice.created_by_username || invoice.created_by_email || t('common.unknown')}
                        </TableCell>
                        <TableCell>
                          {canPerformAction && (
                            <div className="flex gap-1">
                              <Link to={`/invoices/view/${invoice.id}`}>
                                <Button variant="ghost" size="icon" title={t('invoices.view_invoice')}>
                                  <Eye className="h-4 w-4" />
                                </Button>
                              </Link>
                              <Link to={`/invoices/edit/${invoice.id}`}>
                                <Button variant="ghost" size="icon" title={t('invoices.edit_invoice')}>
                                  <Pencil className="h-4 w-4" />
                                </Button>
                              </Link>
                              <Button
                                variant="ghost"
                                size="icon"
                                onClick={() => handleCloneInvoice(invoice.id)}
                                title="Clone invoice"
                              >
                                <Copy className="h-4 w-4" />
                              </Button>
                              <Button
                                variant="ghost"
                                size="icon"
                                onClick={() => handleDeleteInvoice(invoice.id)}
                                className="text-destructive hover:text-destructive hover:bg-destructive/10"
                              >
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
            <div className="text-center py-20 bg-muted/10 rounded-xl border-2 border-dashed border-muted-foreground/20">
              <div className="bg-primary/10 w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-4">
                <FileText className="h-8 w-8 text-primary" />
              </div>
              <h3 className="text-xl font-bold mb-2">{t('invoices.no_invoices', 'No invoices yet')}</h3>
              <p className="text-muted-foreground max-w-sm mx-auto">
                {t('invoices.no_invoices_description', 'Get started by creating your first professional invoice. You can also import one from a PDF.')}
              </p>
            </div>
          )}
        </ProfessionalCard>
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
              <Trash2 className="mr-2 h-4 w-4" />
              {t('invoices.permanent_delete', 'Permanently Delete')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Delete Invoice Modal */}
      <AlertDialog open={deleteModalOpen} onOpenChange={setDeleteModalOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('invoices.delete_confirm_title', 'Delete Invoice')}</AlertDialogTitle>
            <AlertDialogDescription>
              {t('invoices.delete_confirm_description', 'Are you sure you want to delete this invoice? This action cannot be undone.')}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t('common.cancel', 'Cancel')}</AlertDialogCancel>
            <AlertDialogAction onClick={confirmDeleteInvoice} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">
              {t('invoices.delete', 'Delete')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Bulk Delete Modal */}
      <AlertDialog open={bulkDeleteModalOpen} onOpenChange={setBulkDeleteModalOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {selectedIds.length === 1
                ? t('invoices.delete_single_title', 'Move 1 Invoice to Recycle Bin')
                : t('invoices.delete_multiple_title', `Move ${selectedIds.length} Invoices to Recycle Bin`)
              }
            </AlertDialogTitle>
            <AlertDialogDescription>
              {selectedIds.length === 1
                ? t('invoices.delete_single_description', 'Are you sure you want to move this invoice to the recycle bin? You can restore it later if needed.')
                : t('invoices.delete_multiple_description', `Are you sure you want to move ${selectedIds.length} invoices to the recycle bin? You can restore them later if needed.`)
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
            <AlertDialogCancel>{t('common.cancel', 'Cancel')}</AlertDialogCancel>
            <AlertDialogAction onClick={confirmEmptyRecycleBin} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">
              <Trash2 className="mr-2 h-4 w-4" />
              {t('recycleBin.empty_recycle_bin')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </AppLayout>
  );
};

export default Invoices;
