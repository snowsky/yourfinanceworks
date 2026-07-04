import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { PageHeader } from '@/components/ui/professional-layout';
import { ProfessionalCard } from '@/components/ui/professional-card';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { CurrencySelector } from '@/components/ui/currency-selector';
import { Calendar } from '@/components/ui/calendar';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { CalendarIcon, Edit, Eye, Loader2, AlertCircle, RotateCcw } from 'lucide-react';
import { format } from 'date-fns';
import { toast } from 'sonner';
import { invoiceApi, Invoice, approvalApi, INVOICE_STATUSES, settingsApi, Settings } from '@/lib/api';
import { API_BASE_URL, getTenantId } from '@/lib/api/_base';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { ApprovalActionButtons } from '@/components/approvals/ApprovalActionButtons';
import { CurrencyDisplay } from '@/components/ui/currency-display';
import { ApprovalHistoryEntry } from '@/types';
import { canEditInvoice, canEditInvoicePayment } from '@/utils/auth';
import { ProfessionalButton } from '@/components/ui/professional-button';
import { ShareButton } from '@/components/sharing/ShareButton';
import { SendInvoiceDialog } from '@/components/invoices/SendInvoiceDialog';

async function fetchInvoicePreviewHtml(id: number): Promise<string> {
  const tenantId = getTenantId();
  const headers: Record<string, string> = {};
  if (tenantId) headers['X-Tenant-ID'] = tenantId;
  const res = await fetch(`${API_BASE_URL}/invoices/${id}/preview`, {
    headers,
    credentials: 'include',
  });
  if (!res.ok) throw new Error(`Preview fetch failed: ${res.status}`);
  return res.text();
}

