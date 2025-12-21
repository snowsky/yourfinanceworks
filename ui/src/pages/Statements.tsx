import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { AppLayout } from '@/components/layout/AppLayout';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from '@/components/ui/alert-dialog';
import { Calendar } from '@/components/ui/calendar';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { CalendarIcon, Upload, ArrowLeft, Eye, Download, ExternalLink, Trash2, FileText, Plus, Copy, X, Edit, MoreHorizontal, Loader2, ChevronDown, ChevronUp, ArrowDown } from 'lucide-react';
import { format, parseISO, isValid } from 'date-fns';
import { bankStatementApi, BankTransactionEntry, BankStatementDetail, BankStatementSummary, expenseApi, invoiceApi, clientApi, formatStatus, DeletedBankStatement } from '@/lib/api';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { Badge } from '@/components/ui/badge';
import { toast } from 'sonner';
import { InvoiceForm } from '@/components/invoices/InvoiceForm';
import { useFeatures } from '@/contexts/FeatureContext';
import { PageHeader } from '@/components/ui/professional-layout';
import { ProfessionalCard } from '@/components/ui/professional-card';
import { ProfessionalButton } from '@/components/ui/professional-button';

const CATEGORY_OPTIONS = [
  'Income', 'Food', 'Transportation', 'Shopping', 'Bills', 'Healthcare', 'Entertainment', 'Financial', 'Travel', 'Other'
];

const STATEMENT_PROVIDERS = [
  { value: 'bank', label: 'Bank', icon: '🏦' },
  { value: 'paypal', label: 'PayPal', icon: '💰' },
  { value: 'wise', label: 'Wise', icon: '🌍' },
  { value: 'stripe', label: 'Stripe', icon: '💳' },
  { value: 'square', label: 'Square', icon: '🔲' },
  { value: 'other', label: 'Other', icon: '📄' }
];

type BankRow = BankTransactionEntry & { id?: number; invoice_id?: number | null; expense_id?: number | null; backend_id?: number | null };

// Statement Upload Button with feature gating
function StatementUploadButton({ onUpload }: { onUpload: () => void }) {
  const { t } = useTranslation();
  const { isFeatureEnabled } = useFeatures();
  const hasFeature = isFeatureEnabled('ai_bank_statement');

  if (!hasFeature) {
    return (
      <div className="space-y-2">
        <ProfessionalButton disabled className="opacity-50 cursor-not-allowed">
          <Plus className="w-4 h-4 mr-2" />
          {t('statements.new_statement', { defaultValue: 'New Statement' })}
        </ProfessionalButton>
        <div className="bg-amber-50 border border-amber-200 rounded-md p-3 max-w-md">
          <p className="text-sm text-amber-800" dangerouslySetInnerHTML={{
            __html: t('settings.bank_statement_license_required', { defaultValue: 'License Required: Bank statement processing requires the AI Bank Statement feature. Please upgrade your license to enable this functionality.' })
              .replace('License Required:', '<strong>License Required:</strong>')
          }} />
        </div>
      </div>
    );
  }

  return (
    <ProfessionalButton onClick={onUpload}>
      <Plus className="w-4 h-4 mr-2" />
      {t('statements.new_statement', { defaultValue: 'New Statement' })}
    </ProfessionalButton>
  );
}

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

