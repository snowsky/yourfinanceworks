import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { CurrencySelector } from '@/components/ui/currency-selector';
import { Calendar } from '@/components/ui/calendar';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { CalendarIcon, Upload, X, Package, Eye, AlertCircle } from 'lucide-react';
import { format } from 'date-fns';
import { toast } from 'sonner';
import { expenseApi, approvalApi, Expense, ExpenseAttachmentMeta, linkApi } from '@/lib/api';
import { EXPENSE_CATEGORY_OPTIONS } from '@/constants/expenses';
import { canEditExpense } from '@/utils/auth';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Badge } from '@/components/ui/badge';
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import { Users } from 'lucide-react';
import { InventoryConsumptionForm } from '@/components/inventory/InventoryConsumptionForm';
import { ApprovalSubmissionDialog } from '@/components/expenses/ApprovalSubmissionDialog';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { useFeatures } from '@/contexts/FeatureContext';

export default function ExpensesEdit() {
  const { t } = useTranslation();
  const { id } = useParams();
  const navigate = useNavigate();
  const categoryOptions = EXPENSE_CATEGORY_OPTIONS;
  const { isFeatureEnabled } = useFeatures();
  const hasAIExpenseFeature = isFeatureEnabled('ai_expense');
  const [form, setForm] = useState<Partial<Expense>>({ currency: 'USD' });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [newFiles, setNewFiles] = useState<File[]>([]);
  const [attachments, setAttachments] = useState<ExpenseAttachmentMeta[]>([]);
  const [pendingDelete, setPendingDelete] = useState<Set<number>>(new Set());
  const [preview, setPreview] = useState<{ open: boolean; url: string | null; contentType: string | null; filename: string | null }>({ open: false, url: null, contentType: null, filename: null });
  const [previewLoading, setPreviewLoading] = useState<number | null>(null);
  const [invoiceOptions, setInvoiceOptions] = useState<Array<{ id: number; number: string; client_name: string }>>([]);
  const [newLabel, setNewLabel] = useState<string>('');

  // Inventory consumption state
  const [isInventoryConsumption, setIsInventoryConsumption] = useState(false);
  const [consumptionItems, setConsumptionItems] = useState<any[]>([]);

  // Approval submission state
  const [submitForApproval, setSubmitForApproval] = useState(false);
  const [showApprovalDialog, setShowApprovalDialog] = useState(false);
  const [selectedApproverId, setSelectedApproverId] = useState<string>('');
  const [availableApprovers, setAvailableApprovers] = useState<Array<{ id: number; name: string; email: string }>>([]);
  const [approvalsNotLicensed, setApprovalsNotLicensed] = useState(false);
  const { isFeatureEnabled: isApprovalsEnabled } = useFeatures();

  useEffect(() => {
    const load = async () => {
      try {
        setLoading(true);
        if (!id) return;
        const exp = await expenseApi.getExpense(Number(id));

        // Check if user can edit this expense
        if (!canEditExpense(exp)) {
          toast.error('This expense cannot be edited while it is in the approval workflow');
          navigate('/expenses');
          return;
        }

        // Ensure currency has a value
        setForm({
          ...exp,
          currency: exp.currency || 'USD'
        });

        // Initialize consumption state from existing expense data
        const isConsumption = !!(exp as any).is_inventory_consumption;
        const consumptionItemsData = (exp as any).consumption_items || [];
        setIsInventoryConsumption(isConsumption);
        setConsumptionItems(consumptionItemsData);
        const list = await expenseApi.listAttachments(Number(id));
        setAttachments(list);
        try { const invs = await linkApi.getInvoicesBasic(); setInvoiceOptions(invs); } catch { }
      } catch (e: any) {
        toast.error(e?.message || t('expenses.failed_to_load', { defaultValue: 'Failed to load expense' }));
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [id]);

  useEffect(() => {
    const fetchApprovers = async () => {
      try {
        const response = await approvalApi.getApprovers();
        setAvailableApprovers(response);
        setApprovalsNotLicensed(false);
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : String(error);
        // Check if it's a license error (402 Payment Required)
        if (errorMessage.includes('not included in your current license') || errorMessage.includes('requires a valid license')) {
          setApprovalsNotLicensed(true);
          setAvailableApprovers([]);
        } else {
          console.error('Failed to fetch approvers:', error);
          setAvailableApprovers([]);
        }
      }
    };
    fetchApprovers();
  }, []);

  // Calculate amount from consumption items
  useEffect(() => {
    if (isInventoryConsumption && consumptionItems.length > 0) {
      const total = consumptionItems.reduce((sum, item) => sum + (item.quantity * (item.unit_cost || 0)), 0);
      setForm(prev => ({ ...prev, amount: total }));
    }
  }, [consumptionItems, isInventoryConsumption]);

  const validateExpenseForm = () => {
    // Allow deletion of attachments even from analyzed expenses (user already confirmed via dialog)
    // Allow amount 0 if there will be at least one attachment after this save
    const existingCount = (attachments?.length || 0);
    const toDeleteCount = Array.from(pendingDelete).length;
    const effectiveExistingAfterSave = Math.max(0, existingCount - toDeleteCount);
    const hasNewFiles = newFiles.length > 0;
    const willHaveAnyAttachments = effectiveExistingAfterSave > 0 || hasNewFiles;
    if ((!form.amount || Number(form.amount) === 0) && !willHaveAnyAttachments) {
      toast.error(t('expenses.amount_required_with_attachment', { defaultValue: 'Amount is required unless at least one attachment is kept or newly added' }));
      return false;
    }
    if (!form.category) {
      toast.error(t('expenses.category_required'));
      return false;
    }
    if (isInventoryConsumption && (!consumptionItems || consumptionItems.length === 0)) {
      toast.error('Inventory consumption must include at least one item');
      return false;
    }
    if (isInventoryConsumption && consumptionItems && consumptionItems.length > 0) {
      // Validate that all consumption items have valid quantities
      const invalidItems = consumptionItems.filter(item => !item.quantity || item.quantity <= 0);
      if (invalidItems.length > 0) {
        toast.error('All inventory consumption items must have a quantity greater than 0');
        return false;
      }
    }
    return true;
  };

  const updateExpense = async () => {
    // Ensure pending input label is included if user didn't press Enter
    let labelsFromForm: string[] = Array.isArray((form as any).labels) ? ((form as any).labels as string[]) : [];
    const pending = (newLabel || '').trim();
    if (pending) {
      const set = new Set(labelsFromForm);
      if (!set.has(pending) && set.size < 10) {
        set.add(pending);
      }
      labelsFromForm = Array.from(set).slice(0, 10);
    }

    const payload = {
      amount: Number(form.amount),
      currency: form.currency || 'USD',
      expense_date: form.expense_date,
      category: form.category,
      vendor: form.vendor,
      tax_rate: form.tax_rate,
      tax_amount: form.tax_amount,
      total_amount: form.total_amount,
      payment_method: form.payment_method,
      reference_number: form.reference_number,
      status: form.status || 'recorded',
      notes: form.notes,
      labels: labelsFromForm.length ? labelsFromForm : undefined,
      invoice_id: form.invoice_id ?? null,
      is_inventory_consumption: isInventoryConsumption,
      consumption_items: isInventoryConsumption ? consumptionItems : null,
      receipt_timestamp: (form as any).receipt_timestamp || null,
      receipt_time_extracted: (form as any).receipt_time_extracted || false,
    } as any;

    await expenseApi.updateExpense(Number(id), payload);

    // First apply pending deletions (to satisfy max 5 rule before uploads)
    if (pendingDelete.size > 0) {
      const deleteResults = await Promise.allSettled(
        Array.from(pendingDelete.values()).map(attId => expenseApi.deleteAttachment(Number(id), attId))
      );
      const failed = deleteResults.filter(r => r.status === 'rejected');
      if (failed.length > 0) {
        console.error('Failed to delete some attachments:', failed);
        toast.error(`Failed to delete ${failed.length} attachment(s)`);
      }
    }

    // Refresh attachments and compute how many new files can be uploaded (cap 10)
    let currentList: ExpenseAttachmentMeta[] = [];
    try { currentList = await expenseApi.listAttachments(Number(id)); } catch { }
    const remainingSlots = Math.max(0, 10 - (currentList?.length || 0));

    const addNotification = (window as any).addAINotification;
    if (newFiles.length > 0) {
      addNotification?.('processing', 'Processing Expense Receipts', `Analyzing ${Math.min(newFiles.length, remainingSlots)} receipt files with AI...`);
    }

    let uploadedCount = 0;
    for (let i = 0; i < Math.min(newFiles.length, remainingSlots); i++) {
      try {
        await expenseApi.uploadReceipt(Number(id), newFiles[i]);
        uploadedCount++;
      } catch (e) {
        console.error(e);
      }
    }

    if (newFiles.length > 0) {
      if (uploadedCount === Math.min(newFiles.length, remainingSlots)) {
        addNotification?.('success', 'Expense Receipts Processed', `Successfully uploaded ${uploadedCount} receipt files. AI analysis in progress.`);
      } else {
        addNotification?.('error', 'Expense Upload Partial', `Uploaded ${uploadedCount} of ${Math.min(newFiles.length, remainingSlots)} receipt files.`);
      }
    }
  };

  const handleApprovalSubmission = async (notes?: string) => {
    try {
      if (!id) return;

      const approverId = parseInt(selectedApproverId);
      await approvalApi.submitForApproval(Number(id), approverId, notes);

      toast.success('Expense submitted for approval successfully');
      setShowApprovalDialog(false);
      navigate('/expenses');
    } catch (e: any) {
      toast.error(e?.message || 'Failed to submit expense for approval');
      throw e; // Re-throw to prevent dialog from closing
    }
  };

  const onSave = async () => {
    try {
      if (!id) return;
      setSaving(true);

      if (!validateExpenseForm()) {
        return;
      }

      await updateExpense();

      if (submitForApproval) {
        // Show approval dialog
        setShowApprovalDialog(true);
      } else {
        toast.success(t('expenses.expense_updated'));
        setNewLabel('');
        navigate('/expenses');
      }
    } catch (e: any) {
      toast.error(e?.message || t('expenses.failed_to_update'));
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <>
        <div className="p-6">{t('common.loading')}</div>
      </>
    );
  }

  return (
    <>
      <div className="h-full space-y-6 fade-in">
        <div>
          <h1 className="text-3xl font-bold">{t('expenses.edit_title')}</h1>
          <p className="text-muted-foreground">{t('expenses.edit_description')}</p>
        </div>

        <Card className="slide-in">
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>{t('expenses.details')}</CardTitle>
              {((form as any)?.analysis_status === 'pending' || (form as any)?.analysis_status === 'queued' || (form as any)?.analysis_status === 'failed' || (form as any)?.analysis_status === 'done') && (
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
            {(form as any)?.analysis_status && (
              <div className="mt-3 space-y-2">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium">{t('expenses.analysis_status', { defaultValue: 'Analysis Status' })}:</span>
                  <Badge
                    variant={
                      (form as any).analysis_status === 'done' ? 'default' :
                        (form as any).analysis_status === 'failed' ? 'destructive' :
                          (form as any).analysis_status === 'pending' || (form as any).analysis_status === 'queued' ? 'secondary' :
                            'outline'
                    }
                    className="capitalize"
                  >
                    {(form as any).analysis_status === 'done' && '✓ '}
                    {(form as any).analysis_status === 'failed' && '✗ '}
                    {(form as any).analysis_status === 'pending' && '⏳ '}
                    {(form as any).analysis_status === 'queued' && '⏳ '}
                    {(form as any).analysis_status}
                  </Badge>
                </div>
                {(form as any)?.analysis_error && (form as any)?.analysis_status === 'failed' && (
                  <Alert className="border-red-200 bg-red-50">
                    <AlertCircle className="h-4 w-4 text-red-600" />
                    <AlertDescription className="text-red-800">
                      <details className="cursor-pointer">
                        <summary className="font-medium mb-1">{t('expenses.analysis_failed_click_details')}</summary>
                        <div className="mt-2 text-xs font-mono bg-red-100 p-2 rounded border border-red-200 overflow-x-auto">
                          {(form as any).analysis_error}
                        </div>
                      </details>
                    </AlertDescription>
                  </Alert>
                )}
              </div>
            )}
          </CardHeader>
          <CardContent className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="text-sm">{t('expenses.labels.amount')}</label>
              <Input
                type="number"
                value={Number(form.amount || 0)}
                onChange={e => setForm({ ...form, amount: Number(e.target.value) })}
                disabled={isInventoryConsumption}
                placeholder={isInventoryConsumption ? "Calculated from items" : ""}
              />
            </div>
            <div>
              <label className="text-sm">{t('expenses.link_to_invoice')}</label>
              <Select value={form.invoice_id ? String(form.invoice_id) : undefined} onValueChange={v => setForm({ ...form, invoice_id: v === 'none' ? undefined : Number(v) })}>
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
              <CurrencySelector
                value={form.currency || 'USD'}
                onValueChange={v => setForm({ ...form, currency: v })}
              />
            </div>
            <div>
              <label className="text-sm">{t('expenses.labels.date')}</label>
              <Popover>
                <PopoverTrigger asChild>
                  <Button variant="outline" className="w-full justify-start text-left font-normal">
                    <CalendarIcon className="mr-2 h-4 w-4" />
                    {form.expense_date ? format(new Date(form.expense_date + 'T00:00:00'), 'PPP') : t('expenses.labels.pick_date')}
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="w-auto p-0" align="start">
                  <Calendar
                    mode="single"
                    selected={form.expense_date ? new Date(form.expense_date + 'T00:00:00') : undefined}
                    onSelect={(d) => {
                      if (d) {
                        const year = d.getFullYear();
                        const month = String(d.getMonth() + 1).padStart(2, '0');
                        const day = String(d.getDate()).padStart(2, '0');
                        const iso = `${year}-${month}-${day}`;
                        setForm({ ...form, expense_date: iso });
                      }
                    }}
                    initialFocus
                  />
                </PopoverContent>
              </Popover>
            </div>
            <div>
              <label className="text-sm">Receipt Time (HH:MM)</label>
              <Input
                type="time"
                value={(form as any).receipt_timestamp ? new Date((form as any).receipt_timestamp as string).toISOString().substring(11, 16) : ''}
                onChange={(e) => {
                  if (e.target.value && form.expense_date) {
                    // Combine date with time
                    const timestamp = `${form.expense_date}T${e.target.value}:00Z`;
                    setForm({
                      ...form,
                      receipt_timestamp: timestamp,
                      receipt_time_extracted: true
                    } as any);
                  } else {
                    setForm({
                      ...form,
                      receipt_timestamp: null,
                      receipt_time_extracted: false
                    } as any);
                  }
                }}
                placeholder="14:30"
              />
              {(form as any).receipt_time_extracted && (
                <p className="text-xs text-muted-foreground mt-1">
                  🕐 Extracted from receipt
                </p>
              )}
            </div>
            <div>
              <label className="text-sm">{t('expenses.labels.category')}</label>
              <Select value={(form.category as string) || 'General'} onValueChange={v => setForm({ ...form, category: v })}>
                <SelectTrigger className="w-full">
                  <SelectValue placeholder={t('common.select_category')} />
                </SelectTrigger>
                <SelectContent>
                  {categoryOptions.map(c => (<SelectItem key={c} value={c}>{t(`expenses.categories.${c}`)}</SelectItem>))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="text-sm">{t('expenses.labels.vendor')}</label>
              <Input value={form.vendor || ''} onChange={e => setForm({ ...form, vendor: e.target.value })} />
            </div>
            <div>
              <label className="text-sm">{t('expenses.labels.payment_method')}</label>
              <Input value={form.payment_method || ''} onChange={e => setForm({ ...form, payment_method: e.target.value })} />
            </div>
            <div>
              <label className="text-sm">{t('expenses.labels.reference_number')}</label>
              <Input value={form.reference_number || ''} onChange={e => setForm({ ...form, reference_number: e.target.value })} />
            </div>
            <div className="sm:col-span-2">
              <label className="text-sm">{t('common.labels')}</label>
              <div className="flex flex-wrap items-center gap-2 mt-1">
                {((form as any).labels || []).slice(0, 10).map((lab: string, idx: number) => (
                  <Badge key={`lab-${idx}`} variant="secondary" className="text-xs">
                    {lab}
                    <button
                      className="ml-1 text-muted-foreground hover:text-foreground"
                      aria-label={t('common.remove')}
                      onClick={() => {
                        try {
                          const next = ((form as any).labels || []).filter((l: string) => l !== lab);
                          setForm({ ...form, labels: next } as any);
                        } catch { }
                      }}
                    >
                      <X className="w-3 h-3" />
                    </button>
                  </Badge>
                ))}
                <Input
                  placeholder={t('expenses.labels.label_placeholder')}
                  value={newLabel}
                  className="w-[160px] h-8"
                  onChange={(e) => setNewLabel(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      const raw = (newLabel || '').trim();
                      if (!raw) return;
                      const existing: string[] = ((form as any).labels || []);
                      if (existing.includes(raw)) { setNewLabel(''); return; }
                      if (existing.length >= 10) { toast.error(t('expenses.max_labels_reached')); return; }
                      setForm({ ...form, labels: [...existing, raw] } as any);
                      setNewLabel('');
                    }
                  }}
                />
              </div>
            </div>

            {/* Inventory Consumption Section */}
            <div className="sm:col-span-2">
              <div className="space-y-3 p-4 border rounded-lg bg-gray-50">
                <div className="flex items-center gap-2">
                  <Package className="h-4 w-4" />
                  <span className="text-sm font-medium">{t('expenses.inventory_integration')}</span>
                </div>

                <div className="flex items-center space-x-2">
                  <Checkbox
                    id="is-inventory-consumption"
                    checked={isInventoryConsumption}
                    onCheckedChange={(checked) => setIsInventoryConsumption(checked as boolean)}
                  />
                  <label
                    htmlFor="is-inventory-consumption"
                    className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
                  >
                    {t('expenses.this_expense_is_for_consuming_inventory_items')}
                  </label>
                </div>

                {isInventoryConsumption && (
                  <div className="space-y-4">
                    <div className="bg-orange-50 border border-orange-200 rounded-lg p-4">
                      <div className="flex items-center gap-2 text-orange-800 mb-3">
                        <Package className="h-4 w-4" />
                        <span className="text-sm font-medium">{t('expenses.inventory_consumption_details')}</span>
                      </div>
                      <p className="text-sm text-orange-700 mb-4">
                        {t('expenses.select_the_inventory_items_you_consumed')}
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
                            {t('expenses.ready_to_process', { count: consumptionItems.length })}
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
              <Input value={form.notes || ''} onChange={e => setForm({ ...form, notes: e.target.value })} />
            </div>
            <div className="sm:col-span-2">
              <label className="text-sm">{t('expenses.max_attachments')}</label>
              {(form as any)?.analysis_status === 'done' && (
                <div className="text-xs text-muted-foreground mt-1">{t('expenses.attachments_cannot_delete', { defaultValue: 'Attachments cannot be deleted after analysis is completed.' })}</div>
              )}
              {!hasAIExpenseFeature && (
                <Alert className="my-3 border-amber-200 bg-amber-50">
                  <AlertCircle className="h-4 w-4 text-amber-600" />
                  <AlertDescription className="text-amber-800">
                    <strong>Note:</strong> AI-powered receipt analysis is not available in your current plan.
                    Files will be uploaded as attachments only, without automatic data extraction.
                  </AlertDescription>
                </Alert>
              )}
              <div className="flex items-center gap-3">
                <label className="inline-flex items-center gap-2 cursor-pointer">
                  <Upload className="w-4 h-4" />
                  <input multiple type="file" accept="application/pdf,image/jpeg,image/png" className="hidden" onChange={(e) => {
                    const selected = Array.from(e.target.files || []);
                    const combined = [...newFiles, ...selected].slice(0, 10);
                    setNewFiles(combined);
                  }} />
                  {t('expenses.upload')}
                </label>
                <div className="text-sm text-muted-foreground">{newFiles.length} {t('expenses.new_files', { defaultValue: 'new file(s)' })}</div>
              </div>
              <div className="mt-3">
                <div className="text-sm font-medium mb-2">{t('expenses.existing_attachments', { defaultValue: 'Existing attachments' })}</div>
                {attachments.length === 0 ? (
                  <div className="text-sm text-muted-foreground">{t('expenses.none')}</div>
                ) : (
                  <ul className="space-y-2">
                    {attachments.map(att => (
                      <li key={att.id} className="flex items-center justify-between gap-3 border rounded p-2">
                        <div className={`truncate text-sm ${pendingDelete.has(att.id) ? 'line-through text-muted-foreground' : ''}`}>
                          {att.filename}
                          {pendingDelete.has(att.id) && (
                            <span className="ml-2 text-xs text-red-600">({t('expenses.will_delete_on_save', { defaultValue: 'will delete on save' })})</span>
                          )}
                        </div>
                        <div className="flex items-center gap-2">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={async () => {
                              setPreviewLoading(att.id);
                              try {
                                const { blob, contentType } = await expenseApi.downloadAttachmentBlob(Number(id), att.id);
                                const url = URL.createObjectURL(blob);
                                setPreview({ open: true, url, contentType: contentType || att.content_type || null, filename: att.filename || null });
                              } finally {
                                setPreviewLoading(null);
                              }
                            }}
                            disabled={previewLoading === att.id}
                          >
                            {previewLoading === att.id ? (
                              <>
                                <div className="w-4 h-4 mr-2 border-2 border-current border-t-transparent rounded-full animate-spin" />
                                {t('common.loading')}
                              </>
                            ) : (
                              <>
                                <Eye className="w-4 h-4 mr-2" />
                                {t('expenses.preview')}
                              </>
                            )}
                          </Button>
                          <Button
                            variant={pendingDelete.has(att.id) ? 'outline' : 'destructive'}
                            size="sm"
                            onClick={() => {
                              // Warn if expense is analyzed
                              if ((form as any)?.analysis_status === 'done' && !pendingDelete.has(att.id)) {
                                if (!confirm('This expense has been analyzed. Deleting attachments may affect the extracted data. Continue?')) {
                                  return;
                                }
                              }
                              setPendingDelete(prev => {
                                const next = new Set(prev);
                                if (next.has(att.id)) next.delete(att.id); else next.add(att.id);
                                return next;
                              });
                            }}
                          >
                            {pendingDelete.has(att.id) ? t('expenses.undo', { defaultValue: 'Undo' }) : t('common.delete')}
                          </Button>
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Approval Submission Section - Only show if expense is not already in approval workflow (allow rejected to be resubmitted) */}
        {form.status !== 'pending_approval' && form.status !== 'approved' && form.status !== 'resubmitted' && (
          <Card>
            <CardHeader>
              <CardTitle>{t('expenses.approval_workflow')}</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center space-x-2">
                <Checkbox
                  id="submit-for-approval"
                  checked={submitForApproval}
                  onCheckedChange={(checked) => setSubmitForApproval(checked as boolean)}
                />
                <label
                  htmlFor="submit-for-approval"
                  className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
                >
                  {t('expenses.submit_this_expense_for_approval_after_saving_changes')}
                </label>
              </div>
              {submitForApproval && (
                <div className="mt-3 space-y-3">
                  {approvalsNotLicensed ? (
                    <Alert className="border-amber-200 bg-amber-50">
                      <AlertCircle className="h-4 w-4 text-amber-600" />
                      <AlertDescription className="text-amber-800">
                        {t('common.feature_not_licensed', {
                          defaultValue: 'Approval workflows require a commercial license. Please upgrade your license to use this feature.'
                        })}
                      </AlertDescription>
                    </Alert>
                  ) : (
                    <>
                      <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg">
                        <p className="text-sm text-blue-700">
                          {t('expenses.this_expense_will_be_submitted_for_approval')}
                        </p>
                      </div>

                      <div className="space-y-2">
                        <Label htmlFor="approver-select" className="flex items-center gap-2 text-sm font-medium">
                          <Users className="h-4 w-4" />
                          {t('expenses.select_approver')} *
                        </Label>
                        <Select value={selectedApproverId} onValueChange={setSelectedApproverId}>
                          <SelectTrigger>
                            <SelectValue placeholder={t('expenses.choose_an_approver')} />
                          </SelectTrigger>
                          <SelectContent>
                            {availableApprovers.map((approver) => (
                              <SelectItem key={approver.id} value={approver.id.toString()}>
                                {approver.name} ({approver.email})
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                    </>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        )}

        <div className="flex gap-2">
          <Button variant="outline" onClick={() => navigate('/expenses')}>{t('common.cancel')}</Button>
          <Button onClick={onSave} disabled={saving || (submitForApproval && !selectedApproverId)}>
            {saving ? t('common.saving', { defaultValue: 'Saving...' }) :
              (submitForApproval ? t('expenses.save_and_submit_for_approval') : t('expenses.buttons.save_changes'))}
          </Button>
        </div>

        <ApprovalSubmissionDialog
          open={showApprovalDialog}
          onOpenChange={setShowApprovalDialog}
          onConfirm={handleApprovalSubmission}
          expenseAmount={Number(form.amount || 0)}
          currency={form.currency || 'USD'}
          category={form.category || 'General'}
          selectedApproverName={availableApprovers.find(a => a.id.toString() === selectedApproverId)?.name}
          loading={saving}
        />

        {/* File inline preview dialog */}
        <Dialog open={preview.open} onOpenChange={(o) => {
          if (!o && preview.url) URL.revokeObjectURL(preview.url);
          setPreview(prev => ({ open: o, url: o ? prev.url : null, contentType: o ? prev.contentType : null, filename: o ? prev.filename : null }));
        }}>
          <DialogContent className="max-w-4xl">
            <DialogHeader>
              <DialogTitle>{preview.filename || t('expenses.preview', { defaultValue: 'Preview' })}</DialogTitle>
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
    </>
  );
}


