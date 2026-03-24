import { useEffect, useMemo, useState, useRef, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { useQuery } from '@tanstack/react-query';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Pagination, PaginationContent, PaginationItem, PaginationLink, PaginationNext, PaginationPrevious } from '@/components/ui/pagination';
import { Checkbox } from '@/components/ui/checkbox';
import { CurrencyDisplay } from '@/components/ui/currency-display';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Calendar } from '@/components/ui/calendar';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import {
  CalendarIcon, X, Eye, AlertCircle, Loader2, Plus, Minus, Tag, Search, Trash2, Upload,
  ChevronDown, ChevronUp, MoreHorizontal, Edit, Package, RotateCcw, BarChart3, Receipt,
  Clock, Filter, FilterX, FileText, Download, Wand, ChevronLeft, ChevronRight, Check
} from 'lucide-react';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { useFeatures } from '@/contexts/FeatureContext';
import { BulkExpenseModal } from '@/components/BulkExpenseModal';
import { InventoryConsumptionForm } from '@/components/inventory/InventoryConsumptionForm';
import { ExpenseApprovalStatus } from '@/components/approvals/ExpenseApprovalStatus';
import { ReviewDiffModal } from '@/components/ReviewDiffModal';
import ExpenseSummary from '@/components/expenses/ExpenseSummary';
import ExpenseCharts from '@/components/expenses/ExpenseCharts';
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
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
// removed duplicate useEffect import
// removed duplicate icons
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { Link } from 'react-router-dom';
import { useSearchParams } from 'react-router-dom';
import { toast } from 'sonner';
import { expenseApi, Expense, ExpenseAttachmentMeta, api, linkApi, settingsApi, DeletedExpense } from '@/lib/api';
import { Badge } from '@/components/ui/badge';
import { CurrencySelector } from '@/components/ui/currency-selector';
import { Label } from '@/components/ui/label';
import { EXPENSE_CATEGORY_OPTIONS } from '@/constants/expenses';
import { canPerformActions, canEditExpense, canDeleteExpense, getCurrentUser } from '@/utils/auth';
import { formatDate } from '@/lib/utils';
import { PageHeader, ContentSection } from "@/components/ui/professional-layout";
import { ProfessionalCard } from "@/components/ui/professional-card";
import { ProfessionalButton } from "@/components/ui/professional-button";
import { useColumnVisibility, type ColumnDef } from "@/hooks/useColumnVisibility";
import { ColumnPicker } from "@/components/ui/column-picker";

const EXPENSE_COLUMNS: ColumnDef[] = [
  { key: 'select', label: 'Select', essential: true },
  { key: 'id', label: 'ID' },
  { key: 'date', label: 'Date', essential: true },
  { key: 'category', label: 'Category', essential: true },
  { key: 'vendor', label: 'Vendor' },
  { key: 'labels', label: 'Labels' },
  { key: 'amount', label: 'Amount', essential: true },
  { key: 'total', label: 'Total' },
  { key: 'invoice', label: 'Invoice' },
  { key: 'approval_status', label: 'Approval Status' },
  { key: 'created_at_by', label: 'Created at / by' },
  { key: 'analyzed', label: 'Analyzed' },
  { key: 'review', label: 'Review' },
  { key: 'receipt', label: 'Receipt' },
  { key: 'actions', label: 'Actions', essential: true },
];

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