export default function Statements() {
  const { t } = useTranslation();
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
  const [previewType, setPreviewType] = useState<string | null>(null);
  const [previewText, setPreviewText] = useState<string | null>(null);
  const [previewLoading, setPreviewLoading] = useState<number | null>(null);
  const [clients, setClients] = useState<any[]>([]);
  const [showInvoiceForm, setShowInvoiceForm] = useState(false);
  const [invoiceInitialData, setInvoiceInitialData] = useState<any>(null);
  const [statementNotes, setStatementNotes] = useState<string>('');
  const [statementLabels, setStatementLabels] = useState<string[]>([]);
  const [newStatementLabel, setNewStatementLabel] = useState<string>('');
  const [editingRow, setEditingRow] = useState<number | null>(null);
  const [uploadModalOpen, setUploadModalOpen] = useState(false);
  const [selectedProvider, setSelectedProvider] = useState<string>('bank');
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [statementToDelete, setStatementToDelete] = useState<number | null>(null);
  const [reprocessingLocks, setReprocessingLocks] = useState<Set<number>>(new Set());
  const readOnly = detail?.status === 'processing';

  // Recycle bin state
  const [showRecycleBin, setShowRecycleBin] = useState(false);
  const [deletedStatements, setDeletedStatements] = useState<DeletedBankStatement[]>([]);
  const [recycleBinLoading, setRecycleBinLoading] = useState(false);
  const [statementToPermanentlyDelete, setStatementToPermanentlyDelete] = useState<number | null>(null);
  const [emptyRecycleBinModalOpen, setEmptyRecycleBinModalOpen] = useState(false);

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
        status: 'completed',
        analysis_status: 'done'
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
      // Reassign IDs to start from 1 for consistent frontend display
      const transactionsWithIds = (s.transactions || []).map((t, index) => ({
        id: index + 1, // Always start from 1
        date: t.date,
        description: t.description,
        amount: t.amount,
        transaction_type: (t.transaction_type === 'debit' || t.transaction_type === 'credit') ? t.transaction_type : (t.amount < 0 ? 'debit' : 'credit'),
        balance: t.balance ?? null,
        category: t.category ?? null,
        invoice_id: (t as any).invoice_id ?? null,
        expense_id: (t as any).expense_id ?? null,
        backend_id: (t as any).id, // Preserve original backend ID for API calls
      }));
      setRows(transactionsWithIds);
    } catch (e: any) {
      toast.error(e?.message || 'Failed to load statement');
      setSelected(null);
    } finally {
      setDetailLoading(false);
    }
  };

  const onUpload = async () => {
    const addNotification = (window as any).addAINotification;
    try {
      if (files.length === 0) { toast.error(t('statements.select_files')); return; }
      setLoading(true);

      const providerName = STATEMENT_PROVIDERS.find(p => p.value === selectedProvider)?.label || 'Statement';
      addNotification?.('processing', t('statements.processing'), `Analyzing ${files.length} ${providerName.toLowerCase()} statement files with AI...`);

      const resp = await bankStatementApi.uploadAndExtract(files);

      addNotification?.('success', `${providerName} ${t('statements.upload')}`, `Successfully uploaded ${files.length} statement files. AI extraction in progress.`);
      toast.success(`Uploaded ${files.length} ${providerName.toLowerCase()} ${t('statements.statements').toLowerCase()}`);
      setFiles([]);
      setUploadModalOpen(false);
      await loadList();
    } catch (e: any) {
      addNotification?.('error', t('statements.failed_to_delete'), `Failed to process statements: ${e?.message || 'Unknown error'}`);
      toast.error(e?.message || 'Failed to extract transactions');
    } finally {
      setLoading(false);
    }
  };

  const addEmptyRow = () => {
    const today = new Date();
    const iso = formatDateToISO(today);
    setRows(prev => {
      // Add new row at the top, then reassign all IDs to start from 1
      const newRowsWithoutIds = [{
        date: iso,
        description: '',
        amount: 0,
        transaction_type: 'debit' as 'debit',
        balance: null,
        category: 'Other',
        backend_id: null // New row, no backend ID yet
      }, ...prev];

      // Reassign all IDs to start from 1
      const newRowsWithIds = newRowsWithoutIds.map((row, index) => ({
        ...row,
        id: index + 1
      }));

      // Set the newly added row (now at index 0) as editing
      setEditingRow(0);
      return newRowsWithIds;
    });
  };

  const saveRows = async () => {
    if (!selected) return;
    try {
      setDetailLoading(true);
      const cleaned = rows.map(r => ({
        ...r,
        id: r.backend_id || undefined, // Use backend_id for API, or let backend assign new ID
        balance: r.balance === undefined ? null : r.balance,
        category: r.category || null,
        invoice_id: r.invoice_id ?? null,
        expense_id: r.expense_id ?? null,
      }));
      await bankStatementApi.replaceTransactions(selected, cleaned);
      toast.success('Transactions saved');
      // Refresh detail and list counts but preserve frontend ID sequence
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

  const confirmDeleteStatement = async () => {
    if (!statementToDelete) return;

    try {
      await bankStatementApi.delete(statementToDelete);
      toast.success(t('statements.statement_deleted'));
      await loadList();
      // Refresh recycle bin if it's currently open
      if (showRecycleBin) {
        fetchDeletedStatements();
      }
      if (selected === statementToDelete) {
        setSelected(null);
        setDetail(null);
        setRows([]);
      }
    } catch (e: any) {
      toast.error(e?.message || t('statements.failed_to_delete'));
    } finally {
      setDeleteModalOpen(false);
      setStatementToDelete(null);
    }
  };

  // Recycle bin functions
  const fetchDeletedStatements = async () => {
    try {
      setRecycleBinLoading(true);
      const data = await bankStatementApi.getDeletedStatements();
      setDeletedStatements(data);
    } catch (error) {
      console.error('Failed to fetch deleted statements:', error);
      toast.error('Failed to load recycle bin');
    } finally {
      setRecycleBinLoading(false);
    }
  };

  const handleRestoreStatement = async (statementId: number) => {
    try {
      await bankStatementApi.restoreStatement(statementId, 'processed');
      toast.success('Statement restored successfully');
      fetchDeletedStatements();
      loadList(); // Refresh main list
    } catch (error: any) {
      console.error('Failed to restore statement:', error);
      toast.error(error?.message || 'Failed to restore statement');
    }
  };

  const handlePermanentlyDeleteStatement = async (statementId: number) => {
    try {
      await bankStatementApi.permanentlyDeleteStatement(statementId);
      toast.success('Statement permanently deleted');
      fetchDeletedStatements();
      setStatementToPermanentlyDelete(null);
    } catch (error: any) {
      console.error('Failed to permanently delete statement:', error);
      toast.error(error?.message || 'Failed to permanently delete statement');
    }
  };

  const handleEmptyRecycleBin = () => {
    setEmptyRecycleBinModalOpen(true);
  };

  const confirmEmptyRecycleBin = async () => {
    try {
      const response = await bankStatementApi.emptyRecycleBin();
      toast.success('Recycle bin emptied successfully');
      fetchDeletedStatements();
      setEmptyRecycleBinModalOpen(false);
    } catch (error: any) {
      console.error('Failed to empty recycle bin:', error);
      toast.error(error?.message || 'Failed to empty recycle bin');
    }
  };

  const handleToggleRecycleBin = () => {
    setShowRecycleBin(!showRecycleBin);
    if (!showRecycleBin) {
      fetchDeletedStatements();
    }
  };

  // DRY helpers for preview/download
  const handlePreview = async (id: number) => {
    try {
      setPreviewLoading(id);
      const { blob, contentType } = await bankStatementApi.fetchFileBlob(id, true);
      const type = contentType || blob.type || 'application/pdf';
      setPreviewType(type);
      if (previewObjectUrl) URL.revokeObjectURL(previewObjectUrl);
      if (type.includes('text/csv')) {
        const text = await blob.text();
        setPreviewText(text);
        setPreviewUrl(null);
        setPreviewObjectUrl(null);
      } else {
        const objectUrl = URL.createObjectURL(blob);
        setPreviewObjectUrl(objectUrl);
        setPreviewUrl(objectUrl);
        setPreviewText(null);
      }
      setPreviewOpen(true);
    } catch (e: any) {
      toast.error(e?.message || t('statements.failed_to_preview'));
    } finally {
      setPreviewLoading(null);
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
      toast.error(e?.message || t('statements.failed_to_download'));
    }
  };

  return (
    <AppLayout>
      <div className="h-full space-y-6 fade-in">

        <PageHeader
          title={t('statements.title')}
          description={t('statements.description')}
          actions={!selected && (
            <div className="flex gap-2">
              <ProfessionalButton
                variant="outline"
                onClick={handleToggleRecycleBin}
                className="whitespace-nowrap"
              >
                <Trash2 className="mr-2 h-4 w-4" />
                {t('recycleBin.title', { defaultValue: 'Recycle Bin' })}
                {showRecycleBin ? <ChevronUp className="ml-2 h-4 w-4" /> : <ChevronDown className="ml-2 h-4 w-4" />}
              </ProfessionalButton>
              <StatementUploadButton onUpload={() => setUploadModalOpen(true)} />
            </div>
          )}
        />

        {/* Recycle Bin Section */}
        <Collapsible open={showRecycleBin} onOpenChange={setShowRecycleBin}>
          <CollapsibleContent>
            <ProfessionalCard className="slide-in">
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="flex items-center gap-2">
                      <Trash2 className="w-5 h-5" />
                      {t('recycleBin.title', { defaultValue: 'Recycle Bin' })}
                    </CardTitle>
                    <p className="text-muted-foreground text-sm">{t('recycleBin.description', { defaultValue: 'Deleted statements that can be restored or permanently deleted' })}</p>
                  </div>
                  <ProfessionalButton
                    variant="destructive"
                    size="sm"
                    onClick={handleEmptyRecycleBin}
                    className="gap-2"
                  >
                    <Trash2 className="h-4 w-4" />
                    {t('recycleBin.empty_recycle_bin', { defaultValue: 'Empty Recycle Bin' })}
                  </ProfessionalButton>
                </div>
              </CardHeader>
              <CardContent>
                {recycleBinLoading ? (
                  <div className="flex justify-center items-center h-24">
                    <Loader2 className="h-6 w-6 animate-spin mr-2" />
                    {t('recycleBin.loading', { defaultValue: 'Loading...' })}
                  </div>
                ) : deletedStatements.length === 0 ? (
                  <div className="flex flex-col items-center justify-center h-24 text-center">
                    <Trash2 className="h-8 w-8 text-muted-foreground mb-2" />
                    <p className="text-muted-foreground">{t('recycleBin.recycle_bin_empty', { defaultValue: 'Recycle bin is empty' })}</p>
                  </div>
                ) : (
                  <div className="rounded-md border overflow-x-auto">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>{t('statements.filename')}</TableHead>
                          <TableHead>{t('statements.status')}</TableHead>
                          <TableHead>{t('statements.transactions')}</TableHead>
                          <TableHead>{t('recycleBin.deleted_at')}</TableHead>
                          <TableHead>{t('recycleBin.deleted_by')}</TableHead>
                          <TableHead>{t('recycleBin.actions')}</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {deletedStatements.map((statement) => (
                          <TableRow key={statement.id}>
                            <TableCell className="font-medium">{statement.original_filename}</TableCell>
                            <TableCell>{formatStatus(statement.status)}</TableCell>
                            <TableCell>{statement.extracted_count}</TableCell>
                            <TableCell>{statement.deleted_at ? format(new Date(statement.deleted_at), 'PP p') : 'N/A'}</TableCell>
                            <TableCell>{statement.deleted_by_username || t('common.unknown')}</TableCell>
                            <TableCell>
                              <div className="flex items-center gap-2">
                                <Button
                                  variant="outline"
                                  size="sm"
                                  onClick={() => handleRestoreStatement(statement.id)}
                                  className="text-green-600 hover:text-green-700 hover:bg-green-50"
                                >
                                  <ArrowDown className="w-4 h-4 mr-1" />
                                  {t('recycleBin.restore', { defaultValue: 'Restore' })}
                                </Button>
                                <AlertDialog>
                                  <AlertDialogTrigger asChild>
                                    <Button
                                      variant="outline"
                                      size="sm"
                                      className="text-red-600 hover:text-red-700 hover:bg-red-50"
                                    >
                                      <Trash2 className="w-4 h-4 mr-1" />
                                      {t('recycleBin.permanently_delete', { defaultValue: 'Delete' })}
                                    </Button>
                                  </AlertDialogTrigger>
                                  <AlertDialogContent>
                                    <AlertDialogHeader>
                                      <AlertDialogTitle>{t('recycleBin.permanent_delete_confirm_title', { defaultValue: 'Permanently Delete Statement' })}</AlertDialogTitle>
                                      <AlertDialogDescription>
                                        {t('recycleBin.permanent_delete_confirm_description', { defaultValue: 'Are you sure you want to permanently delete this statement? This action cannot be undone.' })}
                                      </AlertDialogDescription>
                                    </AlertDialogHeader>
                                    <AlertDialogFooter>
                                      <AlertDialogCancel>{t('common.cancel')}</AlertDialogCancel>
                                      <AlertDialogAction
                                        onClick={() => handlePermanentlyDeleteStatement(statement.id)}
                                        className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                                      >
                                        <Trash2 className="mr-2 h-4 w-4" />
                                        {t('recycleBin.permanently_delete', { defaultValue: 'Delete Permanently' })}
                                      </AlertDialogAction>
                                    </AlertDialogFooter>
                                  </AlertDialogContent>
                                </AlertDialog>
                              </div>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                )}
              </CardContent>
            </ProfessionalCard>
          </CollapsibleContent>
        </Collapsible>

        {!selected && (
          <ProfessionalCard className="slide-in">
            <CardHeader>
              <CardTitle>{t('statements.list_title')}</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="rounded-md border overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>{t('statements.filename')}</TableHead>
                      <TableHead>{t('statements.labels')}</TableHead>
                      <TableHead>{t('statements.status')}</TableHead>
                      <TableHead>{t('statements.transactions')}</TableHead>
                      <TableHead className="hidden lg:table-cell">{t('common.created_by')}</TableHead>
                      <TableHead>{t('statements.uploaded')}</TableHead>
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
                        <TableCell className="hidden lg:table-cell text-sm text-muted-foreground">
                          {s.created_by_username || s.created_by_email || t('common.unknown')}
                        </TableCell>
                        <TableCell>{s.created_at ? format(new Date(s.created_at), 'PP p') : ''}</TableCell>
                        <TableCell className="text-right flex gap-2 justify-end">
                          <Button size="sm" variant="outline" onClick={() => openStatement(s.id)}>
                            <Eye className="w-4 h-4 mr-1" /> {t('statements.open')}
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => handlePreview(s.id)}
                            disabled={previewLoading === s.id}
                          >
                            {previewLoading === s.id ? (
                              <>
                                <div className="w-4 h-4 mr-1 border-2 border-current border-t-transparent rounded-full animate-spin" />
                                Loading...
                              </>
                            ) : (
                              <>
                                <ExternalLink className="w-4 h-4 mr-1" /> {t('statements.preview')}
                              </>
                            )}
                          </Button>
                          <Button size="sm" variant="outline" onClick={() => handleDownload(s.id, s.original_filename)}>
                            <Download className="w-4 h-4 mr-1" /> {t('statements.download')}
                          </Button>
                          <Button
                            size="sm"
                            variant="destructive"
                            onClick={() => {
                              setStatementToDelete(s.id);
                              setDeleteModalOpen(true);
                            }}
                          >
                            <Trash2 className="w-4 h-4 mr-1" /> {t('statements.delete')}
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                    {statements.length === 0 && (
                      <TableRow>
                        <TableCell colSpan={7} className="h-auto p-0 border-none">
                          <div className="text-center py-20 bg-muted/5 rounded-xl border-2 border-dashed border-muted-foreground/20 m-4">
                            <div className="bg-primary/10 w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-4">
                              <FileText className="h-8 w-8 text-primary" />
                            </div>
                            <h3 className="text-xl font-bold mb-2">{t('statements.no_statements', 'No statements yet')}</h3>
                            <p className="text-muted-foreground max-w-sm mx-auto">
                              {t('statements.no_statements_description', 'Upload your bank statements to automatically extract transactions and link them to invoices or expenses.')}
                            </p>
                          </div>
                        </TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </ProfessionalCard>
        )}

        <Dialog open={previewOpen} onOpenChange={(open) => {
          setPreviewOpen(open);
          if (!open) {
            if (previewObjectUrl) {
              URL.revokeObjectURL(previewObjectUrl);
            }
            setPreviewObjectUrl(null);
            setPreviewUrl(null);
            setPreviewText(null);
            setPreviewType(null);
          }
        }}>
          <DialogContent className="max-w-5xl w-full h-[80vh] flex flex-col">
            <DialogHeader>
              <DialogTitle>{t('statements.preview_title')}</DialogTitle>
            </DialogHeader>
            <div className="w-full flex-1 min-h-0 mt-2">
              {previewText && (
                <div className="w-full h-full overflow-auto rounded-md border p-3 bg-muted/40 whitespace-pre text-xs font-mono">
                  {previewText}
                </div>
              )}
              {!previewText && previewUrl && (
                <>
                  <embed src={previewUrl} type={previewType || 'application/pdf'} className="w-full h-full rounded-md border" />
                  <div className="mt-2 text-xs text-muted-foreground">
                    {t('statements.preview_blank_note')}{' '}
                    <a className="underline" href={previewUrl} target="_blank" rel="noopener noreferrer">{t('statements.open_new_tab')}</a> or use Download.
                  </div>
                </>
              )}
            </div>
          </DialogContent>
        </Dialog>

        {selected && !showInvoiceForm && (
          <ProfessionalCard className="slide-in">
            <CardHeader className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <Button variant="ghost" size="icon" onClick={() => { setSelected(null); setDetail(null); setRows([]); }}>
                    <ArrowLeft className="w-5 h-5" />
                  </Button>
                  <div>
                    <CardTitle>{t('statements.transactions_title', { filename: detail?.original_filename || '' })}</CardTitle>
                    <div className="flex flex-col gap-1 mt-1">
                      <p className="text-muted-foreground text-sm">{t('statements.transactions_description')}</p>
                      {((detail as any)?.created_by_username || (detail as any)?.created_by_email) && (
                        <p className="text-muted-foreground text-sm">
                          {t('common.created_by')}: {(detail as any).created_by_username || (detail as any).created_by_email}
                        </p>
                      )}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    onClick={() => selected && handlePreview(selected)}
                    disabled={previewLoading === selected}
                  >
                    {previewLoading === selected ? (
                      <>
                        <div className="w-4 h-4 mr-1 border-2 border-current border-t-transparent rounded-full animate-spin" />
                        Loading...
                      </>
                    ) : (
                      <>
                        <ExternalLink className="w-4 h-4 mr-1" /> {t('statements.preview')}
                      </>
                    )}
                  </Button>
                  <Button variant="outline" onClick={() => selected && handleDownload(selected, detail?.original_filename)}>
                    <Download className="w-4 h-4 mr-1" /> {t('statements.download')}
                  </Button>
                </div>
              </div>

              <div className="bg-blue-50 border border-blue-200 rounded-md p-3">
                <p className="text-sm text-blue-800">
                  <strong>Note:</strong> Transaction information should match the uploaded bank statement file. Only edit if corrections are needed.
                </p>
              </div>

              {readOnly && (
                <div className="bg-amber-50 border border-amber-200 rounded-md p-3">
                  <p className="text-sm text-amber-800">
                    <strong>Processing…</strong> Editing is disabled until extraction completes.
                  </p>
                </div>
              )}

              <div className="flex items-center justify-between">
                <div className="text-sm text-muted-foreground">
                  Edit transactions and save
                </div>
                <div className="flex items-center gap-2">
                  {(detail?.status === 'failed' || detail?.status === 'processed') && (
                    <Button
                      variant="destructive"
                      onClick={async () => {
                        if (!selected) return;

                        // Check if already processing
                        if (reprocessingLocks.has(selected)) {
                          toast.warning('This statement is already being processed. Please wait for the current processing to complete.');
                          return;
                        }

                        const addNotification = (window as any).addAINotification;
                        try {
                          // Add to processing locks to prevent multiple clicks
                          setReprocessingLocks(prev => new Set([...prev, selected]));

                          addNotification?.('processing', 'Reprocessing Statement', `Re-analyzing ${detail?.original_filename} with AI...`);

                          await bankStatementApi.reprocess(selected);

                          addNotification?.('success', 'Statement Reprocessing Started', `Successfully started reprocessing ${detail?.original_filename}`);
                          toast.success('Reprocessing started');
                          await openStatement(selected);

                          // Remove from processing locks after a delay
                          setTimeout(() => {
                            setReprocessingLocks(prev => {
                              const newLocks = new Set(prev);
                              newLocks.delete(selected);
                              return newLocks;
                            });
                          }, 30000); // Remove lock after 30 seconds

                        } catch (e: any) {
                          // Remove from processing locks on error
                          setReprocessingLocks(prev => {
                            const newLocks = new Set(prev);
                            newLocks.delete(selected);
                            return newLocks;
                          });

                          // Handle specific lock error messages
                          const errorMessage = e?.message || 'Failed to start reprocessing';
                          if (errorMessage.includes('already being processed') || errorMessage.includes('processing lock')) {
                            toast.error('This statement is currently being processed by another operation. Please try again in a few minutes.');
                            addNotification?.('warning', 'Processing Lock Active', 'This statement is already being processed. Please wait and try again.');
                          } else {
                            addNotification?.('error', 'Reprocessing Failed', `Failed to reprocess ${detail?.original_filename}: ${errorMessage}`);
                            toast.error(errorMessage);
                          }
                        }
                      }}
                      disabled={reprocessingLocks.has(selected) || loading}
                    >
                      {reprocessingLocks.has(selected) ? (
                        <div className="flex items-center gap-1">
                          <div className="w-3 h-3 border-2 border-current border-t-transparent rounded-full animate-spin" />
                          Processing...
                        </div>
                      ) : (
                        'Process again'
                      )}
                    </Button>
                  )}
                  <Button variant="outline" onClick={exportToCSV} disabled={rows.length === 0}>
                    <FileText className="w-4 h-4 mr-1" /> Export CSV
                  </Button>
                  <Button variant="outline" onClick={addEmptyRow} disabled={readOnly}>Add Row</Button>
                  <Button onClick={saveRows} disabled={readOnly || detailLoading}>{detailLoading ? 'Saving...' : 'Save'}</Button>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
                <div className="flex flex-col gap-2">
                  <label className="text-sm text-muted-foreground">Labels (up to 10)</label>
                  <div className="flex flex-wrap items-center gap-2">
                    {statementLabels.slice(0, 10).map((lab, idx) => (
                      <Badge key={`stmt-lab-${idx}`} variant="secondary" className="text-xs">
                        {lab}
                        {!readOnly && (
                          <button
                            className="ml-1 text-muted-foreground hover:text-foreground"
                            aria-label="Remove"
                            onClick={async () => {
                              try {
                                const next = statementLabels.filter((l) => l !== lab);
                                if (!selected) return;
                                const resp = await bankStatementApi.updateMeta(selected, { labels: next });
                                setStatementLabels((resp.statement as any).labels || []);
                                setDetail(prev => prev ? { ...prev, labels: (resp.statement as any).labels || [] } : prev);
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
                    {!readOnly && (
                      <Input
                        placeholder="Add label"
                        value={newStatementLabel}
                        className="w-[160px] h-8"
                        onChange={(ev) => setNewStatementLabel(ev.target.value)}
                        onKeyDown={async (ev) => {
                          if (ev.key === 'Enter') {
                            const raw = (newStatementLabel || '').trim();
                            if (!raw) return;
                            const existing = statementLabels || [];
                            if (existing.includes(raw)) { setNewStatementLabel(''); return; }
                            if (existing.length >= 10) { toast.error('Maximum of 10 labels reached'); return; }
                            try {
                              if (!selected) return;
                              const next = [...existing, raw];
                              const resp = await bankStatementApi.updateMeta(selected, { labels: next });
                              setStatementLabels((resp.statement as any).labels || []);
                              setDetail(prev => prev ? { ...prev, labels: (resp.statement as any).labels || [] } : prev);
                              setNewStatementLabel('');
                            } catch (err: any) {
                              toast.error(err?.message || 'Failed to add label');
                            }
                          }
                        }}
                      />
                    )}
                  </div>
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
                <div className="grid grid-cols-4 gap-4 mb-6 p-4 bg-muted/50 rounded-lg">
                  <div className="text-center">
                    <div className="text-2xl font-bold">{rows.length}</div>
                    <div className="text-sm text-muted-foreground">Transactions</div>
                  </div>
                  <div className="text-center">
                    <div className="text-2xl font-bold text-green-600">${totalIncome.toFixed(2)}</div>
                    <div className="text-sm text-muted-foreground">Total Income</div>
                  </div>
                  <div className="text-center">
                    <div className="text-2xl font-bold text-red-600">${totalExpense.toFixed(2)}</div>
                    <div className="text-sm text-muted-foreground">Total Expenses</div>
                  </div>
                  <div className="text-center">
                    <div className={`text-2xl font-bold ${netAmount >= 0 ? 'text-green-600' : 'text-red-600'}`}>${netAmount.toFixed(2)}</div>
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
                          {editingRow === idx ? (
                            <Popover>
                              <PopoverTrigger asChild>
                                <Button variant="outline" className="w-[200px] justify-start text-left font-normal" disabled={readOnly}>
                                  <CalendarIcon className="mr-2 h-4 w-4" />
                                  {r.date ? format(safeParseDateString(r.date), 'PPP') : 'Pick a date'}
                                </Button>
                              </PopoverTrigger>
                              {!readOnly && (
                                <PopoverContent className="w-auto p-0" align="start">
                                  <Calendar
                                    mode="single"
                                    selected={r.date ? safeParseDateString(r.date) : undefined}
                                    defaultMonth={r.date ? safeParseDateString(r.date) : undefined}
                                    onSelect={(d) => {
                                      if (!d) return;
                                      // Format date without timezone conversion to preserve user's selected date
                                      const iso = formatDateToISO(d);
                                      setRows(prev => prev.map((x, i) => i === idx ? { ...x, date: iso } : x));
                                    }}
                                    initialFocus
                                  />
                                </PopoverContent>
                              )}
                            </Popover>
                          ) : (
                            <span className="text-sm">{r.date ? format(safeParseDateString(r.date), 'PPP') : 'No date'}</span>
                          )}
                        </TableCell>
                        <TableCell>
                          {editingRow === idx ? (
                            <div className="space-y-1">
                              <Textarea
                                value={r.description}
                                onChange={(e) => setRows(prev => prev.map((x, i) => i === idx ? { ...x, description: e.target.value } : x))}
                                rows={3}
                                maxLength={500}
                                className="min-w-[200px]"
                              />
                              <div className="text-xs text-muted-foreground">{r.description.length}/500 characters</div>
                            </div>
                          ) : (
                            <span className="text-sm">{r.description}</span>
                          )}
                        </TableCell>
                        <TableCell>
                          {editingRow === idx ? (
                            <Input type="number" value={Number(r.amount)} onChange={(e) => setRows(prev => prev.map((x, i) => i === idx ? { ...x, amount: Number(e.target.value) } : x))} />
                          ) : (
                            <span className="text-sm">${r.amount}</span>
                          )}
                        </TableCell>
                        <TableCell>
                          {editingRow === idx ? (
                            <Input type="number" value={r.balance ?? ''} onChange={(e) => setRows(prev => prev.map((x, i) => i === idx ? { ...x, balance: e.target.value === '' ? null : Number(e.target.value) } : x))} />
                          ) : (
                            <span className="text-sm">{r.balance ?? 'N/A'}</span>
                          )}
                        </TableCell>
                        <TableCell>
                          {editingRow === idx ? (
                            <Select value={r.transaction_type} onValueChange={(v) => setRows(prev => prev.map((x, i) => i === idx ? { ...x, transaction_type: v as 'debit' | 'credit' } : x))}>
                              <SelectTrigger className="w-[140px]"><SelectValue /></SelectTrigger>
                              <SelectContent>
                                <SelectItem value="debit">Debit (expense)</SelectItem>
                                <SelectItem value="credit">Credit (income)</SelectItem>
                              </SelectContent>
                            </Select>
                          ) : (
                            <span className="text-sm">{r.transaction_type === 'debit' ? 'Debit (expense)' : 'Credit (income)'}</span>
                          )}
                        </TableCell>
                        <TableCell>
                          {editingRow === idx ? (
                            <Select value={r.category || 'Other'} onValueChange={(v) => setRows(prev => prev.map((x, i) => i === idx ? { ...x, category: v } : x))}>
                              <SelectTrigger className="w-[180px]"><SelectValue /></SelectTrigger>
                              <SelectContent>
                                {CATEGORY_OPTIONS.map((c) => (<SelectItem key={c} value={c}>{c}</SelectItem>))}
                              </SelectContent>
                            </Select>
                          ) : (
                            <span className="text-sm">{r.category || 'Other'}</span>
                          )}
                        </TableCell>
                        <TableCell className="whitespace-nowrap text-muted-foreground">
                          {Boolean((r as any).expense_id) ? `#${(r as any).expense_id}` : '-'}
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            {editingRow === idx ? (
                              <Button
                                size="sm"
                                onClick={async () => {
                                  setEditingRow(null);
                                  await saveRows();
                                }}
                                disabled={readOnly}
                              >
                                Done
                              </Button>
                            ) : (
                              <DropdownMenu>
                                <DropdownMenuTrigger asChild>
                                  <Button variant="ghost" className="h-8 w-8 p-0" disabled={readOnly}>
                                    <span className="sr-only">Open menu</span>
                                    <MoreHorizontal className="h-4 w-4" />
                                  </Button>
                                </DropdownMenuTrigger>
                                <DropdownMenuContent align="end">
                                  <DropdownMenuItem
                                    onClick={() => setEditingRow(idx)}
                                    disabled={readOnly}
                                  >
                                    <Edit className="w-4 h-4 mr-2" />
                                    Edit
                                  </DropdownMenuItem>

                                  <DropdownMenuSeparator />

                                  {r.transaction_type === 'debit' && (
                                    <>
                                      <DropdownMenuItem
                                        onClick={() => createExpenseFromTransaction(idx)}
                                        disabled={readOnly || Boolean((r as any).expense_id)}
                                      >
                                        <Plus className="w-4 h-4 mr-2" />
                                        {Boolean((r as any).expense_id) ? `Expense #${(r as any).expense_id}` : 'Add to Expense'}
                                      </DropdownMenuItem>
                                      {Boolean((r as any).expense_id) && (
                                        <>
                                          <DropdownMenuItem
                                            onClick={async () => {
                                              try {
                                                await navigator.clipboard.writeText(String((r as any).expense_id));
                                                toast.success(`Copied Expense ID ${(r as any).expense_id}`);
                                              } catch (e) {
                                                toast.error('Failed to copy Expense ID');
                                              }
                                            }}
                                          >
                                            <Copy className="w-4 h-4 mr-2" />
                                            Copy Expense ID
                                          </DropdownMenuItem>
                                          <DropdownMenuItem
                                            onClick={async () => {
                                              if (!confirm('Are you sure you want to delete this expense? This action cannot be undone.')) return;
                                              try {
                                                const expenseId = (r as any).expense_id;
                                                // Delete the expense
                                                await expenseApi.deleteExpense(expenseId);
                                                toast.success(`Expense #${expenseId} deleted successfully`);

                                                // Unlink the expense from the transaction
                                                const updatedRows: BankRow[] = rows.map((row, i) =>
                                                  i === idx ? { ...row, expense_id: null } : row
                                                );
                                                setRows(updatedRows);

                                                // Persist the unlink to backend
                                                if (selected) {
                                                  try {
                                                    const cleaned = updatedRows.map(row => ({
                                                      ...row,
                                                      balance: row.balance === undefined ? null : row.balance,
                                                      category: row.category || null,
                                                      invoice_id: row.invoice_id ?? null,
                                                      expense_id: row.expense_id ?? null,
                                                    }));
                                                    await bankStatementApi.replaceTransactions(selected, cleaned);
                                                    // Reload to confirm changes
                                                    await openStatement(selected);
                                                  } catch (linkErr: any) {
                                                    console.error('Failed to persist expense unlink:', linkErr);
                                                  }
                                                }
                                              } catch (e: any) {
                                                toast.error(e?.message || 'Failed to delete expense');
                                              }
                                            }}
                                            className="text-red-600 focus:text-red-600"
                                          >
                                            <Trash2 className="w-4 h-4 mr-2" />
                                            Delete Expense
                                          </DropdownMenuItem>
                                        </>
                                      )}
                                    </>
                                  )}

                                  {r.transaction_type === 'credit' && (
                                    <>
                                      <DropdownMenuItem
                                        onClick={() => createInvoiceFromTransaction(idx)}
                                        disabled={readOnly || Boolean((r as any).invoice_id)}
                                      >
                                        <Plus className="w-4 h-4 mr-2" />
                                        {Boolean((r as any).invoice_id) ? 'Invoice linked' : 'Add to Invoice'}
                                      </DropdownMenuItem>
                                      {Boolean((r as any).invoice_id) && (
                                        <>
                                          <DropdownMenuItem
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
                                            <Copy className="w-4 h-4 mr-2" />
                                            Copy Invoice ID
                                          </DropdownMenuItem>
                                          <DropdownMenuItem
                                            onClick={async () => {
                                              if (!confirm('Are you sure you want to delete this invoice? This action cannot be undone.')) return;
                                              try {
                                                const invoiceId = Number((r as any).invoice_id);
                                                // Delete the invoice
                                                await invoiceApi.deleteInvoice(invoiceId);
                                                toast.success(`Invoice #${invoiceId} deleted successfully`);

                                                // Unlink the invoice from the transaction
                                                const updatedRows: BankRow[] = rows.map((row, i) =>
                                                  i === idx ? { ...row, invoice_id: null } : row
                                                );
                                                setRows(updatedRows);

                                                // Persist the unlink to backend
                                                if (selected) {
                                                  try {
                                                    const cleaned = updatedRows.map(row => ({
                                                      ...row,
                                                      balance: row.balance === undefined ? null : row.balance,
                                                      category: row.category || null,
                                                      invoice_id: row.invoice_id ?? null,
                                                      expense_id: row.expense_id ?? null,
                                                    }));
                                                    await bankStatementApi.replaceTransactions(selected, cleaned);
                                                    // Reload to confirm changes
                                                    await openStatement(selected);
                                                  } catch (linkErr: any) {
                                                    console.error('Failed to persist invoice unlink:', linkErr);
                                                  }
                                                }
                                              } catch (e: any) {
                                                // Check if it's the linked expenses error and use translated version
                                                let errorMessage = e?.message || 'Failed to delete invoice';
                                                if (errorMessage.includes('linked expenses')) {
                                                  errorMessage = t('invoices.delete_error_linked_expenses');
                                                }
                                                toast.error(errorMessage);
                                              }
                                            }}
                                            className="text-red-600 focus:text-red-600"
                                          >
                                            <Trash2 className="w-4 h-4 mr-2" />
                                            Delete Invoice
                                          </DropdownMenuItem>
                                        </>
                                      )}
                                    </>
                                  )}
                                </DropdownMenuContent>
                              </DropdownMenu>
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
          </ProfessionalCard>
        )}

        {showInvoiceForm && (
          <ProfessionalCard className="slide-in">
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
          </ProfessionalCard>
        )}

        {/* Upload Modal */}
        <Dialog open={uploadModalOpen} onOpenChange={(open) => {
          setUploadModalOpen(open);
          if (!open) {
            setFiles([]);
            setSelectedProvider('bank');
          }
        }}>
          <DialogContent className="sm:max-w-md">
            <DialogHeader>
              <DialogTitle>{t('statements.upload_statement', { defaultValue: 'Upload Statement' })}</DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              <div>
                <label className="text-sm font-medium mb-2 block">
                  {t('statements.select_provider', { defaultValue: 'Statement Provider' })}
                </label>
                <Select value={selectedProvider} onValueChange={setSelectedProvider}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {STATEMENT_PROVIDERS.map((provider) => (
                      <SelectItem key={provider.value} value={provider.value}>
                        <div className="flex items-center gap-2">
                          <span>{provider.icon}</span>
                          <span>{provider.label}</span>
                        </div>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div>
                <label className="text-sm font-medium mb-2 block">
                  {t('statements.select_files')}
                </label>
                <div className="border-2 border-dashed border-muted-foreground/25 rounded-lg p-6 text-center">
                  <Upload className="w-8 h-8 mx-auto mb-2 text-muted-foreground" />
                  <div className="text-sm text-muted-foreground mb-2">
                    {files.length > 0
                      ? `${files.length} file(s) selected`
                      : 'Drop files here or click to browse'
                    }
                  </div>
                  <input
                    type="file"
                    accept=".pdf,.csv,.jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp,application/pdf,text/csv,application/vnd.ms-excel"
                    multiple
                    className="hidden"
                    id="file-upload"
                    onChange={(e) => {
                      const list = Array.from(e.target.files || []).slice(0, 12);
                      setFiles(list);
                    }}
                  />
                  <label
                    htmlFor="file-upload"
                    className="inline-flex items-center px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm font-medium cursor-pointer hover:bg-primary/90 transition-colors"
                  >
                    <Upload className="w-4 h-4 mr-2" />
                    Choose Files
                  </label>
                  <div className="text-xs text-muted-foreground mt-2">
                    Supports PDF, CSV, and image files (JPG, PNG, WebP) (max 12 files)
                  </div>
                </div>
                {files.length > 0 && (
                  <div className="mt-4">
                    <div className="text-sm font-medium mb-2">Selected Files:</div>
                    <div className="space-y-1 max-h-32 overflow-y-auto">
                      {files.map((file, index) => (
                        <div key={index} className="flex items-center justify-between text-sm bg-muted p-2 rounded">
                          <span className="truncate">{file.name}</span>
                          <span className="text-muted-foreground">({Math.round(file.size / 1024)} KB)</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              <div className="flex justify-end gap-2 pt-4">
                <Button variant="outline" onClick={() => setUploadModalOpen(false)}>
                  {t('cancel', { defaultValue: 'Cancel' })}
                </Button>
                <Button onClick={onUpload} disabled={loading || files.length === 0}>
                  {loading ? (
                    <>
                      <div className="w-4 h-4 mr-2 border-2 border-current border-t-transparent rounded-full animate-spin" />
                      {t('statements.processing')}
                    </>
                  ) : (
                    <>
                      <Upload className="w-4 h-4 mr-2" />
                      {t('statements.upload')}
                    </>
                  )}
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>

        {/* Empty Recycle Bin Modal */}
        <AlertDialog open={emptyRecycleBinModalOpen} onOpenChange={setEmptyRecycleBinModalOpen}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>{t('recycleBin.empty_recycle_bin_confirm_title', { defaultValue: 'Empty Recycle Bin' })}</AlertDialogTitle>
              <AlertDialogDescription>
                {t('recycleBin.empty_recycle_bin_confirm_description', { defaultValue: 'Are you sure you want to permanently delete all statements in the recycle bin? This action cannot be undone and all deleted statements will be completely removed from the system.' })}
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>{t('common.cancel')}</AlertDialogCancel>
              <AlertDialogAction onClick={confirmEmptyRecycleBin} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">
                <Trash2 className="mr-2 h-4 w-4" />
                {t('recycleBin.empty_recycle_bin', { defaultValue: 'Empty Recycle Bin' })}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>

        {/* Delete Statement Modal */}
        <AlertDialog open={deleteModalOpen} onOpenChange={setDeleteModalOpen}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>{t('statements.delete_confirm_title', 'Delete Statement')}</AlertDialogTitle>
              <AlertDialogDescription>
                {t('statements.delete_confirm_description')}
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>{t('common.cancel', 'Cancel')}</AlertDialogCancel>
              <AlertDialogAction onClick={confirmDeleteStatement} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">
                <Trash2 className="mr-2 h-4 w-4" />
                {t('statements.delete', 'Delete')}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>
    </AppLayout>
  );
}
