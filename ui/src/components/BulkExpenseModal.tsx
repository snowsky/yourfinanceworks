import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { CurrencySelector } from '@/components/ui/currency-selector';
import { Calendar } from '@/components/ui/calendar';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { CalendarIcon, Plus, Trash2, Upload, X } from 'lucide-react';
import { format } from 'date-fns';
import { toast } from 'sonner';
import { expenseApi, Expense } from '@/lib/api';
import { EXPENSE_CATEGORY_OPTIONS } from '@/constants/expenses';

interface BulkExpenseModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess: () => void;
}

interface ExpenseFormData {
  amount: number;
  currency: string;
  expense_date: string;
  category: string;
  vendor?: string;
  payment_method?: string;
  reference_number?: string;
  notes?: string;
  files: File[];
}

const defaultExpense: ExpenseFormData = {
  amount: 0,
  currency: 'USD',
  expense_date: new Date().toISOString().split('T')[0],
  category: 'General',
  files: [],
};

export function BulkExpenseModal({ open, onOpenChange, onSuccess }: BulkExpenseModalProps) {
  const { t } = useTranslation();
  const [expenses, setExpenses] = useState<ExpenseFormData[]>([defaultExpense]);
  const [saving, setSaving] = useState(false);

  const addExpense = () => {
    if (expenses.length >= 10) {
      toast.error('Maximum 10 expenses allowed');
      return;
    }
    setExpenses([...expenses, { ...defaultExpense }]);
  };

  const removeExpense = (index: number) => {
    if (expenses.length <= 1) return;
    setExpenses(expenses.filter((_, i) => i !== index));
  };

  const updateExpense = (index: number, field: keyof ExpenseFormData, value: any) => {
    const updated = [...expenses];
    updated[index] = { ...updated[index], [field]: value };
    setExpenses(updated);
  };

  const handleSubmit = async () => {
    try {
      setSaving(true);

      // Validate all expenses
      for (let i = 0; i < expenses.length; i++) {
        const expense = expenses[i];
        if ((!expense.amount || expense.amount <= 0) && expense.files.length === 0) {
          toast.error(`Expense ${i + 1}: Amount or attachment is required`);
          return;
        }
        if (!expense.category) {
          toast.error(`Expense ${i + 1}: Category is required`);
          return;
        }
      }

      // Convert to API format
      const expensePayloads = expenses.map(expense => ({
        amount: Number(expense.amount),
        currency: expense.currency,
        expense_date: expense.expense_date,
        category: expense.category,
        vendor: expense.vendor,
        payment_method: expense.payment_method,
        reference_number: expense.reference_number,
        status: 'recorded',
        notes: expense.notes,
        imported_from_attachment: expense.files.length > 0,
      }));

      const createdExpenses = await expenseApi.bulkCreateExpenses(expensePayloads as any);

      // Upload attachments for each expense
      let uploadErrors = 0;
      for (let i = 0; i < createdExpenses.length; i++) {
        const expenseId = createdExpenses[i].id;
        const filesToUpload = expenses[i].files;

        for (const file of filesToUpload) {
          try {
            await expenseApi.uploadReceipt(expenseId, file);
          } catch (error) {
            console.error(`Failed to upload attachment for expense ${expenseId}:`, error);
            uploadErrors++;
          }
        }
      }

      if (uploadErrors > 0) {
        toast.warning(`Created ${expenses.length} expenses, but ${uploadErrors} attachment(s) failed to upload`);
      } else {
        toast.success(`Successfully created ${expenses.length} expenses`);
      }

      onSuccess();
      onOpenChange(false);
      setExpenses([defaultExpense]);
    } catch (e: any) {
      toast.error(e?.message || 'Failed to create expenses');
    } finally {
      setSaving(false);
    }
  };

  const formatDateToISO = (date: Date): string => {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Create Multiple Expenses</DialogTitle>
        </DialogHeader>

        <div className="space-y-6">
          {expenses.map((expense, index) => (
            <div key={index} className="border rounded-lg p-4 space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="font-medium">Expense {index + 1}</h3>
                {expenses.length > 1 && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => removeExpense(index)}
                  >
                    <Trash2 className="w-4 h-4" />
                  </Button>
                )}
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                <div>
                  <label className="text-sm font-medium">Amount *</label>
                  <Input
                    type="number"
                    value={expense.amount}
                    onChange={(e) => updateExpense(index, 'amount', Number(e.target.value))}
                    placeholder="0.00"
                  />
                </div>

                <div>
                  <label className="text-sm font-medium">Currency</label>
                  <CurrencySelector
                    value={expense.currency}
                    onValueChange={(value) => updateExpense(index, 'currency', value)}
                  />
                </div>

                <div>
                  <label className="text-sm font-medium">Date</label>
                  <Popover>
                    <PopoverTrigger asChild>
                      <Button variant="outline" className="w-full justify-start text-left font-normal">
                        <CalendarIcon className="mr-2 h-4 w-4" />
                        {expense.expense_date ? format(new Date(expense.expense_date), 'PPP') : 'Pick a date'}
                      </Button>
                    </PopoverTrigger>
                    <PopoverContent className="w-auto p-0" align="start">
                      <Calendar
                        mode="single"
                        selected={expense.expense_date ? new Date(expense.expense_date) : undefined}
                        onSelect={(date) => {
                          if (date) {
                            updateExpense(index, 'expense_date', formatDateToISO(date));
                          }
                        }}
                        initialFocus
                      />
                    </PopoverContent>
                  </Popover>
                </div>

                <div>
                  <label className="text-sm font-medium">Category *</label>
                  <Select
                    value={expense.category}
                    onValueChange={(value) => updateExpense(index, 'category', value)}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select category" />
                    </SelectTrigger>
                    <SelectContent>
                      {EXPENSE_CATEGORY_OPTIONS.map((category) => (
                        <SelectItem key={category} value={category}>
                          {category}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div>
                  <label className="text-sm font-medium">Vendor</label>
                  <Input
                    value={expense.vendor || ''}
                    onChange={(e) => updateExpense(index, 'vendor', e.target.value)}
                    placeholder="Vendor name"
                  />
                </div>

                <div>
                  <label className="text-sm font-medium">Payment Method</label>
                  <Input
                    value={expense.payment_method || ''}
                    onChange={(e) => updateExpense(index, 'payment_method', e.target.value)}
                    placeholder="Credit Card, Cash, etc."
                  />
                </div>

                <div className="sm:col-span-2 lg:col-span-3">
                  <label className="text-sm font-medium">Reference Number</label>
                  <Input
                    value={expense.reference_number || ''}
                    onChange={(e) => updateExpense(index, 'reference_number', e.target.value)}
                    placeholder="Reference or receipt number"
                  />
                </div>

                <div className="sm:col-span-2 lg:col-span-3">
                  <label className="text-sm font-medium">Notes</label>
                  <Input
                    value={expense.notes || ''}
                    onChange={(e) => updateExpense(index, 'notes', e.target.value)}
                    placeholder="Additional notes"
                  />
                </div>

                <div className="sm:col-span-2 lg:col-span-3">
                  <label className="text-sm font-medium">Attachments (Max 10)</label>
                  <div className="mt-2 space-y-2">
                    <div className="flex flex-wrap gap-2">
                      {expense.files.map((file, fileIndex) => (
                        <div key={fileIndex} className="flex items-center gap-2 bg-muted p-2 rounded-md text-sm">
                          <span className="max-w-[200px] truncate">{file.name}</span>
                          <button
                            type="button"
                            onClick={() => {
                              const newFiles = expense.files.filter((_, i) => i !== fileIndex);
                              updateExpense(index, 'files', newFiles);
                            }}
                            className="text-muted-foreground hover:text-destructive"
                          >
                            <X className="w-4 h-4" />
                          </button>
                        </div>
                      ))}
                    </div>
                    {expense.files.length < 10 && (
                      <div className="flex items-center gap-2">
                        <label className="cursor-pointer">
                          <div className="flex items-center gap-2 px-3 py-2 border rounded-md hover:bg-accent transition-colors">
                            <Upload className="w-4 h-4" />
                            <span className="text-sm font-medium">Upload Files</span>
                          </div>
                          <input
                            type="file"
                            className="hidden"
                            multiple
                            onChange={(e) => {
                              const selectedFiles = Array.from(e.target.files || []);
                              const newFiles = [...expense.files, ...selectedFiles].slice(0, 10);
                              updateExpense(index, 'files', newFiles);
                            }}
                          />
                        </label>
                        <p className="text-xs text-muted-foreground">
                          {expense.files.length}/10 files
                        </p>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          ))}

          {expenses.length < 10 && (
            <Button
              variant="outline"
              onClick={addExpense}
              className="w-full"
            >
              <Plus className="w-4 h-4 mr-2" />
              Add Another Expense ({expenses.length}/10)
            </Button>
          )}
        </div>

        <div className="flex justify-end gap-2 pt-4 border-t">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={saving}>
            {saving ? 'Creating...' : `Create ${expenses.length} Expense${expenses.length > 1 ? 's' : ''}`}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}