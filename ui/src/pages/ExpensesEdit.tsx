import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { AppLayout } from '@/components/layout/AppLayout';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { CurrencySelector } from '@/components/ui/currency-selector';
import { Calendar } from '@/components/ui/calendar';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { CalendarIcon, Upload, X } from 'lucide-react';
import { format } from 'date-fns';
import { toast } from 'sonner';
import { expenseApi, Expense, ExpenseAttachmentMeta, linkApi } from '@/lib/api';
import { EXPENSE_CATEGORY_OPTIONS } from '@/constants/expenses';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Badge } from '@/components/ui/badge';

export default function ExpensesEdit() {
  const { id } = useParams();
  const navigate = useNavigate();
  const categoryOptions = EXPENSE_CATEGORY_OPTIONS;
  const [form, setForm] = useState<Partial<Expense>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [newFiles, setNewFiles] = useState<File[]>([]);
  const [attachments, setAttachments] = useState<ExpenseAttachmentMeta[]>([]);
  const [pendingDelete, setPendingDelete] = useState<Set<number>>(new Set());
  const [preview, setPreview] = useState<{ open: boolean; url: string | null; contentType: string | null; filename: string | null }>({ open: false, url: null, contentType: null, filename: null });
  const [invoiceOptions, setInvoiceOptions] = useState<Array<{ id: number; number: string; client_name: string }>>([]);
  const [newLabel, setNewLabel] = useState<string>('');

  useEffect(() => {
    const load = async () => {
      try {
        setLoading(true);
        if (!id) return;
        const exp = await expenseApi.getExpense(Number(id));
        setForm(exp);
        const list = await expenseApi.listAttachments(Number(id));
        setAttachments(list);
        try { const invs = await linkApi.getInvoicesBasic(); setInvoiceOptions(invs); } catch {}
      } catch (e: any) {
        toast.error(e?.message || 'Failed to load expense');
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [id]);

  const onSave = async () => {
    try {
      if (!id) return;
      setSaving(true);
      const isAnalyzedDone = (form as any)?.analysis_status === 'done';
      if (isAnalyzedDone && pendingDelete.size > 0) {
        toast.error('Cannot delete attachments from an analyzed expense');
        return;
      }
      // Allow amount 0 if there will be at least one attachment after this save
      const existingCount = (attachments?.length || 0);
      const toDeleteCount = Array.from(pendingDelete).length;
      const effectiveExistingAfterSave = Math.max(0, existingCount - toDeleteCount);
      const hasNewFiles = newFiles.length > 0;
      const willHaveAnyAttachments = effectiveExistingAfterSave > 0 || hasNewFiles;
      if ((!form.amount || Number(form.amount) === 0) && !willHaveAnyAttachments) {
        toast.error('Amount is required unless at least one attachment is kept or newly added');
        return;
      }
      if (!form.category) {
        toast.error('Category is required');
        return;
      }
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
      } as any;
      await expenseApi.updateExpense(Number(id), payload);

      // First apply pending deletions (to satisfy max 5 rule before uploads)
      if (pendingDelete.size > 0) {
        await Promise.all(Array.from(pendingDelete.values()).map(attId => expenseApi.deleteAttachment(Number(id), attId).catch(() => {})));
      }

      // Refresh attachments and compute how many new files can be uploaded (cap 10)
      let currentList: ExpenseAttachmentMeta[] = [];
      try { currentList = await expenseApi.listAttachments(Number(id)); } catch {}
      const remainingSlots = Math.max(0, 10 - (currentList?.length || 0));

      for (let i = 0; i < Math.min(newFiles.length, remainingSlots); i++) {
        try { await expenseApi.uploadReceipt(Number(id), newFiles[i]); } catch (e) { console.error(e); }
      }
      toast.success('Expense updated');
      setNewLabel('');
      navigate('/expenses');
    } catch (e: any) {
      toast.error(e?.message || 'Failed to update expense');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <AppLayout>
        <div className="p-6">Loading...</div>
      </AppLayout>
    );
  }

  return (
    <AppLayout>
      <div className="h-full space-y-6 fade-in">
        <div>
          <h1 className="text-3xl font-bold">Edit Expense</h1>
          <p className="text-muted-foreground">Update this expense and manage attachments.</p>
        </div>

        <Card className="slide-in">
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>Details</CardTitle>
              {((form as any)?.analysis_status === 'pending' || (form as any)?.analysis_status === 'queued' || (form as any)?.analysis_status === 'failed') && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={async () => {
                    try {
                      await expenseApi.reprocessExpense(Number(id));
                      toast.success('Expense reprocessing started');
                      // Refresh the expense data
                      const exp = await expenseApi.getExpense(Number(id));
                      setForm(exp);
                    } catch (e: any) {
                      toast.error(e?.message || 'Failed to reprocess expense');
                    }
                  }}
                >
                  Process Again
                </Button>
              )}
            </div>
            {(form as any)?.analysis_status && (
              <div className="text-sm text-muted-foreground">
                Analysis Status: <span className="capitalize">{(form as any).analysis_status}</span>
                {(form as any)?.analysis_error && (
                  <span className="text-red-600 ml-2">({(form as any).analysis_error})</span>
                )}
              </div>
            )}
          </CardHeader>
          <CardContent className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="text-sm">Amount</label>
              <Input type="number" value={Number(form.amount || 0)} onChange={e => setForm({ ...form, amount: Number(e.target.value) })} />
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
              <label className="text-sm">Labels</label>
              <div className="flex flex-wrap items-center gap-2 mt-1">
                {((form as any).labels || []).slice(0, 10).map((lab: string, idx: number) => (
                  <Badge key={`lab-${idx}`} variant="secondary" className="text-xs">
                    {lab}
                    <button
                      className="ml-1 text-muted-foreground hover:text-foreground"
                      aria-label="Remove label"
                      onClick={() => {
                        try {
                          const next = ((form as any).labels || []).filter((l: string) => l !== lab);
                          setForm({ ...form, labels: next } as any);
                        } catch {}
                      }}
                    >
                      <X className="w-3 h-3" />
                    </button>
                  </Badge>
                ))}
                <Input
                  placeholder="Add label"
                  value={newLabel}
                  className="w-[160px] h-8"
                  onChange={(e) => setNewLabel(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      const raw = (newLabel || '').trim();
                      if (!raw) return;
                      const existing: string[] = ((form as any).labels || []);
                      if (existing.includes(raw)) { setNewLabel(''); return; }
                      if (existing.length >= 10) { toast.error('Maximum of 10 labels reached'); return; }
                      setForm({ ...form, labels: [...existing, raw] } as any);
                      setNewLabel('');
                    }
                  }}
                />
              </div>
            </div>
            <div className="sm:col-span-2">
              <label className="text-sm">Notes</label>
              <Input value={form.notes || ''} onChange={e => setForm({ ...form, notes: e.target.value })} />
            </div>
            <div className="sm:col-span-2">
              <label className="text-sm">Add Attachments (max 10)</label>
              {(form as any)?.analysis_status === 'done' && (
                <div className="text-xs text-muted-foreground mt-1">Attachments cannot be deleted after analysis is completed.</div>
              )}
              <div className="flex items-center gap-3">
                <label className="inline-flex items-center gap-2 cursor-pointer">
                  <Upload className="w-4 h-4" />
                  <input multiple type="file" accept="application/pdf,image/jpeg,image/png" className="hidden" onChange={(e) => {
                    const selected = Array.from(e.target.files || []);
                    const combined = [...newFiles, ...selected].slice(0, 10);
                    setNewFiles(combined);
                  }} />
                  Upload
                </label>
                <div className="text-sm text-muted-foreground">{newFiles.length} new file(s)</div>
              </div>
              <div className="mt-3">
                <div className="text-sm font-medium mb-2">Existing attachments</div>
                {attachments.length === 0 ? (
                  <div className="text-sm text-muted-foreground">None</div>
                ) : (
                  <ul className="space-y-2">
                    {attachments.map(att => (
                      <li key={att.id} className="flex items-center justify-between gap-3 border rounded p-2">
                        <div className={`truncate text-sm ${pendingDelete.has(att.id) ? 'line-through text-muted-foreground' : ''}`}>
                          {att.filename}
                          {pendingDelete.has(att.id) && (
                            <span className="ml-2 text-xs text-red-600">(will delete on save)</span>
                          )}
                        </div>
                        <div className="flex items-center gap-2">
                          <Button variant="outline" size="sm" onClick={async () => {
                            const blob = await expenseApi.downloadAttachmentBlob(Number(id), att.id);
                            const url = URL.createObjectURL(blob);
                            setPreview({ open: true, url, contentType: att.content_type || null, filename: att.filename || null });
                          }}>Preview</Button>
                          <Button
                            variant={pendingDelete.has(att.id) ? 'outline' : 'destructive'}
                            size="sm"
                            disabled={(form as any)?.analysis_status === 'done'}
                            onClick={() => {
                              setPendingDelete(prev => {
                                const next = new Set(prev);
                                if (next.has(att.id)) next.delete(att.id); else next.add(att.id);
                                return next;
                              });
                            }}
                          >
                            {pendingDelete.has(att.id) ? 'Undo' : 'Delete'}
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

        <div className="flex gap-2">
          <Button variant="outline" onClick={() => navigate('/expenses')}>Cancel</Button>
          <Button onClick={onSave} disabled={saving}>{saving ? 'Saving...' : 'Save Changes'}</Button>
        </div>
        {/* File inline preview dialog */}
        <Dialog open={preview.open} onOpenChange={(o) => {
          if (!o && preview.url) URL.revokeObjectURL(preview.url);
          setPreview(prev => ({ open: o, url: o ? prev.url : null, contentType: o ? prev.contentType : null, filename: o ? prev.filename : null }));
        }}>
          <DialogContent className="max-w-4xl">
            <DialogHeader>
              <DialogTitle>{preview.filename || 'Preview'}</DialogTitle>
            </DialogHeader>
            <div className="max-h-[70vh] overflow-auto">
              {preview.url && (preview.contentType || '').startsWith('image/') && (
                <img src={preview.url} alt={preview.filename || 'attachment'} className="max-w-full h-auto" />
              )}
              {preview.url && preview.contentType === 'application/pdf' && (
                <iframe src={preview.url} className="w-full h-[70vh]" title="PDF Preview" />
              )}
              {preview.url && preview.contentType && !((preview.contentType || '').startsWith('image/') || preview.contentType === 'application/pdf') && (
                <div className="text-sm text-muted-foreground">This file type cannot be previewed. Please download instead.</div>
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
                }}>Download</Button>
              )}
            </div>
          </DialogContent>
        </Dialog>
      </div>
    </AppLayout>
  );
}


