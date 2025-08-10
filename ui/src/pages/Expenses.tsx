import { useEffect, useMemo, useState } from 'react';
import { AppLayout } from '@/components/layout/AppLayout';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { CurrencyDisplay } from '@/components/ui/currency-display';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Calendar } from '@/components/ui/calendar';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { CalendarIcon } from 'lucide-react';
import { format } from 'date-fns';
import { 
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog';
// removed duplicate useEffect import
import { Loader2, Plus, Search, Trash2, Upload, Pencil } from 'lucide-react';
import { Link } from 'react-router-dom';
import { toast } from 'sonner';
import { expenseApi, Expense, ExpenseAttachmentMeta } from '@/lib/api';
import { CurrencySelector } from '@/components/ui/currency-selector';

const defaultNewExpense: Partial<Expense> = {
  amount: 0,
  currency: 'USD',
  expense_date: new Date().toISOString().split('T')[0],
  category: 'General',
  status: 'recorded',
};

const Expenses = () => {
  const [expenses, setExpenses] = useState<Expense[]>([]);
  const categoryOptions = ['General', 'Travel', 'Meals', 'Software', 'Supplies'];
  const [loading, setLoading] = useState(true);
  const [categoryFilter, setCategoryFilter] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [newExpense, setNewExpense] = useState<Partial<Expense>>(defaultNewExpense);
  const [uploadingId, setUploadingId] = useState<number | null>(null);
  const [isEditOpen, setIsEditOpen] = useState(false);
  const [editExpense, setEditExpense] = useState<Partial<Expense> & { id?: number }>({});
  const [newReceiptFile, setNewReceiptFile] = useState<File | null>(null);
  const [editReceiptFile, setEditReceiptFile] = useState<File | null>(null);
  const [attachmentPreviewOpen, setAttachmentPreviewOpen] = useState<{ expenseId: number | null }>({ expenseId: null });
  const [attachments, setAttachments] = useState<Record<number, ExpenseAttachmentMeta[]>>({});
  const [preview, setPreview] = useState<{ open: boolean; url: string | null; contentType: string | null; filename: string | null }>({ open: false, url: null, contentType: null, filename: null });

  useEffect(() => {
    return () => {
      if (preview.url) URL.revokeObjectURL(preview.url);
    };
  }, [preview.url]);

  // Tenancy change trigger similar to Payments
  const [currentTenantId, setCurrentTenantId] = useState<string | null>(null);
  useEffect(() => {
    const getCurrentTenantId = () => {
      try {
        const selectedTenantId = localStorage.getItem('selected_tenant_id');
        if (selectedTenantId) return selectedTenantId;
        const userStr = localStorage.getItem('user');
        if (userStr) {
          const user = JSON.parse(userStr);
          return user?.tenant_id?.toString();
        }
      } catch {}
      return null;
    };
    const updateTenantId = () => {
      const tid = getCurrentTenantId();
      if (tid !== currentTenantId) setCurrentTenantId(tid);
    };
    updateTenantId();
    const onStorage = () => updateTenantId();
    window.addEventListener('storage', onStorage);
    return () => window.removeEventListener('storage', onStorage);
  }, [currentTenantId]);

  useEffect(() => {
    const fetchExpenses = async () => {
      setLoading(true);
      try {
        const data = await expenseApi.getExpenses(categoryFilter);
        setExpenses(data);
      } catch (e) {
        toast.error('Failed to load expenses');
      } finally {
        setLoading(false);
      }
    };
    fetchExpenses();
  }, [categoryFilter, currentTenantId]);

  const filteredExpenses = useMemo(() => {
    return (expenses || []).filter(e => {
      const s = searchQuery.toLowerCase();
      return (
        (e.vendor || '').toLowerCase().includes(s) ||
        (e.category || '').toLowerCase().includes(s) ||
        (e.notes || '').toLowerCase().includes(s)
      );
    });
  }, [expenses, searchQuery]);

  const openCreate = () => {
    setNewExpense(defaultNewExpense);
    setNewReceiptFile(null);
    setIsCreateOpen(true);
  };

  const handleCreate = async () => {
    try {
      if (!newExpense.amount || !newExpense.category) {
        toast.error('Amount and category are required');
        return;
      }
      const payload = {
        amount: Number(newExpense.amount),
        currency: newExpense.currency || 'USD',
        expense_date: newExpense.expense_date,
        category: newExpense.category,
        vendor: newExpense.vendor,
        tax_rate: newExpense.tax_rate,
        tax_amount: newExpense.tax_amount,
        total_amount: newExpense.total_amount,
        payment_method: newExpense.payment_method,
        reference_number: newExpense.reference_number,
        status: newExpense.status || 'recorded',
        notes: newExpense.notes,
      } as any;
      const created = await expenseApi.createExpense(payload);
      // Upload receipt if provided
      let createdWithReceipt = created;
      if (newReceiptFile) {
        try {
          setUploadingId(created.id);
          const uploadResp = await expenseApi.uploadReceipt(created.id, newReceiptFile);
          createdWithReceipt = { ...created, receipt_filename: uploadResp?.receipt_filename || created.receipt_filename } as Expense;
        } catch (e) {
          console.error('Receipt upload failed on create:', e);
          toast.error('Receipt upload failed');
        } finally {
          setUploadingId(null);
          setNewReceiptFile(null);
        }
      }
      setExpenses(prev => [createdWithReceipt, ...prev]);
      setIsCreateOpen(false);
      toast.success('Expense created');
    } catch (e: any) {
      toast.error(e?.message || 'Failed to create expense');
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await expenseApi.deleteExpense(id);
      setExpenses(prev => prev.filter(e => e.id !== id));
      toast.success('Expense deleted');
    } catch (e: any) {
      toast.error(e?.message || 'Failed to delete expense');
    }
  };

  const handleUpload = async (id: number, file: File) => {
    try {
      setUploadingId(id);
      await expenseApi.uploadReceipt(id, file);
      // Refresh list
      const data = await expenseApi.getExpenses(categoryFilter);
      setExpenses(data);
      toast.success('Receipt uploaded');
    } catch (e: any) {
      toast.error(e?.message || 'Failed to upload receipt');
    } finally {
      setUploadingId(null);
    }
  };

  const handleStartEdit = (e: Expense) => {
    setEditExpense({
      id: e.id,
      amount: e.amount,
      currency: e.currency || 'USD',
      expense_date: e.expense_date,
      category: e.category,
      vendor: e.vendor,
      tax_rate: e.tax_rate,
      tax_amount: e.tax_amount,
      total_amount: e.total_amount,
      payment_method: e.payment_method,
      reference_number: e.reference_number,
      status: e.status,
      notes: e.notes,
    });
    setIsEditOpen(true);
  };

  const handleUpdate = async () => {
    try {
      if (!editExpense.id) return;
      if (!editExpense.amount || !editExpense.category) {
        toast.error('Amount and category are required');
        return;
      }
      const payload = {
        amount: Number(editExpense.amount),
        currency: editExpense.currency || 'USD',
        expense_date: editExpense.expense_date,
        category: editExpense.category,
        vendor: editExpense.vendor,
        tax_rate: editExpense.tax_rate,
        tax_amount: editExpense.tax_amount,
        total_amount: editExpense.total_amount,
        payment_method: editExpense.payment_method,
        reference_number: editExpense.reference_number,
        status: editExpense.status || 'recorded',
        notes: editExpense.notes,
      } as any;
      const updated = await expenseApi.updateExpense(editExpense.id, payload);
      let finalUpdated = updated;
      if (editReceiptFile) {
        try {
          setUploadingId(updated.id);
          const uploadResp = await expenseApi.uploadReceipt(updated.id, editReceiptFile);
          finalUpdated = { ...updated, receipt_filename: uploadResp?.receipt_filename || updated.receipt_filename } as Expense;
        } catch (e) {
          console.error('Receipt upload failed on update:', e);
          toast.error('Receipt upload failed');
        } finally {
          setUploadingId(null);
          setEditReceiptFile(null);
        }
      }
      setExpenses(prev => prev.map(x => (x.id === finalUpdated.id ? finalUpdated : x)));
      setIsEditOpen(false);
      toast.success('Expense updated');
    } catch (e: any) {
      toast.error(e?.message || 'Failed to update expense');
    }
  };

  return (
    <AppLayout>
      <div className="h-full space-y-6 fade-in">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold">Expenses</h1>
            <p className="text-muted-foreground">Track and manage your business expenses.</p>
          </div>
          <Link to="/expenses/new">
            <Button>
              <Plus className="w-4 h-4 mr-2" /> New Expense
            </Button>
          </Link>
        </div>

        <Card className="slide-in">
          <CardHeader className="pb-3">
            <div className="flex flex-col sm:flex-row justify-between gap-4">
              <CardTitle>Expense List</CardTitle>
              <div className="flex flex-col sm:flex-row gap-4">
                <div className="relative">
                  <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                  <Input
                    placeholder="Search by vendor, category, or notes"
                    className="pl-8 w-full sm:w-[260px]"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                  />
                </div>
                <Select value={categoryFilter} onValueChange={setCategoryFilter}>
                  <SelectTrigger className="w-full sm:w-[180px]">
                    <SelectValue placeholder="Filter by category" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All categories</SelectItem>
                    {categoryOptions.map((c) => (
                      <SelectItem key={c} value={c}>{c}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <div className="rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Date</TableHead>
                    <TableHead>Category</TableHead>
                    <TableHead>Vendor</TableHead>
                    <TableHead>Amount</TableHead>
                    <TableHead>Total</TableHead>
                    <TableHead>Invoice</TableHead>
                    <TableHead>Receipt</TableHead>
                    <TableHead>Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {loading ? (
                    <TableRow>
                      <TableCell colSpan={7} className="h-24 text-center">
                        <div className="flex justify-center items-center">
                          <Loader2 className="h-6 w-6 animate-spin mr-2" />
                          Loading expenses
                        </div>
                      </TableCell>
                    </TableRow>
                  ) : (filteredExpenses || []).length > 0 ? (
                    (filteredExpenses || []).map((e) => (
                      <TableRow key={e.id}>
                        <TableCell>{e.expense_date ? new Date(e.expense_date).toLocaleDateString('en-US', { timeZone: 'UTC' }) : 'N/A'} UTC</TableCell>
                        <TableCell>{e.category}</TableCell>
                        <TableCell>{e.vendor || '—'}</TableCell>
                        <TableCell><CurrencyDisplay amount={e.amount || 0} currency={e.currency || 'USD'} /></TableCell>
                        <TableCell><CurrencyDisplay amount={e.total_amount || e.amount || 0} currency={e.currency || 'USD'} /></TableCell>
                        <TableCell>
                          {typeof e.invoice_id === 'number' ? (
                            <Link to={`/invoices/edit/${e.invoice_id}`} className="text-blue-600 hover:underline">#{e.invoice_id}</Link>
                          ) : (
                            <span className="text-muted-foreground">None</span>
                          )}
                        </TableCell>
                        <TableCell className="space-x-2">
                          <label className="inline-flex items-center gap-2 cursor-pointer">
                            <Upload className="w-4 h-4" />
                            <input
                              type="file"
                              accept="application/pdf,image/jpeg,image/png"
                              className="hidden"
                              onChange={async (ev) => {
                                const file = ev.target.files?.[0];
                                if (file) await handleUpload(e.id, file);
                                // refresh attachment list and auto-open preview
                                const list = await expenseApi.listAttachments(e.id);
                                setAttachments(prev => ({ ...prev, [e.id]: list }));
                                setAttachmentPreviewOpen({ expenseId: e.id });
                              }}
                            />
                            {uploadingId === e.id ? 'Uploading...' : 'Upload'}
                          </label>
                          <Button variant="ghost" size="sm" onClick={async () => {
                            const list = await expenseApi.listAttachments(e.id);
                            setAttachments(prev => ({ ...prev, [e.id]: list }));
                            setAttachmentPreviewOpen({ expenseId: e.id });
                          }}>
                            {Array.isArray(attachments[e.id]) ? `${attachments[e.id].length} file(s)` : (typeof e.attachments_count === 'number' ? `${e.attachments_count} file(s)` : 'Preview')}
                          </Button>
                        </TableCell>
                        <TableCell className="space-x-2">
                          <Link to={`/expenses/edit/${e.id}`}>
                            <Button variant="outline" size="sm">
                              <Pencil className="w-4 h-4 mr-1" /> Edit
                            </Button>
                          </Link>
                          <AlertDialog>
                            <AlertDialogTrigger asChild>
                              <Button variant="destructive" size="sm">
                                <Trash2 className="w-4 h-4 mr-1" /> Delete
                              </Button>
                            </AlertDialogTrigger>
                            <AlertDialogContent>
                              <AlertDialogHeader>
                                <AlertDialogTitle>Delete expense?</AlertDialogTitle>
                                <AlertDialogDescription>
                                  This action cannot be undone. This will permanently delete this expense and its attachments.
                                </AlertDialogDescription>
                              </AlertDialogHeader>
                              <AlertDialogFooter>
                                <AlertDialogCancel>Cancel</AlertDialogCancel>
                                <AlertDialogAction onClick={() => handleDelete(e.id)}>Delete</AlertDialogAction>
                              </AlertDialogFooter>
                            </AlertDialogContent>
                          </AlertDialog>
                        </TableCell>
                      </TableRow>
                    ))
                  ) : (
                    <TableRow>
                      <TableCell colSpan={7} className="h-24 text-center">
                        No expenses yet
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </div>
          </CardContent>
        </Card>

        <Dialog open={isCreateOpen} onOpenChange={setIsCreateOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>New Expense</DialogTitle>
            </DialogHeader>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 p-4">
              <div>
                <label className="text-sm">Amount</label>
                <Input type="number" value={Number(newExpense.amount || 0)} onChange={e => setNewExpense({ ...newExpense, amount: Number(e.target.value) })} />
              </div>
              <div>
                <label className="text-sm">Currency</label>
                <CurrencySelector
                  value={newExpense.currency || 'USD'}
                  onValueChange={(v) => setNewExpense({ ...newExpense, currency: v })}
                  placeholder="Select currency"
                />
              </div>
              <div>
                <label className="text-sm">Date</label>
                <Popover>
                  <PopoverTrigger asChild>
                    <Button variant="outline" className="w-full justify-start text-left font-normal">
                      <CalendarIcon className="mr-2 h-4 w-4" />
                      {newExpense.expense_date ? format(new Date(newExpense.expense_date as string), 'PPP') : 'Pick a date'}
                    </Button>
                  </PopoverTrigger>
                  <PopoverContent className="w-auto p-0" align="start">
                    <Calendar
                      mode="single"
                      selected={newExpense.expense_date ? new Date(newExpense.expense_date as string) : undefined}
                      onSelect={(d) => {
                        if (d) {
                          const iso = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate())).toISOString().split('T')[0];
                          setNewExpense({ ...newExpense, expense_date: iso });
                        }
                      }}
                      initialFocus
                    />
                  </PopoverContent>
                </Popover>
              </div>
              <div>
                <label className="text-sm">Category</label>
                <Select
                  value={(newExpense.category as string) || 'General'}
                  onValueChange={(v) => setNewExpense({ ...newExpense, category: v })}
                >
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder="Select category" />
                  </SelectTrigger>
                  <SelectContent>
                    {categoryOptions.map((c) => (
                      <SelectItem key={c} value={c}>{c}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <label className="text-sm">Vendor</label>
                <Input value={newExpense.vendor || ''} onChange={e => setNewExpense({ ...newExpense, vendor: e.target.value })} />
              </div>
              <div>
                <label className="text-sm">Payment method</label>
                <Input value={newExpense.payment_method || ''} onChange={e => setNewExpense({ ...newExpense, payment_method: e.target.value })} />
              </div>
              <div>
                <label className="text-sm">Reference #</label>
                <Input value={newExpense.reference_number || ''} onChange={e => setNewExpense({ ...newExpense, reference_number: e.target.value })} />
              </div>
              <div className="sm:col-span-2">
                <label className="text-sm">Notes</label>
                <Input value={newExpense.notes || ''} onChange={e => setNewExpense({ ...newExpense, notes: e.target.value })} />
              </div>
              <div className="sm:col-span-2">
                <label className="text-sm">Receipt (PDF, JPG, PNG)</label>
                <input
                  type="file"
                  accept="application/pdf,image/jpeg,image/png"
                  onChange={(ev) => setNewReceiptFile(ev.target.files?.[0] || null)}
                />
              </div>
            </div>
            <div className="p-4 flex justify-end gap-2">
              <Button variant="outline" onClick={() => setIsCreateOpen(false)}>Cancel</Button>
              <Button onClick={handleCreate}>Create</Button>
            </div>
          </DialogContent>
        </Dialog>
        <Dialog open={isEditOpen} onOpenChange={setIsEditOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Edit Expense</DialogTitle>
            </DialogHeader>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 p-4">
              <div>
                <label className="text-sm">Amount</label>
                <Input type="number" value={Number(editExpense.amount || 0)} onChange={e => setEditExpense({ ...editExpense, amount: Number(e.target.value) })} />
              </div>
              <div>
                <label className="text-sm">Currency</label>
                <CurrencySelector
                  value={editExpense.currency || 'USD'}
                  onValueChange={(v) => setEditExpense({ ...editExpense, currency: v })}
                  placeholder="Select currency"
                />
              </div>
              <div>
                <label className="text-sm">Date</label>
                <Popover>
                  <PopoverTrigger asChild>
                    <Button variant="outline" className="w-full justify-start text-left font-normal">
                      <CalendarIcon className="mr-2 h-4 w-4" />
                      {editExpense.expense_date ? format(new Date(editExpense.expense_date as string), 'PPP') : 'Pick a date'}
                    </Button>
                  </PopoverTrigger>
                  <PopoverContent className="w-auto p-0" align="start">
                    <Calendar
                      mode="single"
                      selected={editExpense.expense_date ? new Date(editExpense.expense_date as string) : undefined}
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
                <label className="text-sm">Category</label>
                <Select
                  value={(editExpense.category as string) || 'General'}
                  onValueChange={(v) => setEditExpense({ ...editExpense, category: v })}
                >
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder="Select category" />
                  </SelectTrigger>
                  <SelectContent>
                    {categoryOptions.map((c) => (
                      <SelectItem key={c} value={c}>{c}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <label className="text-sm">Vendor</label>
                <Input value={editExpense.vendor || ''} onChange={e => setEditExpense({ ...editExpense, vendor: e.target.value })} />
              </div>
              <div>
                <label className="text-sm">Payment method</label>
                <Input value={editExpense.payment_method || ''} onChange={e => setEditExpense({ ...editExpense, payment_method: e.target.value })} />
              </div>
              <div>
                <label className="text-sm">Reference #</label>
                <Input value={editExpense.reference_number || ''} onChange={e => setEditExpense({ ...editExpense, reference_number: e.target.value })} />
              </div>
              <div className="sm:col-span-2">
                <label className="text-sm">Notes</label>
                <Input value={editExpense.notes || ''} onChange={e => setEditExpense({ ...editExpense, notes: e.target.value })} />
              </div>
              <div className="sm:col-span-2">
                <label className="text-sm">Receipt (PDF, JPG, PNG)</label>
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
              <Button variant="outline" onClick={() => setIsEditOpen(false)}>Cancel</Button>
              <Button onClick={handleUpdate}>Save</Button>
            </div>
          </DialogContent>
        </Dialog>
        {/* Attachment Preview Dialog */}
        <Dialog open={!!attachmentPreviewOpen.expenseId} onOpenChange={(o) => !o && setAttachmentPreviewOpen({ expenseId: null })}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Attachments</DialogTitle>
            </DialogHeader>
            <div className="space-y-3">
              {(attachments[attachmentPreviewOpen.expenseId || -1] || []).length === 0 ? (
                <div className="text-sm text-muted-foreground">No attachments</div>
              ) : (
                <ul className="space-y-2">
                  {(attachments[attachmentPreviewOpen.expenseId || -1] || []).map((att) => (
                    <li key={att.id} className="flex items-center justify-between gap-3 border rounded p-2">
                      <div className="truncate text-sm">
                        {att.filename}
                        {att.size_bytes ? <span className="ml-2 text-xs text-muted-foreground">({Math.round(att.size_bytes/1024)} KB)</span> : null}
                      </div>
                      <div className="flex items-center gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={async () => {
                            if (!attachmentPreviewOpen.expenseId) return;
                            const blob = await expenseApi.downloadAttachmentBlob(attachmentPreviewOpen.expenseId, att.id);
                            const url = URL.createObjectURL(blob);
                            setPreview({ open: true, url, contentType: att.content_type || null, filename: att.filename || null });
                          }}
                        >
                          Preview
                        </Button>
                        <Button
                          variant="destructive"
                          size="sm"
                          onClick={async () => {
                            if (!attachmentPreviewOpen.expenseId) return;
                            await expenseApi.deleteAttachment(attachmentPreviewOpen.expenseId, att.id);
                            const list = await expenseApi.listAttachments(attachmentPreviewOpen.expenseId);
                            setAttachments(prev => ({ ...prev, [attachmentPreviewOpen.expenseId!]: list }));
                          }}
                        >
                          Delete
                        </Button>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </DialogContent>
        </Dialog>
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
};

export default Expenses;


