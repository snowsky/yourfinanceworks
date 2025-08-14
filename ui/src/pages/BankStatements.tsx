import { useEffect, useState } from 'react';
import { AppLayout } from '@/components/layout/AppLayout';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Calendar } from '@/components/ui/calendar';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { CalendarIcon, Upload, ArrowLeft, Eye, Download, ExternalLink, Trash2 } from 'lucide-react';
import { format } from 'date-fns';
import { bankStatementApi, BankTransactionEntry, BankStatementDetail, BankStatementSummary } from '@/lib/api';
import { toast } from 'sonner';

const CATEGORY_OPTIONS = [
  'Income', 'Food', 'Transportation', 'Shopping', 'Bills', 'Healthcare', 'Entertainment', 'Financial', 'Travel', 'Other'
];

export default function BankStatements() {
  const [files, setFiles] = useState<File[]>([]);
  const [loading, setLoading] = useState(false);
  const [statements, setStatements] = useState<BankStatementSummary[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detail, setDetail] = useState<BankStatementDetail | null>(null);
  const [rows, setRows] = useState<BankTransactionEntry[]>([]);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewObjectUrl, setPreviewObjectUrl] = useState<string | null>(null);
  const readOnly = detail?.status === 'processing';

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
      setRows((s.transactions || []).map(t => ({
        date: t.date,
        description: t.description,
        amount: t.amount,
        transaction_type: (t.transaction_type === 'debit' || t.transaction_type === 'credit') ? t.transaction_type : (t.amount < 0 ? 'debit' : 'credit'),
        balance: t.balance ?? null,
        category: t.category ?? null,
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
                        <TableCell>{s.status}</TableCell>
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
                        <TableCell colSpan={5} className="text-center text-muted-foreground">No statements yet</TableCell>
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

        {selected && (
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
                <Button variant="outline" onClick={addEmptyRow} disabled={readOnly}>Add Row</Button>
                <Button onClick={saveRows} disabled={readOnly || detailLoading}>{detailLoading ? 'Saving...' : 'Save'}</Button>
              </div>
            </CardHeader>
            <CardContent>
              <div className="rounded-md border overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Date</TableHead>
                      <TableHead>Description</TableHead>
                      <TableHead>Amount</TableHead>
                      <TableHead>Balance</TableHead>
                      <TableHead>Type</TableHead>
                      <TableHead>Category</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {rows.map((r, idx) => (
                      <TableRow key={idx}>
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
                      </TableRow>
                    ))}
                    {rows.length === 0 && (
                      <TableRow>
                        <TableCell colSpan={6} className="text-center text-muted-foreground">No transactions</TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </AppLayout>
  );
}


