import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { cn } from "@/lib/utils";
import { InvoiceFormWithApproval } from "@/components/invoices/InvoiceFormWithApproval";
import { InvoiceStockImpact } from "@/components/invoices/InvoiceStockImpact";
import { InvoiceHistoryDetailsModal } from "@/components/invoices/InvoiceHistoryDetailsModal";
import { InvoicePDF } from "@/components/invoices/InvoicePDF";
import { invoiceApi, Invoice, getErrorMessage, expenseApi, Expense, inventoryApi, approvalApi, InvoiceHistory, clientApi, settingsApi, Settings } from "@/lib/api";
import { canEditInvoice, canEditInvoicePayment } from "@/utils/auth";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { toast } from "sonner";
import { Trash, Loader2, Package, Plus, FileText, DollarSign, Calendar, AlertTriangle, CheckCircle, Clock, History, Eye, Download, File, ArrowLeft } from "lucide-react";
import { useTranslation } from 'react-i18next';
import { CurrencyDisplay } from '@/components/ui/currency-display';
import { pdf } from '@react-pdf/renderer';
import { ProfessionalButton } from "@/components/ui/professional-button";
import { ProfessionalCard, MetricCard } from "@/components/ui/professional-card";

const EditInvoice = () => {
  const { t } = useTranslation();
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [invoice, setInvoice] = useState<Invoice | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [linkedExpenses, setLinkedExpenses] = useState<Expense[]>([]);
  const [availableExpenses, setAvailableExpenses] = useState<Expense[]>([]);
  const [linkSelect, setLinkSelect] = useState<string | undefined>(undefined);
  const [stockMovements, setStockMovements] = useState<any[]>([]);
  const [existingApproval, setExistingApproval] = useState<{ approver_id: number } | undefined>(undefined);
  const [invoiceHistory, setInvoiceHistory] = useState<InvoiceHistory[]>([]);
  const [showHistoryModal, setShowHistoryModal] = useState(false);
  const [selectedHistoryEntry, setSelectedHistoryEntry] = useState<InvoiceHistory | null>(null);
  const [showAllHistoryModal, setShowAllHistoryModal] = useState(false);
  const [showPreviewModal, setShowPreviewModal] = useState(false);
  const [showLivePreviewModal, setShowLivePreviewModal] = useState(false);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [livePreviewUrl, setLivePreviewUrl] = useState<string | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [livePreviewLoading, setLivePreviewLoading] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [settings, setSettings] = useState<Settings | null>(null);

  // Calculate payment editing permissions when invoice changes
  const canEditPayment = invoice ? canEditInvoicePayment(invoice) : false;

  // Fetch invoice history when invoice changes
  useEffect(() => {
    if (invoice?.id) {
      const fetchHistory = async () => {
        try {
          const history = await invoiceApi.getInvoiceHistory(invoice.id);
          setInvoiceHistory(history);
        } catch (error) {
          console.warn("Failed to fetch invoice history:", error);
          setInvoiceHistory([]);
        }
      };
      fetchHistory();
    } else {
      setInvoiceHistory([]);
    }
  }, [invoice?.id]);

  // Fetch settings data
  useEffect(() => {
    const fetchSettings = async () => {
      try {
        const settingsData = await settingsApi.getSettings();
        setSettings(settingsData);
      } catch (error) {
        console.error("Failed to fetch settings:", error);
        // Set fallback settings
        setSettings({
          company_info: { name: 'InvoiceApp', email: '', phone: '', address: '', tax_id: '', logo: '' },
          invoice_settings: { prefix: 'INV-', next_number: '0001', terms: 'Net 30 days', notes: 'Thank you for your business!', send_copy: true, auto_reminders: true },
          enable_ai_assistant: false
        });
      }
    };
    fetchSettings();
  }, []);

  useEffect(() => {
    const fetchInvoice = async () => {
      if (!id) {
        navigate("/invoices");
        return;
      }

      setLoading(true);
      try {
        const data = await invoiceApi.getInvoice(parseInt(id));

        // Check if user can edit this invoice
        const canEdit = canEditInvoice(data);
        const canEditPayment = canEditInvoicePayment(data);

        if (!canEdit && !canEditPayment) {
          if (data.status === 'approved') {
            toast.error('This invoice can only be edited for payment updates');
          } else {
            toast.error('This invoice cannot be edited while it is in the approval workflow');
          }
          navigate('/invoices');
          return;
        }

        // Check if items exists and has content
        if (!data.items || !Array.isArray(data.items) || data.items.length === 0) {
          console.warn("Invoice items are missing or empty:", data.items);
          toast.warning(t('invoices.errors.invoiceItemsMissing'));
        }

        setInvoice(data);
        try {
          const expenses = await expenseApi.getExpensesFiltered({ invoiceId: data.id });
          setLinkedExpenses(Array.isArray(expenses) ? expenses : []);
          const unlinked = await expenseApi.getExpensesFiltered({ unlinkedOnly: true });
          setAvailableExpenses(Array.isArray(unlinked) ? unlinked : []);

          // Fetch stock movements related to this invoice
          try {
            const movements = await inventoryApi.getStockMovementsByReference('invoice', data.id);
            setStockMovements(movements);
          } catch (stockError) {
            console.warn("Failed to fetch stock movements:", stockError);
            setStockMovements([]);
          }

          // Fetch previous approvals to check if this invoice is under approval or was rejected
          if (data.status === 'pending_approval' || data.status === 'rejected') {
            console.log(`🔍 EDIT INVOICE - Invoice is ${data.status}, fetching approval details...`);
            try {
              const historyResponse = await approvalApi.getInvoiceApprovalHistory(data.id);
              console.log("🔍 EDIT INVOICE - Approval history response:", historyResponse);

              // Find the latest pending or completed approval
              const latestApproval = historyResponse.approval_history
                .filter((a: any) => data.status === 'pending_approval' ? a.status === 'pending' : (a.status === 'approved' || a.status === 'rejected'))
                .sort((a: any, b: any) => {
                  const dateA = new Date(a.decided_at || a.submitted_at || a.timestamp).getTime();
                  const dateB = new Date(b.decided_at || b.submitted_at || b.timestamp).getTime();
                  return dateB - dateA;
                })[0];

              if (latestApproval) {
                console.log("🔍 EDIT INVOICE - Found relevant approval:", latestApproval);
                setExistingApproval({ approver_id: latestApproval.approver_id });
              } else {
                console.warn(`🔍 EDIT INVOICE - Status is ${data.status} but no relevant approval found in history`);
              }
            } catch (approvalError) {
              console.warn("🔍 EDIT INVOICE - Failed to fetch approval history:", approvalError);
            }
          } else {
            console.log("🔍 EDIT INVOICE - Invoice status does not require approval history fetch:", data.status);
          }
        } catch { }
      } catch (error) {
        console.error("Failed to fetch invoice:", error);
        toast.error(getErrorMessage(error, t));
        setError(true);
      } finally {
        setLoading(false);
      }
    };

    fetchInvoice();
  }, [id, navigate, t]);

  if (loading) {
    return (
      <>
        <div className="h-full flex justify-center items-center">
          <Loader2 className="h-8 w-8 animate-spin mr-2" />
          <p>{t('editInvoice.loadingInvoiceData')}</p>
        </div>
      </>
    );
  }

  if (error || !invoice) {
    return (
      <>
        <div className="h-full space-y-6 fade-in">
          <div>
            <h1 className="text-3xl font-bold">{t('editInvoice.invoiceNotFound')}</h1>
            <p className="text-muted-foreground">{t('editInvoice.invoiceNotFoundDescription')}</p>
          </div>
        </div>
      </>
    );
  }

  // Make sure invoice has an items array even if API didn't return one
  if (!invoice.items) {
    invoice.items = [];
  }

  // Handle preview functionality
  const handlePreview = async () => {
    if (!invoice?.id) return;

    setPreviewLoading(true);
    setShowPreviewModal(true);

    try {
      // For now, we'll use the attachment preview if available
      // In a full implementation, this would generate a PDF preview
      if (invoice.has_attachment) {
        const blob = await invoiceApi.previewAttachmentBlob(invoice.id);
        const url = URL.createObjectURL(blob);
        setPreviewUrl(url);
      } else {
        // If no attachment, we could generate a preview or show a placeholder
        toast.info("No attachment available for preview");
        setShowPreviewModal(false);
      }
    } catch (error) {
      console.error("Failed to load preview:", error);
      toast.error("Failed to load preview");
      setShowPreviewModal(false);
    } finally {
      setPreviewLoading(false);
    }
  };

  // Handle download functionality
  const handleDownload = () => {
    if (!invoice?.id) return;
    invoiceApi.downloadAttachment(invoice.id);
  };

  // Handle live preview functionality
  const handleLivePreview = async () => {
    setLivePreviewLoading(true);
    setShowLivePreviewModal(true);

    try {
      // Generate PDF blob using InvoicePDF component
      const blob = await pdf(
        <InvoicePDF
          invoice={invoice}
          companyName={settings?.company_info?.name || 'Your Company Name'}
          clientCompany={invoice.client_name}
          showDiscount={invoice.show_discount_in_pdf || false}
          template="modern"
        />
      ).toBlob();

      const url = URL.createObjectURL(blob);
      setLivePreviewUrl(url);
    } catch (error) {
      console.error("Failed to generate live preview:", error);
      toast.error("Failed to generate live preview");
      setShowLivePreviewModal(false);
    } finally {
      setLivePreviewLoading(false);
    }
  };

  // Handle history entry click
  const handleHistoryEntryClick = async (entry: InvoiceHistory) => {
    // Fetch client data for resolving client_id in history
    let clients: Array<{ id: number; name: string; email?: string }> = [];
    try {
      const clientsResponse = await clientApi.getClients();
      clients = clientsResponse.items;
    } catch (error) {
      console.warn("Failed to fetch clients for history modal:", error);
    }

    setSelectedHistoryEntry({
      ...entry,
      // Add clients array for the modal to use
      clients: clients
    } as any);
    setShowHistoryModal(true);
  };



  // Helper function to get status color
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'paid': return 'bg-green-100 text-green-800 border-green-200';
      case 'pending_approval': return 'bg-yellow-100 text-yellow-800 border-yellow-200';
      case 'sent': return 'bg-blue-100 text-blue-800 border-blue-200';
      case 'overdue': return 'bg-red-100 text-red-800 border-red-200';
      case 'draft': return 'bg-gray-100 text-gray-800 border-gray-200';
      default: return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  // Helper function to get status icon
  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'paid': return <CheckCircle className="h-4 w-4" />;
      case 'pending_approval': return <Clock className="h-4 w-4" />;
      case 'sent': return <FileText className="h-4 w-4" />;
      case 'overdue': return <AlertTriangle className="h-4 w-4" />;
      case 'draft': return <FileText className="h-4 w-4" />;
      default: return <FileText className="h-4 w-4" />;
    }
  };

  return (
    <>
      <div className="h-full space-y-8 fade-in pb-12">
        {/* Hero Header */}
        <div className="bg-gradient-to-r from-primary/10 via-primary/5 to-transparent rounded-2xl border border-primary/20 p-8 backdrop-blur-sm">
          <div className="flex items-center justify-between gap-6">
            <div className="space-y-2">
              <div className="flex items-center gap-3">
                <ProfessionalButton
                  variant="outline"
                  size="icon-sm"
                  onClick={() => navigate('/invoices')}
                  className="rounded-full"
                >
                  <ArrowLeft className="h-4 w-4" />
                </ProfessionalButton>
                <div className="flex items-center gap-2">
                  <Badge
                    variant={
                      invoice.status === 'paid' ? 'default' :
                        invoice.status === 'overdue' ? 'destructive' :
                          invoice.status === 'pending' || invoice.status === 'pending_approval' ? 'secondary' :
                            invoice.status === 'sent' ? 'secondary' : 'outline'
                    }
                    className={cn(
                      "px-3 py-1 font-medium capitalize",
                      invoice.status === 'paid' && "bg-green-100 text-green-800 hover:bg-green-100 border-green-200 dark:bg-green-900/30 dark:text-green-400 dark:border-green-800",
                      invoice.status === 'overdue' && "bg-red-100 text-red-800 hover:bg-red-100 border-red-200 dark:bg-red-900/30 dark:text-red-400 dark:border-red-800",
                      (invoice.status === 'pending' || invoice.status === 'pending_approval') && "bg-amber-100 text-amber-800 hover:bg-amber-100 border-amber-200 dark:bg-amber-900/30 dark:text-amber-400 dark:border-amber-800",
                      invoice.status === 'sent' && "bg-blue-100 text-blue-800 hover:bg-blue-100 border-blue-200 dark:bg-blue-900/30 dark:text-blue-400 dark:border-blue-800"
                    )}
                  >
                    {t(`invoices.status.${invoice.status}`, invoice.status.replace('_', ' '))}
                  </Badge>
                  {invoice.number && (
                    <Badge variant="secondary" className="px-3 py-1 font-mono font-medium">
                      #{invoice.number}
                    </Badge>
                  )}
                </div>
              </div>
              <h1 className="text-4xl font-bold tracking-tight text-foreground">
                {t('editInvoice.editInvoice')}
              </h1>
              <p className="text-lg text-muted-foreground">
                {t('editInvoice.updateInvoiceDetails')}
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <ProfessionalButton
                variant="outline"
                onClick={handleLivePreview}
                leftIcon={<Eye className="h-4 w-4" />}
                loading={livePreviewLoading}
              >
                {t('editInvoice.livePreview')}
              </ProfessionalButton>
              <ProfessionalButton
                variant="outline"
                onClick={() => setShowAllHistoryModal(true)}
                leftIcon={<History className="h-4 w-4" />}
              >
                {t('editInvoice.viewHistory')} ({invoiceHistory.length})
              </ProfessionalButton>
              <ProfessionalButton
                variant="default"
                size="lg"
                onClick={() => {
                  const submitBtn = document.querySelector('button[type="submit"]') as HTMLButtonElement;
                  if (submitBtn) submitBtn.click();
                }}
                className="shadow-lg"
                loading={isSubmitting}
                leftIcon={<CheckCircle className="h-4 w-4" />}
              >
                {t('editInvoice.saveChanges')}
              </ProfessionalButton>
            </div>
          </div>
        </div>

        <div className="px-8 -mt-10 relative z-20">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <MetricCard
              title={t('editInvoice.totalAmount')}
              value={
                <CurrencyDisplay
                  amount={invoice.amount || 0}
                  currency={invoice.currency || 'USD'}
                />
              }
              variant="default"
              icon={DollarSign}
            />

            <MetricCard
              title={t('editInvoice.due_date')}
              value={invoice.due_date ? new Date(invoice.due_date).toLocaleDateString() : 'Not set'}
              variant="success"
              icon={Calendar}
            />

            <MetricCard
              title={t('editInvoice.items')}
              value={invoice.items?.length || 0}
              variant="warning"
              icon={FileText}
            />

            <MetricCard
              title={t('invoices.linked_expenses_header')}
              value={linkedExpenses.length}
              variant="default"
              icon={Package}
            />
          </div>
        </div>

        <div>
          <InvoiceFormWithApproval
            invoice={invoice}
            isEdit={true}
            existingApproval={existingApproval}
            canEditPayment={canEditPayment}
            onSubmitStateChange={setIsSubmitting}
            onInvoiceUpdate={async (updatedInvoice) => {
              console.log("🔍 EDIT INVOICE - Invoice updated via callback:", updatedInvoice);
              setInvoice(updatedInvoice);

              // Refetch stock movements if invoice status changed to payable status
              if (updatedInvoice.status === 'paid') {
                try {
                  const movements = await inventoryApi.getStockMovementsByReference('invoice', updatedInvoice.id);
                  setStockMovements(movements);
                } catch (stockError) {
                  console.warn("Failed to refetch stock movements:", stockError);
                  setStockMovements([]);
                }
              }
            }}
          />
        </div>

        <div className="px-8 space-y-8">
          {/* Enhanced Linked Expenses Section */}
          <ProfessionalCard variant="elevated" className="overflow-hidden border-0">
            <div className="pb-6 border-b border-border/50">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <div className="p-3 bg-orange-100 dark:bg-orange-900/30 rounded-xl">
                    <Package className="h-6 w-6 text-orange-600 dark:text-orange-400" />
                  </div>
                  <div>
                    <h2 className="text-2xl font-bold text-foreground tracking-tight">{t('invoices.linked_expenses_header')}</h2>
                    <p className="text-sm text-muted-foreground">
                      {t('invoices.connect_expenses_to_invoice')}
                    </p>
                  </div>
                </div>
                <Badge variant="secondary" className="px-4 py-1.5 font-bold rounded-full bg-orange-100 dark:bg-orange-900/30 text-orange-700 dark:text-orange-300 border-0">
                  {linkedExpenses.length}
                </Badge>
              </div>
            </div>
            <div className="space-y-6 pt-8">
              {/* Action Bar */}
              <div className="flex flex-col lg:flex-row gap-6 p-6 bg-muted/30 rounded-2xl border border-border/50">
                <div className="flex-1 space-y-2">
                  <label className="text-xs font-bold text-muted-foreground uppercase tracking-widest px-1">
                    {t('invoices.link_existing_expense')}
                  </label>
                  <Select value={linkSelect} onValueChange={setLinkSelect}>
                    <SelectTrigger className="w-full h-11 bg-background border-border/50 rounded-xl">
                      <SelectValue placeholder={t('invoices.choose_unlinked_expense')} />
                    </SelectTrigger>
                    <SelectContent className="rounded-xl">
                      {availableExpenses.length === 0 ? (
                        <div className="p-4 text-center text-sm text-muted-foreground italic">
                          No unlinked expenses available
                        </div>
                      ) : (
                        availableExpenses.map(e => (
                          <SelectItem key={e.id} value={String(e.id)} className="rounded-lg">
                            <div className="flex items-center justify-between w-full py-1">
                              <span className="font-medium">#{e.id} · {e.category}</span>
                              <Badge variant="outline" className="ml-4 font-mono bg-muted/50">
                                <CurrencyDisplay amount={e.amount || 0} currency={e.currency || 'USD'} />
                              </Badge>
                            </div>
                          </SelectItem>
                        ))
                      )}
                    </SelectContent>
                  </Select>
                </div>
                <div className="flex flex-col sm:flex-row gap-3 lg:self-end">
                  <ProfessionalButton
                    disabled={!linkSelect}
                    onClick={async () => {
                      try {
                        if (!linkSelect) return;
                        const expId = Number(linkSelect);
                        const updated = await expenseApi.updateExpense(expId, { invoice_id: invoice!.id } as any);
                        // Optimistic local update
                        setLinkedExpenses(prev => [updated, ...prev.filter(e => e.id !== updated.id)]);
                        setAvailableExpenses(prev => prev.filter(e => e.id !== updated.id));
                        // Then refresh from server
                        try {
                          const [linked, unlinked] = await Promise.all([
                            expenseApi.getExpensesFiltered({ invoiceId: invoice!.id }),
                            expenseApi.getExpensesFiltered({ unlinkedOnly: true })
                          ]);
                          setLinkedExpenses(Array.isArray(linked) ? linked : []);
                          setAvailableExpenses(Array.isArray(unlinked) ? unlinked : []);
                        } catch { }
                        setLinkSelect(undefined);
                        toast.success('Expense linked successfully');
                      } catch (e: any) {
                        toast.error(e?.message || 'Failed to link expense');
                      }
                    }}
                    variant="gradient"
                    className="h-11 px-6 rounded-xl shadow-lg shadow-blue-500/10"
                    leftIcon={<Plus className="h-4 w-4" />}
                  >
                    {t('invoices.link_expense')}
                  </ProfessionalButton>
                  <ProfessionalButton
                    variant="outline"
                    onClick={() => navigate(`/expenses/new?amount=${invoice?.amount || 0}&currency=${invoice?.currency || 'USD'}&invoiceId=${invoice?.id}`)}
                    className="h-11 px-6 rounded-xl border-border/50 hover:bg-muted"
                    leftIcon={<Plus className="h-4 w-4" />}
                  >
                    {t('invoices.create_expense')}
                  </ProfessionalButton>
                </div>
              </div>

              {/* Expenses List */}
              {linkedExpenses.length === 0 ? (
                <div className="text-center py-20 px-6 rounded-2xl border-2 border-dashed border-border/50 bg-muted/10">
                  <div className="inline-flex items-center justify-center w-20 h-20 rounded-full bg-muted mb-6">
                    <Package className="h-10 w-10 text-muted-foreground/40" />
                  </div>
                  <h3 className="text-xl font-bold text-foreground mb-2">{t('invoices.no_expenses_linked_yet')}</h3>
                  <p className="text-muted-foreground max-sm mx-auto">
                    {t('invoices.link_existing_expenses_description')}
                  </p>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {linkedExpenses.map((e, idx) => (
                    <div key={e.id} className="flex items-center justify-between p-5 border border-border/50 rounded-2xl hover:border-primary/30 hover:shadow-xl hover:shadow-primary/5 transition-all duration-300 bg-background group">
                      <div className="flex items-center gap-4 flex-1">
                        <div className="p-3 bg-blue-50 dark:bg-blue-900/20 rounded-xl group-hover:bg-blue-100 dark:group-hover:bg-blue-900/40 transition-colors">
                          <DollarSign className="h-5 w-5 text-blue-600 dark:text-blue-400" />
                        </div>
                        <div className="flex-1">
                          <div className="flex items-center gap-2 mb-1">
                            <span className="font-bold text-foreground tracking-tight">#{e.id}</span>
                            <Badge variant="outline" className="text-[10px] font-bold uppercase tracking-wider bg-muted/30">
                              {e.category}
                            </Badge>
                          </div>
                          <p className="text-sm font-medium text-muted-foreground truncate max-w-[200px]">
                            {e.vendor || 'No vendor specified'}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-6">
                        <div className="text-right">
                          <p className="text-lg font-bold text-foreground">
                            <CurrencyDisplay amount={e.amount || 0} currency={e.currency || 'USD'} />
                          </p>
                        </div>
                        <ProfessionalButton
                          variant="ghost"
                          size="icon-sm"
                          onClick={async () => {
                            try {
                              // Use null to explicitly clear the link on the backend
                              const updated = await expenseApi.updateExpense(e.id, { invoice_id: null } as any);
                              // Optimistic local update
                              setLinkedExpenses(prev => prev.filter(x => x.id !== updated.id));
                              setAvailableExpenses(prev => [updated, ...prev.filter(x => x.id !== updated.id)]);
                              // Then refresh from server
                              try {
                                const [linked, unlinked] = await Promise.all([
                                  expenseApi.getExpensesFiltered({ invoiceId: invoice!.id }),
                                  expenseApi.getExpensesFiltered({ unlinkedOnly: true })
                                ]);
                                setLinkedExpenses(Array.isArray(linked) ? linked : []);
                                setAvailableExpenses(Array.isArray(unlinked) ? unlinked : []);
                              } catch { }
                              toast.success('Expense unlinked successfully');
                            } catch (err: any) {
                              toast.error(err?.message || 'Failed to unlink expense');
                            }
                          }}
                          className="text-muted-foreground hover:text-destructive hover:bg-destructive/10 rounded-xl"
                        >
                          <Trash className="h-4 w-4" />
                        </ProfessionalButton>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </ProfessionalCard>
        </div>

        <div className="px-8 pb-12">
          {invoice && (
            <InvoiceStockImpact
              invoiceId={invoice.id}
              invoiceNumber={invoice.number || ''}
              invoiceStatus={invoice.status}
            />
          )}
        </div>

        {/* Invoice History Details Modal */}
        {selectedHistoryEntry && (
          <InvoiceHistoryDetailsModal
            open={showHistoryModal}
            onClose={() => {
              setShowHistoryModal(false);
              setSelectedHistoryEntry(null);
            }}
            historyEntry={selectedHistoryEntry}
            clients={[]}
          />
        )}

        {/* All History Modal */}
        <Dialog
          open={showAllHistoryModal}
          onOpenChange={(open) => {
            if (!open) {
              setShowAllHistoryModal(false);
            }
          }}
        >
          <DialogContent className="max-w-4xl max-h-[80vh]">
            <DialogHeader className="border-b pb-4">
              <DialogTitle className="flex items-center gap-2 text-2xl">
                <div className="p-2 bg-blue-100 dark:bg-blue-900/30 rounded-lg">
                  <History className="h-5 w-5 text-blue-600 dark:text-blue-400" />
                </div>
                Invoice Update History
              </DialogTitle>
            </DialogHeader>
            <div className="max-h-[70vh] overflow-auto">
              {invoiceHistory.length === 0 ? (
                <div className="flex items-center justify-center h-64 text-muted-foreground">
                  <div className="text-center">
                    <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-slate-100 dark:bg-slate-800 mb-4">
                      <History className="h-8 w-8 text-slate-400 dark:text-slate-600" />
                    </div>
                    <p className="font-medium">No history available for this invoice</p>
                  </div>
                </div>
              ) : (
                <div className="space-y-3 pr-4">
                  {invoiceHistory.map((entry, idx) => (
                    <div
                      key={entry.id}
                      className="flex items-center justify-between p-4 border rounded-lg hover:shadow-soft hover:border-slate-300 dark:hover:border-slate-600 cursor-pointer transition-all duration-200 bg-white dark:bg-slate-950/50 stagger-{idx % 5 + 1}"
                      onClick={() => {
                        handleHistoryEntryClick(entry);
                        setShowAllHistoryModal(false);
                      }}
                    >
                      <div className="flex items-center gap-3 flex-1">
                        <div className="p-2 bg-gradient-to-br from-blue-100 to-blue-50 dark:from-blue-900/30 dark:to-blue-800/20 rounded-lg">
                          <FileText className="h-4 w-4 text-blue-600 dark:text-blue-400" />
                        </div>
                        <div className="flex-1">
                          <div className="flex items-center gap-2 mb-1 flex-wrap">
                            <span className="font-semibold text-slate-900 dark:text-slate-100 capitalize">
                              {entry.action.replace('_', ' ')}
                            </span>
                            <Badge variant="outline" className="text-xs font-medium">
                              {new Date(entry.created_at).toLocaleDateString()}
                            </Badge>
                            <Badge variant="outline" className="text-xs font-medium">
                              {new Date(entry.created_at).toLocaleTimeString()}
                            </Badge>
                          </div>
                          {entry.details && (
                            <p className="text-sm text-muted-foreground mb-1">{entry.details}</p>
                          )}
                          {entry.user_name && (
                            <p className="text-xs text-muted-foreground font-medium">by {entry.user_name}</p>
                          )}
                        </div>
                      </div>
                      <ProfessionalButton variant="ghost" size="sm" className="ml-2">
                        View Details
                      </ProfessionalButton>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </DialogContent>
        </Dialog>

        {/* Live Preview Modal */}
        <Dialog
          open={showLivePreviewModal}
          onOpenChange={(open) => {
            if (!open) {
              setShowLivePreviewModal(false);
              if (livePreviewUrl) {
                URL.revokeObjectURL(livePreviewUrl);
                setLivePreviewUrl(null);
              }
              setLivePreviewLoading(false);
            }
          }}
        >
          <DialogContent className="max-w-4xl max-h-[80vh]">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <File className="h-5 w-5" />
                Live Invoice Preview
              </DialogTitle>
            </DialogHeader>
            <div className="max-h-[70vh] overflow-auto">
              {livePreviewLoading ? (
                <div className="flex items-center justify-center h-64">
                  <Loader2 className="h-8 w-8 animate-spin mr-2" />
                  <p>Generating live preview...</p>
                </div>
              ) : livePreviewUrl ? (
                <iframe
                  src={livePreviewUrl}
                  className="w-full h-[70vh]"
                  title="Live Invoice Preview"
                />
              ) : (
                <div className="flex items-center justify-center h-64 text-muted-foreground">
                  <div className="text-center">
                    <File className="h-12 w-12 mx-auto mb-4 opacity-50" />
                    <p>Failed to generate preview</p>
                  </div>
                </div>
              )}
            </div>
            {livePreviewUrl && (
              <div className="flex gap-2">
                <ProfessionalButton variant="outline" onClick={() => {
                  const a = document.createElement('a');
                  a.href = livePreviewUrl;
                  a.download = `invoice-${invoice.number || 'preview'}.pdf`;
                  document.body.appendChild(a);
                  a.click();
                  document.body.removeChild(a);
                }}>
                  Download PDF
                </ProfessionalButton>
              </div>
            )}
          </DialogContent>
        </Dialog>

        {/* Preview Modal */}
        <Dialog
          open={showPreviewModal}
          onOpenChange={(open) => {
            if (!open) {
              setShowPreviewModal(false);
              setPreviewUrl(null);
              setPreviewLoading(false);
            }
          }}
        >
          <DialogContent className="max-w-4xl max-h-[80vh]">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <Eye className="h-5 w-5" />
                Invoice Preview
              </DialogTitle>
            </DialogHeader>
            <div className="max-h-[70vh] overflow-auto">
              {previewLoading ? (
                <div className="flex items-center justify-center h-64">
                  <Loader2 className="h-8 w-8 animate-spin mr-2" />
                  <p>Loading preview...</p>
                </div>
              ) : previewUrl ? (
                invoice.attachment_filename?.toLowerCase().endsWith('.pdf') ? (
                  <iframe
                    src={previewUrl}
                    className="w-full h-[70vh]"
                    title="PDF Preview"
                  />
                ) : (
                  <img
                    src={previewUrl}
                    alt="Invoice attachment preview"
                    className="max-w-full h-auto mx-auto"
                  />
                )
              ) : (
                <div className="flex items-center justify-center h-64 text-muted-foreground">
                  <div className="text-center">
                    <FileText className="h-12 w-12 mx-auto mb-4 opacity-50" />
                    <p>No preview available</p>
                  </div>
                </div>
              )}
            </div>
          </DialogContent>
        </Dialog>

      </div>
    </>
  );
};

export default EditInvoice;
