import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AppLayout } from '@/components/layout/AppLayout';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Calendar } from '@/components/ui/calendar';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { CalendarIcon, Upload, ArrowLeft, Eye, Download, ExternalLink, Trash2, FileText, Plus, Copy } from 'lucide-react';
import { format } from 'date-fns';
import { bankStatementApi, BankTransactionEntry, BankStatementDetail, BankStatementSummary, expenseApi, invoiceApi, clientApi } from '@/lib/api';
import { toast } from 'sonner';
import { InvoiceForm } from '@/components/invoices/InvoiceForm';

const CATEGORY_OPTIONS = [
  'Income', 'Food', 'Transportation', 'Shopping', 'Bills', 'Healthcare', 'Entertainment', 'Financial', 'Travel', 'Other'
];

type BankRow = BankTransactionEntry & { id?: number; invoice_id?: number | null; expense_id?: number | null };

export default function BankStatements() {
  const [files, setFiles] = useState<File[]>([]);
  const [loading, setLoading] = useState(false);
  const [statements, setStatements] = useState<BankStatementSummary[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detail, setDetail] = useState<BankStatementDetail | null>(null);
  const [rows, setRows] = useState<BankRow[]>([]);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewObjectUrl, setPreviewObjectUrl] = useState<string | null>(null);
  const [clients, setClients] = useState<any[]>([]);
  const [showInvoiceForm, setShowInvoiceForm] = useState(false);
  const [invoiceInitialData, setInvoiceInitialData] = useState<any>(null);
  const [statementNotes, setStatementNotes] = useState<string>('');
  const [statementLabels, setStatementLabels] = useState<string[]>([]);
  const readOnly = detail?.status === 'processing';

  const formatStatus = (value?: string | null) => {
    if (!value) return '';
    return value.charAt(0).toUpperCase() + value.slice(1);
  };

  useEffect(() => {
    const loadClients = async () => {
      try {
        const clientList = await clientApi.getClients();
        setClients(clientList);
      } catch (e) {
        console.error('Failed to load clients:', e);
      }
    };
    loadClients();
  }, []);

  // Calculate totals
  const totalIncome = rows.filter(r => r.transaction_type === 'credit').reduce((sum, r) => sum + r.amount, 0);
  const totalExpense = rows.filter(r => r.transaction_type === 'debit').reduce((sum, r) => sum + Math.abs(r.amount), 0);
  const netAmount = totalIncome - totalExpense;

  const exportToCSV = () => {
    if (rows.length === 0) {
      toast.error('No transactions to export');
      return;
    }

    const headers = ['Date', 'Description', 'Amount', 'Type', 'Balance', 'Category'];
    const csvContent = [
      headers.join(','),
      ...rows.map(row => [
        row.date,
        `"${row.description.replace(/"/g, '""')}"`,
        row.amount,
        row.transaction_type,
        row.balance ?? '',
        row.category ?? ''
      ].join(','))
    ].join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    link.setAttribute('href', url);
    link.setAttribute('download', `transactions-${detail?.original_filename?.replace('.pdf', '') || 'export'}.csv`);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
    toast.success('CSV exported successfully');
  };

  const createExpenseFromTransaction = async (rowIndex: number) => {
    const transaction = rows[rowIndex];
    if (transaction.transaction_type !== 'debit') {
      toast.error('Can only create expenses from debit transactions');
      return;
    }
    if ((transaction as any).expense_id) {
      toast.error('An expense has already been created for this transaction');
      return;
    }

    try {
      // Map bank transaction categories to expense categories
      const categoryMap: Record<string, string> = {
        'Transportation': 'Transportation',
        'Food': 'Meals',
        'Travel': 'Travel',
        'Other': 'General'
      };
      
      const expenseCategory = categoryMap[transaction.category || 'Other'] || 'General';
      
      const expenseData = {
        amount: Math.abs(transaction.amount),
        expense_date: transaction.date,
        category: expenseCategory,
        vendor: transaction.description,
        notes: `Created from bank statement: ${detail?.original_filename}`,
        payment_method: 'Bank Transfer',
        status: 'completed'
      };

      const created = await expenseApi.createExpense(expenseData as any);
      toast.success('Expense created successfully');

      // Link this transaction to the created expense to prevent duplicates
      const updatedRows: BankRow[] = rows.map((r, i) => i === rowIndex ? { ...r, expense_id: created.id } : r);
      setRows(updatedRows);
      if (selected) {
        try {
          const cleaned = updatedRows.map(r => ({
            ...r,
            balance: r.balance === undefined ? null : r.balance,
            category: r.category || null,
            invoice_id: r.invoice_id ?? null,
            expense_id: r.expense_id ?? null,
          }));
          await bankStatementApi.replaceTransactions(selected, cleaned);
          // Reload to confirm persisted link
          await openStatement(selected);
        } catch (linkErr: any) {
          console.error('Failed to persist expense link:', linkErr);
        }
      }
    } catch (e: any) {
      toast.error(e?.message || 'Failed to create expense');
    }
  };

  const createInvoiceFromTransaction = (rowIndex: number) => {
    const transaction = rows[rowIndex];
    if (transaction.transaction_type !== 'credit') {
      toast.error('Can only create invoices from credit transactions');
      return;
    }

    // Prevent duplicate invoice creation if already linked
    if ((transaction as any).invoice_id) {
      toast.error('An invoice has already been created for this transaction');
      return;
    }

    // Normalize transaction date as UTC midnight, then build local Date objects for form controls
    const [y, m, d] = transaction.date.split('-').map(n => parseInt(n, 10));
    const utcMidnightMs = Date.UTC(y, (m || 1) - 1, d || 1);
    const transactionDate = new Date(utcMidnightMs);
    const dueDateLocal = new Date(utcMidnightMs);
    dueDateLocal.setUTCDate(dueDateLocal.getUTCDate() + 30);

    setInvoiceInitialData({
      date: transactionDate,
      dueDate: dueDateLocal,
      status: 'paid',
      paidAmount: transaction.amount,
      notes: `Created from bank statement: ${detail?.original_filename}`,
      items: [{
        description: transaction.description,
        quantity: 1,
        price: transaction.amount,
      }],
      client: '',
      // Pass through the bank transaction id to backend for linkage
      bank_transaction_id: (transaction as any).id || undefined,
    });
    setShowInvoiceForm(true);
  };

  const loadList = async () => {
    try {
      const list = await bankStatementApi.list();
      setStatements(list);
    } catch (e: any) {
      toast.error(e?.message || 'Failed to load statements');
    }
  };

  useEffect(() => {
    loadList();
  }, []);

  const openStatement = async (id: number) => {
    setSelected(id);
    setDetailLoading(true);
    try {
      const s = await bankStatementApi.get(id);
      setDetail(s);
      setStatementLabels(Array.isArray((s as any).labels) ? ((s as any).labels as string[]).slice(0, 10) : []);
      setStatementNotes(s.notes || '');
      setRows((s.transactions || []).map(t => ({
        id: (t as any).id,
        date: t.date,
        description: t.description,
        amount: t.amount,
        transaction_type: (t.transaction_type === 'debit' || t.transaction_type === 'credit') ? t.transaction_type : (t.amount < 0 ? 'debit' : 'credit'),
        balance: t.balance ?? null,
        category: t.category ?? null,
        invoice_id: (t as any).invoice_id ?? null,
        expense_id: (t as any).expense_id ?? null,
      })));
    } catch (e: any) {
      toast.error(e?.message || 'Failed to load statement');
      setSelected(null);
    } finally {
      setDetailLoading(false);
    }
  };

  const onUpload = async () => {
    try {
      if (files.length === 0) { toast.error('Select up to 12 PDF files'); return; }
      setLoading(true);
      const resp = await bankStatementApi.uploadAndExtract(files);
      toast.success(`Created ${resp.statements.length} statement(s)`);
      setFiles([]);
      await loadList();
    } catch (e: any) {
      toast.error(e?.message || 'Failed to extract transactions');
    } finally {
      setLoading(false);
    }
  };

  const addEmptyRow = () => {
    const today = new Date();
    const iso = new Date(Date.UTC(today.getFullYear(), today.getMonth(), today.getDate())).toISOString().split('T')[0];
    setRows(prev => ([...prev, { date: iso, description: '', amount: 0, transaction_type: 'debit', balance: null, category: 'Other' }]));
  };

  const saveRows = async () => {
    if (!selected) return;
    try {
      setDetailLoading(true);
      const cleaned = rows.map(r => ({
        ...r,
        balance: r.balance === undefined ? null : r.balance,
        category: r.category || null,
        invoice_id: r.invoice_id ?? null,
      }));
      await bankStatementApi.replaceTransactions(selected, cleaned);
      toast.success('Transactions saved');
      // Refresh detail and list counts
      await openStatement(selected);
      await loadList();
    } catch (e: any) {
      toast.error(e?.message || 'Failed to save transactions');
    } finally {
      setDetailLoading(false);
    }
  };

  const saveMeta = async () => {
    if (!selected) return;
    try {
      setDetailLoading(true);
      const updates = {
        labels: (statementLabels || []).filter((x) => (x || '').trim()).slice(0, 10),
        notes: statementNotes || null,
      };
      const resp = await bankStatementApi.updateMeta(selected, updates);
      setDetail(prev => prev ? { ...prev, notes: resp.statement.notes || null, labels: (resp.statement as any).labels || [] } : prev);
      await loadList();
      toast.success('Statement updated');
    } catch (e: any) {
      toast.error(e?.message || 'Failed to update statement');
    } finally {
      setDetailLoading(false);
    }
  };

  // DRY helpers for preview/download
  const handlePreview = async (id: number) => {
    try {
      const { blob } = await bankStatementApi.fetchFileBlob(id, true);
      if (previewObjectUrl) URL.revokeObjectURL(previewObjectUrl);
      const objectUrl = URL.createObjectURL(blob);
      setPreviewObjectUrl(objectUrl);
      setPreviewUrl(objectUrl);
      setPreviewOpen(true);
    } catch (e: any) {
      toast.error(e?.message || 'Failed to preview file');
    }
  };

  const handleDownload = async (id: number, defaultName?: string) => {
    try {
      const { blob, filename } = await bankStatementApi.fetchFileBlob(id, false);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename || defaultName || `statement-${id}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e: any) {
      toast.error(e?.message || 'Failed to download file');
    }
  };

  return (
    <AppLayout>
      <div className="h-full space-y-6 fade-in">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold">Bank Statements</h1>
            <p className="text-muted-foreground">Each entry is a PDF. Open to view or edit its transactions.</p>
          </div>
          {!selected && (
            <div className="flex items-center gap-2">
              <label className="inline-flex items-center gap-2 cursor-pointer">
                <Upload className="w-4 h-4" />
                <input type="file" accept="application/pdf" multiple className="hidden" onChange={(e) => {
                  const list = Array.from(e.target.files || []).slice(0, 12);
                  setFiles(list);
                }} />
                {files.length > 0 ? `${files.length} file(s)` : 'Select PDFs'}
              </label>
              <Button onClick={onUpload} disabled={loading || files.length === 0}>{loading ? 'Processing...' : 'Upload'}</Button>
            </div>
          )}
        </div>

        {!selected && (
          <Card className="slide-in">
            <CardHeader>
              <CardTitle>Statements</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="rounded-md border overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Filename</TableHead>
                      <TableHead>Labels</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Transactions</TableHead>
                      <TableHead>Uploaded</TableHead>
                      <TableHead></TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {statements.map((s) => (
                      <TableRow key={s.id}>
                        <TableCell className="font-medium">{s.original_filename}</TableCell>
                        <TableCell className="max-w-[280px] whitespace-nowrap text-muted-foreground overflow-hidden text-ellipsis">
                          {Array.isArray((s as any).labels) && (s as any).labels.length > 0 ? (s as any).labels.join(', ') : '-'}
                        </TableCell>
                        <TableCell>{formatStatus(s.status)}</TableCell>
                        <TableCell>{s.extracted_count}</TableCell>
                        <TableCell>{s.created_at ? format(new Date(s.created_at), 'PP p') : ''}</TableCell>
                        <TableCell className="text-right flex gap-2 justify-end">
                          <Button size="sm" variant="outline" onClick={() => openStatement(s.id)}>
                            <Eye className="w-4 h-4 mr-1" /> Open
                          </Button>
                          <Button size="sm" variant="outline" onClick={() => handlePreview(s.id)}>
                            <ExternalLink className="w-4 h-4 mr-1" /> Preview
                          </Button>
                          <Button size="sm" variant="outline" onClick={() => handleDownload(s.id, s.original_filename)}>
                            <Download className="w-4 h-4 mr-1" /> Download
                          </Button>
                          <Button
                            size="sm"
                            variant="destructive"
                            onClick={async () => {
                              if (!confirm('Delete this statement and its transactions?')) return;
                              try {
                                await bankStatementApi.delete(s.id);
                                toast.success('Statement deleted');
                                await loadList();
                                if (selected === s.id) {
                                  setSelected(null);
                                  setDetail(null);
                                  setRows([]);
                                }
                              } catch (e: any) {
                                toast.error(e?.message || 'Failed to delete statement');
                              }
                            }}
                          >
                            <Trash2 className="w-4 h-4 mr-1" /> Delete
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                    {statements.length === 0 && (
                      <TableRow>
                        <TableCell colSpan={6} className="text-center text-muted-foreground">No statements yet</TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>
        )}

        <Dialog open={previewOpen} onOpenChange={(open) => {
          setPreviewOpen(open);
          if (!open && previewObjectUrl) {
            URL.revokeObjectURL(previewObjectUrl);
            setPreviewObjectUrl(null);
            setPreviewUrl(null);
          }
        }}>
          <DialogContent className="max-w-5xl w-full h-[80vh] flex flex-col">
            <DialogHeader>
              <DialogTitle>Statement Preview</DialogTitle>
            </DialogHeader>
            <div className="w-full flex-1 min-h-0 mt-2">
              {previewUrl && (
                <>
                  <embed src={previewUrl} type="application/pdf" className="w-full h-full rounded-md border" />
                  <div className="mt-2 text-xs text-muted-foreground">
                    If the preview is blank, your browser may not support inline PDF viewing.{' '}
                    <a className="underline" href={previewUrl} target="_blank" rel="noopener noreferrer">Open in a new tab</a> or use Download.
                  </div>
                </>
              )}
            </div>
          </DialogContent>
        </Dialog>

        {selected && !showInvoiceForm && (
          <Card className="slide-in">
            <CardHeader className="flex flex-row items-center justify-between">
              <div className="space-y-1">
                <div className="flex items-center gap-3">
                  <Button variant="ghost" size="icon" onClick={() => { setSelected(null); setDetail(null); setRows([]); }}>
                    <ArrowLeft className="w-5 h-5" />
                  </Button>
                  <CardTitle>Transactions — {detail?.original_filename || ''}</CardTitle>
                </div>
                <p className="text-muted-foreground text-sm">Edit transactions and save</p>
              </div>
              <div className="flex items-center gap-2">
                {readOnly && (
                  <span className="text-sm text-muted-foreground">Processing… Editing is disabled until extraction completes.</span>
                )}
                <Button variant="outline" onClick={() => selected && handlePreview(selected)}>
                  <ExternalLink className="w-4 h-4 mr-1" /> Preview
                </Button>
                <Button variant="outline" onClick={() => selected && handleDownload(selected, detail?.original_filename)}>
                  <Download className="w-4 h-4 mr-1" /> Download
                </Button>
                {(detail?.status === 'failed' || (detail?.status === 'processed' && (detail?.extracted_count || 0) === 0)) && (
                  <Button
                    variant="destructive"
                    onClick={async () => {
                      if (!selected) return;
                      try {
                        await bankStatementApi.reprocess(selected);
                        toast.success('Reprocessing started');
                        await openStatement(selected);
                      } catch (e: any) {
                        toast.error(e?.message || 'Failed to start reprocessing');
                      }
                    }}
                  >
                    Process again
                  </Button>
                )}
                <Button variant="outline" onClick={exportToCSV} disabled={rows.length === 0}>
                  <FileText className="w-4 h-4 mr-1" /> Export CSV
                </Button>
                <Button variant="outline" onClick={addEmptyRow} disabled={readOnly}>Add Row</Button>
                <Button onClick={saveRows} disabled={readOnly || detailLoading}>{detailLoading ? 'Saving...' : 'Save'}</Button>
              </div>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
                <div className="flex flex-col gap-2">
                  <label className="text-sm text-muted-foreground">Labels (up to 10)</label>
                  <Input
                    value={statementLabels.join(', ')}
                    onChange={(e) => {
                      const parts = e.target.value.split(',').map(s => s.trim()).filter(Boolean).slice(0, 10);
                      setStatementLabels(parts);
                    }}
                    placeholder="Comma-separated labels"
                    disabled={readOnly}
                  />
                </div>
                <div className="md:col-span-2 flex flex-col gap-2">
                  <label className="text-sm text-muted-foreground">Notes</label>
                  <Textarea
                    value={statementNotes}
                    onChange={(e) => setStatementNotes(e.target.value)}
                    placeholder="Add any notes about this statement"
                    rows={3}
                    disabled={readOnly}
                  />
                </div>
                <div className="flex items-end">
                  <Button onClick={saveMeta} disabled={readOnly || detailLoading} className="w-full md:w-auto">{detailLoading ? 'Saving…' : 'Save Details'}</Button>
                </div>
              </div>
              {rows.length > 0 && (
                <div className="grid grid-cols-3 gap-4 mb-6 p-4 bg-muted/50 rounded-lg">
                  <div className="text-center">
                    <div className="text-2xl font-bold text-green-600">${totalIncome.toFixed(2)}</div>
                    <div className="text-sm text-muted-foreground">Total Income</div>
                  </div>
                  <div className="text-center">
                    <div className="text-2xl font-bold text-red-600">${totalExpense.toFixed(2)}</div>
                    <div className="text-sm text-muted-foreground">Total Expenses</div>
                  </div>
                  <div className="text-center">
                    <div className={`text-2xl font-bold ${netAmount >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                      ${netAmount.toFixed(2)}
                    </div>
                    <div className="text-sm text-muted-foreground">Net Amount</div>
                  </div>
                </div>
              )}
              <div className="rounded-md border overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>ID</TableHead>
                      <TableHead>Date</TableHead>
                      <TableHead>Description</TableHead>
                      <TableHead>Amount</TableHead>
                      <TableHead>Balance</TableHead>
                      <TableHead>Type</TableHead>
                      <TableHead>Category</TableHead>
                      <TableHead>Expense</TableHead>
                      <TableHead>Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {rows.map((r, idx) => (
                      <TableRow key={idx}>
                        <TableCell className="whitespace-nowrap text-muted-foreground">{(r as any).id ?? ''}</TableCell>
                        <TableCell>
                          <Popover>
                            <PopoverTrigger asChild>
                              <Button variant="outline" className="w-[160px] justify-start text-left font-normal" disabled={readOnly}>
                                <CalendarIcon className="mr-2 h-4 w-4" />
                                {r.date ? format(new Date(r.date), 'PPP') : 'Pick a date'}
                              </Button>
                            </PopoverTrigger>
                            {!readOnly && (
                              <PopoverContent className="w-auto p-0" align="start">
                                <Calendar
                                  mode="single"
                                  selected={r.date ? new Date(r.date) : undefined}
                                  onSelect={(d) => {
                                    if (!d) return;
                                    const iso = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate())).toISOString().split('T')[0];
                                    setRows(prev => prev.map((x, i) => i === idx ? { ...x, date: iso } : x));
                                  }}
                                  initialFocus
                                />
                              </PopoverContent>
                            )}
                          </Popover>
                        </TableCell>
                        <TableCell>
                          <Input value={r.description} onChange={(e) => setRows(prev => prev.map((x, i) => i === idx ? { ...x, description: e.target.value } : x))} />
                        </TableCell>
                        <TableCell>
                          <Input type="number" value={Number(r.amount)} onChange={(e) => setRows(prev => prev.map((x, i) => i === idx ? { ...x, amount: Number(e.target.value) } : x))} />
                        </TableCell>
                        <TableCell>
                          <Input type="number" value={r.balance ?? ''} onChange={(e) => setRows(prev => prev.map((x, i) => i === idx ? { ...x, balance: e.target.value === '' ? null : Number(e.target.value) } : x))} />
                        </TableCell>
                        <TableCell>
                          <Select value={r.transaction_type} onValueChange={(v) => setRows(prev => prev.map((x, i) => i === idx ? { ...x, transaction_type: v as 'debit' | 'credit' } : x))}>
                            <SelectTrigger className="w-[140px]"><SelectValue /></SelectTrigger>
                            <SelectContent>
                              <SelectItem value="debit">debit (expense)</SelectItem>
                              <SelectItem value="credit">credit (income)</SelectItem>
                            </SelectContent>
                          </Select>
                        </TableCell>
                        <TableCell>
                          <Select value={r.category || 'Other'} onValueChange={(v) => setRows(prev => prev.map((x, i) => i === idx ? { ...x, category: v } : x))}>
                            <SelectTrigger className="w-[180px]"><SelectValue /></SelectTrigger>
                            <SelectContent>
                              {CATEGORY_OPTIONS.map((c) => (<SelectItem key={c} value={c}>{c}</SelectItem>))}
                            </SelectContent>
                          </Select>
                        </TableCell>
                        <TableCell className="whitespace-nowrap text-muted-foreground">
                          {Boolean((r as any).expense_id) ? `#${(r as any).expense_id}` : '-'}
                        </TableCell>
                        <TableCell>
                          <div className="flex gap-1">
                            {r.transaction_type === 'debit' && (
                              <>
                                <Button
                                  size="sm"
                                  variant="outline"
                                  onClick={() => createExpenseFromTransaction(idx)}
                                  disabled={readOnly || Boolean((r as any).expense_id)}
                                >
                                  <Plus className="w-3 h-3 mr-1" />
                                  {Boolean((r as any).expense_id) ? `Expense #${(r as any).expense_id}` : 'Expense'}
                                </Button>
                                {Boolean((r as any).expense_id) && (
                                  <Button
                                    size="sm"
                                    variant="outline"
                                    onClick={async () => {
                                      try {
                                        await navigator.clipboard.writeText(String((r as any).expense_id));
                                        toast.success(`Copied Expense ID ${(r as any).expense_id}`);
                                      } catch (e) {
                                        toast.error('Failed to copy Expense ID');
                                      }
                                    }}
                                  >
                                    <Copy className="w-3 h-3 mr-1" />
                                    Copy Expense ID
                                  </Button>
                                )}
                              </>
                            )}
                            {r.transaction_type === 'credit' && (
                              <>
                                <Button
                                  size="sm"
                                  variant="outline"
                                  onClick={() => createInvoiceFromTransaction(idx)}
                                  disabled={readOnly || Boolean((r as any).invoice_id)}
                                >
                                  <Plus className="w-3 h-3 mr-1" />
                                  {Boolean((r as any).invoice_id) ? 'Invoice linked' : 'Invoice'}
                                </Button>
                                {Boolean((r as any).invoice_id) && (
                                  <Button
                                    size="sm"
                                    variant="outline"
                                    onClick={async () => {
                                      try {
                                        const invId = Number((r as any).invoice_id);
                                        const inv = await invoiceApi.getInvoice(invId);
                                        const toCopy = inv.number || String(invId);
                                        await navigator.clipboard.writeText(toCopy);
                                        toast.success(`Copied Invoice No ${toCopy}`);
                                      } catch (e) {
                                        toast.error('Failed to copy Invoice ID');
                                      }
                                    }}
                                  >
                                    <Copy className="w-3 h-3 mr-1" />
                                    Copy Invoice ID
                                  </Button>
                                )}
                              </>
                            )}
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                    {rows.length === 0 && (
                      <TableRow>
                        <TableCell colSpan={7} className="text-center text-muted-foreground">No transactions</TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>
        )}

        {showInvoiceForm && (
          <Card className="slide-in">
            <CardHeader className="flex flex-row items-center justify-between">
              <div className="space-y-1">
                <div className="flex items-center gap-3">
                  <Button variant="ghost" size="icon" onClick={() => { setShowInvoiceForm(false); setInvoiceInitialData(null); }}>
                    <ArrowLeft className="w-5 h-5" />
                  </Button>
                  <CardTitle>Create Invoice from Transaction</CardTitle>
                </div>
                <p className="text-muted-foreground text-sm">Create invoice from bank statement transaction</p>
              </div>
            </CardHeader>
            <CardContent>
              <InvoiceForm 
                initialData={invoiceInitialData}
                onInvoiceUpdate={async () => {
                  setShowInvoiceForm(false);
                  setInvoiceInitialData(null);
                  toast.success('Invoice created successfully!');
                  // Refresh the statement to reflect the linked invoice_id
                  if (selected) {
                    await openStatement(selected);
                  }
                }}
              />
            </CardContent>
          </Card>
        )}
      </div>
    </AppLayout>
  );
}


