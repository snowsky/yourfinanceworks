import { useEffect, useState } from 'react';
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

export default function ExpensesNew() {
  const categoryOptions = EXPENSE_CATEGORY_OPTIONS;
  const [form, setForm] = useState<Partial<Expense>>({
    amount: 0,
    currency: 'USD',
    expense_date: new Date().toISOString().split('T')[0],
    category: 'General',
    status: 'recorded',
  });
  const [files, setFiles] = useState<FileData[]>([]);
  const [saving, setSaving] = useState(false);
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
      try { const invs = await linkApi.getInvoicesBasic(); setInvoiceOptions(invs); } catch {}
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
      toast.error('Amount is required unless importing from files');
      return false;
    }
    if (!form.category) {
      toast.error('Category is required');
      return false;
    }

    // Validate consumption items
    if (isInventoryConsumption) {
      if (!consumptionItems || consumptionItems.length === 0) {
        toast.error('At least one inventory item must be selected for consumption');
        return false;
      }
      // Validate that all consumption items have valid quantities
      const invalidItems = consumptionItems.filter(item => !item.quantity || item.quantity <= 0);
      if (invalidItems.length > 0) {
        toast.error('All inventory consumption items must have a quantity greater than 0');
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

      toast.success('Expense submitted for approval successfully');
      setShowApprovalDialog(false);
      window.history.back();
    } catch (e: any) {
      toast.error(e?.message || 'Failed to submit expense for approval');
      throw e; // Re-throw to prevent dialog from closing
    }
  };

  const onSubmit = async () => {
    try {
      setSaving(true);
      
      if (!validateExpenseForm()) {
        return;
      }

      const created = await createExpense();
      
      if (submitForApproval) {
        // Store the created expense ID and show approval dialog
        setCreatedExpenseId(created.id);
        setShowApprovalDialog(true);
      } else {
        toast.success(isInventoryConsumption ? 'Consumption expense created successfully' : 'Expense created');
        window.history.back();
      }
    } catch (e: any) {
      const addNotification = (window as any).addAINotification;
      if (files.length > 0) {
        addNotification?.('error', 'Expense Processing Failed', `Failed to process expense receipts: ${e?.message || 'Unknown error'}`);
      }
      toast.error(e?.message || 'Failed to create expense');
    } finally {
      setSaving(false);
    }
  };

  return (
    <AppLayout>
      <div className="h-full space-y-6 fade-in">
        <div>
          <h1 className="text-3xl font-bold">New Expense</h1>
          <p className="text-muted-foreground">Create a new expense with optional inventory integration and upload up to 5 attachments.</p>
        </div>

        <Card className="slide-in">
          <CardHeader>
            <CardTitle>Details</CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="text-sm">Amount</label>
              <Input
                type="number"
                value={Number(form.amount || 0)}
                onChange={e => setForm({ ...form, amount: Number(e.target.value) })}
                disabled={isInventoryConsumption}
                placeholder={isInventoryConsumption ? "Calculated from items" : undefined}
              />
              {isInventoryConsumption && (
                <p className="text-xs text-muted-foreground mt-1">Amount calculated from selected inventory items</p>
              )}
            </div>
            <div>
              <label className="text-sm">Currency</label>
              <CurrencySelector value={form.currency || 'USD'} onValueChange={v => setForm({ ...form, currency: v })} />
            </div>
            <div>
              <label className="text-sm">Date</label>
              <Popover>
                <PopoverTrigger asChild>
                  <Button variant="outline" className="w-full justify-start text-left font-normal">
                    <CalendarIcon className="mr-2 h-4 w-4" />
                    {form.expense_date ? format(new Date(form.expense_date as string), 'PPP') : 'Pick a date'}
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
              <label className="text-sm">Link to Invoice (optional)</label>
              <Select value={form.invoice_id ? String(form.invoice_id) : undefined} onValueChange={v => setForm({ ...form, invoice_id: v === 'none' ? undefined : Number(v) })}>
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Select invoice" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">None</SelectItem>
                  {invoiceOptions.map(inv => (
                    <SelectItem key={inv.id} value={String(inv.id)}>{inv.number} — {inv.client_name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="text-sm">Category</label>
              <Select value={(form.category as string) || 'General'} onValueChange={v => setForm({ ...form, category: v })}>
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Select category" />
                </SelectTrigger>
                <SelectContent>
                  {categoryOptions.map(c => (<SelectItem key={c} value={c}>{c}</SelectItem>))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="text-sm">Vendor</label>
              <Input value={form.vendor || ''} onChange={e => setForm({ ...form, vendor: e.target.value })} />
            </div>
            <div>
              <label className="text-sm">Payment method</label>
              <Input value={form.payment_method || ''} onChange={e => setForm({ ...form, payment_method: e.target.value })} />
            </div>
            <div>
              <label className="text-sm">Reference #</label>
              <Input value={form.reference_number || ''} onChange={e => setForm({ ...form, reference_number: e.target.value })} />
            </div>
            <div className="sm:col-span-2">
              <label className="text-sm">Notes</label>
              <Input value={form.notes || ''} onChange={e => setForm({ ...form, notes: e.target.value })} />
            </div>
          </CardContent>
        </Card>

        {/* Inventory Section */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Package className="h-5 w-5" />
              Inventory Integration
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
                  This expense is for purchasing inventory items
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
                  This expense is for consuming inventory items
                </label>
              </div>
            </div>

            {isInventoryPurchase && (
              <div className="space-y-4">
                <div className="bg-purple-50 border border-purple-200 rounded-lg p-4">
                  <div className="flex items-center gap-2 text-purple-800 mb-3">
                    <Package className="h-4 w-4" />
                    <span className="text-sm font-medium">Inventory Purchase Details</span>
                  </div>
                  <p className="text-sm text-purple-700 mb-4">
                    Select the inventory items you purchased with this expense. The system will automatically update stock levels when you save.
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
                        Ready to process: {inventoryPurchaseItems.length} inventory items will be added to stock
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
                    <span className="text-sm font-medium">Inventory Consumption Details</span>
                  </div>
                  <p className="text-sm text-orange-700 mb-4">
                    Select the inventory items you consumed. The system will automatically reduce stock levels and calculate the expense amount based on cost prices.
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
          </CardContent>
        </Card>

        {/* File Upload Section */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Upload className="h-5 w-5" />
              Receipt Attachments
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="sm:col-span-2">
              <FileUpload
                title="Receipt Attachments (max 10)"
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
            <CardTitle>Approval Workflow</CardTitle>
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
                Submit this expense for approval after creation
              </label>
            </div>
              {submitForApproval && (
                <div className="mt-3 space-y-3">
                  <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg">
                    <p className="text-sm text-blue-700">
                      This expense will be submitted for approval. You'll be able to add additional notes before final submission.
                    </p>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="approver-select" className="flex items-center gap-2 text-sm font-medium">
                      <Users className="h-4 w-4" />
                      Select Approver *
                    </Label>
                    <Select value={selectedApproverId} onValueChange={setSelectedApproverId}>
                      <SelectTrigger>
                        <SelectValue placeholder="Choose an approver" />
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
          <Button variant="outline" onClick={() => window.history.back()}>Cancel</Button>
          <Button onClick={onSubmit} disabled={saving || (submitForApproval && !selectedApproverId)}>
            {saving ? 'Saving...' : (submitForApproval ? 'Create & Submit for Approval' : 'Create Expense')}
          </Button>
        </div>

        {/* Approval Submission Dialog */}
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
      </div>
    </AppLayout>
  );
}