const Expenses = () => {
  const { t, i18n } = useTranslation();
  const { isVisible, toggle, reset, hiddenCount } = useColumnVisibility('expenses', EXPENSE_COLUMNS);
  const { isFeatureEnabled } = useFeatures();
  const hasAIExpenseFeature = isFeatureEnabled('ai_expense');

  // Helper function to get locale for date formatting
  const getLocale = () => {
    const language = i18n.language;
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
  const [expenses, setExpenses] = useState<Expense[]>([]);
  const categoryOptions = EXPENSE_CATEGORY_OPTIONS;
  const [loading, setLoading] = useState(true);
  const [categoryFilter, setCategoryFilter] = useState('all');
  const [labelFilter, setLabelFilter] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  // Bulk label removed
  const [unlinkedOnly, setUnlinkedOnly] = useState(false);
  const [showAnalytics, setShowAnalytics] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [totalExpenses, setTotalExpenses] = useState(0);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [bulkLabel, setBulkLabel] = useState('');
  const [newLabelValueById, setNewLabelValueById] = useState<Record<number, string>>({});
  const [searchParams, setSearchParams] = useSearchParams();
  const [hasNextPage, setHasNextPage] = useState(false);
  const [uploadingId, setUploadingId] = useState<number | null>(null);
  const [isEditOpen, setIsEditOpen] = useState(false);
  const [editExpense, setEditExpense] = useState<Partial<Expense> & { id?: number }>({});
  const [editReceiptFile, setEditReceiptFile] = useState<File | null>(null);
  const [attachmentPreviewOpen, setAttachmentPreviewOpen] = useState<{ expenseId: number | null }>({ expenseId: null });
  const [attachments, setAttachments] = useState<Record<number, ExpenseAttachmentMeta[]>>({});

  const [approvalsNotLicensed, setApprovalsNotLicensed] = useState(false);
  const [preview, setPreview] = useState<{ open: boolean; url: string | null; contentType: string | null; filename: string | null }>({ open: false, url: null, contentType: null, filename: null });
  const [previewLoading, setPreviewLoading] = useState<{ expenseId: number; attachmentId: number } | null>(null);
  const [isBulkCreateOpen, setIsBulkCreateOpen] = useState(false);
  const [invoiceOptions, setInvoiceOptions] = useState<Array<{ id: number; number: string; client_name: string }>>([]);


  // Inventory consumption state for edit expense
  const [isEditInventoryConsumption, setIsEditInventoryConsumption] = useState(false);
  const [editConsumptionItems, setEditConsumptionItems] = useState<any[]>([]);

  // Processing lock state for expenses
  const [processingLocks, setProcessingLocks] = useState<Set<number>>(new Set());


  // Recycle bin state
  const [showRecycleBin, setShowRecycleBin] = useState(false);
  const [deletedExpenses, setDeletedExpenses] = useState<DeletedExpense[]>([]);
  const [recycleBinLoading, setRecycleBinLoading] = useState(false);
  const prevDeletedCount = useRef<number>(0);
  const [expenseToPermanentlyDelete, setExpenseToPermanentlyDelete] = useState<number | null>(null);
  const [emptyRecycleBinModalOpen, setEmptyRecycleBinModalOpen] = useState(false);

  // Recycle bin pagination
  const [recycleBinCurrentPage, setRecycleBinCurrentPage] = useState(1);
  const [recycleBinPageSize] = useState(10);
  const [recycleBinTotalCount, setRecycleBinTotalCount] = useState(0);

  // Review state
  const [reviewModalOpen, setReviewModalOpen] = useState(false);
  const [selectedReviewExpense, setSelectedReviewExpense] = useState<Expense | null>(null);
  const [isAcceptingReview, setIsAcceptingReview] = useState(false);
  const [isRejectingReview, setIsRejectingReview] = useState(false);
  const [isRetriggeringReview, setIsRetriggeringReview] = useState(false);

  const handleReviewClick = (expense: Expense) => {
    setSelectedReviewExpense(expense);
    setReviewModalOpen(true);
  };

  const handleAcceptReview = async () => {
    if (!selectedReviewExpense) return;
    setIsAcceptingReview(true);
    try {
      await expenseApi.acceptReview(selectedReviewExpense.id);
      toast.success(t('expenses.review.accepted', { defaultValue: 'Review accepted' }));
      setReviewModalOpen(false);
      fetchExpenses();
    } catch (error) {
      toast.error(t('expenses.review.accept_failed', { defaultValue: 'Failed to accept review' }));
    } finally {
      setIsAcceptingReview(false);
    }
  };

  const handleRejectReview = async () => {
    if (!selectedReviewExpense) return;
    setIsRejectingReview(true);
    try {
      await expenseApi.rejectReview(selectedReviewExpense.id);
      toast.success(t('expenses.review.dismissed', { defaultValue: 'Review dismissed' }));
      setReviewModalOpen(false);
      fetchExpenses();
    } catch (error) {
      toast.error(t('expenses.review.dismiss_failed', { defaultValue: 'Failed to dismiss review' }));
    } finally {
      setIsRejectingReview(false);
    }
  };

  const handleRetriggerReview = async () => {
    if (!selectedReviewExpense) return;
    setIsRetriggeringReview(true);
    try {
      await expenseApi.reReview(selectedReviewExpense.id);
      toast.success(t('expenses.review.retriggered', { defaultValue: 'Review re-triggered' }));
      setReviewModalOpen(false);
      fetchExpenses();
    } catch (error) {
      toast.error(t('expenses.review.retrigger_failed', { defaultValue: 'Failed to re-trigger review' }));
    } finally {
      setIsRetriggeringReview(false);
    }
  };

  const handleRunReview = async (expenseId: number) => {
    try {
      await expenseApi.reReview(expenseId);
      toast.success(t('expenses.review.triggered', { defaultValue: 'Review triggered. The agent will process it shortly.' }));
      // Refresh list
      fetchExpenses();
    } catch (error: any) {
      toast.error(error?.message || t('expenses.review.trigger_failed', { defaultValue: 'Failed to trigger review' }));
    }
  };

  const handleCancelReview = async (expenseId: number) => {
    try {
      await expenseApi.cancelReview(expenseId);
      toast.success(t('expenses.review.cancelled', { defaultValue: 'Review cancelled.' }));
      // Refresh list
      fetchExpenses();
    } catch (error: any) {
      toast.error(error?.message || t('expenses.review.cancel_failed', { defaultValue: 'Failed to cancel review' }));
    }
  };

  const handleBulkRunReview = async () => {
    if (selectedIds.length === 0) return;

    try {
      setLoading(true);
      await Promise.all(selectedIds.map(id => expenseApi.reReview(id)));
      toast.success(t('expenses.review.bulk_triggered', {
        count: selectedIds.length,
        defaultValue: 'Review triggered for {{count}} expenses.'
      }));
      setSelectedIds([]);
      fetchExpenses();
    } catch (error: any) {
      toast.error(error?.message || t('expenses.review.bulk_trigger_failed', { defaultValue: 'Failed to trigger bulk review' }));
    } finally {
      setLoading(false);
    }
  };

  // Fetch settings to get timezone
  const { data: settings } = useQuery({
    queryKey: ['settings'],
    queryFn: () => settingsApi.getSettings(),
    staleTime: 5 * 60 * 1000, // 5 minutes
    refetchOnWindowFocus: false,
  });

  // Get timezone from settings, default to UTC
  const timezone = settings?.timezone || 'UTC';

  // Fetch invoice options for linking
  useEffect(() => {
    (async () => {
      try {
        const invs = await linkApi.getInvoicesBasic();
        setInvoiceOptions(invs);
      } catch (error) {
        console.error('Failed to fetch invoices:', error);
      }
    })();
  }, []);


  // Calculate amount from consumption items for edit expense
  useEffect(() => {
    if (isEditInventoryConsumption && editConsumptionItems.length > 0) {
      const total = editConsumptionItems.reduce((sum, item) => sum + (item.quantity * (item.unit_cost || 0)), 0);
      setEditExpense(prev => ({ ...prev, amount: total }));
    }
  }, [editConsumptionItems, isEditInventoryConsumption]);

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
      } catch { }
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
    if (!recycleBinLoading && deletedExpenses.length === 0 && showRecycleBin && prevDeletedCount.current > 0) {
      setShowRecycleBin(false);
    }
    prevDeletedCount.current = deletedExpenses.length;
  }, [deletedExpenses.length, recycleBinLoading, showRecycleBin]);

  useEffect(() => {
    if (showRecycleBin) {
      fetchDeletedExpenses();
    }
  }, [showRecycleBin, recycleBinCurrentPage]);


  const fetchExpenses = useCallback(async () => {
    setLoading(true);
    try {
      const skip = (page - 1) * pageSize;
      const result = await expenseApi.getExpensesPaginated({
        category: categoryFilter,
        label: labelFilter || undefined,
        unlinkedOnly,
        skip,
        limit: pageSize,
        search: searchQuery || undefined,
        // Don't exclude pending_approval - users should see their own submitted expenses
      });

      // Reset to page 1 if current page has no results but we're not on page 1
      if (result.expenses.length === 0 && page > 1) {
        setPage(1);
        return;
      }

      setExpenses(result.expenses);
      setTotalExpenses(result.total);

      // Determine if there's a next page based on total count
      const hasMore = skip + pageSize < result.total;
      setHasNextPage(hasMore);
    } catch (e) {
      toast.error(t('expenses.load_failed', { defaultValue: 'Failed to load expenses' }));
    } finally {
      setLoading(false);
    }
  }, [categoryFilter, labelFilter, unlinkedOnly, page, pageSize, searchQuery]);

  useEffect(() => {
    fetchExpenses();
  }, [fetchExpenses]);

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
      // Limit page to reasonable bounds - will be validated again after API call
      if (pg && !Number.isNaN(Number(pg))) setPage(Math.max(1, Math.min(1000, Number(pg))));
      if (ps && !Number.isNaN(Number(ps))) setPageSize(Math.min(200, Math.max(5, Number(ps))));
    } catch { }
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

  // Search is now done server-side, so just use expenses directly
  const filteredExpenses = useMemo(() => {
    return expenses || [];
  }, [expenses]);



  const handleDelete = async (id: number) => {
    try {
      await expenseApi.deleteExpense(id);
      setExpenses(prev => prev.filter(e => e.id !== id));
      // Refresh recycle bin if it's currently open
      if (showRecycleBin) {
        fetchDeletedExpenses();
      }
      toast.success(t('expenses.delete_success', { defaultValue: 'Expense deleted' }));
    } catch (e: any) {
      toast.error(e?.message || t('expenses.delete_failed', { defaultValue: 'Failed to delete expense' }));
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
      const startPolling = (window as any).startExpensePolling;
      if (typeof startPolling === 'function') {
        startPolling(id);
      } else {
        console.warn('startExpensePolling is not available globally');
      }
      toast.success(t('expenses.receipt.uploaded', { defaultValue: 'Receipt uploaded' }));
    } catch (e: any) {
      addNotification?.('error', t('expenses.receipt.failed_title', { defaultValue: 'Expense Receipt Failed' }), t('expenses.receipt.failed_message', { defaultValue: 'Failed to upload receipt: {{error}}', error: e?.message || t('common.unknown_error', { defaultValue: 'Unknown error' }) }));
      toast.error(e?.message || t('expenses.receipt.upload_failed', { defaultValue: 'Failed to upload receipt' }));
    } finally {
      setUploadingId(null);
    }
  };

  const handleRequeue = async (expenseId: number) => {
    // Check if already processing
    if (processingLocks.has(expenseId)) {
      toast.warning('This expense is already being processed. Please wait for the current processing to complete.');
      return;
    }

    const addNotification = (window as any).addAINotification;
    addNotification?.('processing', 'Reprocessing Expense', `Re-analyzing expense receipts with AI...`);

    try {
      // Add to processing locks to prevent multiple clicks
      setProcessingLocks(prev => new Set([...prev, expenseId]));

      await expenseApi.reprocessExpense(expenseId);

      addNotification?.('success', 'Expense Reprocessing Started', `Successfully started reprocessing expense receipts.`);
      toast.success(t('expenses.reprocess.started', { defaultValue: 'Expense reprocessing started' }));

      // Refresh the expense list
      const data = await expenseApi.getExpenses(categoryFilter);
      setExpenses(data);

      // Remove from processing locks after a delay
      setTimeout(() => {
        setProcessingLocks(prev => {
          const newLocks = new Set(prev);
          newLocks.delete(expenseId);
          return newLocks;
        });
      }, 30000); // Remove lock after 30 seconds

    } catch (e: any) {
      // Remove from processing locks on error
      setProcessingLocks(prev => {
        const newLocks = new Set(prev);
        newLocks.delete(expenseId);
        return newLocks;
      });

      // Handle specific lock error messages
      const errorMessage = e?.message || t('expenses.reprocess.failed', { defaultValue: 'Failed to reprocess expense' });
      if (errorMessage.includes('already being processed') || errorMessage.includes('processing lock')) {
        toast.error(t('expenses.processing_locked', { defaultValue: 'This expense is currently being processed by another operation. Please try again in a few minutes.' }));
        addNotification?.('warning', 'Processing Lock Active', 'This expense is already being processed. Please wait and try again.');
      } else {
        addNotification?.('error', 'Expense Reprocessing Failed', errorMessage);
        toast.error(errorMessage);
      }
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

    // Initialize consumption state from existing expense data
    const isConsumption = !!(e as any).is_inventory_consumption;
    const consumptionItems = (e as any).consumption_items || [];
    setIsEditInventoryConsumption(isConsumption);
    setEditConsumptionItems(consumptionItems);

    setIsEditOpen(true);
  };

  const handleUpdate = async () => {
    try {
      if (!editExpense.id) return;
      if (!editExpense.amount || !editExpense.category) {
        toast.error(t('expenses.validation.amount_category_required', { defaultValue: 'Amount and category are required' }));
        return;
      }
      if (isEditInventoryConsumption && (!editConsumptionItems || editConsumptionItems.length === 0)) {
        toast.error(t('expenses.validation.inventory_item_required', { defaultValue: 'Inventory consumption must include at least one item' }));
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
        is_inventory_consumption: isEditInventoryConsumption,
        consumption_items: isEditInventoryConsumption ? editConsumptionItems : null,
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
          const startPolling = (window as any).startExpensePolling;
          if (typeof startPolling === 'function') {
            startPolling(updated.id);
          } else {
            console.warn('startExpensePolling is not available globally');
          }
        } catch (e) {
          console.error('Receipt upload failed on update:', e);
          addNotification?.('error', 'Expense Receipt Failed', `Failed to upload receipt: ${e instanceof Error ? e.message : 'Unknown error'}`);
          toast.error(t('expenses.receipt.upload_failed', { defaultValue: 'Receipt upload failed' }));
        } finally {
          setUploadingId(null);
          setEditReceiptFile(null);
        }
      }
      setExpenses(prev => prev.map(x => (x.id === finalUpdated.id ? finalUpdated : x)));
      setIsEditOpen(false);
      toast.success(t('expenses.update_success', { defaultValue: 'Expense updated' }));
    } catch (e: any) {
      toast.error(e?.message || t('expenses.update_failed', { defaultValue: 'Failed to update expense' }));
    }
  };

  // Recycle bin functions
  const fetchDeletedExpenses = async () => {
    try {
      setRecycleBinLoading(true);
      const skip = (recycleBinCurrentPage - 1) * recycleBinPageSize;
      const response = await expenseApi.getDeletedExpenses(skip, recycleBinPageSize);
      setDeletedExpenses(response.items);
      setRecycleBinTotalCount(response.total);
    } catch (error) {
      console.error('Failed to fetch deleted expenses:', error);
      toast.error(t('recycleBin.load_failed', { defaultValue: 'Failed to load recycle bin' }));
    } finally {
      setRecycleBinLoading(false);
    }
  };

  const handleRestoreExpense = async (expenseId: number) => {
    try {
      await expenseApi.restoreExpense(expenseId, 'recorded');
      toast.success(t('expenses.restore_success', { defaultValue: 'Expense restored successfully' }));
      fetchDeletedExpenses();
      fetchExpenses(); // Refresh main list
    } catch (error: any) {
      console.error('Failed to restore expense:', error);
      toast.error(error?.message || t('expenses.restore_failed', { defaultValue: 'Failed to restore expense' }));
    }
  };

  const handlePermanentlyDeleteExpense = async (expenseId: number) => {
    try {
      await expenseApi.permanentlyDeleteExpense(expenseId);
      toast.success(t('expenses.permanent_delete_success', { defaultValue: 'Expense permanently deleted' }));
      fetchDeletedExpenses();
      setExpenseToPermanentlyDelete(null);
    } catch (error: any) {
      console.error('Failed to permanently delete expense:', error);
      toast.error(error?.message || t('expenses.permanent_delete_failed', { defaultValue: 'Failed to permanently delete expense' }));
    }
  };

  const handleEmptyRecycleBin = () => {
    setEmptyRecycleBinModalOpen(true);
  };

  const confirmEmptyRecycleBin = async () => {
    const addNotification = (window as any).addAINotification;
    try {
      const response = await expenseApi.emptyRecycleBin() as { message: string; deleted_count: number; status?: string };

      // Show immediate notification
      toast.success(response.message || t('expenseRecycleBin.deletion_initiated', { count: response.deleted_count }));

      // Add bell notification for completion
      if (addNotification && response.status === 'processing') {
        addNotification(
          'info', 
          t('expenseRecycleBin.deletion_title'), 
          t('expenseRecycleBin.deletion_processing', { count: response.deleted_count })
        );

        // Show completion notification and refresh after background task completes
        setTimeout(() => {
          addNotification(
            'success', 
            t('expenseRecycleBin.deletion_completed_title'), 
            t('expenseRecycleBin.deletion_completed', { count: response.deleted_count })
          );
          // Refresh the list after deletion completes
          fetchDeletedExpenses();
        }, 2000);
      } else {
        // If not async, refresh immediately
        fetchDeletedExpenses();
      }
    } catch (error: any) {
      console.error('Failed to empty recycle bin:', error);
      toast.error(error?.message || t('expenseRecycleBin.failed_to_empty_recycle_bin'));
    } finally {
      setEmptyRecycleBinModalOpen(false);
    }
  };

  const handleToggleRecycleBin = () => {
    const willShow = !showRecycleBin;
    setShowRecycleBin(willShow);
    if (willShow) {
      setRecycleBinCurrentPage(1); // Reset to first page when opening
      fetchDeletedExpenses();
    }
  };

  return (
    <>
      <div className="h-full space-y-8 fade-in">
        {/* Hero Header */}
        <div className="bg-gradient-to-r from-primary/10 via-primary/5 to-transparent rounded-2xl border border-primary/20 p-8 backdrop-blur-sm">
          <div className="flex items-center justify-between gap-6">
            <div className="space-y-2">
              <h1 className="text-4xl font-bold tracking-tight">{t('expenses.title')}</h1>
              <p className="text-lg text-muted-foreground">{t('expenses.description')}</p>
            </div>
            {canPerformActions() && (
              <div className="flex gap-2 items-center flex-wrap justify-end">
                <ProfessionalButton
                  variant="outline"
                  size="default"
                  onClick={fetchExpenses}
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
                  {t('expenseRecycleBin.title', { defaultValue: 'Recycle Bin' })}
                  {showRecycleBin ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                </ProfessionalButton>
                <ProfessionalButton
                  variant="outline"
                  size="default"
                  onClick={() => setShowAnalytics(!showAnalytics)}
                  className="whitespace-nowrap"
                >
                  <BarChart3 className="h-4 w-4" />
                  {t('expenses.analytics')}
                  {showAnalytics ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                </ProfessionalButton>
                <ColumnPicker columns={EXPENSE_COLUMNS} isVisible={isVisible} onToggle={toggle} onReset={reset} hiddenCount={hiddenCount} />
                <div className="flex gap-1">
                  <Link to="/expenses/new">
                    <ProfessionalButton variant="default" size="default" className="shadow-lg">
                      <Plus className="w-4 h-4 mr-2" /> {t('expenses.new')}
                    </ProfessionalButton>
                  </Link>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <ProfessionalButton variant="default" size="icon" className="shadow-lg">
                        <ChevronDown className="h-4 w-4" />
                      </ProfessionalButton>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" className="w-56">
                      <DropdownMenuItem onClick={() => setIsBulkCreateOpen(true)} className="flex items-center cursor-pointer">
                        <Plus className="mr-2 h-4 w-4" />
                        <div className="flex flex-col">
                          <span>{t('expenses.create_multiple', 'Create Multiple Expenses')}</span>
                          <span className="text-xs text-muted-foreground">{t('expenses.batch_create_description')}</span>
                        </div>
                      </DropdownMenuItem>
                      <DropdownMenuItem asChild>
                        <Link to="/expenses/import" className="flex items-center w-full cursor-pointer">
                          <Upload className="mr-2 h-4 w-4" />
                          <div className="flex flex-col">
                            <span>{t('expenses.import_from_pdf_images')}</span>
                            <span className="text-xs text-muted-foreground">{t('expenses.upload_and_extract_description')}</span>
                          </div>
                        </Link>
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Recycle Bin Section */}
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
                      <h3 className="font-bold text-xl text-foreground">{t('expenseRecycleBin.title', { defaultValue: 'Recycle Bin' })}</h3>
                      <p className="text-sm text-muted-foreground">
                        {recycleBinTotalCount} {t('expenseRecycleBin.items', 'items')} • Recover or permanently delete expenses
                      </p>
                    </div>
                  </div>
                  {deletedExpenses.length > 0 && (
                    <ProfessionalButton
                      variant="destructive"
                      size="default"
                      onClick={handleEmptyRecycleBin}
                    >
                      <Trash2 className="h-4 w-4" />
                      {t('expenseRecycleBin.empty_recycle_bin', { defaultValue: 'Empty Recycle Bin' })}
                    </ProfessionalButton>
                  )}
                </div>
                <div className="rounded-xl border border-border/50 overflow-hidden shadow-sm">
                  <Table>
                    <TableHeader>
                      <TableRow className="bg-gradient-to-r from-muted/50 to-muted/30 hover:bg-gradient-to-r hover:from-muted/50 hover:to-muted/30">
                        <TableHead className="font-bold text-foreground">{t('expenseRecycleBin.expense')}</TableHead>
                        <TableHead className="font-bold text-foreground">{t('expenseRecycleBin.amount')}</TableHead>
                        <TableHead className="font-bold text-foreground">{t('expenseRecycleBin.category')}</TableHead>
                        <TableHead className="font-bold text-foreground">{t('expenseRecycleBin.deleted_at')}</TableHead>
                        <TableHead className="font-bold text-foreground">{t('expenseRecycleBin.deleted_by')}</TableHead>
                        <TableHead className="w-[100px] font-bold text-foreground text-right">{t('expenseRecycleBin.actions')}</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {recycleBinLoading ? (
                        <TableRow>
                          <TableCell colSpan={6} className="h-24 text-center">
                            <div className="flex justify-center items-center gap-2">
                              <Loader2 className="h-5 w-5 animate-spin text-primary" />
                              <span className="text-muted-foreground">{t('expenseRecycleBin.loading', { defaultValue: 'Loading...' })}</span>
                            </div>
                          </TableCell>
                        </TableRow>
                      ) : deletedExpenses.length > 0 ? (
                        deletedExpenses.map((expense) => (
                          <TableRow key={expense.id} className="hover:bg-muted/60 transition-all duration-200 border-b border-border/30">
                            <TableCell className="font-semibold text-foreground">
                              <span className="inline-flex items-center gap-2">
                                <Receipt className="h-4 w-4 text-primary/60" />
                                #{expense.id}
                              </span>
                            </TableCell>
                            <TableCell className="font-semibold text-foreground">
                              <CurrencyDisplay amount={expense.amount} currency={expense.currency} />
                            </TableCell>
                            <TableCell className="text-foreground">{expense.category}</TableCell>
                            <TableCell className="text-muted-foreground text-sm">{formatDate(expense.deleted_at)}</TableCell>
                            <TableCell className="text-muted-foreground text-sm">{expense.deleted_by_username || t('expenseRecycleBin.unknown')}</TableCell>
                            <TableCell>
                              <div className="flex gap-2 justify-end">
                                <ProfessionalButton
                                  variant="ghost"
                                  size="icon-sm"
                                  onClick={() => handleRestoreExpense(expense.id)}
                                  title="Restore expense"
                                  className="hover:bg-success/10 hover:text-success"
                                >
                                  <RotateCcw className="h-4 w-4" />
                                </ProfessionalButton>
                                <ProfessionalButton
                                  variant="ghost"
                                  size="icon-sm"
                                  onClick={() => setExpenseToPermanentlyDelete(expense.id)}
                                  title="Permanently delete"
                                  className="hover:bg-destructive/10 hover:text-destructive"
                                >
                                  <Trash2 className="h-4 w-4" />
                                </ProfessionalButton>
                              </div>
                            </TableCell>
                          </TableRow>
                        ))
                      ) : (
                        <TableRow>
                          <TableCell colSpan={6} className="h-32 text-center">
                            <div className="flex flex-col items-center justify-center gap-3">
                              <div className="p-4 rounded-full bg-muted/50">
                                <Trash2 className="h-8 w-8 text-muted-foreground/50" />
                              </div>
                              <p className="text-muted-foreground font-medium">{t('expenseRecycleBin.recycle_bin_empty', { defaultValue: 'Recycle bin is empty' })}</p>
                            </div>
                          </TableCell>
                        </TableRow>
                      )}
                    </TableBody>
                  </Table>
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
              </div>
            </ProfessionalCard>
          </CollapsibleContent>
        </Collapsible>

        {/* Expense Summary and Analytics */}
        {showAnalytics && (
          <>
            <ExpenseSummary />
            <ExpenseCharts />
          </>
        )}

        <ProfessionalCard id="expense-list" className="slide-in" variant="default">
          <div className="space-y-6">
            {/* Header with filters */}
            <div className="flex flex-col lg:flex-row justify-between gap-6 pb-6 border-b border-border/50">
              <div>
                <h2 className="text-2xl font-bold text-foreground">{t('expenses.list_title')}</h2>
              </div>
              <div className="flex flex-col sm:flex-row gap-3 items-start sm:items-center">
                {/* Search */}
                <div className="relative w-full sm:w-auto">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <Input
                    placeholder={t('expenses.search_placeholder')}
                    className="pl-9 w-full sm:w-[240px] h-10 rounded-lg border-border/50 bg-muted/30 focus:bg-background transition-colors"
                    value={searchQuery}
                    onChange={(e) => { setSearchQuery(e.target.value); setPage(1); }}
                  />
                </div>

                {/* Category Filter */}
                <div className="flex items-center gap-2">
                  <Filter className="h-4 w-4 text-muted-foreground" />
                  <Select value={categoryFilter} onValueChange={setCategoryFilter}>
                    <SelectTrigger className="w-full sm:w-[170px] h-10 rounded-lg border-border/50 bg-muted/30">
                      <SelectValue placeholder={t('expenses.filter_by_category')} />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">{t('expenses.all_categories')}</SelectItem>
                      {categoryOptions.map((c) => (
                        <SelectItem key={c} value={c}>{t(`expenses.categories.${c}`)}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                {/* Label Filter */}
                <div className="relative">
                  <Tag className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <Input
                    placeholder={t('expenses.filter_by_label', { defaultValue: 'Filter by label' })}
                    className="pl-9 w-full sm:w-[150px] h-10 rounded-lg border-border/50 bg-muted/30 focus:bg-background transition-colors"
                    value={labelFilter}
                    onChange={(e) => { setLabelFilter(e.target.value); setPage(1); }}
                  />
                  {labelFilter && (
                    <button
                      aria-label="Clear label filter"
                      className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                      onClick={() => { setLabelFilter(''); setPage(1); }}
                    >
                      <X className="w-4 h-4" />
                    </button>
                  )}
                </div>

                {/* Unlinked Only Checkbox */}
                <label className="inline-flex items-center gap-2 text-sm text-muted-foreground">
                  <input type="checkbox" checked={unlinkedOnly} onChange={(e) => { setUnlinkedOnly(e.target.checked); setPage(1); }} />
                  {t('expenses.unlinked_only', { defaultValue: 'Unlinked only' })}
                </label>

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
              </div>
            </div>

          </div>

          <CardContent className="px-0">
            {/* Results Count and Selection Toolbar */}
            <div className="space-y-4 mb-6">
              {selectedIds.length > 0 && (
                <div className="flex flex-col md:flex-row items-center justify-between p-4 bg-gradient-to-r from-primary/10 to-primary/5 border border-primary/20 rounded-xl shadow-sm gap-4 slide-in">
                  <div className="flex items-center gap-3">
                    <div className="h-2 w-2 rounded-full bg-primary animate-pulse shadow-[0_0_8px_rgba(var(--primary),0.5)]"></div>
                    <span className="text-sm font-bold text-foreground">
                      {selectedIds.length} {t('expenses.selected', { defaultValue: 'selected' })}
                    </span>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setSelectedIds([])}
                      className="h-8 text-xs hover:bg-primary/10 transition-colors"
                    >
                      {t('common.clear', { defaultValue: 'Clear' })}
                    </Button>
                  </div>

                  <div className="flex flex-wrap items-center gap-3 w-full md:w-auto justify-end">
                    <div className="relative group flex-1 md:flex-initial min-w-[200px]">
                      <Tag className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
                      <Input
                        placeholder={t('expenses.bulk_label_placeholder', { defaultValue: 'Add or remove label' })}
                        value={bulkLabel}
                        onChange={(e) => setBulkLabel(e.target.value)}
                        className="pl-8 h-9 text-sm border-primary/20 focus:border-primary/40 bg-background/50"
                      />
                    </div>

                    <div className="flex items-center gap-1.5">
                      <ProfessionalButton
                        variant="outline"
                        size="sm"
                        disabled={!canPerformActions() || !bulkLabel.trim()}
                        onClick={async () => {
                          try {
                            const skip = (page - 1) * pageSize;
                            await expenseApi.bulkLabels(selectedIds, 'add', bulkLabel.trim());
                            const result = await expenseApi.getExpensesPaginated({ category: categoryFilter, label: labelFilter || undefined, unlinkedOnly, skip, limit: pageSize, excludeStatus: 'pending_approval' });
                            setExpenses(result.expenses);
                            setTotalExpenses(result.total);
                            setSelectedIds([]);
                            setBulkLabel('');
                            toast.success(t('expenses.labels.added', { defaultValue: 'Labels added' }));
                          } catch (e: any) {
                            toast.error(e?.message || t('expenses.labels.add_failed', { defaultValue: 'Failed to add label' }));
                          }
                        }}
                        className="h-9 px-3 gap-1.5"
                      >
                        <Plus className="h-3.5 w-3.5" />
                        {t('expenses.add')}
                      </ProfessionalButton>

                      <ProfessionalButton
                        variant="outline"
                        size="sm"
                        disabled={!canPerformActions() || !bulkLabel.trim()}
                        onClick={async () => {
                          try {
                            const skip = (page - 1) * pageSize;
                            await expenseApi.bulkLabels(selectedIds, 'remove', bulkLabel.trim());
                            const result = await expenseApi.getExpensesPaginated({ category: categoryFilter, label: labelFilter || undefined, unlinkedOnly, skip, limit: pageSize, excludeStatus: 'pending_approval' });
                            setExpenses(result.expenses);
                            setTotalExpenses(result.total);
                            setSelectedIds([]);
                            setBulkLabel('');
                            toast.success(t('expenses.labels.removed', { defaultValue: 'Labels removed' }));
                          } catch (e: any) {
                            toast.error(e?.message || t('expenses.labels.remove_failed', { defaultValue: 'Failed to remove label' }));
                          }
                        }}
                        className="h-9 px-3 gap-1.5"
                      >
                        <Minus className="h-3.5 w-3.5" />
                        {t('expenses.remove')}
                      </ProfessionalButton>
                    </div>

                    <div className="flex items-center gap-1.5 ml-2">
                       <ProfessionalButton
                        variant="outline"
                        size="sm"
                        onClick={handleBulkRunReview}
                        disabled={!canPerformActions() || loading}
                        className="h-9 px-3 gap-1.5 shadow-sm border-primary/20 bg-primary/5 hover:bg-primary/10 text-primary whitespace-nowrap"
                      >
                        <Wand className="w-3.5 h-3.5" />
                        Run Review
                      </ProfessionalButton>
                    </div>

                    <div className="w-px h-6 bg-primary/10 hidden md:block mx-1"></div>

                    <AlertDialog>
                      <AlertDialogTrigger asChild>
                        <ProfessionalButton
                          variant="destructive"
                          size="sm"
                          disabled={!canPerformActions()}
                          className="h-9 px-3 gap-1.5 shadow-sm"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                          {t('expenses.delete_selected', { defaultValue: 'Delete' })}
                        </ProfessionalButton>
                      </AlertDialogTrigger>
                      <AlertDialogContent>
                        <AlertDialogHeader>
                          <AlertDialogTitle>
                            {selectedIds.length === 1
                              ? t('expenses.delete_single_title', 'Delete 1 Expense')
                              : t('expenses.delete_multiple_title', 'Delete {{count}} Expenses', { count: selectedIds.length })}
                          </AlertDialogTitle>
                          <AlertDialogDescription>
                            {selectedIds.length === 1
                              ? t('expenses.delete_single_description', 'Are you sure you want to delete 1 expense? This will move it to the recycle bin.')
                              : t('expenses.delete_multiple_description', 'Are you sure you want to delete {{count}} expenses? They will be moved to the recycle bin.', { count: selectedIds.length })}
                          </AlertDialogDescription>
                        </AlertDialogHeader>
                        <AlertDialogFooter>
                          <AlertDialogCancel>{t('common.cancel')}</AlertDialogCancel>
                          <AlertDialogAction
                            className="bg-destructive text-white hover:bg-destructive/90"
                            onClick={async () => {
                              try {
                                await expenseApi.bulkDelete(selectedIds);
                                const result = await expenseApi.getExpensesPaginated({ category: categoryFilter, label: labelFilter || undefined, unlinkedOnly, skip: (page - 1) * pageSize, limit: pageSize, excludeStatus: 'pending_approval' });
                                setExpenses(result.expenses);
                                setTotalExpenses(result.total);
                                // Refresh recycle bin if it's currently open
                                if (showRecycleBin) {
                                  console.log('🔄 Expenses bulk delete: Refreshing recycle bin, showRecycleBin:', showRecycleBin);
                                  // Reset to first page since total count may have changed
                                  setRecycleBinCurrentPage(1);
                                  await fetchDeletedExpenses();
                                  console.log('✅ Expenses bulk delete: Recycle bin refreshed');
                                } else {
                                  console.log('ℹ️ Expenses bulk delete: Recycle bin not open, skipping refresh');
                                }
                                setSelectedIds([]);
                                toast.success(`Successfully deleted ${selectedIds.length} expense${selectedIds.length > 1 ? 's' : ''}`);
                              } catch (e: any) {
                                toast.error(e?.message || t('expenses.bulk_delete_failed', { defaultValue: 'Failed to delete expenses' }));
                              }
                            }}
                          >
                            {t('common.delete', { defaultValue: 'Delete' })}
                          </AlertDialogAction>
                        </AlertDialogFooter>
                      </AlertDialogContent>
                    </AlertDialog>
                  </div>
                </div>
              )}
            </div>
            <div className="rounded-xl border border-border/50 overflow-hidden shadow-sm">
              <Table>
                <TableHeader>
                  <TableRow className="bg-gradient-to-r from-muted/50 to-muted/30 hover:bg-gradient-to-r hover:from-muted/50 hover:to-muted/30 border-b border-border/50">
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
                    {isVisible('id') && <TableHead className="font-bold text-foreground">{t('expenses.table.id', { defaultValue: 'ID' })}</TableHead>}
                    <TableHead className="font-bold text-foreground">{t('expenses.table.date')}</TableHead>
                    <TableHead className="font-bold text-foreground">{t('expenses.table.category')}</TableHead>
                    {isVisible('vendor') && <TableHead className="font-bold text-foreground">{t('expenses.table.vendor')}</TableHead>}
                    {isVisible('labels') && <TableHead className="font-bold text-foreground">{t('expenses.table.labels', { defaultValue: 'Labels' })}</TableHead>}
                    <TableHead className="font-bold text-foreground">{t('expenses.table.amount')}</TableHead>
                    {isVisible('total') && <TableHead className="font-bold text-foreground">{t('expenses.table.total')}</TableHead>}
                    {isVisible('invoice') && <TableHead className="font-bold text-foreground">{t('expenses.table.invoice')}</TableHead>}
                    {isVisible('approval_status') && <TableHead className="font-bold text-foreground">{t('expenses.table.approval_status', { defaultValue: 'Approval Status' })}</TableHead>}
                    {isVisible('created_at_by') && <TableHead className="font-bold text-foreground">{t('expenses.table.created_at_by', { defaultValue: 'Created at / by' })}</TableHead>}
                    {isVisible('analyzed') && <TableHead className="font-bold text-foreground">{t('expenses.table.analyzed')}</TableHead>}
                    {isVisible('review') && <TableHead className="font-bold text-foreground">{t('expenses.review.title', { defaultValue: 'Review' })}</TableHead>}
                    {isVisible('receipt') && <TableHead className="font-bold text-foreground">{t('expenses.table.receipt')}</TableHead>}
                    <TableHead className="w-[100px] text-right font-bold text-foreground">{t('expenses.table.actions')}</TableHead>
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
                        {isVisible('id') && <TableCell className="text-muted-foreground whitespace-nowrap">#{e.id}</TableCell>}
                        <TableCell>
                          <div className="flex flex-col">
                            <div className="font-medium text-sm">
                              {e.expense_date ? new Date(e.expense_date).toLocaleDateString(getLocale(), { timeZone: timezone }) : 'N/A'}
                            </div>
                            {e.receipt_timestamp && e.receipt_time_extracted && (
                              <span className="text-xs text-muted-foreground">
                                🕐 {new Date(e.receipt_timestamp).toLocaleTimeString(getLocale(), { timeZone: timezone, hour: '2-digit', minute: '2-digit' })}
                              </span>
                            )}
                          </div>
                        </TableCell>
                        <TableCell>{e.category}</TableCell>
                        {isVisible('vendor') && <TableCell>{e.vendor || '—'}</TableCell>}
                        {isVisible('labels') && <TableCell>
                          <div className="flex flex-wrap items-center gap-2">
                            {(e.labels || []).slice(0, 10).map((lab, idx) => (
                              <Badge
                                key={`${e.id}-lab-${idx}`}
                                variant="secondary"
                                className="text-[10px] px-1.5 py-0 h-5 bg-primary/10 text-primary border-primary/20 flex items-center gap-1 group/badge"
                              >
                                {lab}
                                {canPerformActions() && (
                                  <button
                                    className="hover:text-destructive transition-colors"
                                    aria-label={t('expenses.remove')}
                                    onClick={async () => {
                                      try {
                                        const next = (e.labels || []).filter((l) => l !== lab);
                                        await expenseApi.updateExpense(e.id, { labels: next });
                                        setExpenses((prev) => prev.map((x) => (x.id === e.id ? { ...x, labels: next } as Expense : x)));
                                      } catch (err: any) {
                                        toast.error(err?.message || t('expenses.labels.remove_failed', { defaultValue: 'Failed to remove label' }));
                                      }
                                    }}
                                  >
                                    <X className="h-2.5 w-2.5" />
                                  </button>
                                )}
                              </Badge>
                            ))}
                            {canPerformActions() && (
                              <Input
                                placeholder={t('expenses.labels.label_placeholder', { defaultValue: 'Add label...' })}
                                value={newLabelValueById[e.id] || ''}
                                className="w-[100px] h-7 text-[10px] px-2 bg-muted/20 border-border/40 focus:bg-background transition-all"
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
                                      toast.error(err?.message || t('expenses.labels.add_failed', { defaultValue: 'Failed to add label' }));
                                    }
                                  }
                                }}
                              />
                            )}
                          </div>
                        </TableCell>}
                        <TableCell><CurrencyDisplay amount={e.amount || 0} currency={e.currency || 'USD'} /></TableCell>
                        {isVisible('total') && <TableCell><CurrencyDisplay amount={e.total_amount || e.amount || 0} currency={e.currency || 'USD'} /></TableCell>}
                        {isVisible('invoice') && <TableCell>
                          {typeof e.invoice_id === 'number' ? (
                            <Link to={`/invoices/edit/${e.invoice_id}`} className="text-blue-600 hover:underline">#{e.invoice_id}</Link>
                          ) : (
                            <span className="text-muted-foreground">{t('expenses.none')}</span>
                          )}
                        </TableCell>}
                        {isVisible('approval_status') && <TableCell>
                          <ExpenseApprovalStatus
                            expense={{
                              id: e.id,
                              status: e.status,
                              amount: e.amount || 0,
                              currency: e.currency || 'USD'
                            }}
                            approvals={[]} // TODO: Fetch approvals data
                          />
                        </TableCell>}
                        {isVisible('created_at_by') && <TableCell>
                          <div className="text-sm">
                            <div className="text-muted-foreground">
                              {e.created_at ? new Date(e.created_at).toLocaleString(getLocale(), { 
                                timeZone: timezone,
                                year: 'numeric',
                                month: 'short',
                                day: 'numeric',
                                hour: '2-digit',
                                minute: '2-digit'
                              }) : 'N/A'}
                            </div>
                            <div className="text-xs text-muted-foreground">
                              {e.created_by_username || e.created_by_email || t('common.unknown')}
                            </div>
                          </div>
                        </TableCell>}
                        {isVisible('analyzed') && <TableCell>
                          <div className="flex flex-col gap-2">
                            <div>
                              {e.analysis_status === 'done' ? (
                                <div className="text-xs px-2 py-1 bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200 rounded">{t('expenses.status_done')}</div>
                              ) : e.analysis_status === 'processing' || e.analysis_status === 'queued' ? (
                                <div className="text-xs px-2 py-1 bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200 rounded capitalize">{e.analysis_status === 'processing' ? t('expenses.status_processing') : t('expenses.status_queued')}</div>
                              ) : e.analysis_status === 'failed' ? (
                                <div className="text-xs px-2 py-1 bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200 rounded">{t('common.failed', { defaultValue: 'Failed' })}</div>
                              ) : e.analysis_status === 'cancelled' ? (
                                <div className="text-xs px-2 py-1 bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200 rounded">{t('common.cancelled', { defaultValue: 'Cancelled' })}</div>
                              ) : e.imported_from_attachment ? (
                                <div className="text-xs px-2 py-1 bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200 rounded">{t('common.not_started', { defaultValue: 'Not Started' })}</div>
                              ) : (
                                <span className="text-muted-foreground text-xs">—</span>
                              )}
                            </div>
                            {(e.analysis_status || (e.attachments_count && e.attachments_count > 0) || e.imported_from_attachment) && canPerformActions() && e.status !== 'pending_approval' && e.status !== 'approved' && (
                              <Button
                                variant="ghost"
                                size="sm"
                                className="w-fit"
                                onClick={() => handleRequeue(e.id)}
                                disabled={
                                  !e.imported_from_attachment &&
                                  (!e.attachments_count || e.attachments_count === 0) ||
                                  processingLocks.has(e.id) ||
                                  uploadingId === e.id
                                }
                                title="Process Again"
                              >
                                {processingLocks.has(e.id) ? (
                                  <div className="flex items-center gap-1">
                                    <div className="w-3 h-3 border-2 border-current border-t-transparent rounded-full animate-spin" />
                                    <span className="animate-pulse">...</span>
                                  </div>
                                ) : uploadingId === e.id ? (
                                  'Uploading...'
                                ) : (
                                  <RotateCcw className="w-4 h-4" />
                                )}
                              </Button>
                            )}
                          </div>
                        </TableCell>}
                        {isVisible('review') && <TableCell>
                          {/* Review Status Column */}
                          {e.review_status === 'diff_found' ? (
                            <Button size="sm" variant="outline" className="border-amber-500 text-amber-600 hover:bg-amber-50" onClick={() => handleReviewClick(e)}>
                              <AlertCircle className="w-3 h-3 mr-1" />
                              Review Diff
                            </Button>
                          ) : (e.review_status === 'reviewed' || e.review_status === 'no_diff') ? (
                            <div className="flex flex-col gap-1 items-start">
                              <Badge variant="outline" className={cn(
                                "font-medium shadow-none",
                                e.review_status === 'reviewed' ? "text-green-600 border-green-200 bg-green-50" : "text-blue-600 border-blue-200 bg-blue-50"
                              )}>
                                {e.review_status === 'reviewed' ? 'Reviewed' : 'Verified'}
                              </Badge>
                              <Button
                                size="sm"
                                variant="ghost"
                                className="h-6 text-[10px] px-2 text-muted-foreground hover:text-foreground"
                                onClick={() => handleReviewClick(e)}
                              >
                                <Eye className="w-3 h-3 mr-1" />
                                View Report
                              </Button>
                            </div>
                          ) : (
                            <div className="flex flex-col gap-1 items-start">
                              <Badge variant="outline" className={cn(
                                "font-medium shadow-none",
                                e.review_status === 'pending'
                                  ? "bg-blue-50 text-blue-700 border-blue-200"
                                  : e.review_status === 'rejected'
                                  ? "bg-amber-50 text-amber-700 border-amber-200"
                                  : e.review_status === 'failed'
                                  ? "bg-red-50 text-red-700 border-red-200"
                                  : "bg-muted/50 text-muted-foreground border-transparent"
                              )}>
                                {e.review_status === 'pending' ? 'Review Pending' : 
                                 e.review_status === 'rejected' ? 'Review Dismissed' : 
                                 e.review_status === 'failed' ? 'Review Failed' : 
                                 t('common.not_started', { defaultValue: 'Not Started' })}
                              </Badge>
                              {(!e.review_status || e.review_status === 'not_started' || e.review_status === 'failed' || e.review_status === 'rejected') && (
                                <Button
                                  size="sm"
                                  variant="ghost"
                                  className="h-6 text-[10px] text-primary hover:bg-primary/5 p-0 px-1"
                                  onClick={() => handleRunReview(e.id)}
                                >
                                  <RotateCcw className="h-2.5 w-2.5 mr-1" />
                                  Trigger Review
                                </Button>
                              )}
                              {(e.review_status === 'pending' || e.review_status === 'rejected' || e.review_status === 'failed') && (
                                <Button
                                  size="sm"
                                  variant="ghost"
                                  className="h-6 text-[10px] text-destructive hover:bg-destructive/5 p-0 px-1"
                                  onClick={() => handleCancelReview(e.id)}
                                >
                                  <X className="h-2.5 w-2.5 mr-1" />
                                  {e.review_status === 'pending' ? 'Cancel Review' : 'Clear Status'}
                                </Button>
                              )}
                            </div>
                          )}
                        </TableCell>}
                        {isVisible('receipt') && <TableCell>
                          <div className="flex flex-col gap-2">
                            <label className="inline-flex items-center gap-2 cursor-pointer w-fit">
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
                              <span className="text-sm">{uploadingId === e.id ? t('expenses.uploading') : t('expenses.upload')}</span>
                            </label>
                            <Button variant="ghost" size="sm" className="w-fit justify-start px-0" onClick={async () => {
                              const list = await expenseApi.listAttachments(e.id);
                              setAttachments(prev => ({ ...prev, [e.id]: list }));
                              setAttachmentPreviewOpen({ expenseId: e.id });
                            }}>
                              {Array.isArray(attachments[e.id]) || typeof e.attachments_count === 'number' ? (
                                <span className="text-sm">{Array.isArray(attachments[e.id]) ? attachments[e.id].length : e.attachments_count} {t('expenses.file_count', { defaultValue: 'file(s)', count: Array.isArray(attachments[e.id]) ? attachments[e.id].length : e.attachments_count })}</span>
                              ) : (
                                <>
                                  <Eye className="w-4 h-4 mr-2" />
                                  <span className="text-sm">{t('common.view')}</span>
                                </>
                              )}
                            </Button>
                          </div>
                        </TableCell>}
                        <TableCell>
                          {canPerformActions() && (
                            <div className="text-right flex gap-2 justify-end">
                              <Button size="sm" variant="outline" onClick={() => window.location.href = `/expenses/view/${e.id}`}>
                                <Eye className="w-4 h-4" />
                              </Button>
                              {canEditExpense(e) && (
                                <Button size="sm" variant="outline" onClick={() => window.location.href = `/expenses/edit/${e.id}`}>
                                  <Edit className="w-4 h-4" />
                                </Button>
                              )}
                              {canDeleteExpense(e) && (
                                <AlertDialog>
                                  <AlertDialogTrigger asChild>
                                    <Button size="sm" variant="destructive">
                                      <Trash2 className="w-4 h-4" />
                                    </Button>
                                  </AlertDialogTrigger>
                                  <AlertDialogContent>
                                    <AlertDialogHeader>
                                      <AlertDialogTitle>{t('expenses.delete_confirm_title')}</AlertDialogTitle>
                                      <AlertDialogDescription>
                                        {t('expenses.delete_confirm_description')}
                                      </AlertDialogDescription>
                                    </AlertDialogHeader>
                                    <AlertDialogFooter>
                                      <AlertDialogCancel>{t('expenses.cancel')}</AlertDialogCancel>
                                      <AlertDialogAction onClick={() => handleDelete(e.id)}>{t('expenses.delete')}</AlertDialogAction>
                                    </AlertDialogFooter>
                                  </AlertDialogContent>
                                </AlertDialog>
                              )}
                            </div>
                          )}
                        </TableCell>
                      </TableRow>
                    ))
                  ) : (
                    <TableRow>
                      <TableCell colSpan={15} className="h-auto p-0 border-none">
                        <div className="text-center py-20 bg-muted/5 rounded-xl border-2 border-dashed border-muted-foreground/20 m-4">
                          <div className="bg-primary/10 w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-4">
                            <Receipt className="h-8 w-8 text-primary" />
                          </div>
                          <h3 className="text-xl font-bold mb-2">{t('expenses.no_expenses_yet', 'No expenses yet')}</h3>
                          <p className="text-muted-foreground max-w-sm mx-auto">
                            {t('expenses.no_expenses_description', 'Start tracking your business outgoings. You can create expenses manually or upload receipts for AI-powered data extraction.')}
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
                Showing <span className="font-medium text-foreground">{expenses.length}</span> of <span className="font-medium text-foreground">{totalExpenses}</span> {t('expenses.results', 'results')}
              </div>
              <div className="flex items-center gap-2">
                <ProfessionalButton
                  variant="outline"
                  size="sm"
                  onClick={() => setPage(prev => Math.max(1, prev - 1))}
                  disabled={page === 1}
                  className="h-9 px-4"
                >
                  {t('common.previous', 'Previous')}
                </ProfessionalButton>
                <div className="flex items-center gap-1">
                  {Array.from({ length: Math.ceil(totalExpenses / pageSize) }, (_, i) => i + 1)
                    .filter(p => p === 1 || p === Math.ceil(totalExpenses / pageSize) || Math.abs(p - page) <= 1)
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
                  onClick={() => setPage(prev => Math.min(Math.ceil(totalExpenses / pageSize), prev + 1))}
                  disabled={page >= Math.ceil(totalExpenses / pageSize)}
                  className="h-9 px-4"
                >
                  {t('common.next', 'Next')}
                </ProfessionalButton>
              </div>
            </div>
          </CardContent>
        </ProfessionalCard>

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
                        {att.file_size ? <span className="ml-2 text-xs text-muted-foreground">({Math.round(att.file_size / 1024)} KB)</span> : null}
                      </div>
                      <div className="flex items-center gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={async () => {
                            if (!attachmentPreviewOpen.expenseId) return;
                            setPreviewLoading({ expenseId: attachmentPreviewOpen.expenseId, attachmentId: att.id });
                            try {
                              const { blob, contentType } = await expenseApi.downloadAttachmentBlob(attachmentPreviewOpen.expenseId, att.id);
                              const url = URL.createObjectURL(blob);
                              setPreview({ open: true, url, contentType: contentType || att.content_type || null, filename: att.filename || null });
                            } finally {
                              setPreviewLoading(null);
                            }
                          }}
                          disabled={previewLoading?.expenseId === attachmentPreviewOpen.expenseId && previewLoading?.attachmentId === att.id}
                        >
                          {previewLoading?.expenseId === attachmentPreviewOpen.expenseId && previewLoading?.attachmentId === att.id ? (
                            <>
                              <div className="w-4 h-4 mr-1 border-2 border-current border-t-transparent rounded-full animate-spin" />
                              Loading...
                            </>
                          ) : (
                            t('expenses.preview')
                          )}
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
              <DialogTitle>{preview.filename || t('expenses.preview', { defaultValue: 'Preview' })}</DialogTitle>
            </DialogHeader>
            <div className="max-h-[70vh] overflow-auto">
              {preview.url && (preview.contentType || '').startsWith('image/') && (
                <img src={preview.url} alt={preview.filename || 'attachment'} className="max-w-full h-auto" />
              )}
              {preview.url && preview.contentType === 'application/pdf' && (
                <iframe src={preview.url} className="w-full h-[70vh]" title={t('expenses.pdf_preview', { defaultValue: 'PDF Preview' })} />
              )}
              {preview.url && preview.contentType && !((preview.contentType || '').startsWith('image/') || preview.contentType === 'application/pdf') && (
                <div className="text-sm text-muted-foreground">{t('expenses.cannot_preview', { defaultValue: 'This file type cannot be previewed. Please download instead.' })}</div>
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

        {/* Permanent Delete Modal */}
        <AlertDialog open={!!expenseToPermanentlyDelete} onOpenChange={(open) => !open && setExpenseToPermanentlyDelete(null)}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>{t('expenseRecycleBin.permanent_delete_confirm_title', { defaultValue: 'Permanently Delete Expense?' })}</AlertDialogTitle>
              <AlertDialogDescription>
                {t('expenseRecycleBin.permanent_delete_confirm_description', { defaultValue: 'This action cannot be undone. This will permanently delete the expense and remove it from our servers.' })}
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>{t('common.cancel')}</AlertDialogCancel>
              <AlertDialogAction
                className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                onClick={() => expenseToPermanentlyDelete && handlePermanentlyDeleteExpense(expenseToPermanentlyDelete)}
              >
                {t('expenseRecycleBin.permanent_delete', { defaultValue: 'Permanently Delete' })}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>

        {/* Empty Recycle Bin Modal */}
        <AlertDialog open={emptyRecycleBinModalOpen} onOpenChange={setEmptyRecycleBinModalOpen}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>{t('expenseRecycleBin.empty_recycle_bin_confirm_title', { defaultValue: 'Empty Recycle Bin' })}</AlertDialogTitle>
              <AlertDialogDescription>
                {t('expenseRecycleBin.empty_recycle_bin_confirm_description', { defaultValue: 'Are you sure you want to permanently delete all expenses in the recycle bin? This action cannot be undone and all deleted expenses will be completely removed from the system.' })}
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>{t('common.cancel')}</AlertDialogCancel>
              <AlertDialogAction onClick={confirmEmptyRecycleBin} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">
                <Trash2 className="mr-2 h-4 w-4" />
                {t('expenseRecycleBin.empty_recycle_bin', { defaultValue: 'Empty Recycle Bin' })}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>

        {/* Bulk Expense Creation Modal */}
        <BulkExpenseModal
          open={isBulkCreateOpen}
          onOpenChange={setIsBulkCreateOpen}
          onSuccess={fetchExpenses}
        />

      </div>
      {selectedReviewExpense && (
        <ReviewDiffModal
          isOpen={reviewModalOpen}
          onClose={() => setReviewModalOpen(false)}
          originalData={selectedReviewExpense}
          reviewResult={selectedReviewExpense.review_result}
          onAccept={handleAcceptReview}
          onReject={handleRejectReview}
          onRetrigger={handleRetriggerReview}
          isAccepting={isAcceptingReview}
          isRejecting={isRejectingReview}
          isRetriggering={isRetriggeringReview}
          type="expense"
          readOnly={selectedReviewExpense?.review_status === 'reviewed' || selectedReviewExpense?.review_status === 'no_diff'}
        />
      )}
    </>
  );
};

export default Expenses;
