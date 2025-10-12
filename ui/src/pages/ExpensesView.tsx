import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { AppLayout } from '@/components/layout/AppLayout';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { CurrencySelector } from '@/components/ui/currency-selector';
import { Calendar } from '@/components/ui/calendar';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { CalendarIcon, Upload, Package, Eye } from 'lucide-react';
import { format } from 'date-fns';
import { toast } from 'sonner';
import { expenseApi, approvalApi, Expense, ExpenseAttachmentMeta, linkApi } from '@/lib/api';
import { EXPENSE_CATEGORY_OPTIONS } from '@/constants/expenses';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Badge } from '@/components/ui/badge';
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import { InventoryConsumptionForm } from '@/components/inventory/InventoryConsumptionForm';
import { ApprovalActionButtons } from '@/components/approvals/ApprovalActionButtons';
import { ExpenseApproval } from '@/types';

export default function ExpensesView() {
  const { t } = useTranslation();
  const { id } = useParams();
  const navigate = useNavigate();
  const categoryOptions = EXPENSE_CATEGORY_OPTIONS;
  const [form, setForm] = useState<Partial<Expense>>({});
  const [loading, setLoading] = useState(true);
  const [attachments, setAttachments] = useState<ExpenseAttachmentMeta[]>([]);
  const [preview, setPreview] = useState<{ open: boolean; url: string | null; contentType: string | null; filename: string | null }>({ open: false, url: null, contentType: null, filename: null });
  const [invoiceOptions, setInvoiceOptions] = useState<Array<{ id: number; number: string; client_name: string }>>([]);
  const [approval, setApproval] = useState<ExpenseApproval | null>(null);

  // Inventory consumption state (read-only)
  const [isInventoryConsumption, setIsInventoryConsumption] = useState(false);
  const [consumptionItems, setConsumptionItems] = useState<any[]>([]);

  useEffect(() => {
    const load = async () => {
      try {
        setLoading(true);
        if (!id) return;
        const exp = await expenseApi.getExpense(Number(id));

        setForm(exp);

        // Initialize consumption state from existing expense data
        const isConsumption = !!(exp as any).is_inventory_consumption;
        const consumptionItemsData = (exp as any).consumption_items || [];
        setIsInventoryConsumption(isConsumption);
        setConsumptionItems(consumptionItemsData);

        const list = await expenseApi.listAttachments(Number(id));
        setAttachments(list);

        try {
          const invs = await linkApi.getInvoicesBasic();
          setInvoiceOptions(invs);
        } catch {}

        // Try to fetch approval data for this expense
        try {
          const pendingApprovals = await approvalApi.getPendingApprovals();
          const expenseApproval = pendingApprovals.approvals?.find((a: ExpenseApproval) => a.expense_id === Number(id));
          setApproval(expenseApproval || null);
        } catch {
          setApproval(null);
        }
      } catch (e: any) {
        toast.error(e?.message || t('expenses.failed_to_load', { defaultValue: 'Failed to load expense' }));
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [id]);


  // Calculate amount from consumption items
  useEffect(() => {
    if (isInventoryConsumption && consumptionItems.length > 0) {
      const total = consumptionItems.reduce((sum, item) => sum + (item.quantity * (item.unit_cost || 0)), 0);
      setForm(prev => ({ ...prev, amount: total }));
    }
  }, [consumptionItems, isInventoryConsumption]);

  const handleApprovalAction = async (approvalId: number, action: 'approve' | 'reject', data?: any) => {
    try {
      if (action === 'approve') {
        await approvalApi.approveExpense(approvalId, data?.notes || '');
        toast.success('Expense approved successfully');
      } else {
        await approvalApi.rejectExpense(approvalId, data?.rejection_reason || '', data?.notes || '');
        toast.success('Expense rejected successfully');
      }
      // Refresh the page to show updated status
      navigate(0);
    } catch (error: any) {
      toast.error(error?.message || `Failed to ${action} expense`);
      throw error;
    }
  };




  if (loading) {
    return (
      <AppLayout>
        <div className="p-6">{t('common.loading')}</div>
      </AppLayout>
    );
  }

  return (
    <AppLayout>
      <div className="h-full space-y-6 fade-in">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-3xl font-bold">{t('expenses.view_title', { defaultValue: 'View Expense' })}</h1>
            <p className="text-muted-foreground">{t('expenses.view_description', { defaultValue: 'Review expense details and take approval actions.' })}</p>
          </div>
          {approval && (
            <div className="flex-shrink-0">
              <ApprovalActionButtons
                approval={approval}
                onAction={handleApprovalAction}
              />
            </div>
          )}
        </div>

        <Card className="slide-in">
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>{t('expenses.details')}</CardTitle>
              {((form as any)?.analysis_status === 'pending' || (form as any)?.analysis_status === 'queued' || (form as any)?.analysis_status === 'failed') && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={async () => {
                    try {
                      const addNotification = (window as any).addAINotification;
                      addNotification?.('processing', 'Reprocessing Expense', `Re-analyzing expense receipts with AI...`);
                      
                      await expenseApi.reprocessExpense(Number(id));
                      
                      addNotification?.('success', 'Expense Reprocessed', `Successfully reprocessed expense receipts.`);
                      toast.success(t('expenses.reprocessing_started'));
                      // Refresh the expense data
                      const exp = await expenseApi.getExpense(Number(id));
                      setForm(exp);
                    } catch (e: any) {
                      const addNotification = (window as any).addAINotification;
                      addNotification?.('error', 'Expense Reprocessing Failed', `Failed to reprocess expense: ${e?.message || 'Unknown error'}`);
                      toast.error(e?.message || t('expenses.failed_to_reprocess'));
                    }
                  }}
                >
                  {t('expenses.process_again')}
                </Button>
              )}
            </div>
          </CardHeader>
          <CardContent className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="text-sm">{t('expenses.labels.amount')}</label>
              <Input
                type="number"
                value={Number(form.amount || 0)}
                disabled={true}
                placeholder={isInventoryConsumption ? "Calculated from items" : ""}
              />
            </div>
            <div>
              <label className="text-sm">{t('expenses.link_to_invoice')}</label>
              <Select value={form.invoice_id ? String(form.invoice_id) : undefined} disabled={true}>
                <SelectTrigger className="w-full">
                  <SelectValue placeholder={t('expenses.select_invoice')} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">{t('expenses.none')}</SelectItem>
                  {invoiceOptions.map(inv => (
                    <SelectItem key={inv.id} value={String(inv.id)}>{inv.number} — {inv.client_name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="text-sm">{t('expenses.labels.currency')}</label>
              <CurrencySelector value={form.currency || 'USD'} disabled={true} />
            </div>
            <div>
              <label className="text-sm">{t('expenses.labels.date')}</label>
              <Popover>
                <PopoverTrigger asChild>
                  <Button variant="outline" className="w-full justify-start text-left font-normal" disabled={true}>
                    <CalendarIcon className="mr-2 h-4 w-4" />
                    {form.expense_date ? format(new Date(form.expense_date + 'T00:00:00'), 'PPP') : t('expenses.labels.pick_date')}
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="w-auto p-0" align="start">
                  <Calendar
                    mode="single"
                    selected={form.expense_date ? new Date(form.expense_date + 'T00:00:00') : undefined}
                    initialFocus
                  />
                </PopoverContent>
              </Popover>
            </div>
            <div>
              <label className="text-sm">{t('expenses.labels.category')}</label>
              <Select value={(form.category as string) || 'General'} disabled={true}>
                <SelectTrigger className="w-full">
                  <SelectValue placeholder={t('common.select_category')} />
                </SelectTrigger>
                <SelectContent>
                  {categoryOptions.map(c => (<SelectItem key={c} value={c}>{c}</SelectItem>))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="text-sm">{t('expenses.labels.vendor')}</label>
              <Input value={form.vendor || ''} disabled={true} />
            </div>
            <div>
              <label className="text-sm">{t('expenses.labels.payment_method')}</label>
              <Input value={form.payment_method || ''} disabled={true} />
            </div>
            <div>
              <label className="text-sm">{t('expenses.labels.reference_number')}</label>
              <Input value={form.reference_number || ''} disabled={true} />
            </div>
            <div className="sm:col-span-2">
              <label className="text-sm">{t('common.labels')}</label>
              <div className="flex flex-wrap items-center gap-2 mt-1">
                {((form as any).labels || []).slice(0, 10).map((lab: string, idx: number) => (
                  <Badge key={`lab-${idx}`} variant="secondary" className="text-xs">
                    {lab}
                  </Badge>
                ))}
              </div>
            </div>
            
            {/* Inventory Consumption Section */}
            <div className="sm:col-span-2">
              <div className="space-y-3 p-4 border rounded-lg bg-gray-50">
                <div className="flex items-center gap-2">
                  <Package className="h-4 w-4" />
                  <span className="text-sm font-medium">Inventory Integration</span>
                </div>
                
                <div className="flex items-center space-x-2">
                  <Checkbox
                    id="is-inventory-consumption"
                    checked={isInventoryConsumption}
                    disabled={true}
                  />
                  <label
                    htmlFor="is-inventory-consumption"
                    className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
                  >
                    This expense is for consuming inventory items
                  </label>
                </div>

                {isInventoryConsumption && (
                  <div className="space-y-4">
                    <div className="bg-orange-50 border border-orange-200 rounded-lg p-4">
                      <div className="flex items-center gap-2 text-orange-800 mb-3">
                        <Package className="h-4 w-4" />
                        <span className="text-sm font-medium">Inventory Consumption Details</span>
                      </div>
                      <p className="text-sm text-orange-700 mb-4">
                        Select the inventory items you consumed. The system will automatically reduce stock levels and calculate the expense amount.
                      </p>

                      <InventoryConsumptionForm
                        onConsumptionItemsChange={setConsumptionItems}
                        currency={form.currency || 'USD'}
                        initialConsumptionItems={consumptionItems}
                      />
                    </div>

                    {consumptionItems.length > 0 && (
                      <div className="bg-green-50 border border-green-200 rounded-lg p-3">
                        <div className="flex items-center gap-2 text-green-800">
                          <Package className="h-4 w-4" />
                          <span className="text-sm font-medium">
                            Ready to process: {consumptionItems.length} inventory items will be consumed
                          </span>
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>

            <div className="sm:col-span-2">
              <label className="text-sm">{t('expenses.labels.notes')}</label>
              <Input value={form.notes || ''} disabled={true} />
            </div>
            <div className="sm:col-span-2">
              <label className="text-sm">{t('expenses.max_attachments')}</label>
              {(form as any)?.analysis_status === 'done' && (
                <div className="text-xs text-muted-foreground mt-1">{t('expenses.attachments_cannot_delete', { defaultValue: 'Attachments cannot be deleted after analysis is completed.' })}</div>
              )}
              <div className="mt-3">
                <div className="text-sm font-medium mb-2">{t('expenses.existing_attachments', { defaultValue: 'Existing attachments' })}</div>
                {attachments.length === 0 ? (
                  <div className="text-sm text-muted-foreground">{t('expenses.none')}</div>
                ) : (
                  <ul className="space-y-2">
                    {attachments.map(att => (
                      <li key={att.id} className="flex items-center justify-between gap-3 border rounded p-2">
                        <div className="truncate text-sm">
                          {att.filename}
                        </div>
                        <Button variant="outline" size="sm" onClick={async () => {
                          const blob = await expenseApi.downloadAttachmentBlob(Number(id), att.id);
                          const url = URL.createObjectURL(blob);
                          setPreview({ open: true, url, contentType: att.content_type || null, filename: att.filename || null });
                        }}>
                          <Eye className="w-4 h-4 mr-2" />
                          View
                        </Button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          </CardContent>
        </Card>


        <div className="flex gap-2">
          <Button variant="outline" onClick={() => navigate(-1)}>{t('common.back', { defaultValue: 'Back' })}</Button>
        </div>

        {/* File inline preview dialog */}
        <Dialog open={preview.open} onOpenChange={(o) => {
          if (!o && preview.url) URL.revokeObjectURL(preview.url);
          setPreview(prev => ({ open: o, url: o ? prev.url : null, contentType: o ? prev.contentType : null, filename: o ? prev.filename : null }));
        }}>
          <DialogContent className="max-w-4xl">
            <DialogHeader>
              <DialogTitle>{preview.filename || t('expenses.preview')}</DialogTitle>
            </DialogHeader>
            <div className="max-h-[70vh] overflow-auto">
              {preview.url && (preview.contentType || '').startsWith('image/') && (
                <img src={preview.url} alt={preview.filename || t('expenses.attachment', { defaultValue: 'attachment' })} className="max-w-full h-auto" />
              )}
              {preview.url && preview.contentType === 'application/pdf' && (
                <iframe src={preview.url} className="w-full h-[70vh]" title={t('expenses.pdf_preview', { defaultValue: 'PDF Preview' })} />
              )}
              {preview.url && preview.contentType && !((preview.contentType || '').startsWith('image/') || preview.contentType === 'application/pdf') && (
                <div className="text-sm text-muted-foreground">{t('expenses.cannot_preview', { defaultValue: 'This file type cannot be previewed. Please download instead.' })}</div>
              )}
            </div>
            <div className="flex gap-2">
              {preview.url && (
                <Button variant="outline" onClick={() => {
                  if (!preview.url) return;
                  const a = document.createElement('a');
                  a.href = preview.url;
                  a.download = preview.filename || 'attachment';
                  document.body.appendChild(a);
                  a.click();
                  document.body.removeChild(a);
                }}>{t('expenses.download')}</Button>
              )}
            </div>
          </DialogContent>
        </Dialog>
      </div>
    </AppLayout>
  );
}


