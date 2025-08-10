import { useEffect, useState } from 'react';
import { AppLayout } from '@/components/layout/AppLayout';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { CurrencySelector } from '@/components/ui/currency-selector';
import { Calendar } from '@/components/ui/calendar';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { CalendarIcon, Upload } from 'lucide-react';
import { format } from 'date-fns';
import { toast } from 'sonner';
import { expenseApi, Expense, linkApi } from '@/lib/api';

export default function ExpensesNew() {
  const categoryOptions = ['General', 'Travel', 'Meals', 'Software', 'Supplies'];
  const [form, setForm] = useState<Partial<Expense>>({
    amount: 0,
    currency: 'USD',
    expense_date: new Date().toISOString().split('T')[0],
    category: 'General',
    status: 'recorded',
  });
  const [files, setFiles] = useState<File[]>([]);
  const [saving, setSaving] = useState(false);
  const [invoiceOptions, setInvoiceOptions] = useState<Array<{ id: number; number: string; client_name: string }>>([]);

  useEffect(() => {
    (async () => {
      try { const invs = await linkApi.getInvoicesBasic(); setInvoiceOptions(invs); } catch {}
    })();
  }, []);

  const onSubmit = async () => {
    try {
      setSaving(true);
      if (!form.amount || !form.category) {
        toast.error('Amount and category are required');
        return;
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
      } as any;
      const created = await expenseApi.createExpense(payload);
      // Upload up to 5 files
      for (let i = 0; i < Math.min(files.length, 5); i++) {
        try { await expenseApi.uploadReceipt(created.id, files[i]); } catch (e) { console.error(e); }
      }
      toast.success('Expense created');
      window.history.back();
    } catch (e: any) {
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
          <p className="text-muted-foreground">Create a new expense and upload up to 5 attachments.</p>
        </div>

        <Card className="slide-in">
          <CardHeader>
            <CardTitle>Details</CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="text-sm">Amount</label>
              <Input type="number" value={Number(form.amount || 0)} onChange={e => setForm({ ...form, amount: Number(e.target.value) })} />
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
                    selected={form.expense_date ? new Date(form.expense_date as string) : undefined}
                    onSelect={(d) => {
                      if (d) {
                        const iso = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate())).toISOString().split('T')[0];
                        setForm({ ...form, expense_date: iso });
                      }
                    }}
                    initialFocus
                  />
                </PopoverContent>
              </Popover>
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
            <div className="sm:col-span-2">
              <label className="text-sm">Attachments (max 5)</label>
              <div className="flex items-center gap-3">
                <label className="inline-flex items-center gap-2 cursor-pointer">
                  <Upload className="w-4 h-4" />
                  <input multiple type="file" accept="application/pdf,image/jpeg,image/png" className="hidden" onChange={(e) => {
                    const selected = Array.from(e.target.files || []);
                    const combined = [...files, ...selected].slice(0, 5);
                    setFiles(combined);
                  }} />
                  Upload
                </label>
                <div className="text-sm text-muted-foreground">{files.length} file(s) selected</div>
              </div>
            </div>
          </CardContent>
        </Card>

        <div className="flex gap-2">
          <Button variant="outline" onClick={() => window.history.back()}>Cancel</Button>
          <Button onClick={onSubmit} disabled={saving}>{saving ? 'Saving...' : 'Create Expense'}</Button>
        </div>
      </div>
    </AppLayout>
  );
}


