import { useEffect, useState, useRef, useCallback } from 'react';
import { cn } from '@/lib/utils';
import { useNavigate, useLocation, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from '@/components/ui/alert-dialog';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Calendar } from '@/components/ui/calendar';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Checkbox } from '@/components/ui/checkbox';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { ContextMenu, ContextMenuContent, ContextMenuItem, ContextMenuTrigger, ContextMenuSeparator } from '@/components/ui/context-menu';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { CalendarIcon, Upload, ArrowLeft, Eye, Download, ExternalLink, Trash2, FileText, Plus, Copy, X, Edit, MoreHorizontal, Loader2, ChevronDown, ChevronUp, RotateCcw, Search, Tag, Minus, Filter, Save, AlertCircle, CreditCard, Wallet, Columns, ArrowLeftRight, Share2 } from 'lucide-react';
import { format, parseISO, isValid } from 'date-fns';
import { bankStatementApi, BankTransactionEntry, BankStatementDetail, BankStatementSummary, expenseApi, invoiceApi, clientApi, formatStatus, DeletedBankStatement } from '@/lib/api';
import { TransactionLinkInfo } from '@/lib/api/bank-statements';
import { LinkTransferModal } from '@/components/statements/LinkTransferModal';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { Badge } from '@/components/ui/badge';
import { toast } from 'sonner';
import { InvoiceForm } from '@/components/invoices/InvoiceForm';
import { useFeatures } from '@/contexts/FeatureContext';
import { PageHeader } from '@/components/ui/professional-layout';
import { ProfessionalCard } from '@/components/ui/professional-card';
import { ProfessionalButton } from '@/components/ui/professional-button';
import { LicenseAlert } from '@/components/ui/license-alert';
import { ShareButton } from '@/components/sharing/ShareButton';
import { CurrencyDisplay } from '@/components/ui/currency-display';
import { Pagination, PaginationContent, PaginationEllipsis, PaginationItem, PaginationLink, PaginationNext, PaginationPrevious } from '@/components/ui/pagination';
import { useQuery } from '@tanstack/react-query';
import { settingsApi } from '@/lib/api';
import { ReviewDiffModal } from '@/components/ReviewDiffModal';
import { Wand } from 'lucide-react';
import { usePageContext } from '@/contexts/PageContext';
import { useColumnVisibility, type ColumnDef } from '@/hooks/useColumnVisibility';
import { ColumnPicker } from '@/components/ui/column-picker';

const STATEMENT_COLUMNS: ColumnDef[] = [
  { key: 'select', label: 'Select', essential: true },
  { key: 'id', label: 'ID' },
  { key: 'filename', label: 'Filename', essential: true },
  { key: 'labels', label: 'Labels' },
  { key: 'type', label: 'Type' },
  { key: 'status', label: 'Status', essential: true },
  { key: 'review_status', label: 'Review Status' },
  { key: 'transactions', label: 'Transactions' },
  { key: 'created_at_by', label: 'Created at/by' },
  { key: 'actions', label: 'Actions', essential: true },
];

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

const STATEMENT_STATUSES = ['uploaded', 'processing', 'processed', 'failed', 'merged'] as const;
type StatementStatus = typeof STATEMENT_STATUSES[number];

type BankRow = BankTransactionEntry & { id?: number; invoice_id?: number | null; expense_id?: number | null; backend_id?: number | null; linked_transfer?: TransactionLinkInfo | null };

// Helper component to display analysis status consistently
function StatusBadge({
  status,
  extraction_method,
  analysis_error
}: {
  status?: string;
  extraction_method?: string;
  analysis_error?: string | null;
}) {
  const { t } = useTranslation();

  return (
    <div className="flex flex-col gap-1">
      <Badge
        variant="outline"
        className={`
          font-medium capitalize h-6 px-3
          ${status === 'processed' ? 'bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300 border-green-200 dark:border-green-800' : ''}
          ${status === 'processing' ? 'bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300 border-blue-200 dark:border-blue-800 animate-pulse' : ''}
          ${status === 'failed' ? 'bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300 border-red-200 dark:border-red-800' : ''}
          ${status === 'uploaded' ? 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-300 border-yellow-200 dark:border-yellow-800' : ''}
          ${status === 'merged' ? 'bg-violet-100 text-violet-800 dark:bg-violet-900/40 dark:text-violet-300 border-violet-200 dark:border-violet-800' : ''}
        `}
      >
        {status === 'merged' ? t('common.merged', 'Merged') : (status === 'processed' || status === 'done') ? t('common.done', 'Done') : t(`common.${status || 'unknown'}`, status || 'Unknown')}
      </Badge>
      {status === 'processed' && extraction_method && (
        <span className="text-[10px] text-muted-foreground ml-1 uppercase font-bold tracking-tighter">
          via {extraction_method}
        </span>
      )}
    </div>
  );
}

// Helper for card type display
function CardTypeBadge({ type }: { type?: string }) {
  const { t } = useTranslation();
  const isCredit = type === 'credit';
  
  return (
    <Badge
      variant="secondary"
      className={cn(
        "flex items-center gap-1.5 h-6 px-2.5 font-medium border shadow-sm",
        isCredit 
          ? "bg-purple-100 text-purple-800 dark:bg-purple-900/40 dark:text-purple-300 border-purple-200 dark:border-purple-800" 
          : "bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300 border-blue-200 dark:border-blue-800"
      )}
    >
      {isCredit ? <CreditCard className="h-3.5 w-3.5" /> : <Wallet className="h-3.5 w-3.5" />}
      {isCredit ? t('statements.card_type.credit', 'Credit') : t('statements.card_type.debit', 'Debit')}
    </Badge>
  );
}