export default function ViewInvoice() {
  const { t } = useTranslation();
  const { id } = useParams();
  const navigate = useNavigate();
  const [invoice, setInvoice] = useState<Invoice | null>(null);
  const [loading, setLoading] = useState(true);
  const [approval, setApproval] = useState<ApprovalHistoryEntry | null>(null);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [showLivePreviewModal, setShowLivePreviewModal] = useState(false);
  const [previewHtml, setPreviewHtml] = useState<string>('');
  const [livePreviewLoading, setLivePreviewLoading] = useState(false);

  useEffect(() => {
    const load = async () => {
      try {
        setLoading(true);
        if (!id) return;
        const inv = await invoiceApi.getInvoice(Number(id));
        setInvoice(inv);

        // Fetch settings for company information
        try {
          const settingsData = await settingsApi.getSettings();
          setSettings(settingsData);
        } catch (error) {
          console.error('Error fetching settings:', error);
        }

        // Try to fetch approval data for this invoice
        try {
          const historyResponse = await approvalApi.getInvoiceApprovalHistory(Number(id));
          console.log('Invoice approval history response:', historyResponse);

          if (inv.status === 'pending_approval') {
            // Get pending approval
            const pendingApproval = historyResponse.approval_history
              .filter((a: any) => a.status === 'pending')
              .sort((a: any, b: any) => new Date(b.submitted_at || b.timestamp).getTime() - new Date(a.submitted_at || a.timestamp).getTime())[0];

            if (pendingApproval) {
              console.log('Found pending approval:', pendingApproval);
              setApproval(pendingApproval);
            }
          } else {
            // Get most recent completed approval (approved or rejected)
            const completedApproval = historyResponse.approval_history
              ?.filter((a: any) => a.status === 'approved' || a.status === 'rejected')
              .sort((a: any, b: any) => new Date(b.decided_at || b.timestamp).getTime() - new Date(a.decided_at || a.timestamp).getTime())[0];

            if (completedApproval) {
              console.log('Found completed approval:', completedApproval);
              setApproval(completedApproval);
            }
          }
        } catch (error) {
          console.error('Error fetching approval history:', error);
          setApproval(null);
        }
      } catch (e: any) {
        toast.error(e?.message || t('invoices.errors.load_failed'));
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [id]);

  const handleApprovalAction = async (approvalId: number, action: 'approve' | 'reject', data?: any) => {
    try {
      if (action === 'approve') {
        await approvalApi.approveInvoice(approvalId, data?.notes || '');
        toast.success('Invoice approved successfully');
      } else {
        await approvalApi.rejectInvoice(approvalId, data?.rejection_reason || '', data?.notes || '');
        toast.success('Invoice rejected successfully');
      }
      navigate(0);
    } catch (error: any) {
      toast.error(error?.message || `Failed to ${action} invoice`);
      throw error;
    }
  };

  // Handle live preview functionality — fetches the server-rendered HTML template
  const handleLivePreview = async () => {
    if (!invoice) return;

    setLivePreviewLoading(true);
    setShowLivePreviewModal(true);

    try {
      const html = await fetchInvoicePreviewHtml(invoice.id);
      setPreviewHtml(html);
    } catch (error) {
      console.error("Failed to generate live preview:", error);
      toast.error("Failed to generate live preview");
      setShowLivePreviewModal(false);
    } finally {
      setLivePreviewLoading(false);
    }
  };
  // Handle trigger review functionality
  const handleTriggerReview = async () => {
    if (!invoice?.id) return;

    try {
      const addNotification = (window as any).addAINotification;
      addNotification?.('processing', 'Triggering Review', `The AI agent is starting the review for invoice #${invoice.number}...`);

      await invoiceApi.reReview(invoice.id);

      addNotification?.('success', 'Review Triggered', `Review successfully triggered for invoice #${invoice.number}.`);
      toast.success(t('invoices.review_triggered_success', { defaultValue: 'Review triggered successfully' }));

      // Refresh data
      const inv = await invoiceApi.getInvoice(invoice.id);
      setInvoice(inv);
    } catch (error: any) {
      toast.error(error?.message || 'Failed to trigger review');
    }
  };


  const reloadInvoice = async () => {
    if (!id) return;
    try {
      const inv = await invoiceApi.getInvoice(Number(id));
      setInvoice(inv);
    } catch (e) {
      console.error('Error reloading invoice:', e);
    }
  };

  const [unsubmitLoading, setUnsubmitLoading] = useState(false);
  const handleUnsubmit = async () => {
    try {
      setUnsubmitLoading(true);
      await approvalApi.unsubmitInvoiceApproval(Number(id));
      toast.success('Approval request unsubmitted successfully');
      // Refresh the page
      navigate(0);
    } catch (error: any) {
      toast.error(error?.message || 'Failed to unsubmit approval request');
    } finally {
      setUnsubmitLoading(false);
    }
  };

  if (loading) {
    return (
      <>
        <div className="p-6">{t('common.loading')}</div>
      </>
    );
  }

  if (!invoice) {
    return (
      <>
        <div className="p-6 text-center">
          <p className="text-muted-foreground">{t('invoices.errors.not_found')}</p>
          <Button onClick={() => navigate('/invoices')} className="mt-4">
            {t('common.back_to_invoices')}
          </Button>
        </div>
      </>
    );
  }

  const subtotal = invoice.items?.reduce((sum, item) => sum + (item.quantity * item.price), 0) || 0;
  const discount = invoice.discount_type === 'percentage'
    ? (subtotal * (invoice.discount_value || 0)) / 100
    : (invoice.discount_value || 0);
  const total = Math.max(0, subtotal - discount);

  return (
    <>
      <div className="h-full space-y-6 fade-in">
        <PageHeader
          title={t('invoices.view_title', { defaultValue: 'View Invoice' })}
          description={t('invoices.view_description', { defaultValue: 'Review invoice details.' })}
          breadcrumbs={[
            { label: t('invoices.title'), href: '/invoices' },
            { label: invoice.number || 'Invoice', href: '#' }
          ]}
          actions={
            <div className="flex gap-2">
              <ShareButton recordType="invoice" recordId={invoice.id} />
              <SendInvoiceDialog invoice={invoice} settings={settings} onSent={reloadInvoice} />
              <ProfessionalButton
                variant="outline"
                onClick={handleLivePreview}
                leftIcon={<Eye className="h-4 w-4" />}
                loading={livePreviewLoading}
                disabled={!invoice}
              >
                {t('viewInvoice.livePreview', { defaultValue: 'Live Preview' })}
              </ProfessionalButton>
              {invoice.status === 'pending_approval' && approval && (
                <ApprovalActionButtons
                  approval={approval as any}
                  onAction={handleApprovalAction}
                />
              )}
              {invoice.status === 'pending_approval' && (
                <Button
                  onClick={handleUnsubmit}
                  variant="outline"
                  disabled={unsubmitLoading}
                  className="border-warning/40 text-warning hover:bg-warning/10"
                >
                  <AlertCircle className="mr-2 h-4 w-4" />
                  {t('invoices.unsubmit', { defaultValue: 'Unsubmit' })}
                </Button>
              )}
              {(!invoice.review_status || invoice.review_status === 'not_started' || invoice.review_status === 'failed' || invoice.review_status === 'rejected') && (
                <ProfessionalButton
                  variant="outline"
                  onClick={handleTriggerReview}
                  leftIcon={<RotateCcw className="h-4 w-4" />}
                >
                  {t('invoices.trigger_review', { defaultValue: 'Trigger Review' })}
                </ProfessionalButton>
              )}
              {invoice.status !== 'pending_approval' && (
                <Button
                  onClick={() => navigate(`/invoices/edit/${invoice.id}`)}
                  variant="outline"
                  disabled={!canEditInvoice(invoice) && !canEditInvoicePayment(invoice)}
                >
                  <Edit className="mr-2 h-4 w-4" />
                  {t('common.edit')}
                </Button>
              )}
            </div>
          }
        />

        {/* Show approval request message if exists */}
        {approval && approval.notes && (
          <ProfessionalCard className="slide-in border-primary/30 bg-primary/10">
            <CardHeader>
              <CardTitle className="text-primary">{t('invoices.approval_request_message', { defaultValue: 'Approval Request Message' })}</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-foreground">{approval.notes}</p>
            </CardContent>
          </ProfessionalCard>
        )}

        {/* Show approval/rejection information if invoice has been processed */}
        {approval && approval.status === 'approved' && (
          <ProfessionalCard className="slide-in border-success/30 bg-success/10">
            <CardHeader>
              <CardTitle className="text-success">{t('invoices.approval_information', { defaultValue: 'Approval Information' })}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <div>
                <span className="text-sm font-medium text-foreground">{t('invoices.approved_by', { defaultValue: 'Approved by' })}: </span>
                <span className="text-sm text-muted-foreground">
                  {approval.approved_by_username || approval.approver?.name || approval.approver?.email || 'Unknown'}
                </span>
              </div>
              {approval.decided_at && (
                <div>
                  <span className="text-sm font-medium text-foreground">{t('invoices.approved_at', { defaultValue: 'Approved at' })}: </span>
                  <span className="text-sm text-muted-foreground">{new Date(approval.decided_at).toLocaleString()}</span>
                </div>
              )}
              {approval.notes && (
                <div>
                  <span className="text-sm font-medium text-foreground">{t('invoices.approval_notes', { defaultValue: 'Notes' })}: </span>
                  <span className="text-sm text-muted-foreground">{approval.notes}</span>
                </div>
              )}
            </CardContent>
          </ProfessionalCard>
        )}

        {approval && approval.status === 'rejected' && (
          <ProfessionalCard className="slide-in border-destructive/30 bg-destructive/10">
            <CardHeader>
              <CardTitle className="text-destructive">{t('invoices.rejection_information', { defaultValue: 'Rejection Information' })}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <div>
                <span className="text-sm font-medium text-foreground">{t('invoices.rejected_by', { defaultValue: 'Rejected by' })}: </span>
                <span className="text-sm text-muted-foreground">
                  {approval.rejected_by_username || approval.approver?.name || approval.approver?.email || 'Unknown'}
                </span>
              </div>
              {approval.decided_at && (
                <div>
                  <span className="text-sm font-medium text-foreground">{t('invoices.rejected_at', { defaultValue: 'Rejected at' })}: </span>
                  <span className="text-sm text-muted-foreground">{new Date(approval.decided_at).toLocaleString()}</span>
                </div>
              )}
              {approval.rejection_reason && (
                <div>
                  <span className="text-sm font-medium text-foreground">{t('invoices.rejection_reason', { defaultValue: 'Reason' })}: </span>
                  <span className="text-sm text-muted-foreground">{approval.rejection_reason}</span>
                </div>
              )}
              {approval.notes && (
                <div>
                  <span className="text-sm font-medium text-foreground">{t('invoices.rejection_notes', { defaultValue: 'Notes' })}: </span>
                  <span className="text-sm text-muted-foreground">{approval.notes}</span>
                </div>
              )}
            </CardContent>
          </ProfessionalCard>
        )}

        <ProfessionalCard className="slide-in">
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>{t('invoices.details')}</CardTitle>
              <Badge>{t(`invoices.status.${invoice.status}`)}</Badge>
            </div>
          </CardHeader>
          <CardContent className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="text-sm font-medium">{t('invoices.invoice_number')}</label>
              <Input value={invoice.number || ''} disabled={true} />
            </div>
            <div>
              <label className="text-sm font-medium">{t('invoices.client')}</label>
              <Input value={invoice.client_name || ''} disabled={true} />
            </div>
            <div>
              <label className="text-sm font-medium">{t('invoices.amount')}</label>
              <Input
                type="number"
                value={Number(invoice.amount || 0)}
                disabled={true}
              />
            </div>
            <div>
              <label className="text-sm font-medium">{t('invoices.currency')}</label>
              <CurrencySelector value={invoice.currency || 'USD'} disabled={true} onValueChange={() => { }} />
            </div>
            <div>
              <label className="text-sm font-medium">{t('invoices.date')}</label>
              <Popover>
                <PopoverTrigger asChild>
                  <Button variant="outline" className="w-full justify-start text-left font-normal" disabled={true}>
                    <CalendarIcon className="mr-2 h-4 w-4" />
                    {invoice.created_at ? format(new Date(invoice.created_at), 'PPP') : t('invoices.pick_date')}
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="w-auto p-0" align="start">
                  <Calendar
                    mode="single"
                    selected={invoice.created_at ? new Date(invoice.created_at) : undefined}
                    initialFocus
                  />
                </PopoverContent>
              </Popover>
            </div>
            <div>
              <label className="text-sm font-medium">{t('invoices.due_date')}</label>
              <Popover>
                <PopoverTrigger asChild>
                  <Button variant="outline" className="w-full justify-start text-left font-normal" disabled={true}>
                    <CalendarIcon className="mr-2 h-4 w-4" />
                    {invoice.due_date ? format(new Date(invoice.due_date), 'PPP') : t('invoices.pick_date')}
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="w-auto p-0" align="start">
                  <Calendar
                    mode="single"
                    selected={invoice.due_date ? new Date(invoice.due_date) : undefined}
                    initialFocus
                  />
                </PopoverContent>
              </Popover>
            </div>
            <div>
              <label className="text-sm font-medium">{t('invoices.status_label')}</label>
              <Select value={invoice.status || 'draft'} disabled={true}>
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {INVOICE_STATUSES.map((status) => (
                    <SelectItem key={status} value={status}>
                      {t(`invoices.status.${status}`)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="text-sm font-medium">{t('invoices.paid_amount')}</label>
              <Input
                type="number"
                value={Number(invoice.paid_amount || 0)}
                disabled={true}
              />
            </div>
            <div>
              <label className="text-sm font-medium">{t('common.created_by')}</label>
              <Input value={invoice.created_by_username || invoice.created_by_email || t('common.unknown')} disabled={true} />
            </div>
            {invoice.notes && (
              <div className="sm:col-span-2">
                <label className="text-sm font-medium">{t('invoices.notes')}</label>
                <Textarea value={invoice.notes || ''} disabled={true} className="min-h-[100px] resize-none" />
              </div>
            )}
          </CardContent>
        </ProfessionalCard>

        {/* Invoice Items */}
        {invoice.items && invoice.items.length > 0 && (
          <ProfessionalCard className="slide-in">
            <CardHeader>
              <CardTitle>{t('invoices.items')}</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="rounded-md border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>{t('invoices.item_description')}</TableHead>
                      <TableHead className="text-right">{t('invoices.quantity')}</TableHead>
                      <TableHead className="text-right">{t('invoices.price')}</TableHead>
                      <TableHead className="text-right">{t('invoices.amount')}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {invoice.items.map((item, index) => (
                      <TableRow key={index}>
                        <TableCell>{item.description}</TableCell>
                        <TableCell className="text-right">{item.quantity}</TableCell>
                        <TableCell className="text-right">
                          <CurrencyDisplay amount={item.price} currency={invoice.currency} />
                        </TableCell>
                        <TableCell className="text-right">
                          <CurrencyDisplay amount={item.quantity * item.price} currency={invoice.currency} />
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>

              {/* Totals */}
              <div className="mt-6 space-y-2 text-right">
                <div className="flex justify-end gap-4">
                  <span className="font-medium">{t('invoices.subtotal')}:</span>
                  <span><CurrencyDisplay amount={subtotal} currency={invoice.currency} /></span>
                </div>
                {discount > 0 && (
                  <div className="flex justify-end gap-4">
                    <span className="font-medium">{t('invoices.discount')}:</span>
                    <span>-<CurrencyDisplay amount={discount} currency={invoice.currency} /></span>
                  </div>
                )}
                <div className="flex justify-end gap-4 border-t pt-2">
                  <span className="font-bold">{t('invoices.total')}:</span>
                  <span className="font-bold"><CurrencyDisplay amount={total} currency={invoice.currency} /></span>
                </div>
              </div>
            </CardContent>
          </ProfessionalCard>
        )}

        {/* Live Preview Modal */}
        <Dialog
          open={showLivePreviewModal}
          onOpenChange={(open) => {
            if (!open) {
              setShowLivePreviewModal(false);
              setPreviewHtml('');
              setLivePreviewLoading(false);
            }
          }}
        >
          <DialogContent className="max-w-4xl max-h-[90vh]">
            <DialogHeader>
              <DialogTitle>{t('viewInvoice.livePreviewTitle', { defaultValue: 'Live Invoice Preview' })}</DialogTitle>
            </DialogHeader>
            <div className="max-h-[70vh] overflow-auto">
              {livePreviewLoading ? (
                <div className="flex items-center justify-center h-64">
                  <Loader2 className="h-8 w-8 animate-spin mr-2" />
                  <p>{t('viewInvoice.generatingPreview', { defaultValue: 'Generating live preview...' })}</p>
                </div>
              ) : previewHtml ? (
                <iframe
                  title="Invoice preview"
                  sandbox=""
                  srcDoc={previewHtml}
                  className="w-full min-h-[1000px] border rounded"
                />
              ) : (
                <div className="flex items-center justify-center h-64">
                  <p className="text-muted-foreground">{t('viewInvoice.previewError', { defaultValue: 'Failed to load preview' })}</p>
                </div>
              )}
            </div>
            {previewHtml && (
              <div className="flex gap-2">
                <ProfessionalButton variant="outline" onClick={() => {
                  window.open(`${API_BASE_URL}/invoices/${invoice.id}/pdf`, '_blank');
                }}>
                  {t('viewInvoice.downloadPDF', { defaultValue: 'Download PDF' })}
                </ProfessionalButton>
              </div>
            )}
          </DialogContent>
        </Dialog>
      </div>
    </>
  );
}
