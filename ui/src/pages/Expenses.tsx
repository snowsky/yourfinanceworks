import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { AppLayout } from '@/components/layout/AppLayout';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Pagination, PaginationContent, PaginationItem, PaginationNext, PaginationPrevious } from '@/components/ui/pagination';
import { Checkbox } from '@/components/ui/checkbox';
import { CurrencyDisplay } from '@/components/ui/currency-display';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Calendar } from '@/components/ui/calendar';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { CalendarIcon, X } from 'lucide-react';
import { format, parseISO, isValid } from 'date-fns';
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
import { Loader2, Plus, Search, Trash2, Upload, ChevronDown, MoreHorizontal, Edit } from 'lucide-react';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { Link } from 'react-router-dom';
import { useSearchParams } from 'react-router-dom';
import { toast } from 'sonner';
import { expenseApi, Expense, ExpenseAttachmentMeta, api } from '@/lib/api';
import { Badge } from '@/components/ui/badge';
import { CurrencySelector } from '@/components/ui/currency-selector';
import { EXPENSE_CATEGORY_OPTIONS } from '@/constants/expenses';
import { canPerformActions } from '@/utils/auth';

// Helper function to format date without timezone issues
const formatDateToISO = (date: Date): string => {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
};

// Helper function to safely parse date strings without timezone issues
const safeParseDateString = (dateString?: string): Date => {
  if (!dateString) return new Date();
  
  try {
    const parsedDate = parseISO(dateString);
    return isValid(parsedDate) ? parsedDate : new Date();
  } catch (error) {
    console.warn('Failed to parse date:', dateString, error);
    return new Date();
  }
};

const defaultNewExpense: Partial<Expense> = {
  amount: 0,
  currency: 'USD',
  expense_date: formatDateToISO(new Date()),
  category: 'General',
  status: 'recorded',
};

