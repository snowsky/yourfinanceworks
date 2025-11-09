import { useEffect, useState, useRef, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { AppLayout } from '@/components/layout/AppLayout';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { CurrencySelector } from '@/components/ui/currency-selector';
import { Calendar } from '@/components/ui/calendar';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { CalendarIcon, Upload, Package } from 'lucide-react';
import { format } from 'date-fns';
import { toast } from 'sonner';
import { expenseApi, approvalApi, Expense, linkApi } from '@/lib/api';
import { EXPENSE_CATEGORY_OPTIONS } from '@/constants/expenses';
import { FileUpload, FileData } from '@/components/ui/file-upload';
import { InventoryPurchaseForm } from '@/components/inventory/InventoryPurchaseForm';
import { InventoryConsumptionForm } from '@/components/inventory/InventoryConsumptionForm';
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import { Users } from 'lucide-react';
import { ApprovalSubmissionDialog } from '@/components/expenses/ApprovalSubmissionDialog';
import { useTranslation } from 'react-i18next';

export default function ExpensesNew() {
  const { t } = useTranslation();
  const [searchParams] = useSearchParams();
  const categoryOptions = EXPENSE_CATEGORY_OPTIONS;

  // Get prefill values from URL parameters
  const prefillAmount = searchParams.get('amount');
  const prefillCurrency = searchParams.get('currency');
  const prefillInvoiceId = searchParams.get('invoiceId');

  const [form, setForm] = useState<Partial<Expense>>({
    amount: prefillAmount ? Number(prefillAmount) : 0,
    currency: prefillCurrency || 'USD',
    expense_date: new Date().toISOString().split('T')[0],
    category: 'General',
    status: 'recorded',
    invoice_id: prefillInvoiceId ? Number(prefillInvoiceId) : undefined,
  });
  const [files, setFiles] = useState<FileData[]>([]);
  const [saving, setSaving] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const isProcessingRef = useRef(false);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const [invoiceOptions, setInvoiceOptions] = useState<Array<{ id: number; number: string; client_name: string }>>([]);
  const [isInventoryPurchase, setIsInventoryPurchase] = useState(false);
  const [inventoryPurchaseItems, setInventoryPurchaseItems] = useState<any[]>([]);
  const [isInventoryConsumption, setIsInventoryConsumption] = useState(false);
  const [consumptionItems, setConsumptionItems] = useState<any[]>([]);
  const [submitForApproval, setSubmitForApproval] = useState(false);
  const [showApprovalDialog, setShowApprovalDialog] = useState(false);
  const [createdExpenseId, setCreatedExpenseId] = useState<number | null>(null);
  const [selectedApproverId, setSelectedApproverId] = useState<string>('');
  const [availableApprovers, setAvailableApprovers] = useState<Array<{ id: number; name: string; email: string }>>([]);

  useEffect(() => {
    (async () => {
      try { const invs = await linkApi.getInvoicesBasic(); setInvoiceOptions(invs); } catch { }
    })();
  }, []);

  useEffect(() => {
    const fetchApprovers = async () => {
      try {
        const response = await approvalApi.getApprovers();
        setAvailableApprovers(response);
      } catch (error) {
        console.error('Failed to fetch approvers:', error);
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

  // Ensure only one inventory option is selected
  useEffect(() => {
    if (isInventoryPurchase && isInventoryConsumption) {
      // If both are somehow selected, prefer consumption
      setIsInventoryPurchase(false);
    }
  }, [isInventoryPurchase, isInventoryConsumption]);

  const validateExpenseForm = () => {
    if ((!form.amount || Number(form.amount) === 0) && files.length === 0) {
      toast.error(t('expenses.amount_required'));
      return false;
    }
    if (!form.category) {
      toast.error(t('expenses.category_required'));
      return false;
    }

    // Validate consumption items
    if (isInventoryConsumption) {
      if (!consumptionItems || consumptionItems.length === 0) {
        toast.error(t('expenses.at_least_one_inventory_item_must_be_selected_for_consumption'));
        return false;
      }
      // Validate that all consumption items have valid quantities
      const invalidItems = consumptionItems.filter(item => !item.quantity || item.quantity <= 0);
      if (invalidItems.length > 0) {
        toast.error(t('expenses.all_inventory_consumption_items_must_have_quantity_greater_than_0'));
        return false;
      }
    }

    return true;
  };

  const createExpense = async () => {
    const addNotification = (window as any).addAINotification;
    if (files.length > 0) {
      addNotification?.('processing', 'Processing Expense Receipts', `Analyzing ${files.length} receipt files with AI...`);
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
      invoice_id: form.invoice_id ?? null,
      is_inventory_purchase: isInventoryPurchase,
      inventory_items: isInventoryPurchase ? inventoryPurchaseItems : undefined,
      is_inventory_consumption: isInventoryConsumption,
      consumption_items: isInventoryConsumption ? consumptionItems : undefined,
    } as any;

    const created = await expenseApi.createExpense({
      ...payload,
      imported_from_attachment: files.length > 0,
      analysis_status: files.length > 0 ? 'queued' : 'not_started'
    } as any);

    // Upload up to 10 files
    let uploadedCount = 0;
    for (let i = 0; i < Math.min(files.length, 10); i++) {
      try {
        await expenseApi.uploadReceipt(created.id, files[i].file);
        uploadedCount++;
      } catch (e) {
        console.error(e);
      }
    }

    if (files.length > 0) {
      if (uploadedCount === files.length) {
        addNotification?.('success', 'Expense Receipts Processed', `Successfully uploaded ${uploadedCount} receipt files. AI analysis in progress.`);
      } else {
        addNotification?.('error', 'Expense Upload Partial', `Uploaded ${uploadedCount} of ${files.length} receipt files.`);
      }
    }

    return created;
  };

  const handleApprovalSubmission = async (notes?: string) => {
    try {
      if (!createdExpenseId) return;

      const approverId = parseInt(selectedApproverId);
      await approvalApi.submitForApproval(createdExpenseId, approverId, notes);

      toast.success(t('expenses.expense_submitted_for_approval_successfully'));
      setShowApprovalDialog(false);
      window.history.back();
    } catch (e: any) {
      toast.error(e?.message || t('expenses.failed_to_submit_expense_for_approval'));
      throw e; // Re-throw to prevent dialog from closing
    }
  };

  const onSubmit = useCallback(async (event?: React.MouseEvent) => {
    // Prevent default behavior and stop propagation immediately
    if (event) {
      event.preventDefault();
      event.stopPropagation();
    }

    // Check if already processing - return early if so
    if (isProcessingRef.current || isSubmitting) {
      return;
    }

    // Immediately disable button and set processing state
    if (buttonRef.current) {
      buttonRef.current.disabled = true;
      buttonRef.current.style.pointerEvents = 'none';
      buttonRef.current.style.opacity = '0.5';
      buttonRef.current.style.cursor = 'not-allowed';
    }

    isProcessingRef.current = true;
    setIsSubmitting(true);
    setSaving(true);

    try {
      if (!validateExpenseForm()) {
        // Re-enable button on validation failure
        if (buttonRef.current) {
          buttonRef.current.disabled = false;
          buttonRef.current.style.pointerEvents = 'auto';
          buttonRef.current.style.opacity = '1';
          buttonRef.current.style.cursor = 'pointer';
        }
        isProcessingRef.current = false;
        setIsSubmitting(false);
        return;
      }

      const created = await createExpense();

      if (submitForApproval) {
        // Store the created expense ID and show approval dialog
        setCreatedExpenseId(created.id);
        setShowApprovalDialog(true);
        // Keep button disabled when showing approval dialog
      } else {
        toast.success(isInventoryConsumption ? t('expenses.consumption_expense_created_successfully') : t('expenses.expense_created'));
        // Small delay to show success message before navigating
        setTimeout(() => {
          window.history.back();
        }, 1000);
      }
    } catch (e: any) {
      const addNotification = (window as any).addAINotification;
      if (files.length > 0) {
        addNotification?.('error', 'Expense Processing Failed', `Failed to process expense receipts: ${e?.message || 'Unknown error'}`);
      }
      toast.error(e?.message || t('expenses.failed_to_create'));
      // Re-enable button on error
      if (buttonRef.current) {
        buttonRef.current.disabled = false;
        buttonRef.current.style.pointerEvents = 'auto';
        buttonRef.current.style.opacity = '1';
        buttonRef.current.style.cursor = 'pointer';
      }
      isProcessingRef.current = false;
      setIsSubmitting(false);
    } finally {
      setSaving(false);
    }
  }, [submitForApproval, isInventoryConsumption, files, isSubmitting]);

  // Reset button state when approval dialog is closed
  const handleApprovalDialogClose = (open: boolean) => {
    setShowApprovalDialog(open);
    if (!open) {
      // When dialog is closed (either submitted or cancelled), reset processing state and re-enable button
      if (buttonRef.current) {
        buttonRef.current.disabled = false;
        buttonRef.current.style.pointerEvents = 'auto';
        buttonRef.current.style.opacity = '1';
        buttonRef.current.style.cursor = 'pointer';
      }
      isProcessingRef.current = false;
      setIsSubmitting(false);
    }
  };

  // Cleanup effect to reset processing state
  useEffect(() => {
    return () => {
      isProcessingRef.current = false;
    };
  }, []);

  return (
    <AppLayout>
      <div className="h-full space-y-6 fade-in">
        <div>
          <h1 className="text-3xl font-bold">{t('expenses.new_title')}</h1>
          <p className="text-muted-foreground">{t('expenses.new_description')}</p>
        </div>

        <Card className="slide-in">
          <CardHeader>
            <CardTitle>{t('expenses.details')}</CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="text-sm">{t('expenses.labels.amount')}</label>
              <Input
                type="number"
                value={Number(form.amount || 0)}
                onChange={e => setForm({ ...form, amount: Number(e.target.value) })}
                disabled={isInventoryConsumption}
                placeholder={isInventoryConsumption ? t('expenses.calculated_from_items') : undefined}
              />
              {isInventoryConsumption && (
                <p className="text-xs text-muted-foreground mt-1">{t('expenses.amount_calculated_from_selected_inventory_items')}</p>
              )}
            </div>
            <div>
              <label className="text-sm">{t('expenses.labels.currency')}</label>
              <CurrencySelector value={form.currency || 'USD'} onValueChange={v => setForm({ ...form, currency: v })} />
            </div>
            <div>
              <label className="text-sm">{t('expenses.labels.date')}</label>
              <Popover>
                <PopoverTrigger asChild>
                  <Button variant="outline" className="w-full justify-start text-left font-normal">
                    <CalendarIcon className="mr-2 h-4 w-4" />
                    {form.expense_date ? format(new Date(form.expense_date as string), 'PPP') : t('expenses.labels.pick_date')}
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="w-auto p-0" align="start">
                  <Calendar
                    mode="single"
                    selected={form.expense_date ? new Date(form.expense_date) : undefined}
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
              <label className="text-sm">{t('expenses.labels.category')}</label>
              <Select value={(form.category as string) || 'General'} onValueChange={v => setForm({ ...form, category: v })}>
                <SelectTrigger className="w-full">
                  <SelectValue placeholder={t('expenses.select_category')} />
                </SelectTrigger>
                <SelectContent>
                  {categoryOptions.map(c => (<SelectItem key={c} value={c}>{c}</SelectItem>))}
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
              <label className="text-sm">{t('expenses.labels.notes')}</label>
              <Input value={form.notes || ''} onChange={e => setForm({ ...form, notes: e.target.value })} />
            </div>
          </CardContent>
        </Card>

        {/* Inventory Section */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Package className="h-5 w-5" />
              {t('expenses.inventory_integration')}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-3">
              <div className="flex items-center space-x-2">
                <Checkbox
                  id="is-inventory-purchase"
                  checked={isInventoryPurchase}
                  onCheckedChange={(checked) => {
                    setIsInventoryPurchase(checked as boolean);
                    if (checked) setIsInventoryConsumption(false); // Disable consumption when purchase is selected
                  }}
                />
                <label
                  htmlFor="is-inventory-purchase"
                  className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
                >
                  {t('expenses.this_expense_is_for_purchasing_inventory_items')}
                </label>
              </div>

              <div className="flex items-center space-x-2">
                <Checkbox
                  id="is-inventory-consumption"
                  checked={isInventoryConsumption}
                  onCheckedChange={(checked) => {
                    setIsInventoryConsumption(checked as boolean);
                    if (checked) setIsInventoryPurchase(false); // Disable purchase when consumption is selected
                  }}
                />
                <label
                  htmlFor="is-inventory-consumption"
                  className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
                >
                  {t('expenses.this_expense_is_for_consuming_inventory_items')}
                </label>
              </div>
            </div>

            {isInventoryPurchase && (
              <div className="space-y-4">
                <div className="bg-purple-50 border border-purple-200 rounded-lg p-4">
                  <div className="flex items-center gap-2 text-purple-800 mb-3">
                    <Package className="h-4 w-4" />
                    <span className="text-sm font-medium">{t('expenses.inventory_purchase_details')}</span>
                  </div>
                  <p className="text-sm text-purple-700 mb-4">
                    {t('expenses.select_the_inventory_items_you_purchased_with_this_expense')}
                  </p>

                  <InventoryPurchaseForm
                    onPurchaseItemsChange={setInventoryPurchaseItems}
                    currency={form.currency || 'USD'}
                    totalAmount={Number(form.amount || 0)}
                  />
                </div>

                {inventoryPurchaseItems.length > 0 && (
                  <div className="bg-green-50 border border-green-200 rounded-lg p-3">
                    <div className="flex items-center gap-2 text-green-800">
                      <Package className="h-4 w-4" />
                      <span className="text-sm font-medium">
                        {t('expenses.ready_to_process', { count: inventoryPurchaseItems.length })}
                      </span>
                    </div>
                  </div>
                )}
              </div>
            )}

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
          </CardContent>
        </Card>

        {/* File Upload Section */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Upload className="h-5 w-5" />
              {t('expenses.receipt_attachments')}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="sm:col-span-2">
              <FileUpload
                title={t('expenses.receipt_attachments_max_10')}
                maxFiles={10}
                allowedTypes={['application/pdf', 'image/jpeg', 'image/png']}
                selectedFiles={files}
                onFilesSelected={(newFiles) => {
                  const combined = [...files, ...newFiles].slice(0, 10);
                  setFiles(combined);
                }}
                onRemoveFile={(index) => setFiles(files.filter((_, i) => i !== index))}
                uploading={saving}
                enableCompression={true}
                enableBulkOperations={true}
              />
            </div>
          </CardContent>
        </Card>

        {/* Approval Submission Section */}
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
                {t('expenses.submit_this_expense_for_approval_after_creation')}
              </label>
            </div>
            {submitForApproval && (
              <div className="mt-3 space-y-3">
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
              </div>
            )}
          </CardContent>
        </Card>

        <div className="flex gap-2">
          <Button 
            variant="outline" 
            onClick={() => window.history.back()}
            disabled={saving || isSubmitting}
          >
            {t('common.cancel')}
          </Button>
          <Button
            ref={buttonRef}
            onClick={onSubmit}
            disabled={saving || isSubmitting || (submitForApproval && !selectedApproverId)}
            className={(saving || isSubmitting) ? 'opacity-50 cursor-not-allowed pointer-events-none' : ''}
          >
            {saving ? t('common.saving') : (submitForApproval ? t('expenses.create_and_submit_for_approval') : t('expenses.create_expense'))}
          </Button>
        </div>

        {/* Approval Submission Dialog */}
        <ApprovalSubmissionDialog
          open={showApprovalDialog}
          onOpenChange={handleApprovalDialogClose}
          onConfirm={handleApprovalSubmission}
          expenseAmount={Number(form.amount || 0)}
          currency={form.currency || 'USD'}
          category={form.category || 'General'}
          selectedApproverName={availableApprovers.find(a => a.id.toString() === selectedApproverId)?.name}
          loading={saving}
        />
      </div>
    </AppLayout>
  );
}


