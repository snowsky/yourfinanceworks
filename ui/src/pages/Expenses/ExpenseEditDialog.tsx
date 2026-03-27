import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Calendar } from '@/components/ui/calendar';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { CalendarIcon, AlertCircle, Package } from 'lucide-react';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Checkbox } from '@/components/ui/checkbox';
import { CurrencySelector } from '@/components/ui/currency-selector';
import { InventoryConsumptionForm } from '@/components/inventory/InventoryConsumptionForm';
import { format } from 'date-fns';
import type { Expense } from '@/lib/api';

interface ExpenseEditDialogProps {
  isEditOpen: boolean;
  setIsEditOpen: (v: boolean) => void;
  editExpense: Partial<Expense> & { id?: number };
  setEditExpense: (expense: Partial<Expense> & { id?: number }) => void;
  isEditInventoryConsumption: boolean;
  setIsEditInventoryConsumption: (v: boolean) => void;
  editConsumptionItems: any[];
  setEditConsumptionItems: (items: any[]) => void;
  setEditReceiptFile: (file: File | null) => void;
  onUpdate: () => Promise<void>;
  expenses: Expense[];
  hasAIExpenseFeature: boolean;
  categoryOptions: string[];
}

export function ExpenseEditDialog({
  isEditOpen,
  setIsEditOpen,
  editExpense,
  setEditExpense,
  isEditInventoryConsumption,
  setIsEditInventoryConsumption,
  editConsumptionItems,
  setEditConsumptionItems,
  setEditReceiptFile,
  onUpdate,
  expenses,
  hasAIExpenseFeature,
  categoryOptions,
}: ExpenseEditDialogProps) {
  const { t } = useTranslation();

  return (
    <Dialog open={isEditOpen} onOpenChange={setIsEditOpen}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t('expenses.edit_title')}</DialogTitle>
        </DialogHeader>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 p-4">
          <div>
            <label className="text-sm">{t('expenses.labels.amount')}</label>
            <Input
              type="number"
              value={Number(editExpense.amount || 0)}
              onChange={e => setEditExpense({ ...editExpense, amount: Number(e.target.value) })}
              disabled={isEditInventoryConsumption}
              placeholder={isEditInventoryConsumption ? t('expenses.calculated_from_items') : ""}
            />
          </div>
          <div>
            <label className="text-sm">{t('expenses.labels.currency')}</label>
            <CurrencySelector
              value={editExpense.currency || 'USD'}
              onValueChange={(v) => setEditExpense({ ...editExpense, currency: v })}
              placeholder={t('expenses.select_currency')}
            />
          </div>
          <div>
            <label className="text-sm">{t('expenses.labels.date')}</label>
            <Popover>
              <PopoverTrigger asChild>
                <Button variant="outline" className="w-full justify-start text-left font-normal">
                  <CalendarIcon className="mr-2 h-4 w-4" />
                  {editExpense.expense_date ? format(new Date((editExpense.expense_date as string) + 'T00:00:00'), 'PPP') : t('expenses.labels.pick_date')}
                </Button>
              </PopoverTrigger>
              <PopoverContent className="w-auto p-0" align="start">
                <Calendar
                  mode="single"
                  selected={editExpense.expense_date ? new Date((editExpense.expense_date as string) + 'T00:00:00') : undefined}
                  onSelect={(d) => {
                    if (d) {
                      const iso = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate())).toISOString().split('T')[0];
                      setEditExpense({ ...editExpense, expense_date: iso });
                    }
                  }}
                  initialFocus
                />
              </PopoverContent>
            </Popover>
          </div>
          <div>
            <label className="text-sm">{t('expenses.receipt_time', { defaultValue: 'Receipt Time (HH:MM)' })}</label>
            <Input
              type="time"
              value={editExpense.receipt_timestamp ? new Date(editExpense.receipt_timestamp as string).toISOString().substring(11, 16) : ''}
              onChange={(e) => {
                if (e.target.value && editExpense.expense_date) {
                  // Combine date with time
                  const timestamp = `${editExpense.expense_date}T${e.target.value}:00Z`;
                  setEditExpense({
                    ...editExpense,
                    receipt_timestamp: timestamp,
                    receipt_time_extracted: true
                  });
                } else {
                  setEditExpense({
                    ...editExpense,
                    receipt_timestamp: null,
                    receipt_time_extracted: false
                  });
                }
              }}
              placeholder="14:30"
            />
            {editExpense.receipt_time_extracted && (
              <p className="text-xs text-muted-foreground mt-1">
                🕐 Extracted from receipt
              </p>
            )}
          </div>
          <div>
            <label className="text-sm">{t('expenses.labels.category')}</label>
            <Select
              value={(editExpense.category as string) || 'General'}
              onValueChange={(v) => setEditExpense({ ...editExpense, category: v })}
            >
              <SelectTrigger className="w-full">
                <SelectValue placeholder={t('expenses.select_category') as string} />
              </SelectTrigger>
              <SelectContent>
                {categoryOptions.map((c) => (
                  <SelectItem key={c} value={c}>{t(`expenses.categories.${c}`)}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <label className="text-sm">{t('expenses.labels.vendor')}</label>
            <Input value={editExpense.vendor || ''} onChange={e => setEditExpense({ ...editExpense, vendor: e.target.value })} />
          </div>
          <div>
            <label className="text-sm">{t('expenses.labels.payment_method')}</label>
            <Input value={editExpense.payment_method || ''} onChange={e => setEditExpense({ ...editExpense, payment_method: e.target.value })} />
          </div>
          <div>
            <label className="text-sm">{t('expenses.labels.reference_number')}</label>
            <Input value={editExpense.reference_number || ''} onChange={e => setEditExpense({ ...editExpense, reference_number: e.target.value })} />
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
                  id="is-edit-inventory-consumption"
                  checked={isEditInventoryConsumption}
                  onCheckedChange={(checked) => setIsEditInventoryConsumption(checked as boolean)}
                />
                <label
                  htmlFor="is-edit-inventory-consumption"
                  className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
                >
                  {t('expenses.this_expense_is_for_consuming_inventory_items')}
                </label>
              </div>

              {isEditInventoryConsumption && (
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
                      onConsumptionItemsChange={setEditConsumptionItems}
                      currency={editExpense.currency || 'USD'}
                    />
                  </div>

                  {editConsumptionItems.length > 0 && (
                    <div className="bg-green-50 border border-green-200 rounded-lg p-3">
                      <div className="flex items-center gap-2 text-green-800">
                        <Package className="h-4 w-4" />
                        <span className="text-sm font-medium">
                          {t('expenses.ready_to_process', { count: editConsumptionItems.length })}
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
            <Input value={editExpense.notes || ''} onChange={e => setEditExpense({ ...editExpense, notes: e.target.value })} />
          </div>
          <div className="sm:col-span-2">
            <label className="text-sm">{t('expenses.labels.receipt')}</label>
            {!hasAIExpenseFeature && (
              <Alert className="mb-3 border-amber-200 bg-amber-50">
                <AlertCircle className="h-4 w-4 text-amber-600" />
                <AlertDescription className="text-amber-800 text-sm">
                  <strong>{t('common.note', { defaultValue: 'Note:' })}</strong> {t('expenses.ai_receipt_unavailable', { defaultValue: 'AI-powered receipt analysis is not available.' })}
                  Files will be uploaded as attachments only, without automatic data extraction.
                </AlertDescription>
              </Alert>
            )}
            <input
              type="file"
              accept="application/pdf,image/jpeg,image/png"
              onChange={(ev) => setEditReceiptFile(ev.target.files?.[0] || null)}
            />
            <div className="text-xs text-muted-foreground mt-1">
              Current: {editExpense?.id ? (expenses.find(x => x.id === editExpense.id)?.receipt_filename || 'None') : 'None'}
            </div>
          </div>
        </div>
        <div className="p-4 flex justify-end gap-2">
          <Button variant="outline" onClick={() => setIsEditOpen(false)}>{t('expenses.cancel')}</Button>
          <Button onClick={onUpdate}>{t('expenses.buttons.save')}</Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