// Statement Upload Button with feature gating
function StatementUploadButton({ onUpload }: { onUpload: () => void }) {
  const { t } = useTranslation();
  const { isFeatureEnabled } = useFeatures();
  const hasFeature = isFeatureEnabled('ai_bank_statement');

  return (
    <ProfessionalButton onClick={onUpload} disabled={!hasFeature} className={!hasFeature ? 'opacity-50 cursor-not-allowed' : ''}>
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
  const { isFeatureEnabled } = useFeatures();
  const { isVisible, toggle, reset, hiddenCount } = useColumnVisibility('statements', STATEMENT_COLUMNS);
  const [shareStatementId, setShareStatementId] = useState<number | null>(null);
  const location = useLocation();
  const [searchParams, setSearchParams] = useSearchParams();
  const { setPageContext } = usePageContext();

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
  const [cardType, setCardType] = useState<string>('auto');
  const [dragActive, setDragActive] = useState(false);
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [statementToDelete, setStatementToDelete] = useState<number | null>(null);
  const [reprocessingLocks, setReprocessingLocks] = useState<Set<number>>(new Set());
  const [isSplitView, setIsSplitView] = useState(false);
  const [splitViewPdfUrl, setSplitViewPdfUrl] = useState<string | null>(null);
  const [splitViewPdfObjectUrl, setSplitViewPdfObjectUrl] = useState<string | null>(null);
  const [linkTransferModalOpen, setLinkTransferModalOpen] = useState(false);
  const [linkTransferModalMounted, setLinkTransferModalMounted] = useState(false);
  const [linkingRowIdx, setLinkingRowIdx] = useState<number | null>(null);
  const [highlightedBackendId, setHighlightedBackendId] = useState<number | null>(null);
  const highlightTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const readOnly = detail?.status === 'processing' || detail?.status === 'merged';
  const isCompleted = (s: { status?: string }) => s.status === 'processed' || s.status === 'done' || s.status === 'failed' || s.status === 'uploaded' || s.status === 'merged';

  useEffect(() => {
    if (location.pathname === '/statements' && !searchParams.get('id')) {
      setSelected(null);
      setDetail(null);
      setRows([]);
      setIsSplitView(false);
    }
  }, [location.key, location.pathname]);

  // Split view cleanup
  useEffect(() => {
    return () => {
      if (splitViewPdfObjectUrl) {
        URL.revokeObjectURL(splitViewPdfObjectUrl);
      }
    };
  }, [splitViewPdfObjectUrl]);

  // Effect to automatically update PDF when switching statements in Split View
  useEffect(() => {
    let active = true;

    const updateSplitViewPdf = async () => {
      if (!isSplitView || !selected) {
        return;
      }

      try {
        setDetailLoading(true);
        const { blob } = await bankStatementApi.fetchFileBlob(selected, true);
        
        if (!active) return;

        const objectUrl = URL.createObjectURL(blob);

        setSplitViewPdfObjectUrl(prev => {
          if (prev) URL.revokeObjectURL(prev);
          return objectUrl;
        });
        setSplitViewPdfUrl(objectUrl);
      } catch (e: any) {
        if (active) {
          console.error('Failed to update parallel view PDF:', e);
        }
      } finally {
        if (active) {
          setDetailLoading(false);
        }
      }
    };

    updateSplitViewPdf();
    
    return () => {
      active = false;
    };
  }, [selected, isSplitView]);

  const toggleSplitView = () => {
    setIsSplitView(!isSplitView);
  };

  useEffect(() => {
    if (!selected || !detail) {
      setPageContext({
        title: t('navigation.bank_statements', { defaultValue: 'Statements' }),
        entity: undefined,
        metadata: undefined
      });
      return;
    }

    setPageContext({
      title: t('navigation.bank_statements', { defaultValue: 'Statements' }),
      entity: { type: 'bank_statement', id: selected },
      metadata: {
        status: detail.status,
        labels: detail.labels || [],
        extracted_count: detail.extracted_count,
        original_filename: detail.original_filename
      }
    });
  }, [detail, selected, setPageContext, t]);


  // Fetch settings to get timezone
  const { data: settings } = useQuery({
    queryKey: ['settings'],
    queryFn: () => settingsApi.getSettings(),
    staleTime: 5 * 60 * 1000, // 5 minutes
    refetchOnWindowFocus: false,
  });

  // Get timezone from settings, default to UTC
  const timezone = settings?.timezone || 'UTC';

  // Helper function to get locale for date formatting
  const getLocale = () => {
    const language = t('language', { defaultValue: 'en' });
    switch (language) {
      case 'es':
        return 'es-ES';
      case 'fr':
        return 'fr-FR';
      case 'de':
        return 'de-DE';
      default:
        return 'en-US';
    }
  };

  // Selection and filtering
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [statusFilter, setStatusFilter] = useState('all');
  const [labelFilter, setLabelFilter] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [bulkLabel, setBulkLabel] = useState('');
  const [bulkDeleteModalOpen, setBulkDeleteModalOpen] = useState(false);
  const [bulkMergeModalOpen, setBulkMergeModalOpen] = useState(false);

  // Review Mode State
  const [reviewModalOpen, setReviewModalOpen] = useState(false);
  const [selectedReviewStatement, setSelectedReviewStatement] = useState<BankStatementSummary | null>(null);
  const [isAcceptingReview, setIsAcceptingReview] = useState(false);
  const [isRejectingReview, setIsRejectingReview] = useState(false);
  const [isRetriggeringReview, setIsRetriggeringReview] = useState(false);

  const handleReviewClick = (statement: BankStatementSummary) => {
    setSelectedReviewStatement(statement);
    setReviewModalOpen(true);
  };

  const handleAcceptReview = async () => {
    if (!selectedReviewStatement) return;

    try {
      setIsAcceptingReview(true);
      await bankStatementApi.acceptReview(selectedReviewStatement.id);
      toast.success(t('statements.review.accepted_success', { defaultValue: 'Review accepted successfully' }));
      setReviewModalOpen(false);
      // Refresh list
      loadList();
    } catch (error) {
      toast.error(t('statements.review.accept_failed', { defaultValue: 'Failed to accept review' }));
    } finally {
      setIsAcceptingReview(false);
    }
  };

  const handleRejectReview = async () => {
    if (!selectedReviewStatement) return;

    try {
      setIsRejectingReview(true);
      await bankStatementApi.rejectReview(selectedReviewStatement.id);
      toast.success(t('statements.review.dismissed', { defaultValue: 'Review dismissed' }));
      setReviewModalOpen(false);
      loadList();
    } catch (error) {
      toast.error(t('statements.review.dismiss_failed', { defaultValue: 'Failed to dismiss review' }));
    } finally {
      setIsRejectingReview(false);
    }
  };

  const handleRetriggerReview = async () => {
    if (!selectedReviewStatement) return;

    try {
      setIsRetriggeringReview(true);
      await bankStatementApi.reReview(selectedReviewStatement.id);
      toast.success(t('statements.review.retriggered', { defaultValue: 'Review re-triggered' }));
      setReviewModalOpen(false);
      loadList();
    } catch (error) {
      toast.error(t('statements.review.retrigger_failed', { defaultValue: 'Failed to re-trigger review' }));
    } finally {
      setIsRetriggeringReview(false);
    }
  };

  const handleRunReview = async (statementId: number) => {
    try {
      await bankStatementApi.reReview(statementId);
      toast.success(t('statements.review.triggered', { defaultValue: 'Review triggered. The agent will process it shortly.' }));
      // Refresh list
      loadList();
    } catch (error: any) {
      toast.error(error?.message || t('statements.review.trigger_failed', { defaultValue: 'Failed to trigger review' }));
    }
  };

  const handleCancelReview = async (statementId: number) => {
    try {
      await bankStatementApi.cancelReview(statementId);
      toast.success(t('statements.review.cancelled', { defaultValue: 'Review cancelled.' }));
      // Refresh list
      loadList();
    } catch (error: any) {
      toast.error(error?.message || t('statements.review.cancel_failed', { defaultValue: 'Failed to cancel review' }));
    }
  };

  const handleBulkRunReview = async () => {
    if (selectedIds.length === 0) return;

    try {
      setLoading(true);
      await Promise.all(selectedIds.map(id => bankStatementApi.reReview(id)));
      toast.success(`Review triggered for ${selectedIds.length} statements.`);
      setSelectedIds([]);
      loadList();
    } catch (error: any) {
      toast.error(error?.message || t('statements.review.bulk_trigger_failed', { defaultValue: 'Failed to trigger bulk review' }));
    } finally {
      setLoading(false);
    }
  };

  // Pagination
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [totalStatements, setTotalStatements] = useState(0);
  const [newLabelValueById, setNewLabelValueById] = useState<Record<number, string>>({});

  // Recycle bin state
  const [showRecycleBin, setShowRecycleBin] = useState(false);
  const [deletedStatements, setDeletedStatements] = useState<DeletedBankStatement[]>([]);
  const [recycleBinLoading, setRecycleBinLoading] = useState(false);
  const prevDeletedCount = useRef<number>(0);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [statementToPermanentlyDelete, setStatementToPermanentlyDelete] = useState<number | null>(null);
  const [emptyRecycleBinModalOpen, setEmptyRecycleBinModalOpen] = useState(false);

  // Recycle bin pagination
  const [recycleBinCurrentPage, setRecycleBinCurrentPage] = useState(1);
  const [recycleBinPageSize] = useState(10);
  const [recycleBinTotalCount, setRecycleBinTotalCount] = useState(0);

  useEffect(() => {
    const loadClients = async () => {
      try {
        const clientList = await clientApi.getClients();
        setClients(clientList.items);
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
      toast.error(t('statements.export.no_transactions', { defaultValue: 'No transactions to export' }));
      return;
    }

    const headers = ['Date', 'Description', 'Amount', 'Type', 'Balance', 'Category', 'Reference'];
    const csvContent = [
      headers.join(','),
      ...rows.map(row => {
        const refs: string[] = [];
        if ((row as any).expense_id) refs.push(`EXP #${(row as any).expense_id}`);
        if ((row as any).invoice_id) refs.push(`INV #${(row as any).invoice_id}`);
        if ((row as any).linked_transfer) {
          const lt = (row as any).linked_transfer;
          const linkType = lt?.link_type === 'fx_conversion' ? 'FX' : 'TRF';
          const statementId = lt?.linked_statement_id;
          const filename = lt?.linked_statement_filename || '';
          const url = statementId ? `${window.location.origin}/statements?id=${statementId}` : '';
          refs.push(`${linkType}${filename ? ` (${filename})` : ''}${url ? ` ${url}` : ''}`);
        }
        return [
          row.date,
          `"${row.description.replace(/"/g, '""')}"`,
          row.amount,
          row.transaction_type,
          row.balance ?? '',
          row.category ?? '',
          refs.join('; ')
        ].join(',');
      })
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
    toast.success(t('statements.export.csv_success', { defaultValue: 'CSV exported successfully' }));
  };

  const createExpenseFromTransaction = async (rowIndex: number) => {
    const transaction = rows[rowIndex];
    if (transaction.transaction_type !== 'debit') {
      toast.error(t('statements.expense.create_only_debit', { defaultValue: 'Can only create expenses from debit transactions' }));
      return;
    }
    if ((transaction as any).expense_id) {
      toast.error(t('statements.expense.already_created', { defaultValue: 'An expense has already been created for this transaction' }));
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
        status: 'recorded',
        analysis_status: 'done'
      };

      const created = await expenseApi.createExpense(expenseData as any);
      toast.success(t('statements.expense.create_success', { defaultValue: 'Expense created successfully' }));

      // Link this transaction to the created expense to prevent duplicates
      setRows(prev => prev.map((r, i) => i === rowIndex ? { ...r, expense_id: created.id } : r));
      const backendId = (transaction as any).backend_id;
      if (selected && backendId) {
        try {
          await bankStatementApi.patchTransaction(selected, backendId, { expense_id: created.id });
          await openStatement(selected);
        } catch (linkErr: any) {
          console.error('Failed to persist expense link:', linkErr);
        }
      }
    } catch (e: any) {
      toast.error(e?.message || t('statements.expense.create_failed', { defaultValue: 'Failed to create expense' }));
    }
  };

  const createInvoiceFromTransaction = (rowIndex: number) => {
    const transaction = rows[rowIndex];
    if (transaction.transaction_type !== 'credit') {
      toast.error(t('statements.invoice.create_only_credit', { defaultValue: 'Can only create invoices from credit transactions' }));
      return;
    }

    // Prevent duplicate invoice creation if already linked
    if ((transaction as any).invoice_id) {
      toast.error(t('statements.invoice.already_created', { defaultValue: 'An invoice has already been created for this transaction' }));
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

  const loadList = useCallback(async () => {
    try {
      const skip = (page - 1) * pageSize;
      const status = statusFilter !== 'all' ? statusFilter : undefined;
      const data = await bankStatementApi.list(skip, pageSize, labelFilter || undefined, searchQuery || undefined, status);
      setStatements(data.statements);
      setTotalStatements(data.total);

      // Start polling for any statements that are still processing
      const processingIds = data.statements
        .filter(s => s.status === 'processing' || s.status === 'uploaded')
        .map(s => s.id);
      
      if (processingIds.length > 0) {
        const startPolling = (window as any).startStatementPolling;
        if (typeof startPolling === 'function') {
          startPolling(processingIds);
        }
      }
    } catch (e: any) {
      toast.error(e?.message || t('statements.load_failed', { defaultValue: 'Failed to load statements' }));
    }
  }, [statusFilter, labelFilter, searchQuery, page, pageSize]);

  useEffect(() => {
    loadList();
  }, [statusFilter, labelFilter, searchQuery, page, pageSize]);

  // Auto-open statement from URL ?id= param on initial mount only
  useEffect(() => {
    const idParam = new URLSearchParams(window.location.search).get('id');
    if (idParam) {
      const id = parseInt(idParam, 10);
      if (!isNaN(id)) openStatement(id);
    }
  }, []);

  // Listen for polling completion events
  useEffect(() => {
    const handleRefresh = (e: any) => {
      loadList();
      
      // If we're looking at the detail for the processed statement, reload it
      if (selected && e?.detail?.id === selected) {
        openStatement(selected);
      }
    };

    window.addEventListener('statement-processed', handleRefresh);
    window.addEventListener('statement-failed', handleRefresh);

    return () => {
      window.removeEventListener('statement-processed', handleRefresh);
      window.removeEventListener('statement-failed', handleRefresh);
    };
  }, [loadList, selected]);

  useEffect(() => {
    if (!recycleBinLoading && deletedStatements.length === 0 && showRecycleBin && prevDeletedCount.current > 0) {
      setShowRecycleBin(false);
    }
    prevDeletedCount.current = deletedStatements.length;
  }, [deletedStatements.length, recycleBinLoading, showRecycleBin]);

  useEffect(() => {
    if (showRecycleBin) {
      fetchDeletedStatements();
    }
  }, [showRecycleBin, recycleBinCurrentPage]);

  const closeLinkTransferModal = () => {
    setLinkTransferModalOpen(false);
    setLinkingRowIdx(null);
    // Unmount after animation completes so Radix can clean up the overlay properly
    setTimeout(() => setLinkTransferModalMounted(false), 300);
  };

  const handleTransactionLinked = (rowIdx: number, link: TransactionLinkInfo) => {
    setRows((prev) => prev.map((r, i) => i === rowIdx ? { ...r, linked_transfer: link } : r));
    closeLinkTransferModal();
    if (selected) {
      const id = selected;
      setTimeout(() => openStatement(id), 350);
    }
  };

  const handleUnlinkTransfer = async (rowIdx: number) => {
    const row = rows[rowIdx];
    const linkId = row.linked_transfer?.id;
    if (!linkId) return;
    if (!confirm('Remove this transfer link?')) return;
    try {
      await bankStatementApi.deleteTransactionLink(linkId);
      toast.success('Transfer link removed');
      if (selected) await openStatement(selected);
    } catch (e: any) {
      toast.error(e?.message || 'Failed to remove transfer link');
    }
  };

  const openStatement = async (id: number, highlightBackendId?: number) => {
    setSelected(id);
    if (searchParams.get('id') !== String(id)) {
      setSearchParams({ id: String(id) }, { replace: true });
    }
    setDetailLoading(true);
    setHighlightedBackendId(null);
    if (highlightTimerRef.current) clearTimeout(highlightTimerRef.current);
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
        linked_transfer: (t as any).linked_transfer ?? null,
        backend_id: (t as any).id, // Preserve original backend ID for API calls
      }));
      setRows(transactionsWithIds);
      if (highlightBackendId) {
        setHighlightedBackendId(highlightBackendId);
        highlightTimerRef.current = setTimeout(() => setHighlightedBackendId(null), 3000);
      }
    } catch (e: any) {
      toast.error(e?.message || t('statements.detail_load_failed', { defaultValue: 'Failed to load statement' }));
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

      const resp = await bankStatementApi.uploadAndExtract(files, cardType);

      if (resp.statements && resp.statements.length > 0) {
        const startPolling = (window as any).startStatementPolling;
        if (typeof startPolling === 'function') {
          startPolling(resp.statements.map((s: any) => s.id));
        }
      }

      addNotification?.('success', `${providerName} ${t('statements.upload')}`, `Successfully uploaded ${files.length} statement files. AI extraction in progress.`);
      toast.success(`Uploaded ${files.length} ${providerName.toLowerCase()} ${t('statements.statements').toLowerCase()}`);
      setFiles([]);
      setUploadModalOpen(false);
      await loadList();
    } catch (e: any) {
      addNotification?.('error', t('statements.failed_to_delete'), t('statements.process_failed_message', { defaultValue: 'Failed to process statements: {{error}}', error: e?.message || t('common.unknown_error', { defaultValue: 'Unknown error' }) }));
      toast.error(e?.message || t('statements.extract_failed', { defaultValue: 'Failed to extract transactions' }));
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
      toast.success(t('statements.transactions_saved', { defaultValue: 'Transactions saved' }));
      // Refresh detail and list counts but preserve frontend ID sequence
      await openStatement(selected);
      await loadList();
    } catch (e: any) {
      toast.error(e?.message || t('statements.save_transactions_failed', { defaultValue: 'Failed to save transactions' }));
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
      toast.success(t('statements.update_success', { defaultValue: 'Statement updated' }));
    } catch (e: any) {
      toast.error(e?.message || t('statements.update_failed', { defaultValue: 'Failed to update statement' }));
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
        setSearchParams({}, { replace: true });
      }
    } catch (e: any) {
      toast.error(e?.message || t('statements.failed_to_delete'));
    } finally {
      setDeleteModalOpen(false);
      setStatementToDelete(null);
    }
  };

  const handleBulkDelete = async () => {
    setLoading(true);
    try {
      for (const id of selectedIds) {
        await bankStatementApi.delete(id);
      }
      toast.success(t('statements.bulk_delete_success', { count: selectedIds.length, defaultValue: 'Statements deleted successfully' }));
      await loadList();
      // Refresh recycle bin if it's currently open
      if (showRecycleBin) {
        // Reset to first page since total count may have changed
        setRecycleBinCurrentPage(1);
        await fetchDeletedStatements();
      }
      setSelectedIds([]);
      setBulkDeleteModalOpen(false);
    } catch (e: any) {
      toast.error(e?.message || t('statements.delete_failed', { defaultValue: 'Failed to delete statements' }));
    } finally {
      setLoading(false);
    }
  };

  const handleBulkMerge = async () => {
    setLoading(true);
    try {
      const resp = await bankStatementApi.merge(selectedIds);
      toast.success(resp.message || t('statements.merge_success', { defaultValue: 'Statements merged successfully' }));
      await loadList();
      setSelectedIds([]);
      setBulkMergeModalOpen(false);
      if (resp.id) {
        openStatement(resp.id);
      }
    } catch (e: any) {
      toast.error(e?.message || t('statements.merge_failed', { defaultValue: 'Failed to merge statements' }));
    } finally {
      setLoading(false);
    }
  };

  // Recycle bin functions
  const fetchDeletedStatements = async () => {
    try {
      setRecycleBinLoading(true);
      const skip = (recycleBinCurrentPage - 1) * recycleBinPageSize;
      const response = await bankStatementApi.getDeletedStatements(skip, recycleBinPageSize);
      setDeletedStatements(response.items);
      setRecycleBinTotalCount(response.total);
    } catch (error) {
      console.error('Failed to fetch deleted statements:', error);
      toast.error(t('recycleBin.load_failed', { defaultValue: 'Failed to load recycle bin' }));
    } finally {
      setRecycleBinLoading(false);
    }
  };

  const handleRestoreStatement = async (statementId: number) => {
    try {
      await bankStatementApi.restoreStatement(statementId, 'processed');
      toast.success(t('statements.restore_success', { defaultValue: 'Statement restored successfully' }));
      fetchDeletedStatements();
      loadList(); // Refresh main list
    } catch (error: any) {
      console.error('Failed to restore statement:', error);
      toast.error(error?.message || t('statements.restore_failed', { defaultValue: 'Failed to restore statement' }));
    }
  };

  const handlePermanentlyDeleteStatement = async (statementId: number) => {
    try {
      await bankStatementApi.permanentlyDeleteStatement(statementId);
      toast.success(t('statements.permanent_delete_success', { defaultValue: 'Statement permanently deleted' }));
      fetchDeletedStatements();
      setStatementToPermanentlyDelete(null);
    } catch (error: any) {
      console.error('Failed to permanently delete statement:', error);
      toast.error(error?.message || t('statements.permanent_delete_failed', { defaultValue: 'Failed to permanently delete statement' }));
    }
  };

  const handleEmptyRecycleBin = () => {
    setEmptyRecycleBinModalOpen(true);
  };

  const confirmEmptyRecycleBin = async () => {
    const addNotification = (window as any).addAINotification;
    try {
      const response = await bankStatementApi.emptyRecycleBin() as { message: string; deleted_count: number; status?: string };

      // Show immediate notification
      toast.success(response.message || t('statementRecycleBin.deletion_initiated', { count: response.deleted_count }));

      // Add bell notification for completion
      if (addNotification && response.status === 'processing') {
        addNotification(
          'info', 
          t('statementRecycleBin.deletion_title'), 
          t('statementRecycleBin.deletion_processing', { count: response.deleted_count })
        );

        // Show completion notification and refresh after background task completes
        setTimeout(() => {
          addNotification(
            'success', 
            t('statementRecycleBin.deletion_completed_title'), 
            t('statementRecycleBin.deletion_completed', { count: response.deleted_count })
          );
          // Refresh the list after deletion completes
          fetchDeletedStatements();
        }, 2000);
      } else {
        // If not async (empty bin already or other reason), refresh immediately
        fetchDeletedStatements();
      }

      setEmptyRecycleBinModalOpen(false);
    } catch (error: any) {
      console.error('Failed to empty recycle bin:', error);
      toast.error(error?.message || t('statementRecycleBin.failed_to_empty_recycle_bin'));
    }
  };

  const handleToggleRecycleBin = () => {
    const willShow = !showRecycleBin;
    setShowRecycleBin(willShow);
    if (willShow) {
      setRecycleBinCurrentPage(1); // Reset to first page when opening
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
    <>
      <div className="space-y-8 overflow-visible">
        {/* License Alert */}
        {!isFeatureEnabled('ai_bank_statement') && (
          <LicenseAlert
            message={t('settings.bank_statement_license_required', { defaultValue: 'Bank statement processing requires the AI Bank Statement feature. Please upgrade your license to enable this functionality.' })}
            feature="ai_bank_statement"
            compact={true}
          />
        )}

        {/* Hero Header */}
        {/* Hero Header - Only show when no statement selected */}
        {!selected && (
          <div className="bg-gradient-to-r from-primary/10 via-primary/5 to-transparent rounded-2xl border border-primary/20 p-8 backdrop-blur-sm">
            <div className="flex items-center justify-between gap-6">
              <div className="space-y-2">
                <h1 className="text-4xl font-bold tracking-tight">{t('navigation.bank_statements')}</h1>
                <p className="text-lg text-muted-foreground">{t('statements.description')}</p>
              </div>
              <div className="flex gap-3 items-center flex-wrap justify-end">
                <ProfessionalButton
                  variant="outline"
                  size="default"
                  onClick={loadList}
                  className="whitespace-nowrap"
                  disabled={loading}
                >
                  <RotateCcw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
                  {t('common.refresh', { defaultValue: 'Refresh' })}
                </ProfessionalButton>
                <ProfessionalButton
                  variant="outline"
                  size="default"
                  onClick={handleToggleRecycleBin}
                  className="whitespace-nowrap"
                >
                  <Trash2 className="h-4 w-4" />
                  {t('statementRecycleBin.title', { defaultValue: 'Recycle Bin' })}
                  {showRecycleBin ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                </ProfessionalButton>
                <div className="flex gap-1">
                  <StatementUploadButton onUpload={() => setUploadModalOpen(true)} />
                </div>
              </div>
            </div>
          </div>
        )}

        {!selected && showRecycleBin && (
          <Collapsible open={showRecycleBin} onOpenChange={setShowRecycleBin}>
            <CollapsibleContent>
              <ProfessionalCard className="slide-in mb-8 border-l-4 border-l-destructive overflow-hidden" variant="elevated">
                <div className="absolute top-0 right-0 w-40 h-40 bg-destructive/5 rounded-full -mr-20 -mt-20 blur-3xl"></div>
                <div className="relative space-y-6">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4">
                      <div className="p-3 rounded-xl bg-destructive/10 border border-destructive/20">
                        <Trash2 className="h-6 w-6 text-destructive" />
                      </div>
                      <div>
                        <h3 className="font-bold text-xl text-foreground">{t('statementRecycleBin.title', { defaultValue: 'Recycle Bin' })}</h3>
                        <p className="text-sm text-muted-foreground">
                          {recycleBinTotalCount} {t('statementRecycleBin.items', 'items')} • Recover or permanently delete statements
                        </p>
                      </div>
                    </div>
                    {deletedStatements.length > 0 && (
                      <ProfessionalButton
                        variant="destructive"
                        size="default"
                        onClick={handleEmptyRecycleBin}
                      >
                        <Trash2 className="h-4 w-4" />
                        {t('statementRecycleBin.empty_recycle_bin', { defaultValue: 'Empty Recycle Bin' })}
                      </ProfessionalButton>
                    )}
                  </div>
                  <div className="rounded-xl border border-border/50 overflow-hidden shadow-sm">
                    <Table>
                      <TableHeader>
                        <TableRow className="bg-gradient-to-r from-muted/50 to-muted/30 hover:bg-gradient-to-r hover:from-muted/50 hover:to-muted/30">
                          <TableHead className="font-bold text-foreground">{t('statements.filename')}</TableHead>
                          <TableHead className="font-bold text-foreground">{t('statements.review_status.label')}</TableHead>
                          <TableHead className="font-bold text-foreground">{t('statements.transactions')}</TableHead>
                          <TableHead className="font-bold text-foreground">{t('statementRecycleBin.deleted_at')}</TableHead>
                          <TableHead className="font-bold text-foreground">{t('statementRecycleBin.deleted_by')}</TableHead>
                          <TableHead className="w-[100px] font-bold text-foreground text-right">{t('statementRecycleBin.actions')}</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {recycleBinLoading ? (
                          <TableRow>
                            <TableCell colSpan={6} className="h-24 text-center">
                              <div className="flex justify-center items-center gap-2">
                                <Loader2 className="h-5 w-5 animate-spin text-primary" />
                                <span className="text-muted-foreground">{t('statementRecycleBin.loading', { defaultValue: 'Loading...' })}</span>
                              </div>
                            </TableCell>
                          </TableRow>
                        ) : deletedStatements.length === 0 ? (
                          <TableRow>
                            <TableCell colSpan={6} className="h-32 text-center">
                              <div className="flex flex-col items-center justify-center gap-3">
                                <div className="p-4 rounded-full bg-muted/50">
                                  <Trash2 className="h-8 w-8 text-muted-foreground/50" />
                                </div>
                                <p className="text-muted-foreground font-medium">{t('statementRecycleBin.recycle_bin_empty', { defaultValue: 'Recycle bin is empty' })}</p>
                              </div>
                            </TableCell>
                          </TableRow>
                        ) : (
                          deletedStatements.map((statement) => (
                            <TableRow key={statement.id} className="hover:bg-muted/60 transition-all duration-200 border-b border-border/30">
                              <TableCell className="font-semibold text-foreground">
                                <span className="inline-flex items-center gap-2">
                                  <FileText className="h-4 w-4 text-primary/60" />
                                  {statement.original_filename}
                                </span>
                              </TableCell>
                              <TableCell className="text-foreground">
                                <Badge variant="outline" className="capitalize font-medium">
                                  {formatStatus(statement.status)}
                                </Badge>
                              </TableCell>
                              <TableCell className="text-foreground">{statement.extracted_count}</TableCell>
                              <TableCell className="text-muted-foreground text-sm">{statement.deleted_at ? format(new Date(statement.deleted_at), 'PP p') : 'N/A'}</TableCell>
                              <TableCell className="text-muted-foreground text-sm">{statement.deleted_by_username || t('common.unknown')}</TableCell>
                              <TableCell>
                                <div className="flex gap-2 justify-end">
                                  <ProfessionalButton
                                    variant="ghost"
                                    size="icon-sm"
                                    onClick={() => handleRestoreStatement(statement.id)}
                                    title="Restore statement"
                                    className="hover:bg-success/10 hover:text-success"
                                  >
                                    <RotateCcw className="h-4 w-4" />
                                  </ProfessionalButton>
                                  <AlertDialog>
                                    <AlertDialogTrigger asChild>
                                      <ProfessionalButton
                                        variant="ghost"
                                        size="icon-sm"
                                        className="hover:bg-destructive/10 hover:text-destructive"
                                        title="Permanently delete"
                                      >
                                        <Trash2 className="h-4 w-4" />
                                      </ProfessionalButton>
                                    </AlertDialogTrigger>
                                    <AlertDialogContent>
                                      <AlertDialogHeader>
                                        <AlertDialogTitle>{t('statementRecycleBin.permanently_delete_confirm_title', { defaultValue: 'Permanently Delete Statement' })}</AlertDialogTitle>
                                        <AlertDialogDescription>
                                          {t('statementRecycleBin.permanently_delete_confirm_description', { defaultValue: 'Are you sure you want to permanently delete this statement? This action cannot be undone.' })}
                                        </AlertDialogDescription>
                                      </AlertDialogHeader>
                                      <AlertDialogFooter>
                                        <AlertDialogCancel>{t('common.cancel')}</AlertDialogCancel>
                                        <AlertDialogAction onClick={() => handlePermanentlyDeleteStatement(statement.id)} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">
                                          <Trash2 className="mr-2 h-4 w-4" />
                                          {t('statementRecycleBin.permanently_delete', { defaultValue: 'Permanently Delete' })}
                                        </AlertDialogAction>
                                      </AlertDialogFooter>
                                    </AlertDialogContent>
                                  </AlertDialog>
                                </div>
                              </TableCell>
                            </TableRow>
                          ))
                        )}
                      </TableBody>
                    </Table>
                  </div>
                  {Math.ceil(recycleBinTotalCount / recycleBinPageSize) > 1 && (
                    <div className="mt-4">
                      <Pagination>
                        <PaginationContent>
                          <PaginationItem>
                            <PaginationPrevious
                              onClick={() => setRecycleBinCurrentPage(prev => Math.max(1, prev - 1))}
                              className={recycleBinCurrentPage === 1 ? 'pointer-events-none opacity-50' : 'cursor-pointer'}
                            />
                          </PaginationItem>
                          {Array.from({ length: Math.min(5, Math.ceil(recycleBinTotalCount / recycleBinPageSize)) }, (_, i) => {
                            let pageNum = recycleBinCurrentPage;
                            const totalPages = Math.ceil(recycleBinTotalCount / recycleBinPageSize);
                            if (totalPages <= 5) pageNum = i + 1;
                            else if (recycleBinCurrentPage <= 3) pageNum = i + 1;
                            else if (recycleBinCurrentPage >= totalPages - 2) pageNum = totalPages - 4 + i;
                            else pageNum = recycleBinCurrentPage - 2 + i;

                            return (
                              <PaginationItem key={pageNum}>
                                <PaginationLink
                                  onClick={() => setRecycleBinCurrentPage(pageNum)}
                                  isActive={recycleBinCurrentPage === pageNum}
                                  className="cursor-pointer"
                                >
                                  {pageNum}
                                </PaginationLink>
                              </PaginationItem>
                            );
                          })}
                          <PaginationItem>
                            <PaginationNext
                              onClick={() => setRecycleBinCurrentPage(prev => Math.min(Math.ceil(recycleBinTotalCount / recycleBinPageSize), prev + 1))}
                              className={recycleBinCurrentPage >= Math.ceil(recycleBinTotalCount / recycleBinPageSize) ? 'pointer-events-none opacity-50' : 'cursor-pointer'}
                            />
                          </PaginationItem>
                        </PaginationContent>
                      </Pagination>
                    </div>
                  )}
                </div>
              </ProfessionalCard>
            </CollapsibleContent>
          </Collapsible>
        )}

        {!selected && (
          <ProfessionalCard className="slide-in" variant="elevated">
            <div className="space-y-6">
              {/* Header with filters */}
              <div className="flex flex-col lg:flex-row justify-between gap-6 pb-6 border-b border-border/50">
                <div>
                  <h2 className="text-2xl font-bold text-foreground">{t('statements.list_title')}</h2>
                </div>
                <div className="flex flex-col sm:flex-row gap-3 items-start sm:items-center">
                  {/* Search */}
                  <div className="relative w-full sm:w-auto">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <Input
                      placeholder={t('statements.search_placeholder')}
                      className="pl-9 w-full sm:w-[240px] h-10 rounded-lg border-border/50 bg-muted/30 focus:bg-background transition-colors"
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                    />
                    {searchQuery && (
                      <button
                        aria-label="Clear search"
                        className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                        onClick={() => setSearchQuery('')}
                      >
                        <X className="w-4 h-4" />
                      </button>
                    )}
                  </div>

                  {/* Status Filter */}
                  <div className="flex items-center gap-2">
                    <Filter className="h-4 w-4 text-muted-foreground" />
                    <Select value={statusFilter} onValueChange={setStatusFilter}>
                      <SelectTrigger className="w-full sm:w-[170px] h-10 rounded-lg border-border/50 bg-muted/30">
                        <SelectValue placeholder={t('statements.filter_by_status', { defaultValue: 'Filter by status' })} />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">{t('statements.all_statuses', { defaultValue: 'All Statuses' })}</SelectItem>
                        {STATEMENT_STATUSES.map((status) => (
                          <SelectItem key={status} value={status}>
                            {t(`statements.status.${status}`, { defaultValue: formatStatus(status) })}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  {/* Label Filter */}
                  <div className="relative">
                    <Tag className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <Input
                      placeholder={t('statements.filter_by_label', { defaultValue: 'Filter by label' })}
                      className="pl-9 w-full sm:w-[150px] h-10 rounded-lg border-border/50 bg-muted/30 focus:bg-background transition-colors"
                      value={labelFilter}
                      onChange={(e) => setLabelFilter(e.target.value)}
                    />
                    {labelFilter && (
                      <button
                        aria-label="Clear label filter"
                        className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                        onClick={() => setLabelFilter('')}
                      >
                        <X className="w-4 h-4" />
                      </button>
                    )}
                  </div>

                  {/* Page Size */}
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-muted-foreground">{t('common.page_size', { defaultValue: 'Page Size' })}</span>
                    <Select value={String(pageSize)} onValueChange={(v) => { setPageSize(Number(v)); setPage(1); }}>
                      <SelectTrigger className="w-[100px] h-10 rounded-lg border-border/50 bg-muted/30">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {[10, 20, 50, 100].map(n => (
                          <SelectItem key={n} value={String(n)}>{n}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  <ColumnPicker
                    columns={STATEMENT_COLUMNS}
                    isVisible={isVisible}
                    onToggle={toggle}
                    onReset={reset}
                    hiddenCount={hiddenCount}
                  />
                </div>
              </div>

              {/* Selection Toolbar */}
              {selectedIds.length > 0 && (
                <div className="flex flex-col md:flex-row items-center justify-between p-4 mb-6 bg-gradient-to-r from-primary/10 to-primary/5 border border-primary/30 rounded-xl shadow-sm gap-4 slide-in">
                  <div className="flex items-center gap-3">
                    <div className="h-2 w-2 rounded-full bg-primary animate-pulse shadow-[0_0_8px_rgba(var(--primary),0.5)]"></div>
                    <span className="text-sm font-bold text-foreground">
                      {selectedIds.length} {t('statements.title', { defaultValue: 'statement' })}{selectedIds.length !== 1 ? 's' : ''} {t('common.selected', { defaultValue: 'selected' })}
                    </span>
                    <ProfessionalButton
                      variant="ghost"
                      size="sm"
                      onClick={() => setSelectedIds([])}
                      className="h-8 text-xs hover:bg-primary/10 transition-colors"
                    >
                      {t('common.clear')}
                    </ProfessionalButton>
                  </div>

                  <div className="flex flex-wrap items-center gap-3 w-full md:w-auto justify-end">
                    <div className="relative group flex-1 md:flex-initial min-w-[200px]">
                      <Tag className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
                      <Input
                        placeholder={t('statements.bulk_label_placeholder', { defaultValue: 'Add or remove label' })}
                        value={bulkLabel}
                        onChange={(e) => setBulkLabel(e.target.value)}
                        className="pl-8 h-9 text-sm border-primary/20 focus:border-primary/40 bg-background/50"
                      />
                    </div>

                    <div className="flex items-center gap-1.5">
                      <ProfessionalButton
                        variant="outline"
                        size="sm"
                        disabled={!bulkLabel.trim()}
                        onClick={async () => {
                          try {
                            await bankStatementApi.bulkLabels(selectedIds, 'add', bulkLabel.trim());
                            loadList();
                            setSelectedIds([]);
                            setBulkLabel('');
                            toast.success(t('statements.labels.added', { defaultValue: 'Labels added' }));
                          } catch (e: any) {
                            toast.error(e?.message || t('statements.labels.add_failed', { defaultValue: 'Failed to add label' }));
                          }
                        }}
                        className="h-9 px-3 gap-1.5"
                      >
                        <Plus className="h-3.5 w-3.5" />
                        {t('common.add')}
                      </ProfessionalButton>

                      <ProfessionalButton
                        variant="outline"
                        size="sm"
                        disabled={!bulkLabel.trim()}
                        onClick={async () => {
                          try {
                            await bankStatementApi.bulkLabels(selectedIds, 'remove', bulkLabel.trim());
                            await loadList();
                            setSelectedIds([]);
                            setBulkLabel('');
                            toast.success(t('statements.labels.removed', { defaultValue: 'Labels removed' }));
                          } catch (e: any) {
                            toast.error(e?.message || t('statements.labels.remove_failed', { defaultValue: 'Failed to remove label' }));
                          }
                        }}
                        className="h-9 px-3 gap-1.5"
                      >
                        <Minus className="h-3.5 w-3.5" />
                        {t('common.remove')}
                      </ProfessionalButton>
                    </div>

                    <div className="w-px h-6 bg-primary/10 hidden md:block mx-1"></div>

                    <div className="flex items-center gap-2">
                      <ProfessionalButton
                        variant="outline"
                        size="sm"
                        onClick={handleBulkRunReview}
                        disabled={loading}
                        className="h-9 px-3 gap-1.5 shadow-sm border-primary/20 bg-primary/5 hover:bg-primary/10 text-primary whitespace-nowrap"
                      >
                        <Wand className="w-3.5 h-3.5" />
                        Run Review
                      </ProfessionalButton>

                      <ProfessionalButton
                        variant="outline"
                        size="sm"
                        onClick={() => setBulkMergeModalOpen(true)}
                        disabled={selectedIds.length < 2 || statements.some(s => selectedIds.includes(s.id) && s.status === 'merged')}
                        className="h-9 px-3 gap-1.5 shadow-sm border-primary/20 hover:bg-primary/10 transition-colors"
                      >
                        <Plus className="w-3.5 h-3.5" />
                        {t('statements.merge_transactions')}
                      </ProfessionalButton>

                      <ProfessionalButton
                        variant="destructive"
                        size="sm"
                        onClick={() => setBulkDeleteModalOpen(true)}
                        className="h-9 px-3 gap-1.5 shadow-sm"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                        {t('statements.delete_selected')}
                      </ProfessionalButton>
                    </div>
                  </div>
                </div>
              )}

              <div className="rounded-xl border border-border/50 overflow-x-auto shadow-sm">
                <Table>
                  <TableHeader>
                    <TableRow className="bg-gradient-to-r from-muted/50 to-muted/30 hover:bg-gradient-to-r hover:from-muted/50 hover:to-muted/30 border-b border-border/50">
                      <TableHead className="w-[40px]">
                        <Checkbox
                          checked={statements.length > 0 && selectedIds.length === statements.length}
                          onCheckedChange={(checked) => {
                            if (checked) {
                              setSelectedIds(statements.map(s => s.id));
                            } else {
                              setSelectedIds([]);
                            }
                          }}
                        />
                      </TableHead>
                      {isVisible('id') && <TableHead className="font-bold text-foreground">{t('common.id', { defaultValue: 'ID' })}</TableHead>}
                      <TableHead className="font-bold text-foreground">{t('statements.filename')}</TableHead>
                      {isVisible('labels') && <TableHead className="font-bold text-foreground">{t('statements.labels')}</TableHead>}
                      {isVisible('type') && <TableHead className="font-bold text-foreground">{t('statements.card_type.label', 'Type')}</TableHead>}
                      <TableHead className="font-bold text-foreground">{t('statements.status.label')}</TableHead>
                      {isVisible('review_status') && <TableHead className="font-bold text-foreground">{t('statements.review_status.label')}</TableHead>}
                      {isVisible('transactions') && <TableHead className="font-bold text-foreground">{t('statements.transactions')}</TableHead>}
                      {isVisible('created_at_by') && <TableHead className="font-bold text-foreground">{t('statements.created_at_by', { defaultValue: 'Created at / by' })}</TableHead>}
                      <TableHead className="w-[100px] text-right font-bold text-foreground">{t('statements.actions', { defaultValue: 'Actions' })}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {statements.map((s) => (
                      <TableRow key={s.id} className="hover:bg-muted/60 transition-all duration-200 border-b border-border/30">
                        <TableCell>
                          <Checkbox
                            checked={selectedIds.includes(s.id)}
                            onCheckedChange={(checked) => {
                              if (checked) {
                                setSelectedIds(prev => [...prev, s.id]);
                              } else {
                                setSelectedIds(prev => prev.filter(id => id !== s.id));
                              }
                            }}
                          />
                        </TableCell>
                        {isVisible('id') && <TableCell className="font-mono text-sm text-muted-foreground">#{s.id}</TableCell>}
                        <TableCell className="font-semibold text-foreground">{s.original_filename}</TableCell>
                        {isVisible('labels') && <TableCell>
                          <div className="flex flex-wrap gap-1 items-center min-w-[200px]">
                            {Array.isArray((s as any).labels) && (s as any).labels.map((label: string, idx: number) => (
                              <Badge
                                key={idx}
                                variant="secondary"
                                className="text-[10px] px-1.5 py-0 h-5 bg-primary/10 text-primary border-primary/20 flex items-center gap-1 group/badge"
                              >
                                {label}
                                <button
                                  className="hover:text-destructive transition-colors"
                                  onClick={() => {
                                    const next = (s as any).labels?.filter((_: any, i: number) => i !== idx) || [];
                                    bankStatementApi.updateMeta(s.id, { labels: next }).then(() => {
                                      setStatements((prev) => prev.map((x) => (x.id === s.id ? { ...x, labels: next } : x)));
                                    }).catch((err: any) => {
                                      toast.error(err?.message || t('statements.labels.remove_failed', { defaultValue: 'Failed to remove label' }));
                                    });
                                  }}
                                >
                                  <X className="h-2.5 w-2.5" />
                                </button>
                              </Badge>
                            ))}
                            <Input
                              placeholder={t('expenses.labels.label_placeholder', { defaultValue: 'Add label...' })}
                              className="w-[100px] h-7 text-[10px] px-2 bg-muted/20 border-border/40 focus:bg-background transition-all"
                              value={newLabelValueById[s.id] || ''}
                              onChange={(ev) => setNewLabelValueById((prev) => ({ ...prev, [s.id]: ev.target.value }))}
                              onKeyDown={(ev) => {
                                if (ev.key === 'Enter' && newLabelValueById[s.id]?.trim()) {
                                  const raw = newLabelValueById[s.id].trim();
                                  const existing = (s as any).labels || [];
                                  if (existing.includes(raw)) {
                                    setNewLabelValueById((prev) => ({ ...prev, [s.id]: '' }));
                                    return;
                                  }
                                  const next = [...existing, raw].slice(0, 10);
                                  bankStatementApi.updateMeta(s.id, { labels: next }).then(() => {
                                    setStatements((prev) => prev.map((x) => (x.id === s.id ? { ...x, labels: next } : x)));
                                    setNewLabelValueById((prev) => ({ ...prev, [s.id]: '' }));
                                  }).catch((err: any) => {
                                    toast.error(err?.message || t('statements.labels.add_failed', { defaultValue: 'Failed to add label' }));
                                  });
                                }
                              }}
                            />
                          </div>
                        </TableCell>}
                        {isVisible('type') && (
                          <TableCell>
                            <CardTypeBadge type={(s as any).card_type} />
                          </TableCell>
                        )}
                        <TableCell>
                          <StatusBadge
                            status={s.status}
                            extraction_method={s.extraction_method}
                            analysis_error={s.analysis_error}
                          />
                        </TableCell>
                        {isVisible('review_status') && <TableCell>
                          {s.review_status === 'diff_found' ? (
                            <Button 
                              size="sm" 
                              variant="outline" 
                              className="h-7 text-xs border-amber-500/50 text-amber-600 hover:bg-amber-50"
                              onClick={() => handleReviewClick(s)}
                            >
                              <Wand className="h-3 w-3 mr-1" />
                              Review Diff
                            </Button>
                          ) : (s.review_status === 'reviewed' || s.review_status === 'no_diff') ? (
                            <div className="flex flex-col gap-1 items-start">
                              <Badge variant="outline" className={cn(
                                "font-medium shadow-none",
                                s.review_status === 'reviewed' ? "bg-green-50 text-green-700 border-green-200" : "bg-blue-50 text-blue-700 border-blue-200"
                              )}>
                                {s.review_status === 'reviewed' ? t('statements.review_status.reviewed') : 'Verified'}
                              </Badge>
                              <Button
                                size="sm"
                                variant="ghost"
                                className="h-6 text-[10px] px-2 text-muted-foreground hover:text-foreground"
                                onClick={() => handleReviewClick(s)}
                              >
                                <Eye className="w-3 h-3 mr-1" />
                                View Report
                              </Button>
                            </div>
                          ) : (
                            <div className="flex flex-col gap-1 items-start">
                              <Badge variant="outline" className={cn(
                                "font-medium shadow-none",
                                s.review_status === 'pending'
                                  ? "bg-blue-50 text-blue-700 border-blue-200"
                                  : s.review_status === 'rejected'
                                  ? "bg-amber-50 text-amber-700 border-amber-200"
                                  : s.review_status === 'failed'
                                  ? "bg-red-50 text-red-700 border-red-200"
                                  : "bg-muted/50 text-muted-foreground border-transparent"
                              )}>
                                {s.review_status === 'pending' ? t('statements.review_status.pending', { defaultValue: 'Review Pending' }) :
                                 s.review_status === 'rejected' ? 'Review Dismissed' :
                                 s.review_status === 'failed' ? 'Review Failed' :
                                 t('common.not_started', { defaultValue: 'Not Started' })}
                              </Badge>
                              {(!s.review_status || s.review_status === 'not_started' || s.review_status === 'failed' || s.review_status === 'rejected') && (
                                <Button
                                  size="sm"
                                  variant="ghost"
                                  className="h-6 text-[10px] text-primary hover:bg-primary/5 p-0 px-1"
                                  onClick={() => handleRunReview(s.id)}
                                >
                                  <RotateCcw className="h-2.5 w-2.5 mr-1" />
                                  Trigger Review
                                </Button>
                              )}
                              {(s.review_status === 'pending' || s.review_status === 'rejected' || s.review_status === 'failed') && (
                                <Button
                                  size="sm"
                                  variant="ghost"
                                  className="h-6 text-[10px] text-destructive hover:bg-destructive/5 p-0 px-1"
                                  onClick={() => handleCancelReview(s.id)}
                                >
                                  <X className="h-2.5 w-2.5 mr-1" />
                                  {s.review_status === 'pending' ? 'Cancel Review' : 'Clear Status'}
                                </Button>
                              )}
                            </div>
                          )}
                        </TableCell>}
                        {isVisible('transactions') && <TableCell className="text-center font-medium">{s.extracted_count}</TableCell>}
                        {isVisible('created_at_by') && (
                          <TableCell>
                            <div className="text-sm">
                              <div className="text-muted-foreground">
                                {s.created_at ? new Date(s.created_at).toLocaleString(getLocale(), {
                                  timeZone: timezone,
                                  year: 'numeric',
                                  month: 'short',
                                  day: 'numeric',
                                  hour: '2-digit',
                                  minute: '2-digit'
                                }) : ''}
                              </div>
                              <div className="text-xs text-muted-foreground">
                                {s.created_by_username || s.created_by_email || t('common.unknown')}
                              </div>
                            </div>
                          </TableCell>
                        )}
                        <TableCell className="text-right">
                          <div className="flex items-center gap-1 justify-end">
                            <ShareButton
                              recordType="bank_statement"
                              recordId={s.id}
                              open={shareStatementId === s.id}
                              onOpenChange={(isOpen: boolean) => { if (!isOpen) setShareStatementId(null); }}
                            />
                            <DropdownMenu>
                              <DropdownMenuTrigger asChild>
                                <Button variant="ghost" size="icon">
                                  <MoreHorizontal className="w-4 h-4" />
                                </Button>
                              </DropdownMenuTrigger>
                              <DropdownMenuContent align="end">
                                <DropdownMenuItem onClick={() => openStatement(s.id)}>
                                  <Eye className="mr-2 w-4 h-4" /> {t('common.view', 'View')}
                                </DropdownMenuItem>
                                <DropdownMenuItem onClick={() => setShareStatementId(s.id)}>
                                  <Share2 className="mr-2 w-4 h-4" /> Share
                                </DropdownMenuItem>
                                {isCompleted(s) && s.status !== 'merged' && (
                                  <DropdownMenuItem
                                    disabled={reprocessingLocks.has(s.id)}
                                    onClick={async () => {
                                      if (reprocessingLocks.has(s.id)) return;
                                      try {
                                        setReprocessingLocks(prev => new Set([...prev, s.id]));
                                        await bankStatementApi.reprocess(s.id);
                                        const startPolling = (window as any).startStatementPolling;
                                        if (typeof startPolling === 'function') startPolling([s.id]);
                                        toast.success(t('statements.reprocess.started', { defaultValue: 'Reprocessing started' }));
                                        await loadList();
                                        setTimeout(() => {
                                          setReprocessingLocks(prev => { const next = new Set(prev); next.delete(s.id); return next; });
                                        }, 30000);
                                      } catch (err: any) {
                                        setReprocessingLocks(prev => { const next = new Set(prev); next.delete(s.id); return next; });
                                        toast.error(err?.message || t('statements.reprocess.failed', { defaultValue: 'Failed to reprocess' }));
                                      }
                                    }}
                                  >
                                    {reprocessingLocks.has(s.id) ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RotateCcw className="mr-2 h-4 w-4" />}
                                    {t('statements.reprocess.label', 'Reprocess')}
                                  </DropdownMenuItem>
                                )}
                                <DropdownMenuItem
                                  disabled={previewLoading === s.id || s.status === 'merged'}
                                  onClick={() => handlePreview(s.id)}
                                >
                                  {previewLoading === s.id ? <Loader2 className="mr-2 w-4 h-4 animate-spin" /> : <ExternalLink className="mr-2 w-4 h-4" />}
                                  {t('common.preview', 'Preview')}
                                </DropdownMenuItem>
                                <DropdownMenuItem
                                  disabled={s.status === 'merged'}
                                  onClick={() => handleDownload(s.id, s.original_filename)}
                                >
                                  <Download className="mr-2 w-4 h-4" /> {t('common.download', 'Download')}
                                </DropdownMenuItem>
                                <DropdownMenuSeparator />
                                <DropdownMenuItem
                                  className="text-destructive focus:text-destructive"
                                  onClick={() => { setStatementToDelete(s.id); setDeleteModalOpen(true); }}
                                >
                                  <Trash2 className="mr-2 w-4 h-4" /> {t('common.delete', 'Delete')}
                                </DropdownMenuItem>
                              </DropdownMenuContent>
                            </DropdownMenu>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                    {statements.length === 0 && (
                      <TableRow>
                        <TableCell colSpan={9} className="h-auto p-0 border-none">
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
              {/* Pagination */}
              <div className="flex flex-col sm:flex-row items-center justify-between gap-4 mt-6 pt-6 border-t border-border/50">
                <div className="text-sm text-muted-foreground">
                  Showing <span className="font-medium text-foreground">{statements.length}</span> of <span className="font-medium text-foreground">{totalStatements}</span> statements
                </div>
                <div className="flex items-center gap-2">
                  <ProfessionalButton
                    variant="outline"
                    size="sm"
                    onClick={() => setPage(prev => Math.max(1, prev - 1))}
                    disabled={page === 1}
                    className="h-9 px-4"
                  >
                    {t('common.previous')}
                  </ProfessionalButton>
                  <div className="flex items-center gap-1">
                    {Array.from({ length: Math.ceil(totalStatements / pageSize) }, (_, i) => i + 1)
                      .filter(p => p === 1 || p === Math.ceil(totalStatements / pageSize) || Math.abs(p - page) <= 1)
                      .map((p, i, arr) => (
                        <div key={p} className="flex items-center">
                          {i > 0 && arr[i - 1] !== p - 1 && <span className="text-muted-foreground px-1">...</span>}
                          <ProfessionalButton
                            variant={page === p ? "default" : "outline"}
                            size="sm"
                            onClick={() => setPage(p)}
                            className={`h-9 w-9 p-0 ${page === p ? 'shadow-md shadow-primary/20' : ''}`}
                          >
                            {p}
                          </ProfessionalButton>
                        </div>
                      ))}
                  </div>
                  <ProfessionalButton
                    variant="outline"
                    size="sm"
                    onClick={() => setPage(prev => Math.min(Math.ceil(totalStatements / pageSize), prev + 1))}
                    disabled={page >= Math.ceil(totalStatements / pageSize)}
                    className="h-9 px-4"
                  >
                    {t('common.next')}
                  </ProfessionalButton>
                </div>
              </div>
            </div>
        </ProfessionalCard>
        )}

        {/* Review Diff Modal */}
        {selectedReviewStatement && (
          <ReviewDiffModal
            isOpen={reviewModalOpen}
            onClose={() => setReviewModalOpen(false)}
            originalData={{
              // For statement, we can pass relevant metadata or summary
              filename: selectedReviewStatement.original_filename,
              extracted_count: selectedReviewStatement.extracted_count,
              formatted_extracted_count: selectedReviewStatement.extracted_count, // Fallback if modal looked for something else
              transaction_count: selectedReviewStatement.extracted_count,
              status: selectedReviewStatement.status,
            }}
            reviewResult={{
              ...(selectedReviewStatement.review_result || {}),
              transaction_count: selectedReviewStatement.review_result?.transactions?.length ?? 0
            }}
            onAccept={handleAcceptReview}
            onReject={handleRejectReview}
            onRetrigger={handleRetriggerReview}
            isAccepting={isAcceptingReview}
            isRejecting={isRejectingReview}
            isRetriggering={isRetriggeringReview}
            type="statement"
            readOnly={selectedReviewStatement?.review_status === 'reviewed' || selectedReviewStatement?.review_status === 'no_diff'}
          />
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
          <div className="space-y-6 overflow-visible">
            {/* Hero Header */}
            <div className="bg-gradient-to-r from-primary/10 via-primary/5 to-transparent rounded-2xl border border-primary/20 p-8 backdrop-blur-sm">
              <div className="flex items-center justify-between gap-6">
                <div className="space-y-2">
                  <div className="flex items-center gap-3">
                    <ProfessionalButton
                      variant="outline"
                      size="icon-sm"
                      onClick={() => { setSelected(null); setDetail(null); setRows([]); setSearchParams({}, { replace: true }); }}
                      className="rounded-full"
                    >
                      <ArrowLeft className="h-4 w-4" />
                    </ProfessionalButton>

                    <Badge variant="secondary" className="px-3 py-1 font-mono font-medium self-start h-6">
                      #{selected}
                    </Badge>
                    <CardTypeBadge type={(detail as any)?.card_type} />
                  </div>
                  <h1 className="text-4xl font-bold tracking-tight">
                    {detail?.original_filename || t('statements.statement_detail', { defaultValue: 'Statement Detail' })}
                  </h1>
                  <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-muted-foreground text-sm">
                    {((detail as any)?.created_by_username || (detail as any)?.created_by_email) && (
                      <span className="flex items-center gap-2">
                        <span className="p-1"><FileText className="h-3 w-3" /></span>
                        {t('common.created_by')}: <span className="text-foreground">{(detail as any).created_by_username || (detail as any).created_by_email}</span>
                      </span>
                    )}
                  </div>
                </div>

                <div className="flex flex-wrap items-center gap-3">
                  <ProfessionalButton
                    variant="outline"
                    onClick={() => selected && handlePreview(selected)}
                    disabled={previewLoading === selected || detail?.status === 'merged'}
                    leftIcon={previewLoading === selected ? <Loader2 className="h-4 w-4 animate-spin" /> : <ExternalLink className="h-4 w-4" />}
                  >
                    {t('statements.preview')}
                  </ProfessionalButton>

                  <ProfessionalButton
                    variant="outline"
                    onClick={() => selected && handleDownload(selected, detail?.original_filename)}
                    disabled={detail?.status === 'merged'}
                    leftIcon={<Download className="h-4 w-4" />}
                  >
                    {t('statements.download')}
                  </ProfessionalButton>

                  {detail && isCompleted(detail) && detail.status !== 'merged' && (
                    <ProfessionalButton
                      variant="outline"
                      onClick={async () => {
                        if (!selected) return;
                        if (reprocessingLocks.has(selected)) {
                          toast.warning('Already processing...');
                          return;
                        }
                        const addNotification = (window as any).addAINotification;
                        try {
                          setReprocessingLocks(prev => new Set([...prev, selected]));
                          addNotification?.('processing', 'Reprocessing', `Re-analyzing ${detail?.original_filename}...`);
                          await bankStatementApi.reprocess(selected);
                          addNotification?.('success', 'Started', `Reprocessing ${detail?.original_filename}`);
                          toast.success(t('statements.reprocess.started', { defaultValue: 'Reprocessing started' }));
                          await openStatement(selected);
                          setTimeout(() => {
                            setReprocessingLocks(prev => {
                              const next = new Set(prev);
                              next.delete(selected);
                              return next;
                            });
                          }, 30000);
                        } catch (e: any) {
                          setReprocessingLocks(prev => {
                            const next = new Set(prev);
                            next.delete(selected);
                            return next;
                          });
                          toast.error(e?.message || t('statements.reprocess.failed', { defaultValue: 'Failed to reprocess' }));
                        }
                      }}
                      disabled={reprocessingLocks.has(selected) || loading}
                      leftIcon={reprocessingLocks.has(selected) ? <Loader2 className="h-4 w-4 animate-spin" /> : <RotateCcw className="h-4 w-4" />}
                    >
                      {reprocessingLocks.has(selected) ? 'Processing...' : 'Reprocess'}
                    </ProfessionalButton>
                  )}

                  <ProfessionalButton
                    variant="outline"
                    onClick={toggleSplitView}
                    disabled={detail?.status === 'merged'}
                    leftIcon={<Columns className="h-4 w-4" />}
                  >
                    {isSplitView ? t('statements.standard_view', 'Standard View') : t('statements.parallel_view', 'Parallel View')}
                  </ProfessionalButton>

                  <ProfessionalButton
                    variant="default"
                    onClick={saveRows}
                    disabled={readOnly || detailLoading}
                    className="shadow-lg"
                    leftIcon={detailLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                  >
                    {t('common.save', 'Save')}
                  </ProfessionalButton>
                </div>
              </div>
            </div>

            <div className={cn(
              "flex flex-col gap-6",
              isSplitView && "lg:flex-row lg:items-stretch"
            )}>
              {/* Split View PDF Pane */}
              {isSplitView && splitViewPdfUrl && (
                <div className="lg:w-[45%]">
                  <div className="sticky top-4 h-[calc(100vh-40px)] z-30 flex flex-col">
                    <ProfessionalCard className="flex-1 flex flex-col overflow-hidden p-0 border-primary/30 shadow-2xl ring-1 ring-primary/5">
                      <div className="p-3 border-b flex items-center justify-between bg-muted/30">
                        <div className="flex items-center gap-2">
                          <FileText className="h-4 w-4 text-primary" />
                          <span className="text-xs font-bold uppercase tracking-wider">{t('statements.original_pdf', 'Original PDF')}</span>
                        </div>
                        <ProfessionalButton
                          variant="ghost"
                          size="icon-sm"
                          onClick={() => setIsSplitView(false)}
                        >
                          <X className="h-4 w-4" />
                        </ProfessionalButton>
                      </div>
                      <div className="flex-1 min-h-0 bg-muted/10">
                        {splitViewPdfUrl && (
                          <embed
                            key={splitViewPdfUrl}
                            src={splitViewPdfUrl}
                            type="application/pdf"
                            className="w-full h-full border-none"
                          />
                        )}
                      </div>
                      <div className="p-2 border-t text-[10px] text-muted-foreground bg-muted/30 text-center">
                        {t('statements.split_view_hint', 'Review transactions alongside the PDF')}
                      </div>
                    </ProfessionalCard>
                  </div>
                </div>
              )}

              {/* Transactions/Details Pane */}
              <div className={cn(
                "space-y-6",
                isSplitView ? "lg:w-[55%] flex-1" : "w-full"
              )}>


            {/* Status & Alerts Section */}
            {(readOnly || (detail as any)?.error_message) && (
              <div className="space-y-4">
                {detail?.status === 'processing' && (
                  <div className="bg-amber-500/10 border border-amber-500/20 rounded-xl p-4 flex items-center gap-3 text-amber-700 dark:text-amber-400 slide-in">
                    <Loader2 className="h-5 w-5 animate-spin" />
                    <div className="text-sm">
                      <span className="font-bold">{t('common.processing', 'Processing')}:</span> {t('statements.processing_message', { defaultValue: 'Statement is being analyzed by AI. Editing is disabled until completion.' })}
                    </div>
                  </div>
                )}

                {(detail as any)?.error_message && (
                  <div className="bg-destructive/10 border border-destructive/20 rounded-xl p-4 flex items-start gap-3 text-destructive slide-in">
                    <Trash2 className="h-5 w-5 mt-0.5 flex-shrink-0" />
                    <div className="text-sm">
                      <span className="font-bold">{t('common.analysis_error', 'Analysis Error')}:</span> {(detail as any).error_message}
                    </div>
                  </div>
                )}

                  {detail?.status !== 'merged' && (
                    <div className="bg-blue-500/10 border border-blue-500/20 rounded-xl p-4 flex items-center gap-3 text-blue-700 dark:text-blue-400 slide-in">
                      <div className="h-2 w-2 rounded-full bg-blue-500 animate-pulse" />
                      <div className="text-sm">
                        <strong>{t('common.note', { defaultValue: 'Note:' })}</strong> {t('statements.transaction_edit_note', { defaultValue: 'Transaction information should match the uploaded bank statement file. Only edit if corrections are needed.' })}
                      </div>
                    </div>
                  )}
              </div>
            )}



            {/* Summary Statistics */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <ProfessionalCard variant="elevated" className="p-0 overflow-hidden border-none shadow-sm">
                <div className="p-5 flex flex-col items-center justify-center bg-background border-b-4 border-primary/20">
                  <span className="text-xs font-bold text-muted-foreground uppercase tracking-wider mb-1">{t('statements.transactions', { defaultValue: 'Transactions' })}</span>
                  <div className="flex items-baseline gap-2">
                    <span className="text-3xl font-black text-foreground">{rows.length}</span>
                    <FileText className="h-4 w-4 text-primary opacity-50" />
                  </div>
                </div>
              </ProfessionalCard>

              <ProfessionalCard variant="elevated" className="p-0 overflow-hidden border-none shadow-sm">
                <div className="p-5 flex flex-col items-center justify-center bg-background border-b-4 border-success/20">
                  <span className="text-xs font-bold text-muted-foreground uppercase tracking-wider mb-1">{t('statements.total_income', { defaultValue: 'Total Income' })}</span>
                  <div className="text-2xl font-black text-success">
                    <CurrencyDisplay amount={totalIncome} currency="USD" />
                  </div>
                </div>
              </ProfessionalCard>

              <ProfessionalCard variant="elevated" className="p-0 overflow-hidden border-none shadow-sm">
                <div className="p-5 flex flex-col items-center justify-center bg-background border-b-4 border-destructive/20">
                  <span className="text-xs font-bold text-muted-foreground uppercase tracking-wider mb-1">{t('statements.total_expenses', { defaultValue: 'Total Expenses' })}</span>
                  <div className="text-2xl font-black text-destructive">
                    <CurrencyDisplay amount={totalExpense} currency="USD" />
                  </div>
                </div>
              </ProfessionalCard>

              <ProfessionalCard variant="elevated" className="p-0 overflow-hidden border-none shadow-sm">
                <div className="p-5 flex flex-col items-center justify-center bg-background border-b-4 border-blue-500/20">
                  <span className="text-xs font-bold text-muted-foreground uppercase tracking-wider mb-1">{t('statements.net_amount', { defaultValue: 'Net Amount' })}</span>
                  <div className={`text-2xl font-black ${netAmount >= 0 ? 'text-success' : 'text-destructive'}`}>
                    <CurrencyDisplay amount={netAmount} currency="USD" />
                  </div>
                </div>
              </ProfessionalCard>
            </div>

            {/* Details Card */}
            <ProfessionalCard>
              <CardHeader>
                <CardTitle>{t('statements.details', { defaultValue: 'Details' })}</CardTitle>
                {detail && (
                  <div className="mt-3 space-y-2">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium">{t('statements.analysis_status', { defaultValue: 'Analysis Status' })}:</span>
                      {(detail.status === 'processed' || detail.status === 'done') ? (
                        <Badge variant="success" className="h-6">{t('common.done', 'Done')}</Badge>
                      ) : detail.status === 'processing' ? (
                        <Badge variant="secondary" className="h-6 bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400 border-amber-200 dark:border-amber-800 capitalize">
                          {t('common.processing', 'Processing')}
                        </Badge>
                      ) : detail.status === 'failed' ? (
                        <Badge variant="destructive" className="h-6">Failed</Badge>
                      ) : detail.status === 'uploaded' ? (
                        <Badge variant="secondary" className="h-6 bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400 border-yellow-200 dark:border-yellow-800 capitalize">
                          {t('common.uploaded', 'Uploaded')}
                        </Badge>
                      ) : null}
                    </div>
                    {detail.analysis_error && detail.status === 'failed' && (
                      <Alert className="border-red-200 bg-red-50">
                        <AlertCircle className="h-4 w-4 text-red-600" />
                        <AlertDescription className="text-red-800">
                          <details className="cursor-pointer">
                            <summary className="font-medium mb-1">{t('statements.analysis_failed_click_details', { defaultValue: 'Analysis failed (click for details)' })}</summary>
                            <div className="mt-2 text-xs font-mono bg-red-100 p-2 rounded border border-red-200 overflow-x-auto">
                              {detail.analysis_error}
                            </div>
                          </details>
                        </AlertDescription>
                      </Alert>
                    )}
                  </div>
                )}
              </CardHeader>
              <CardContent className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="text-sm">{t('statements.original_filename', { defaultValue: 'Original Filename' })}</label>
                  <Input value={detail?.original_filename || ''} disabled={true} />
                </div>
                <div>
                  <label className="text-sm">{t('statements.uploaded_at', { defaultValue: 'Uploaded At' })}</label>
                  <Input value={detail?.created_at ? new Date(detail.created_at).toLocaleString(getLocale(), { 
                    timeZone: timezone,
                    year: 'numeric',
                    month: 'short',
                    day: 'numeric',
                    hour: '2-digit',
                    minute: '2-digit'
                  }) : ''} disabled={true} />
                </div>
                {((detail as any)?.created_by_username || (detail as any)?.created_by_email) && (
                  <div>
                    <label className="text-sm">{t('common.created_by')}</label>
                    <Input value={(detail as any).created_by_username || (detail as any).created_by_email || t('common.unknown')} disabled={true} />
                  </div>
                )}
                <div>
                  <label className="text-sm">{t('statements.extracted_count', { defaultValue: 'Extracted Transactions' })}</label>
                  <Input value={detail?.extracted_count || 0} disabled={true} />
                </div>
              </CardContent>
            </ProfessionalCard>

            {/* Details Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Labels Card */}
              <ProfessionalCard className="lg:col-span-1">
                <CardHeader className="pb-3 border-b border-border/50 mb-4 px-0">
                  <div className="flex items-center gap-2">
                    <Tag className="w-4 h-4 text-primary" />
                    <CardTitle className="text-sm font-bold uppercase tracking-tight">{t('statements.labels')}</CardTitle>
                  </div>
                </CardHeader>
                <div className="space-y-4">
                  <div className="flex flex-wrap gap-2 min-h-[40px]">
                    {statementLabels.length > 0 ? (
                      statementLabels.slice(0, 10).map((lab, idx) => (
                        <div key={`stmt-lab-${idx}`}>
                          <Badge className="pl-2 pr-1.5 py-1 gap-1 border border-border/50 bg-muted/50 hover:bg-muted font-medium transition-all text-foreground">
                            {lab}
                            {!readOnly && (
                              <button
                                className="ml-1 rounded-full p-0.5 hover:bg-destructive/10 hover:text-destructive text-muted-foreground transition-colors"
                                onClick={async () => {
                                  try {
                                    const next = statementLabels.filter((l) => l !== lab);
                                    if (!selected) return;
                                    const resp = await bankStatementApi.updateMeta(selected, { labels: next });
                                    setStatementLabels((resp.statement as any).labels || []);
                                    setDetail(prev => prev ? { ...prev, labels: (resp.statement as any).labels || [] } : prev);
                                  } catch (err: any) {
                                    toast.error(err?.message || t('statements.labels.remove_failed', { defaultValue: 'Failed to remove label' }));
                                  }
                                }}
                              >
                                <X className="w-3 h-3" />
                              </button>
                            )}
                          </Badge>
                        </div>
                      ))
                    ) : (
                      <span className="text-xs text-muted-foreground italic px-1">{t('statements.no_labels', { defaultValue: 'No labels' })}</span>
                    )}
                  </div>

                  {!readOnly && (
                    <div className="relative group">
                      <Tag className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground group-focus-within:text-primary transition-colors" />
                      <Input
                        placeholder={t('statements.add_label_placeholder', { defaultValue: 'Add label (Enter)' })}
                        value={newStatementLabel}
                        className="pl-9 h-10 border-border/50 bg-muted/20 focus:bg-background rounded-lg transition-all"
                        onChange={(ev) => setNewStatementLabel(ev.target.value)}
                        onKeyDown={async (ev) => {
                          if (ev.key === 'Enter') {
                            const raw = (newStatementLabel || '').trim();
                            if (!raw) return;
                            const existing = statementLabels || [];
                            if (existing.includes(raw)) { setNewStatementLabel(''); return; }
                            if (existing.length >= 10) { toast.error(t('common.max_labels_reached', { defaultValue: 'Maximum of 10 labels reached' })); return; }
                            try {
                              if (!selected) return;
                              const next = [...existing, raw];
                              const resp = await bankStatementApi.updateMeta(selected, { labels: next });
                              setStatementLabels((resp.statement as any).labels || []);
                              setDetail(prev => prev ? { ...prev, labels: (resp.statement as any).labels || [] } : prev);
                              setNewStatementLabel('');
                              toast.success(t('common.label_added', { defaultValue: 'Label added' }));
                            } catch (err: any) {
                              toast.error(err?.message || t('statements.labels.add_failed', { defaultValue: 'Failed to add label' }));
                            }
                          }
                        }}
                      />
                    </div>
                  )}
                </div>
              </ProfessionalCard>

              {/* Notes Card */}
              <ProfessionalCard className="lg:col-span-2 flex flex-col">
                <CardHeader className="pb-3 border-b border-border/50 mb-4 px-0 flex flex-row items-center justify-between">
                  <div className="flex items-center gap-2">
                    <FileText className="w-4 h-4 text-primary" />
                    <CardTitle className="text-sm font-bold uppercase tracking-tight">{t('statements.notes')}</CardTitle>
                  </div>
                  <ProfessionalButton
                    variant="ghost"
                    size="sm"
                    onClick={saveMeta}
                    disabled={readOnly || detailLoading}
                    className="h-8 text-xs font-bold text-primary hover:text-primary hover:bg-primary/5"
                  >
                    {detailLoading ? <Loader2 className="w-3 h-3 mr-1 animate-spin" /> : <Save className="w-3 h-3 mr-1" />}
                    {t('common.save_notes', { defaultValue: 'Save Notes' })}
                  </ProfessionalButton>
                </CardHeader>
                <div className="flex-1">
                  <Textarea
                    value={statementNotes}
                    onChange={(e) => setStatementNotes(e.target.value)}
                    placeholder={t('statements.notes_placeholder', { defaultValue: 'Add any notes about this statement...' })}
                    className="min-h-[100px] border-border/50 bg-muted/20 focus:bg-background rounded-lg transition-all resize-none p-4"
                    disabled={readOnly}
                  />
                </div>
              </ProfessionalCard>
            </div>

            {/* Transactions Table */}
            <ProfessionalCard variant="elevated" className="overflow-hidden">
              <CardHeader className="flex flex-row items-center justify-between pb-4 border-b border-border/50 mb-6 px-0">
                <div>
                  <CardTitle className="text-xl font-bold">{t('statements.transactions_list', { defaultValue: 'Transactions List' })}</CardTitle>
                  <p className="text-sm text-muted-foreground mt-1">{t('statements.edit_transactions_instruction', { defaultValue: 'Review and edit transaction details if needed' })}</p>
                </div>
                <div className="flex items-center gap-2">
                  <ProfessionalButton
                    variant="outline"
                    size="sm"
                    onClick={exportToCSV}
                    disabled={rows.length === 0}
                    className="h-9 px-3 border-border/50"
                  >
                    <FileText className="w-4 h-4 mr-2 text-primary" />
                    {t('statements.export_csv', { defaultValue: 'Export CSV' })}
                  </ProfessionalButton>
                  <ProfessionalButton
                    variant="outline"
                    size="sm"
                    onClick={addEmptyRow}
                    disabled={readOnly}
                    className="h-9 px-3 border-border/50"
                  >
                    <Plus className="w-4 h-4 mr-2 text-primary" />
                    {t('statements.add_row', { defaultValue: 'Add Row' })}
                  </ProfessionalButton>
                </div>
              </CardHeader>

              <div className="rounded-xl border border-border/50 overflow-x-auto shadow-sm bg-background">
                <Table>
                  <TableHeader>
                    <TableRow className="bg-muted/30 hover:bg-muted/30 border-b border-border/50">
                      <TableHead className="w-[60px] font-bold text-foreground text-center">{t('common.id', { defaultValue: 'ID' })}</TableHead>
                      <TableHead className="w-[180px] font-bold text-foreground">{t('statements.table_date', { defaultValue: 'Date' })}</TableHead>
                      <TableHead className="min-w-[250px] font-bold text-foreground">{t('statements.table_description', { defaultValue: 'Description' })}</TableHead>
                      <TableHead className="w-[120px] font-bold text-foreground text-right">{t('statements.table_amount', { defaultValue: 'Amount' })}</TableHead>
                      <TableHead className="w-[120px] font-bold text-foreground text-right">{t('statements.table_balance', { defaultValue: 'Balance' })}</TableHead>
                      <TableHead className="w-[140px] font-bold text-foreground">{t('statements.table_type', { defaultValue: 'Type' })}</TableHead>
                      <TableHead className="w-[180px] font-bold text-foreground">{t('statements.table_category', { defaultValue: 'Category' })}</TableHead>
                      <TableHead className="w-[120px] font-bold text-foreground text-center">{t('common.reference', { defaultValue: 'Reference' })}</TableHead>
                      <TableHead className="w-[80px] text-right font-bold text-foreground">{t('statements.table_actions', { defaultValue: 'Actions' })}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {rows.map((r, idx) => (
                      <ContextMenu key={idx}>
                        <ContextMenuTrigger asChild>
                          <TableRow className={`hover:bg-muted/20 transition-colors border-b border-border/30${(r as any).backend_id && (r as any).backend_id === highlightedBackendId ? ' ring-2 ring-inset ring-blue-400 bg-blue-50/50 dark:bg-blue-950/20' : ''}`}>
                            <TableCell className="text-center font-mono text-xs text-muted-foreground">{(r as any).id ?? idx + 1}</TableCell>
                            <TableCell>
                              {editingRow === idx ? (
                                <Popover>
                                  <PopoverTrigger asChild>
                                    <Button variant="outline" className="w-full justify-start text-left font-normal h-9 border-border/50 bg-muted/20" disabled={readOnly}>
                                      <CalendarIcon className="mr-2 h-4 w-4 text-primary" />
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
                                          const iso = formatDateToISO(d);
                                          setRows(prev => prev.map((x, i) => i === idx ? { ...x, date: iso } : x));
                                        }}
                                        initialFocus
                                      />
                                    </PopoverContent>
                                  )}
                                </Popover>
                              ) : (
                                <span className="text-sm font-medium">{r.date ? format(safeParseDateString(r.date), 'PP') : '-'}</span>
                              )}
                            </TableCell>
                            <TableCell>
                              {editingRow === idx ? (
                                <div className="space-y-1">
                                  <Textarea
                                    value={r.description}
                                    onChange={(e) => setRows(prev => prev.map((x, i) => i === idx ? { ...x, description: e.target.value } : x))}
                                    rows={2}
                                    maxLength={500}
                                    className="w-full border-border/50 bg-muted/20 focus:bg-background text-sm min-h-[60px]"
                                  />
                                </div>
                              ) : (
                                <span className="text-sm break-words line-clamp-2" title={r.description}>{r.description}</span>
                              )}
                            </TableCell>
                            <TableCell className="text-right">
                              {editingRow === idx ? (
                                <Input
                                  type="number"
                                  value={r.amount}
                                  onChange={(e) => setRows(prev => prev.map((x, i) => i === idx ? { ...x, amount: Number(e.target.value) } : x))}
                                  className="h-9 border-border/50 bg-muted/20 text-right font-bold w-full"
                                />
                              ) : (
                                <span className={`text-sm font-bold ${r.transaction_type === 'credit' ? 'text-success' : 'text-destructive'}`}>
                                  <CurrencyDisplay amount={r.amount} currency="USD" />
                                </span>
                              )}
                            </TableCell>
                            <TableCell className="text-right">
                              {editingRow === idx ? (
                                <Input
                                  type="number"
                                  value={r.balance ?? ''}
                                  onChange={(e) => setRows(prev => prev.map((x, i) => i === idx ? { ...x, balance: e.target.value === '' ? null : Number(e.target.value) } : x))}
                                  className="h-9 border-border/50 bg-muted/20 text-right w-full"
                                />
                              ) : (
                                <span className="text-sm font-mono opacity-80">{r.balance !== null ? <CurrencyDisplay amount={r.balance} currency="USD" /> : '-'}</span>
                              )}
                            </TableCell>
                            <TableCell>
                              {editingRow === idx ? (
                                <Select value={r.transaction_type} onValueChange={(v) => setRows(prev => prev.map((x, i) => i === idx ? { ...x, transaction_type: v as 'debit' | 'credit' } : x))}>
                                  <SelectTrigger className="h-9 border-border/50 bg-muted/20 w-full"><SelectValue /></SelectTrigger>
                                  <SelectContent>
                                    <SelectItem value="debit">{t('statements.type_debit', { defaultValue: 'Debit' })}</SelectItem>
                                    <SelectItem value="credit">{t('statements.type_credit', { defaultValue: 'Credit' })}</SelectItem>
                                  </SelectContent>
                                </Select>
                              ) : (
                                <Badge className={`capitalize font-medium text-[10px] bg-transparent border border-current ${r.transaction_type === 'credit' ? 'border-success/30 text-success bg-success/5' : 'border-destructive/30 text-destructive bg-destructive/5'}`}>
                                  {r.transaction_type}
                                </Badge>
                              )}
                            </TableCell>
                            <TableCell>
                              {editingRow === idx ? (
                                <Select value={r.category || 'Other'} onValueChange={(v) => setRows(prev => prev.map((x, i) => i === idx ? { ...x, category: v } : x))}>
                                  <SelectTrigger className="h-9 border-border/50 bg-muted/20 w-full"><SelectValue /></SelectTrigger>
                                  <SelectContent>
                                    {CATEGORY_OPTIONS.map((c) => (<SelectItem key={c} value={c}>{c}</SelectItem>))}
                                  </SelectContent>
                                </Select>
                              ) : (
                                <Badge className="font-normal text-muted-foreground border-border/50 bg-transparent border">
                                  {r.category || '-'}
                                </Badge>
                              )}
                            </TableCell>
                            <TableCell className="text-center">
                              <div className="flex flex-col gap-1">
                                {Boolean((r as any).expense_id) && (
                                  <Badge className="bg-destructive/5 text-destructive border-destructive/20 border text-[10px] h-5 justify-center">
                                    EXP #{(r as any).expense_id}
                                  </Badge>
                                )}
                                {Boolean((r as any).invoice_id) && (
                                  <Badge className="bg-success/5 text-success border-success/20 border text-[10px] h-5 justify-center">
                                    INV #{(r as any).invoice_id}
                                  </Badge>
                                )}
                                {Boolean((r as any).linked_transfer) && (
                                  <Badge
                                    className="bg-blue-500/10 text-blue-600 border-blue-500/20 border text-[10px] h-5 justify-center gap-1 cursor-pointer hover:bg-blue-500/20 transition-colors"
                                    title={`Jump to: ${(r as any).linked_transfer?.linked_statement_filename}`}
                                    onClick={() => openStatement(
                                      (r as any).linked_transfer.linked_statement_id,
                                      (r as any).linked_transfer.linked_transaction_id
                                    )}
                                  >
                                    <ArrowLeftRight className="w-2.5 h-2.5" />
                                    {(r as any).linked_transfer?.link_type === 'fx_conversion' ? 'FX' : 'TRF'}
                                  </Badge>
                                )}
                                {!Boolean((r as any).expense_id) && !Boolean((r as any).invoice_id) && !Boolean((r as any).linked_transfer) && (
                                  <span className="text-xs text-muted-foreground opacity-50">-</span>
                                )}
                              </div>
                            </TableCell>
                            <TableCell className="text-right">
                              <div className="flex items-center justify-end gap-2">
                                {editingRow === idx ? (
                                  <ProfessionalButton
                                    size="sm"
                                    onClick={async () => {
                                      setEditingRow(null);
                                      await saveRows();
                                    }}
                                    disabled={readOnly}
                                    className="h-8 px-3"
                                  >
                                    {t('common.done', { defaultValue: 'Done' })}
                                  </ProfessionalButton>
                                ) : (
                                  <DropdownMenu>
                                    <DropdownMenuTrigger asChild>
                                      <Button variant="ghost" className="h-8 w-8 p-0 hover:bg-muted/50 transition-colors" disabled={readOnly}>
                                        <MoreHorizontal className="h-4 w-4 text-muted-foreground" />
                                      </Button>
                                    </DropdownMenuTrigger>
                                    <DropdownMenuContent align="end" className="w-48">
                                      <DropdownMenuItem onClick={() => setEditingRow(idx)} disabled={readOnly}>
                                        <Edit className="w-4 h-4 mr-2 text-primary" />
                                        {t('common.edit', { defaultValue: 'Edit' })}
                                      </DropdownMenuItem>

                                      <DropdownMenuSeparator />

                                      <DropdownMenuItem
                                        onClick={() => {
                                          setLinkingRowIdx(idx);
                                          setLinkTransferModalOpen(true);
                                          setLinkTransferModalMounted(true);
                                        }}
                                        disabled={readOnly || Boolean((r as any).linked_transfer) || !(r as any).backend_id}
                                      >
                                        <ArrowLeftRight className="w-4 h-4 mr-2 text-blue-500" />
                                        {Boolean((r as any).linked_transfer) ? 'Transfer linked' : 'Link Transfer'}
                                      </DropdownMenuItem>
                                      {Boolean((r as any).linked_transfer) && (
                                        <DropdownMenuItem
                                          onClick={() => handleUnlinkTransfer(idx)}
                                          className="text-destructive focus:text-destructive"
                                          disabled={readOnly}
                                        >
                                          <X className="w-4 h-4 mr-2" />
                                          Unlink Transfer
                                        </DropdownMenuItem>
                                      )}

                                      <DropdownMenuSeparator />

                                      {r.transaction_type === 'debit' && (
                                        <>
                                          <DropdownMenuItem
                                            onClick={() => createExpenseFromTransaction(idx)}
                                            disabled={readOnly || Boolean((r as any).expense_id)}
                                          >
                                            <Plus className="w-4 h-4 mr-2 text-success" />
                                            {Boolean((r as any).expense_id) ? `Expense linked` : t('statements.add_to_expense', { defaultValue: 'Add to Expense' })}
                                          </DropdownMenuItem>
                                          {Boolean((r as any).expense_id) && (
                                            <>
                                              <DropdownMenuItem
                                                onClick={async () => {
                                                  try {
                                                    await navigator.clipboard.writeText(String((r as any).expense_id));
                                                    toast.success(`Copied Expense ID ${(r as any).expense_id}`);
                                                  } catch (e) {
                                                    toast.error(t('common.copy_failed', { defaultValue: 'Failed to copy' }));
                                                  }
                                                }}
                                              >
                                                <Copy className="w-4 h-4 mr-2" />
                                                {t('common.copy_id', { defaultValue: 'Copy ID' })}
                                              </DropdownMenuItem>
                                              <DropdownMenuItem
                                                onClick={async () => {
                                                  if (!confirm(t('common.confirm_delete', { defaultValue: 'Are you sure?' }))) return;
                                                  try {
                                                    const expId = (r as any).expense_id;
                                                    await expenseApi.deleteExpense(expId);
                                                    toast.success(t('expenses.delete_success', { defaultValue: 'Expense deleted' }));
                                                    setRows(prev => prev.map((row, i) => i === idx ? { ...row, expense_id: null } : row));
                                                    const backendId = (r as any).backend_id;
                                                    if (selected && backendId) {
                                                      await bankStatementApi.patchTransaction(selected, backendId, { expense_id: null });
                                                      await openStatement(selected);
                                                    }
                                                  } catch (e: any) {
                                                    toast.error(e?.message || t('common.delete_failed', { defaultValue: 'Failed to delete' }));
                                                  }
                                                }}
                                                className="text-destructive focus:text-destructive"
                                              >
                                                <Trash2 className="w-4 h-4 mr-2" />
                                                {t('statements.delete_expense', { defaultValue: 'Delete Expense' })}
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
                                            <Plus className="w-4 h-4 mr-2 text-success" />
                                            {Boolean((r as any).invoice_id) ? 'Invoice linked' : t('statements.add_to_invoice', { defaultValue: 'Add to Invoice' })}
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
                                                    toast.error(t('common.copy_failed', { defaultValue: 'Failed to copy' }));
                                                  }
                                                }}
                                              >
                                                <Copy className="w-4 h-4 mr-2" />
                                                {t('common.copy_id', { defaultValue: 'Copy ID' })}
                                              </DropdownMenuItem>
                                              <DropdownMenuItem
                                                onClick={async () => {
                                                  if (!confirm(t('common.confirm_delete', { defaultValue: 'Are you sure?' }))) return;
                                                  try {
                                                    const invId = Number((r as any).invoice_id);
                                                    await invoiceApi.deleteInvoice(invId);
                                                    toast.success(t('invoices.delete_success', { defaultValue: 'Invoice deleted' }));
                                                    setRows(prev => prev.map((row, i) => i === idx ? { ...row, invoice_id: null } : row));
                                                    const backendId = (r as any).backend_id;
                                                    if (selected && backendId) {
                                                      await bankStatementApi.patchTransaction(selected, backendId, { invoice_id: null });
                                                      await openStatement(selected);
                                                    }
                                                  } catch (e: any) {
                                                    let errorMessage = e?.message || t('invoices.delete_failed', { defaultValue: 'Failed to delete invoice' });
                                                    if (errorMessage.includes('linked expenses')) {
                                                      errorMessage = t('invoices.delete_error_linked_expenses');
                                                    }
                                                    toast.error(errorMessage);
                                                  }
                                                }}
                                                className="text-destructive focus:text-destructive"
                                              >
                                                <Trash2 className="w-4 h-4 mr-2" />
                                                {t('statements.delete_invoice', { defaultValue: 'Delete Invoice' })}
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
                        </ContextMenuTrigger>
                        <ContextMenuContent className="w-56">
                          <ContextMenuItem onClick={() => setEditingRow(idx)} disabled={readOnly}>
                            <Edit className="w-4 h-4 mr-2 text-primary" />
                            {t('common.edit', { defaultValue: 'Edit' })}
                          </ContextMenuItem>

                          <ContextMenuSeparator />

                          {r.transaction_type === 'debit' && (
                            <>
                              <ContextMenuItem
                                onClick={() => createExpenseFromTransaction(idx)}
                                disabled={readOnly || Boolean((r as any).expense_id)}
                              >
                                <Plus className="w-4 h-4 mr-2 text-success" />
                                {Boolean((r as any).expense_id) ? `Expense linked` : t('statements.add_to_expense', { defaultValue: 'Add to Expense' })}
                              </ContextMenuItem>
                              {Boolean((r as any).expense_id) && (
                                <>
                                  <ContextMenuItem
                                    onClick={async () => {
                                      try {
                                        await navigator.clipboard.writeText(String((r as any).expense_id));
                                        toast.success(`Copied Expense ID ${(r as any).expense_id}`);
                                      } catch (e) {
                                        toast.error(t('common.copy_failed', { defaultValue: 'Failed to copy' }));
                                      }
                                    }}
                                  >
                                    <Copy className="w-4 h-4 mr-2" />
                                    {t('common.copy_id', { defaultValue: 'Copy ID' })}
                                  </ContextMenuItem>
                                  <ContextMenuItem
                                    onClick={async () => {
                                      if (!confirm(t('common.confirm_delete', { defaultValue: 'Are you sure?' }))) return;
                                      try {
                                        const expId = (r as any).expense_id;
                                        await expenseApi.deleteExpense(expId);
                                        toast.success(t('expenses.delete_success', { defaultValue: 'Expense deleted' }));
                                        setRows(prev => prev.map((row, i) => i === idx ? { ...row, expense_id: null } : row));
                                        const backendId = (r as any).backend_id;
                                        if (selected && backendId) {
                                          await bankStatementApi.patchTransaction(selected, backendId, { expense_id: null });
                                          await openStatement(selected);
                                        }
                                      } catch (e: any) {
                                        toast.error(e?.message || t('common.delete_failed', { defaultValue: 'Failed to delete' }));
                                      }
                                    }}
                                    className="text-destructive focus:text-destructive"
                                  >
                                    <Trash2 className="w-4 h-4 mr-2" />
                                    {t('statements.delete_expense', { defaultValue: 'Delete Expense' })}
                                  </ContextMenuItem>
                                </>
                              )}
                            </>
                          )}

                          {r.transaction_type === 'credit' && (
                            <>
                              <ContextMenuItem
                                onClick={() => createInvoiceFromTransaction(idx)}
                                disabled={readOnly || Boolean((r as any).invoice_id)}
                              >
                                <Plus className="w-4 h-4 mr-2 text-success" />
                                {Boolean((r as any).invoice_id) ? 'Invoice linked' : t('statements.add_to_invoice', { defaultValue: 'Add to Invoice' })}
                              </ContextMenuItem>
                              {Boolean((r as any).invoice_id) && (
                                <>
                                  <ContextMenuItem
                                    onClick={async () => {
                                      try {
                                        const invId = Number((r as any).invoice_id);
                                        const inv = await invoiceApi.getInvoice(invId);
                                        const toCopy = inv.number || String(invId);
                                        await navigator.clipboard.writeText(toCopy);
                                        toast.success(`Copied Invoice No ${toCopy}`);
                                      } catch (e) {
                                        toast.error(t('common.copy_failed', { defaultValue: 'Failed to copy' }));
                                      }
                                    }}
                                  >
                                    <Copy className="w-4 h-4 mr-2" />
                                    {t('common.copy_id', { defaultValue: 'Copy ID' })}
                                  </ContextMenuItem>
                                  <ContextMenuItem
                                    onClick={async () => {
                                      if (!confirm(t('common.confirm_delete', { defaultValue: 'Are you sure?' }))) return;
                                      try {
                                        const invId = Number((r as any).invoice_id);
                                        await invoiceApi.deleteInvoice(invId);
                                        toast.success(t('invoices.delete_success', { defaultValue: 'Invoice deleted' }));
                                        setRows(prev => prev.map((row, i) => i === idx ? { ...row, invoice_id: null } : row));
                                        const backendId = (r as any).backend_id;
                                        if (selected && backendId) {
                                          await bankStatementApi.patchTransaction(selected, backendId, { invoice_id: null });
                                          await openStatement(selected);
                                        }
                                      } catch (e: any) {
                                        let errorMessage = e?.message || t('invoices.delete_failed', { defaultValue: 'Failed to delete invoice' });
                                        if (errorMessage.includes('linked expenses')) {
                                          errorMessage = t('invoices.delete_error_linked_expenses');
                                        }
                                        toast.error(errorMessage);
                                      }
                                    }}
                                    className="text-destructive focus:text-destructive"
                                  >
                                    <Trash2 className="w-4 h-4 mr-2" />
                                    {t('statements.delete_invoice', { defaultValue: 'Delete Invoice' })}
                                  </ContextMenuItem>
                                </>
                              )}
                            </>
                          )}
                        </ContextMenuContent>
                      </ContextMenu>
                    ))}
                    {rows.length === 0 && (
                      <TableRow>
                        <TableCell colSpan={9} className="h-32 text-center text-muted-foreground italic">
                          <div className="flex flex-col items-center justify-center gap-2">
                            <FileText className="h-8 w-8 opacity-20" />
                            {t('statements.no_transactions', { defaultValue: 'No transactions found' })}
                          </div>
                        </TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>
              </div>
            </ProfessionalCard>
              </div>
            </div>
          </div>
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
                  toast.success(t('invoices.create_success', { defaultValue: 'Invoice created successfully!' }));
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
          <DialogContent className="sm:max-w-md flex flex-col max-h-[90vh]">
            <DialogHeader>
              <DialogTitle>{t('statements.upload_statement', { defaultValue: 'Upload Statement' })}</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 overflow-y-auto flex-1 pr-1">
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
                  {t('statements.card_type.label', 'Card Type')}
                </label>
                <Select value={cardType} onValueChange={setCardType}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="auto">Auto-detect (AI)</SelectItem>
                    <SelectItem value="debit">Debit Card (Standard)</SelectItem>
                    <SelectItem value="credit">Credit Card (Inverted)</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div>
                <label className="text-sm font-medium mb-2 block">
                  {t('statements.select_files')}
                </label>
                <div 
                  className={cn(
                    "border-2 border-dashed rounded-lg p-6 text-center transition-colors",
                    dragActive ? "border-primary bg-primary/10" : "border-muted-foreground/25"
                  )}
                  onDragOver={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    setDragActive(true);
                  }}
                  onDragLeave={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    setDragActive(false);
                  }}
                  onDrop={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    setDragActive(false);
                    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
                      const newFiles = Array.from(e.dataTransfer.files);
                      setFiles(prev => {
                        const combined = [...prev, ...newFiles];
                        if (combined.length > 12) {
                          toast.warning(t('statements.max_files_warning', { defaultValue: 'Maximum 12 files allowed. Some files were ignored.' }));
                          return combined.slice(0, 12);
                        }
                        return combined;
                      });
                    }
                  }}
                >
                  <Upload className="w-8 h-8 mx-auto mb-2 text-muted-foreground" />
                  <div className="text-sm text-muted-foreground mb-2">
                    {files.length > 0
                      ? `${files.length} file(s) selected`
                      : t('statements.drop_files_here')
                    }
                  </div>
                  <div className="relative inline-flex">
                    <span className="inline-flex items-center px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm font-medium pointer-events-none">
                      <Upload className="w-4 h-4 mr-2" />
                      {t('statements.choose_files')}
                    </span>
                    <input
                      type="file"
                      accept=".pdf,.csv,.jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp,application/pdf,text/csv,application/vnd.ms-excel"
                      multiple
                      className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                      onChange={(e) => {
                        const newFiles = Array.from(e.target.files || []);
                        setFiles(prev => {
                          const combined = [...prev, ...newFiles];
                          if (combined.length > 12) {
                            toast.warning(t('statements.max_files_warning', { defaultValue: 'Maximum 12 files allowed. Some files were ignored.' }));
                            return combined.slice(0, 12);
                          }
                          return combined;
                        });
                        e.target.value = '';
                      }}
                    />
                  </div>
                  <div className="text-xs text-muted-foreground mt-2">
                    {t('statements.supported_formats')}
                  </div>
                </div>
                {files.length > 0 && (
                  <div className="mt-4">
                    <div className="text-sm font-medium mb-2">Selected Files:</div>
                    <div className="space-y-1 max-h-32 overflow-y-auto">
                      {files.map((file, index) => (
                        <div key={index} className="flex items-center gap-2 text-sm bg-muted/50 p-2 rounded-md group border border-transparent hover:border-border/50 transition-all overflow-hidden">
                          <FileText className="w-4 h-4 text-primary/60 shrink-0" />
                          <span className="truncate font-medium min-w-0 flex-1">{file.name}</span>
                          <span className="text-[10px] text-muted-foreground shrink-0 opacity-70">({Math.round(file.size / 1024)} KB)</span>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-6 w-6 text-muted-foreground hover:text-destructive hover:bg-destructive/10 shrink-0"
                            onClick={() => {
                              setFiles(prev => prev.filter((_, i) => i !== index));
                            }}
                          >
                            <X className="w-3.5 h-3.5" />
                          </Button>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>

            </div>
            <div className="flex justify-end gap-2 pt-4 border-t border-border/50 shrink-0">
              <Button variant="outline" onClick={() => setUploadModalOpen(false)}>
                {t('common.cancel', 'Cancel')}
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
          </DialogContent>
        </Dialog>

        {/* Empty Recycle Bin Modal */}
        <AlertDialog open={emptyRecycleBinModalOpen} onOpenChange={setEmptyRecycleBinModalOpen}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>{t('statementRecycleBin.empty_recycle_bin_confirm_title', { defaultValue: 'Empty Recycle Bin' })}</AlertDialogTitle>
              <AlertDialogDescription>
                {t('statementRecycleBin.empty_recycle_bin_confirm_description', { defaultValue: 'Are you sure you want to permanently delete all statements in the recycle bin? This action cannot be undone and all deleted statements will be completely removed from the system.' })}
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>{t('common.cancel')}</AlertDialogCancel>
              <AlertDialogAction onClick={confirmEmptyRecycleBin} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">
                <Trash2 className="mr-2 h-4 w-4" />
                {t('statementRecycleBin.empty_recycle_bin', { defaultValue: 'Empty Recycle Bin' })}
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

        {/* Bulk Delete Modal */}
        <AlertDialog open={bulkDeleteModalOpen} onOpenChange={setBulkDeleteModalOpen}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>{t('statements.bulk_delete_confirm_title', { count: selectedIds.length, defaultValue: 'Delete Selected Statements' })}</AlertDialogTitle>
              <AlertDialogDescription>
                {t('statements.bulk_delete_confirm_description', { count: selectedIds.length, defaultValue: `Are you sure you want to delete ${selectedIds.length} statements? This action will move them to the recycle bin.` })}
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>{t('common.cancel')}</AlertDialogCancel>
              <AlertDialogAction onClick={handleBulkDelete} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">
                <Trash2 className="mr-2 h-4 w-4" />
                {t('statements.delete', 'Delete')}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>

        {/* Bulk Merge Modal */}
        <AlertDialog open={bulkMergeModalOpen} onOpenChange={setBulkMergeModalOpen}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>{t('statements.bulk_merge_confirm_title', { count: selectedIds.length, defaultValue: 'Merge Selected Statements' })}</AlertDialogTitle>
              <AlertDialogDescription>
                {t('statements.bulk_merge_confirm_description', { count: selectedIds.length, defaultValue: `Are you sure you want to merge ${selectedIds.length} statements? This will create a single, non-editable statement containing all transactions. The original statements will remain in the list.` })}
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>{t('common.cancel')}</AlertDialogCancel>
              <AlertDialogAction onClick={handleBulkMerge} className="bg-primary text-primary-foreground hover:bg-primary/90">
                <Plus className="mr-2 h-4 w-4" />
                {t('statements.merge', { defaultValue: 'Merge' })}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>

        {linkTransferModalMounted && linkingRowIdx !== null && rows[linkingRowIdx]?.backend_id && selected && (
          <LinkTransferModal
            isOpen={linkTransferModalOpen}
            onClose={closeLinkTransferModal}
            sourceTransaction={{ ...rows[linkingRowIdx], id: rows[linkingRowIdx].backend_id ?? undefined }}
            sourceStatementId={selected}
            onLinked={(link) => handleTransactionLinked(linkingRowIdx, link)}
          />
        )}
      </div>
    </>
  );
}
