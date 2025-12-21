import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { AppLayout } from "@/components/layout/AppLayout";
import { InvoiceFormWithApproval } from "@/components/invoices/InvoiceFormWithApproval";
import { InvoiceStockImpact } from "@/components/invoices/InvoiceStockImpact";
import { InvoiceHistoryDetailsModal } from "@/components/invoices/InvoiceHistoryDetailsModal";
import { InvoicePDF } from "@/components/invoices/InvoicePDF";
import { invoiceApi, Invoice, getErrorMessage, expenseApi, Expense, inventoryApi, approvalApi, InvoiceHistory, clientApi } from "@/lib/api";
import { canEditInvoice, canEditInvoicePayment } from "@/utils/auth";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Table, TableHeader, TableRow, TableHead, TableBody, TableCell } from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { toast } from "sonner";
import { Loader2, Package, Plus, FileText, DollarSign, Calendar, AlertTriangle, CheckCircle, Clock, History, Eye, Download, File } from "lucide-react";
import { useTranslation } from 'react-i18next';
import { CurrencyDisplay } from '@/components/ui/currency-display';
import { pdf } from '@react-pdf/renderer';

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
          setLinkedExpenses(expenses);
          const unlinked = await expenseApi.getExpensesFiltered({ unlinkedOnly: true });
          setAvailableExpenses(unlinked);

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
      <AppLayout>
        <div className="h-full flex justify-center items-center">
          <Loader2 className="h-8 w-8 animate-spin mr-2" />
          <p>{t('editInvoice.loadingInvoiceData')}</p>
        </div>
      </AppLayout>
    );
  }

  if (error || !invoice) {
    return (
      <AppLayout>
        <div className="h-full space-y-6 fade-in">
          <div>
            <h1 className="text-3xl font-bold">{t('editInvoice.invoiceNotFound')}</h1>
            <p className="text-muted-foreground">{t('editInvoice.invoiceNotFoundDescription')}</p>
          </div>
        </div>
      </AppLayout>
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
          companyName="Your Company Name" // This should come from settings/tenant info
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
      clients = await clientApi.getClients();
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
    <AppLayout>
      <div className="h-full space-y-6 fade-in">
        {/* Enhanced Header with Status Overview */}
        <div className="space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div>
              <h1 className="text-3xl font-bold">{t('editInvoice.editInvoice')}</h1>
              <p className="text-muted-foreground">{t('editInvoice.updateInvoiceDetails')}</p>
            </div>
            <div className="flex flex-col sm:flex-row gap-2">
              <Badge variant="outline" className={`flex items-center gap-2 px-3 py-1 ${getStatusColor(invoice.status)}`}>
                {getStatusIcon(invoice.status)}
                {t(`invoices.status.${invoice.status}`, invoice.status.replace('_', ' '))}
              </Badge>
              {invoice.number && (
                <Badge variant="secondary" className="px-3 py-1">
                  #{invoice.number}
                </Badge>
              )}
            </div>
          </div>

          {/* Invoice Summary Cards */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <Card className="p-4">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-blue-100 rounded-lg">
                  <DollarSign className="h-5 w-5 text-blue-600" />
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">{t('editInvoice.totalAmount')}</p>
                  <p className="text-lg font-semibold">
                    <CurrencyDisplay
                      amount={invoice.amount || 0}
                      currency={invoice.currency || 'USD'}
                    />
                  </p>
                </div>
              </div>
            </Card>

            <Card className="p-4">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-green-100 rounded-lg">
                  <Calendar className="h-5 w-5 text-green-600" />
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">{t('editInvoice.dueDate')}</p>
                  <p className="text-lg font-semibold">
                    {invoice.due_date ? new Date(invoice.due_date).toLocaleDateString() : 'Not set'}
                  </p>
                </div>
              </div>
            </Card>

            <Card className="p-4">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-purple-100 rounded-lg">
                  <FileText className="h-5 w-5 text-purple-600" />
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">{t('editInvoice.items')}</p>
                  <p className="text-lg font-semibold">{invoice.items?.length || 0}</p>
                </div>
              </div>
            </Card>

            <Card className="p-4">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-orange-100 rounded-lg">
                  <Package className="h-5 w-5 text-orange-600" />
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">{t('invoices.linked_expenses_header')}</p>
                  <p className="text-lg font-semibold">{linkedExpenses.length}</p>
                </div>
              </div>
            </Card>
          </div>

          {/* Action Buttons Row */}
          <div className="flex flex-wrap gap-3 justify-center">
            <Button
              variant="outline"
              onClick={handleLivePreview}
              className="flex items-center gap-2"
            >
              <File className="h-4 w-4" />
              {t('editInvoice.livePreview')}
            </Button>
            <Button
              variant="outline"
              onClick={() => setShowAllHistoryModal(true)}
              className="flex items-center gap-2"
            >
              <History className="h-4 w-4" />
              {t('editInvoice.viewHistory')} ({invoiceHistory.length})
            </Button>
            <Button
              variant="outline"
              onClick={() => navigate('/invoices')}
            >
              {t('editInvoice.cancel')}
            </Button>
            <Button
              onClick={() => {
                const submitBtn = document.querySelector('button[type="submit"]') as HTMLButtonElement;
                if (submitBtn) submitBtn.click();
              }}
            >
              {t('editInvoice.saveChanges')}
            </Button>
          </div>
        </div>

        <div className="mt-8">
          <InvoiceFormWithApproval
            invoice={invoice}
            isEdit={true}
            existingApproval={existingApproval}
            canEditPayment={canEditPayment}
            key={`${invoice.id}-${invoice.has_attachment}-${invoice.attachment_filename}`}
            onInvoiceUpdate={async (updatedInvoice) => {
              console.log("🔍 EDIT INVOICE - Invoice updated via callback:", updatedInvoice);
              console.log("🔍 EDIT INVOICE - Updated attachment info:", {
                has_attachment: updatedInvoice.has_attachment,
                attachment_filename: updatedInvoice.attachment_filename
              });
              setInvoice(updatedInvoice);

              // Refetch stock movements if invoice status changed to payable status
              if (updatedInvoice.status === 'paid') {
                try {
                  const movements = await inventoryApi.getStockMovementsByReference('invoice', updatedInvoice.id);
                  setStockMovements(movements);
                  console.log("🔍 EDIT INVOICE - Refetched stock movements after status change:", movements);
                } catch (stockError) {
                  console.warn("Failed to refetch stock movements:", stockError);
                  setStockMovements([]);
                }
              }
            }}
          />
        </div>

        <div className="px-6">
          {/* Enhanced Linked Expenses Section */}
          <Card className="slide-in">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-orange-100 rounded-lg">
                    <Package className="h-5 w-5 text-orange-600" />
                  </div>
                  <div>
                    <CardTitle className="text-lg">{t('invoices.linked_expenses_header')}</CardTitle>
                    <p className="text-sm text-muted-foreground">
                      {t('invoices.connect_expenses_to_invoice')}
                    </p>
                  </div>
                </div>
                <Badge variant="secondary" className="px-2 py-1">
                  {t('invoices.zero_linked', { count: linkedExpenses.length })}
                </Badge>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Action Bar */}
              <div className="flex flex-col lg:flex-row gap-3 p-4 bg-gray-50 rounded-lg border">
                <div className="flex-1">
                  <label className="text-sm font-medium text-gray-700 mb-2 block">
                    {t('invoices.link_existing_expense')}
                  </label>
                  <Select value={linkSelect} onValueChange={setLinkSelect}>
                    <SelectTrigger className="w-full">
                      <SelectValue placeholder={t('invoices.choose_unlinked_expense')} />
                    </SelectTrigger>
                    <SelectContent>
                      {availableExpenses.length === 0 ? (
                        <div className="p-3 text-center text-sm text-muted-foreground">
                          No unlinked expenses available
                        </div>
                      ) : (
                        availableExpenses.map(e => (
                          <SelectItem key={e.id} value={String(e.id)}>
                            <div className="flex items-center justify-between w-full">
                              <span>#{e.id} · {e.category}</span>
                              <span className="text-muted-foreground">
                                <CurrencyDisplay amount={e.amount || 0} currency={e.currency || 'USD'} />
                              </span>
                            </div>
                          </SelectItem>
                        ))
                      )}
                    </SelectContent>
                  </Select>
                </div>
                <div className="flex flex-col sm:flex-row gap-2 lg:self-end">
                  <Button
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
                          setLinkedExpenses(linked);
                          setAvailableExpenses(unlinked);
                        } catch { }
                        setLinkSelect(undefined);
                        toast.success('Expense linked successfully');
                      } catch (e: any) {
                        toast.error(e?.message || 'Failed to link expense');
                      }
                    }}
                    className="flex items-center gap-2"
                  >
                    <Plus className="h-4 w-4" />
                    {t('invoices.link_expense')}
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => navigate(`/expenses/new?amount=${invoice?.amount || 0}&currency=${invoice?.currency || 'USD'}&invoiceId=${invoice?.id}`)}
                    className="flex items-center gap-2"
                  >
                    <Plus className="h-4 w-4" />
                    {t('invoices.create_expense')}
                  </Button>
                </div>
              </div>

              {/* Expenses List */}
              {linkedExpenses.length === 0 ? (
                <div className="text-center py-8">
                  <Package className="h-12 w-12 text-gray-300 mx-auto mb-4" />
                  <h3 className="text-lg font-medium text-gray-900 mb-2">{t('invoices.no_expenses_linked_yet')}</h3>
                  <p className="text-muted-foreground mb-4">
                    {t('invoices.link_existing_expenses_description')}
                  </p>
                </div>
              ) : (
                <div className="space-y-3">
                  {linkedExpenses.map(e => (
                    <div key={e.id} className="flex items-center justify-between p-4 border rounded-lg hover:bg-gray-50 transition-colors">
                      <div className="flex items-center gap-4">
                        <div className="p-2 bg-blue-100 rounded-lg">
                          <DollarSign className="h-4 w-4 text-blue-600" />
                        </div>
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="font-medium">#{e.id}</span>
                            <Badge variant="outline" className="text-xs">
                              {e.category}
                            </Badge>
                          </div>
                          <p className="text-sm text-muted-foreground">
                            {e.vendor || 'No vendor specified'}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-4">
                        <div className="text-right">
                          <p className="font-semibold">
                            <CurrencyDisplay amount={e.amount || 0} currency={e.currency || 'USD'} />
                          </p>
                          <p className="text-xs text-muted-foreground">Expense amount</p>
                        </div>
                        <Button
                          variant="outline"
                          size="sm"
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
                                setLinkedExpenses(linked);
                                setAvailableExpenses(unlinked);
                              } catch { }
                              toast.success('Expense unlinked successfully');
                            } catch (err: any) {
                              toast.error(err?.message || 'Failed to unlink expense');
                            }
                          }}
                          className="text-red-600 hover:text-red-700 hover:bg-red-50"
                        >
                          Unlink
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Enhanced Stock Impact Section */}
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
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <History className="h-5 w-5" />
                Invoice Update History
              </DialogTitle>
            </DialogHeader>
            <div className="max-h-[70vh] overflow-auto">
              {invoiceHistory.length === 0 ? (
                <div className="flex items-center justify-center h-64 text-muted-foreground">
                  <div className="text-center">
                    <History className="h-12 w-12 mx-auto mb-4 opacity-50" />
                    <p>No history available for this invoice</p>
                  </div>
                </div>
              ) : (
                <div className="space-y-3">
                  {invoiceHistory.map((entry) => (
                    <div
                      key={entry.id}
                      className="flex items-center justify-between p-4 border rounded-lg hover:bg-gray-50 cursor-pointer transition-colors"
                      onClick={() => {
                        handleHistoryEntryClick(entry);
                        setShowAllHistoryModal(false);
                      }}
                    >
                      <div className="flex items-center gap-3">
                        <div className="p-2 bg-blue-100 rounded-lg">
                          <FileText className="h-4 w-4 text-blue-600" />
                        </div>
                        <div className="flex-1">
                          <div className="flex items-center gap-2 mb-1">
                            <span className="font-medium capitalize">
                              {entry.action.replace('_', ' ')}
                            </span>
                            <Badge variant="outline" className="text-xs">
                              {new Date(entry.created_at).toLocaleDateString()}
                            </Badge>
                            <Badge variant="outline" className="text-xs">
                              {new Date(entry.created_at).toLocaleTimeString()}
                            </Badge>
                          </div>
                          {entry.details && (
                            <p className="text-sm text-muted-foreground mb-1">{entry.details}</p>
                          )}
                          {entry.user_name && (
                            <p className="text-xs text-muted-foreground">by {entry.user_name}</p>
                          )}
                        </div>
                      </div>
                      <Button variant="ghost" size="sm">
                        View Details
                      </Button>
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
                <Button variant="outline" onClick={() => {
                  const a = document.createElement('a');
                  a.href = livePreviewUrl;
                  a.download = `invoice-${invoice.number || 'preview'}.pdf`;
                  document.body.appendChild(a);
                  a.click();
                  document.body.removeChild(a);
                }}>
                  Download PDF
                </Button>
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
    </AppLayout>
  );
};

export default EditInvoice;