const Expenses = () => {
  const { t } = useTranslation();
  const [expenses, setExpenses] = useState<Expense[]>([]);
  const categoryOptions = EXPENSE_CATEGORY_OPTIONS;
  const [loading, setLoading] = useState(true);
  const [categoryFilter, setCategoryFilter] = useState('all');
  const [labelFilter, setLabelFilter] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  // Bulk label removed
  const [unlinkedOnly, setUnlinkedOnly] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [bulkLabel, setBulkLabel] = useState('');
  const [newLabelValueById, setNewLabelValueById] = useState<Record<number, string>>({});
  const [searchParams, setSearchParams] = useSearchParams();
  const [hasNextPage, setHasNextPage] = useState(false);
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
        const skip = (page - 1) * pageSize;
        const data = await expenseApi.getExpensesFiltered({ category: categoryFilter, label: labelFilter || undefined, unlinkedOnly, skip, limit: pageSize });
        setExpenses(data);
        // Probe next page existence precisely
        try {
          const probe = await expenseApi.getExpensesFiltered({ category: categoryFilter, label: labelFilter || undefined, unlinkedOnly, skip: skip + pageSize, limit: 1 });
          setHasNextPage(Array.isArray(probe) && probe.length > 0);
        } catch {
          setHasNextPage(data.length === pageSize);
        }
      } catch (e) {
        toast.error('Failed to load expenses');
      } finally {
        setLoading(false);
      }
    };
    fetchExpenses();
  }, [categoryFilter, labelFilter, unlinkedOnly, page, pageSize, currentTenantId]);

  // Initialize from URL on first render
  useEffect(() => {
    try {
      const cat = searchParams.get('category');
      const lab = searchParams.get('label');
      const q = searchParams.get('q');
      const ul = searchParams.get('unlinked');
      const pg = searchParams.get('page');
      const ps = searchParams.get('pageSize');
      if (cat) setCategoryFilter(cat);
      if (lab) setLabelFilter(lab);
      if (q) setSearchQuery(q);
      if (ul === '1') setUnlinkedOnly(true);
      if (pg && !Number.isNaN(Number(pg))) setPage(Math.max(1, Number(pg)));
      if (ps && !Number.isNaN(Number(ps))) setPageSize(Math.min(200, Math.max(5, Number(ps))));
    } catch {}
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Persist filters to URL
  useEffect(() => {
    const p = new URLSearchParams();
    if (categoryFilter && categoryFilter !== 'all') p.set('category', categoryFilter);
    if (labelFilter) p.set('label', labelFilter);
    if (searchQuery) p.set('q', searchQuery);
    if (unlinkedOnly) p.set('unlinked', '1');
    if (page && page !== 1) p.set('page', String(page));
    if (pageSize && pageSize !== 20) p.set('pageSize', String(pageSize));
    setSearchParams(p, { replace: true });
  }, [categoryFilter, labelFilter, searchQuery, unlinkedOnly, page, pageSize, setSearchParams]);

  const filteredExpenses = useMemo(() => {
    return (expenses || []).filter(e => {
      const s = searchQuery.toLowerCase();
      return (
        (e.vendor || '').toLowerCase().includes(s) ||
        (e.category || '').toLowerCase().includes(s) ||
        (e.notes || '').toLowerCase().includes(s) ||
        ((e.labels || []).join(',').toLowerCase().includes(s))
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
      if ((!newExpense.amount || Number(newExpense.amount) === 0) && !newReceiptFile) {
        toast.error('Amount is required unless importing from a file');
        return;
      }
      if (!newExpense.category) {
        toast.error('Category is required');
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
      const created = await expenseApi.createExpense({ ...payload, imported_from_attachment: !!newReceiptFile, analysis_status: newReceiptFile ? 'queued' : 'not_started' } as any);
      // Upload receipt if provided
      let createdWithReceipt = created;
      if (newReceiptFile) {
        const addNotification = (window as any).addAINotification;
        addNotification?.('processing', 'Processing Expense Receipt', `Analyzing receipt file with AI...`);
        
        try {
          setUploadingId(created.id);
          const uploadResp = await expenseApi.uploadReceipt(created.id, newReceiptFile);
          createdWithReceipt = { ...created, receipt_filename: uploadResp?.receipt_filename || created.receipt_filename } as Expense;
          
          addNotification?.('success', 'Expense Receipt Uploaded', `Successfully uploaded receipt file. AI analysis in progress.`);
          (window as any).startExpensePolling?.(created.id);
        } catch (e) {
          console.error('Receipt upload failed on create:', e);
          addNotification?.('error', 'Expense Receipt Failed', `Failed to upload receipt: ${e instanceof Error ? e.message : 'Unknown error'}`);
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
    const addNotification = (window as any).addAINotification;
    addNotification?.('processing', 'Processing Expense Receipt', `Analyzing receipt file with AI...`);
    
    try {
      setUploadingId(id);
      await expenseApi.uploadReceipt(id, file);
      // Refresh list
      const data = await expenseApi.getExpenses(categoryFilter);
      setExpenses(data);
      
      addNotification?.('success', 'Expense Receipt Uploaded', `Successfully uploaded receipt file. AI analysis in progress.`);
      (window as any).startExpensePolling?.(id);
      toast.success('Receipt uploaded');
    } catch (e: any) {
      addNotification?.('error', 'Expense Receipt Failed', `Failed to upload receipt: ${e?.message || 'Unknown error'}`);
      toast.error(e?.message || 'Failed to upload receipt');
    } finally {
      setUploadingId(null);
    }
  };

  const handleRequeue = async (expenseId: number) => {
    const addNotification = (window as any).addAINotification;
    addNotification?.('processing', 'Reprocessing Expense', `Re-analyzing expense receipts with AI...`);
    
    try {
      await expenseApi.reprocessExpense(expenseId);
      
      addNotification?.('success', 'Expense Reprocessing Started', `Successfully started reprocessing expense receipts.`);
      toast.success('Expense reprocessing started');
      const data = await expenseApi.getExpenses(categoryFilter);
      setExpenses(data);
    } catch (e: any) {
      addNotification?.('error', 'Expense Reprocessing Failed', `Failed to reprocess expense: ${e?.message || 'Unknown error'}`);
      toast.error(e?.message || 'Failed to reprocess expense');
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
        const addNotification = (window as any).addAINotification;
        addNotification?.('processing', 'Processing Expense Receipt', `Analyzing receipt file with AI...`);
        
        try {
          setUploadingId(updated.id);
          const uploadResp = await expenseApi.uploadReceipt(updated.id, editReceiptFile);
          finalUpdated = { ...updated, receipt_filename: uploadResp?.receipt_filename || updated.receipt_filename } as Expense;
          
          addNotification?.('success', 'Expense Receipt Uploaded', `Successfully uploaded receipt file. AI analysis in progress.`);
          (window as any).startExpensePolling?.(updated.id);
        } catch (e) {
          console.error('Receipt upload failed on update:', e);
          addNotification?.('error', 'Expense Receipt Failed', `Failed to upload receipt: ${e instanceof Error ? e.message : 'Unknown error'}`);
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
            <h1 className="text-3xl font-bold">{t('expenses.title')}</h1>
            <p className="text-muted-foreground">{t('expenses.description')}</p>
          </div>
          {canPerformActions() && (
            <div className="flex gap-2">
              <div className="flex">
                <Button onClick={openCreate} className="rounded-r-none border-r-0">
                  <Plus className="w-4 h-4 mr-2" /> {t('expenses.new')}
                </Button>
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button className="rounded-l-none px-2">
                      <ChevronDown className="h-4 w-4" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    <DropdownMenuItem asChild>
                      <Link to="/expenses/import" className="flex items-center w-full">
                        <Upload className="mr-2 h-4 w-4" />
                        {t('expenses.import_from_pdf_images')}
                      </Link>
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
            </div>
          )}
        </div>

        <Card className="slide-in">
          <CardHeader className="pb-3">
            <div className="flex flex-col sm:flex-row justify-between gap-4">
              <CardTitle>{t('expenses.list_title')}</CardTitle>
              <div className="flex flex-col sm:flex-row gap-4">
                <div className="relative">
                  <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                  <Input
                     placeholder={t('expenses.search_placeholder')}
                    className="pl-8 w-full sm:w-[260px]"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                  />
                </div>
                <Select value={categoryFilter} onValueChange={setCategoryFilter}>
                  <SelectTrigger className="w-full sm:w-[180px]">
                     <SelectValue placeholder={t('expenses.filter_by_category')} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">{t('expenses.all_categories')}</SelectItem>
                    {categoryOptions.map((c) => (
                      <SelectItem key={c} value={c}>{c}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <div className="relative">
                  <Input
                    placeholder={t('expenses.filter_by_label', { defaultValue: 'Filter by label' })}
                    className="pl-8 w-full sm:w-[180px] pr-8"
                    value={labelFilter}
                    onChange={(e) => { setLabelFilter(e.target.value); setPage(1); }}
                  />
                  {labelFilter && (
                    <button
                      aria-label="Clear label filter"
                      className="absolute right-2 top-2 text-muted-foreground hover:text-foreground"
                      onClick={() => { setLabelFilter(''); setPage(1); }}
                    >
                      <X className="w-4 h-4" />
                    </button>
                  )}
                </div>
                <label className="inline-flex items-center gap-2 text-sm text-muted-foreground">
                  <input type="checkbox" checked={unlinkedOnly} onChange={(e) => { setUnlinkedOnly(e.target.checked); setPage(1); }} />
                  {t('expenses.unlinked_only', { defaultValue: 'Unlinked only' })}
                </label>
                <div className="flex items-center gap-2">
                  <span className="text-sm text-muted-foreground">{t('page_size', { defaultValue: 'Page size' })}</span>
                  <Select value={String(pageSize)} onValueChange={(v) => { setPageSize(Number(v)); setPage(1); }}>
                    <SelectTrigger className="w-[100px]">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {[10,20,50,100].map(n => (
                        <SelectItem key={n} value={String(n)}>{n}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <div className="flex flex-col md:flex-row md:items-center gap-2 mb-3 md:justify-between">
              <div className="text-sm text-muted-foreground">
                {selectedIds.length > 0 ? `${selectedIds.length} selected` : `${expenses.length} ${t('expenses.results', { defaultValue: 'results' })}`}
              </div>
              <div className="flex items-center gap-2 md:ml-auto">
                <Input
                  placeholder={t('expenses.bulk_label_placeholder', { defaultValue: 'Label' })}
                  value={bulkLabel}
                  onChange={(e) => setBulkLabel(e.target.value)}
                  className="w-full sm:w-[220px]"
                />
                <Button
                  variant="outline"
                  disabled={!canPerformActions() || selectedIds.length === 0 || !bulkLabel.trim()}
                  onClick={async () => {
                    try {
                      const skip = (page - 1) * pageSize;
                      await expenseApi.bulkLabels(selectedIds, 'add', bulkLabel.trim());
                      const data = await expenseApi.getExpensesFiltered({ category: categoryFilter, label: labelFilter || undefined, unlinkedOnly, skip, limit: pageSize });
                      setExpenses(data);
                      setSelectedIds([]);
                      setBulkLabel('');
                      toast.success('Labels added');
                    } catch (e: any) {
                      toast.error(e?.message || 'Failed to add label');
                    }
                  }}
                >
                  {t('add')}
                </Button>
                <Button
                  variant="outline"
                  disabled={!canPerformActions() || selectedIds.length === 0 || !bulkLabel.trim()}
                  onClick={async () => {
                    try {
                      const skip = (page - 1) * pageSize;
                      await expenseApi.bulkLabels(selectedIds, 'remove', bulkLabel.trim());
                      const data = await expenseApi.getExpensesFiltered({ category: categoryFilter, label: labelFilter || undefined, unlinkedOnly, skip, limit: pageSize });
                      setExpenses(data);
                      setSelectedIds([]);
                      setBulkLabel('');
                      toast.success('Labels removed');
                    } catch (e: any) {
                      toast.error(e?.message || 'Failed to remove label');
                    }
                  }}
                >
                  {t('remove')}
                </Button>
              </div>
            </div>
            <div className="rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-[40px]">
                      <Checkbox
                        checked={selectedIds.length > 0 && selectedIds.length === filteredExpenses.length}
                        onCheckedChange={(v) => {
                          if (v) setSelectedIds(filteredExpenses.map(x => x.id));
                          else setSelectedIds([]);
                        }}
                        aria-label="Select all"
                      />
                    </TableHead>
                    <TableHead>ID</TableHead>
                    <TableHead>{t('expenses.table.date')}</TableHead>
                    <TableHead>{t('expenses.table.category')}</TableHead>
                    <TableHead>{t('expenses.table.vendor')}</TableHead>
                    <TableHead>{t('labels', { defaultValue: 'Labels' })}</TableHead>
                    <TableHead>{t('expenses.table.amount')}</TableHead>
                    <TableHead>{t('expenses.table.total')}</TableHead>
                    <TableHead>{t('expenses.table.invoice')}</TableHead>
                    <TableHead>{t('expenses.table.analyzed')}</TableHead>
                    <TableHead>{t('expenses.table.receipt')}</TableHead>
                    <TableHead>{t('expenses.table.actions')}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {loading ? (
                    <TableRow>
                      <TableCell colSpan={7} className="h-24 text-center">
                        <div className="flex justify-center items-center">
                          <Loader2 className="h-6 w-6 animate-spin mr-2" />
                          {t('expenses.loading')}
                        </div>
                      </TableCell>
                    </TableRow>
                  ) : (filteredExpenses || []).length > 0 ? (
                    (filteredExpenses || []).map((e) => (
                      <TableRow key={e.id}>
                        <TableCell>
                          <Checkbox
                            checked={selectedIds.includes(e.id)}
                            onCheckedChange={(v) => {
                              if (v) setSelectedIds(prev => Array.from(new Set([...prev, e.id])));
                              else setSelectedIds(prev => prev.filter(x => x !== e.id));
                            }}
                            aria-label={`Select expense ${e.id}`}
                          />
                        </TableCell>
                        <TableCell className="text-muted-foreground whitespace-nowrap">#{e.id}</TableCell>
                        <TableCell>{e.expense_date ? new Date(e.expense_date).toLocaleDateString('en-US', { timeZone: 'UTC' }) : 'N/A'} UTC</TableCell>
                        <TableCell>{e.category}</TableCell>
                        <TableCell>{e.vendor || '—'}</TableCell>
                        <TableCell>
                          <div className="flex flex-wrap items-center gap-2">
                            {(e.labels || []).slice(0, 10).map((lab, idx) => (
                              <Badge key={`${e.id}-lab-${idx}`} variant="secondary" className="text-xs">
                                {lab}
                                {canPerformActions() && (
                                  <button
                                    className="ml-1 text-muted-foreground hover:text-foreground"
                                    aria-label={t('remove', { defaultValue: 'Remove' })}
                                    onClick={async () => {
                                      try {
                                        const next = (e.labels || []).filter((l) => l !== lab);
                                        await expenseApi.updateExpense(e.id, { labels: next });
                                        setExpenses((prev) => prev.map((x) => (x.id === e.id ? { ...x, labels: next } as Expense : x)));
                                      } catch (err: any) {
                                        toast.error(err?.message || 'Failed to remove label');
                                      }
                                    }}
                                  >
                                    <X className="w-3 h-3" />
                                  </button>
                                )}
                              </Badge>
                            ))}
                            {canPerformActions() && (
                              <Input
                                placeholder={t('expenses.label_placeholder', { defaultValue: 'Add label' })}
                                value={newLabelValueById[e.id] || ''}
                                className="w-[140px] h-8"
                                onChange={(ev) => setNewLabelValueById((prev) => ({ ...prev, [e.id]: ev.target.value }))}
                                onKeyDown={async (ev) => {
                                  if (ev.key === 'Enter') {
                                    const raw = (newLabelValueById[e.id] || '').trim();
                                    if (!raw) return;
                                    const existing = e.labels || [];
                                    if (existing.includes(raw)) { setNewLabelValueById((prev) => ({ ...prev, [e.id]: '' })); return; }
                                    if (existing.length >= 10) { toast.error(t('max_labels_reached', { defaultValue: 'Maximum of 10 labels reached' })); return; }
                                    try {
                                      const next = [...existing, raw];
                                      await expenseApi.updateExpense(e.id, { labels: next });
                                      setExpenses((prev) => prev.map((x) => (x.id === e.id ? { ...x, labels: next } as Expense : x)));
                                      setNewLabelValueById((prev) => ({ ...prev, [e.id]: '' }));
                                    } catch (err: any) {
                                      toast.error(err?.message || 'Failed to add label');
                                    }
                                  }
                                }}
                              />
                            )}
                          </div>
                        </TableCell>
                        <TableCell><CurrencyDisplay amount={e.amount || 0} currency={e.currency || 'USD'} /></TableCell>
                        <TableCell><CurrencyDisplay amount={e.total_amount || e.amount || 0} currency={e.currency || 'USD'} /></TableCell>
                        <TableCell>
                          {typeof e.invoice_id === 'number' ? (
                            <Link to={`/invoices/edit/${e.invoice_id}`} className="text-blue-600 hover:underline">#{e.invoice_id}</Link>
                          ) : (
                             <span className="text-muted-foreground">{t('expenses.none')}</span>
                          )}
                        </TableCell>
                        <TableCell>
                          {e.analysis_status === 'done' ? (
                             <span className="text-green-700 bg-green-100 px-2 py-0.5 rounded text-xs">{t('expenses.status_done')}</span>
                          ) : e.analysis_status === 'processing' || e.analysis_status === 'queued' ? (
                             <span className="text-amber-700 bg-amber-100 px-2 py-0.5 rounded text-xs capitalize">{e.analysis_status === 'processing' ? t('expenses.status_processing') : t('expenses.status_queued')}</span>
                          ) : e.analysis_status === 'failed' ? (
                             <span className="text-red-700 bg-red-100 px-2 py-0.5 rounded text-xs">Failed</span>
                          ) : e.analysis_status === 'cancelled' ? (
                             <span className="text-gray-700 bg-gray-100 px-2 py-0.5 rounded text-xs">Cancelled</span>
                          ) : e.imported_from_attachment ? (
                             <span className="text-muted-foreground text-xs">Not Started</span>
                          ) : (
                            <span className="text-muted-foreground text-xs">—</span>
                          )}
                          {e.analysis_status && e.analysis_status !== 'done' && canPerformActions() && (
                            <Button variant="ghost" size="sm" className="ml-2" onClick={() => handleRequeue(e.id)}>
                              {t('expenses.process_again', { defaultValue: 'Process Again' })}
                            </Button>
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
                             {uploadingId === e.id ? t('expenses.uploading') : t('expenses.upload')}
                          </label>
                          <Button variant="ghost" size="sm" onClick={async () => {
                            const list = await expenseApi.listAttachments(e.id);
                            setAttachments(prev => ({ ...prev, [e.id]: list }));
                            setAttachmentPreviewOpen({ expenseId: e.id });
                          }}>
                             {Array.isArray(attachments[e.id]) ? `${attachments[e.id].length} ${t('attachments_count', { defaultValue: 'file(s)' })}` : (typeof e.attachments_count === 'number' ? `${e.attachments_count} ${t('attachments_count', { defaultValue: 'file(s)' })}` : t('expenses.preview'))}
                          </Button>
                        </TableCell>
                        <TableCell>
                          {canPerformActions() && (
                            <DropdownMenu>
                              <DropdownMenuTrigger asChild>
                                <Button variant="ghost" className="h-8 w-8 p-0">
                                  <span className="sr-only">Open menu</span>
                                  <MoreHorizontal className="h-4 w-4" />
                                </Button>
                              </DropdownMenuTrigger>
                              <DropdownMenuContent align="end">
                                <DropdownMenuItem asChild>
                                  <Link to={`/expenses/edit/${e.id}`} className="flex items-center w-full">
                                    <Edit className="w-4 h-4 mr-2" />
                                    {t('edit', { defaultValue: 'Edit' })}
                                  </Link>
                                </DropdownMenuItem>
                                
                                <DropdownMenuSeparator />
                                
                                <AlertDialog>
                                  <AlertDialogTrigger asChild>
                                    <DropdownMenuItem onSelect={(e) => e.preventDefault()}>
                                      <Trash2 className="w-4 h-4 mr-2" />
                                      Delete
                                    </DropdownMenuItem>
                                  </AlertDialogTrigger>
                                  <AlertDialogContent>
                                    <AlertDialogHeader>
                                      <AlertDialogTitle>{t('expenses.delete_confirm_title')}</AlertDialogTitle>
                                      <AlertDialogDescription>
                                        {t('expenses.delete_confirm_description')}
                                      </AlertDialogDescription>
                                    </AlertDialogHeader>
                                    <AlertDialogFooter>
                                      <AlertDialogCancel>{t('cancel')}</AlertDialogCancel>
                                      <AlertDialogAction onClick={() => handleDelete(e.id)}>{t('delete')}</AlertDialogAction>
                                    </AlertDialogFooter>
                                  </AlertDialogContent>
                                </AlertDialog>
                              </DropdownMenuContent>
                            </DropdownMenu>
                          )}
                        </TableCell>
                      </TableRow>
                    ))
                  ) : (
                    <TableRow>
                      <TableCell colSpan={12} className="h-24 text-center text-muted-foreground">
                        No expenses yet
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </div>
            <div className="mt-3">
              <Pagination>
                <PaginationContent>
                  <PaginationItem>
                    <PaginationPrevious
                      href="#"
                      className={page <= 1 ? 'opacity-50 pointer-events-none' : ''}
                      onClick={(e) => { e.preventDefault(); if (page > 1 && !loading) setPage(p => Math.max(1, p - 1)); }}
                    />
                  </PaginationItem>
                  <PaginationItem>
                    <PaginationNext
                      href="#"
                      className={!hasNextPage ? 'opacity-50 pointer-events-none' : ''}
                      onClick={(e) => { e.preventDefault(); if (hasNextPage && !loading) setPage(p => p + 1); }}
                    />
                  </PaginationItem>
                </PaginationContent>
              </Pagination>
            </div>
          </CardContent>
        </Card>

        <Dialog open={isCreateOpen} onOpenChange={setIsCreateOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>{t('expenses.new_title')}</DialogTitle>
            </DialogHeader>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 p-4">
              <div>
                <label className="text-sm">{t('expenses.labels.amount')}</label>
                <Input type="number" value={Number(newExpense.amount || 0)} onChange={e => setNewExpense({ ...newExpense, amount: Number(e.target.value) })} />
              </div>
              <div>
                <label className="text-sm">{t('expenses.labels.currency')}</label>
                <CurrencySelector
                  value={newExpense.currency || 'USD'}
                  onValueChange={(v) => setNewExpense({ ...newExpense, currency: v })}
                  placeholder={t('select_currency')}
                />
              </div>
              <div>
                <label className="text-sm">{t('expenses.labels.date')}</label>
                <Popover>
                  <PopoverTrigger asChild>
                    <Button variant="outline" className="w-full justify-start text-left font-normal">
                      <CalendarIcon className="mr-2 h-4 w-4" />
                       {newExpense.expense_date ? format(safeParseDateString(newExpense.expense_date as string), 'PPP') : t('expenses.labels.pick_date')}
                    </Button>
                  </PopoverTrigger>
                  <PopoverContent className="w-auto p-0" align="start">
                    <Calendar
                      mode="single"
                      selected={newExpense.expense_date ? safeParseDateString(newExpense.expense_date as string) : undefined}
                      onSelect={(d) => {
                        if (d) {
                          const iso = formatDateToISO(d);
                          setNewExpense({ ...newExpense, expense_date: iso });
                        }
                      }}
                      initialFocus
                    />
                  </PopoverContent>
                </Popover>
              </div>
              <div>
                <label className="text-sm">{t('expenses.labels.category')}</label>
                <Select
                  value={(newExpense.category as string) || 'General'}
                  onValueChange={(v) => setNewExpense({ ...newExpense, category: v })}
                >
                  <SelectTrigger className="w-full">
                     <SelectValue placeholder={t('select_category', { defaultValue: 'Select category' }) as string} />
                  </SelectTrigger>
                  <SelectContent>
                    {categoryOptions.map((c) => (
                      <SelectItem key={c} value={c}>{c}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <label className="text-sm">{t('expenses.labels.vendor')}</label>
                <Input value={newExpense.vendor || ''} onChange={e => setNewExpense({ ...newExpense, vendor: e.target.value })} />
              </div>
              <div>
                <label className="text-sm">{t('expenses.labels.payment_method')}</label>
                <Input value={newExpense.payment_method || ''} onChange={e => setNewExpense({ ...newExpense, payment_method: e.target.value })} />
              </div>
              <div>
                <label className="text-sm">{t('expenses.labels.reference_number')}</label>
                <Input value={newExpense.reference_number || ''} onChange={e => setNewExpense({ ...newExpense, reference_number: e.target.value })} />
              </div>
              <div className="sm:col-span-2">
                <label className="text-sm">{t('expenses.labels.notes')}</label>
                <Input value={newExpense.notes || ''} onChange={e => setNewExpense({ ...newExpense, notes: e.target.value })} />
              </div>
              <div className="sm:col-span-2">
                <label className="text-sm">{t('expenses.labels.receipt')}</label>
                <input
                  type="file"
                  accept="application/pdf,image/jpeg,image/png"
                  onChange={(ev) => setNewReceiptFile(ev.target.files?.[0] || null)}
                />
              </div>
            </div>
            <div className="p-4 flex justify-end gap-2">
              <Button variant="outline" onClick={() => setIsCreateOpen(false)}>{t('cancel')}</Button>
              <Button onClick={handleCreate}>{t('expenses.buttons.create')}</Button>
            </div>
          </DialogContent>
        </Dialog>
        <Dialog open={isEditOpen} onOpenChange={setIsEditOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>{t('expenses.edit_title')}</DialogTitle>
            </DialogHeader>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 p-4">
              <div>
                <label className="text-sm">{t('expenses.labels.amount')}</label>
                <Input type="number" value={Number(editExpense.amount || 0)} onChange={e => setEditExpense({ ...editExpense, amount: Number(e.target.value) })} />
              </div>
              <div>
                <label className="text-sm">{t('expenses.labels.currency')}</label>
                <CurrencySelector
                  value={editExpense.currency || 'USD'}
                  onValueChange={(v) => setEditExpense({ ...editExpense, currency: v })}
                  placeholder={t('select_currency')}
                />
              </div>
              <div>
                <label className="text-sm">{t('expenses.labels.date')}</label>
                <Popover>
                  <PopoverTrigger asChild>
                    <Button variant="outline" className="w-full justify-start text-left font-normal">
                      <CalendarIcon className="mr-2 h-4 w-4" />
                       {editExpense.expense_date ? format(new Date(editExpense.expense_date as string), 'PPP') : t('expenses.labels.pick_date')}
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
                <label className="text-sm">{t('expenses.labels.category')}</label>
                <Select
                  value={(editExpense.category as string) || 'General'}
                  onValueChange={(v) => setEditExpense({ ...editExpense, category: v })}
                >
                  <SelectTrigger className="w-full">
                     <SelectValue placeholder={t('select_category', { defaultValue: 'Select category' }) as string} />
                  </SelectTrigger>
                  <SelectContent>
                    {categoryOptions.map((c) => (
                      <SelectItem key={c} value={c}>{c}</SelectItem>
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
              <div className="sm:col-span-2">
                <label className="text-sm">{t('expenses.labels.notes')}</label>
                <Input value={editExpense.notes || ''} onChange={e => setEditExpense({ ...editExpense, notes: e.target.value })} />
              </div>
              <div className="sm:col-span-2">
                <label className="text-sm">{t('expenses.labels.receipt')}</label>
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
              <Button variant="outline" onClick={() => setIsEditOpen(false)}>{t('cancel')}</Button>
              <Button onClick={handleUpdate}>{t('expenses.buttons.save')}</Button>
            </div>
          </DialogContent>
        </Dialog>
        {/* Attachment Preview Dialog */}
        <Dialog open={!!attachmentPreviewOpen.expenseId} onOpenChange={(o) => !o && setAttachmentPreviewOpen({ expenseId: null })}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>{t('expenses.attachments')}</DialogTitle>
            </DialogHeader>
            <div className="space-y-3">
              {(attachments[attachmentPreviewOpen.expenseId || -1] || []).length === 0 ? (
                <div className="text-sm text-muted-foreground">{t('expenses.no_attachments')}</div>
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
                          {t('expenses.preview')}
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
                           {t('delete')}
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
                }}>{t('expenses.download')}</Button>
              )}
            </div>
          </DialogContent>
        </Dialog>
      </div>
    </AppLayout>
  );
};

export default Expenses;



