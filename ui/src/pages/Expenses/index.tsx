import { useEffect, useMemo, useState, useRef, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { useQuery } from '@tanstack/react-query';
import { CardContent } from '@/components/ui/card';
import {
  RotateCcw, Plus, ChevronDown, ChevronUp, BarChart3, Trash2, Upload
} from 'lucide-react';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { Link } from 'react-router-dom';
import { useSearchParams } from 'react-router-dom';
import { toast } from 'sonner';
import { expenseApi, Expense, ExpenseAttachmentMeta, settingsApi, DeletedExpense } from '@/lib/api';
import { EXPENSE_CATEGORY_OPTIONS } from '@/constants/expenses';
import { canPerformActions } from '@/utils/auth';
import { ProfessionalCard } from '@/components/ui/professional-card';
import { ProfessionalButton } from '@/components/ui/professional-button';
import { useColumnVisibility } from '@/hooks/useColumnVisibility';
import { BulkExpenseModal } from '@/components/BulkExpenseModal';
import { ReviewDiffModal } from '@/components/ReviewDiffModal';
import ExpenseSummary from '@/components/expenses/ExpenseSummary';
import ExpenseCharts from '@/components/expenses/ExpenseCharts';
import { useFeatures } from '@/contexts/FeatureContext';
import { ShareButton } from '@/components/sharing/ShareButton';

import { EXPENSE_COLUMNS, type PreviewState, type AttachmentPreviewState } from './types';
import { ExpenseFilters } from './ExpenseFilters';
import { BulkActionsToolbar } from './BulkActionsToolbar';
import { ExpenseTable } from './ExpenseTable';
import { RecycleBinSection } from './RecycleBinSection';
import { ExpenseEditDialog } from './ExpenseEditDialog';
import { AttachmentPreviewDialog } from './AttachmentPreviewDialog';

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

  const [uploadingId, setUploadingId] = useState<number | null>(null);
  const [isEditOpen, setIsEditOpen] = useState(false);
  const [editExpense, setEditExpense] = useState<Partial<Expense> & { id?: number }>({});
  const [editReceiptFile, setEditReceiptFile] = useState<File | null>(null);
  const [attachmentPreviewOpen, setAttachmentPreviewOpen] = useState<AttachmentPreviewState>({ expenseId: null });
  const [attachments, setAttachments] = useState<Record<number, ExpenseAttachmentMeta[]>>({});

  const [preview, setPreview] = useState<PreviewState>({ open: false, url: null, contentType: null, filename: null });
  const [previewLoading, setPreviewLoading] = useState<{ expenseId: number; attachmentId: number } | null>(null);
  const [isBulkCreateOpen, setIsBulkCreateOpen] = useState(false);


  // Inventory consumption state for edit expense
  const [isEditInventoryConsumption, setIsEditInventoryConsumption] = useState(false);
  const [expenseIdToDelete, setExpenseIdToDelete] = useState<number | null>(null);
  const [shareExpenseId, setShareExpenseId] = useState<number | null>(null);
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

    } catch (e) {
      toast.error(t('expenses.load_failed', { defaultValue: 'Failed to load expenses' }));
    } finally {
      setLoading(false);
    }
  }, [categoryFilter, labelFilter, unlinkedOnly, page, pageSize, searchQuery]);

  useEffect(() => {
    fetchExpenses();
  }, [fetchExpenses]);

  // Listen for polling completion events
  useEffect(() => {
    const handleRefresh = () => {
      fetchExpenses();
    };
    window.addEventListener('expense-processed', handleRefresh);
    window.addEventListener('expense-failed', handleRefresh);
    return () => {
      window.removeEventListener('expense-processed', handleRefresh);
      window.removeEventListener('expense-failed', handleRefresh);
    };
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
        <RecycleBinSection
          showRecycleBin={showRecycleBin}
          setShowRecycleBin={setShowRecycleBin}
          recycleBinLoading={recycleBinLoading}
          deletedExpenses={deletedExpenses}
          recycleBinTotalCount={recycleBinTotalCount}
          recycleBinCurrentPage={recycleBinCurrentPage}
          setRecycleBinCurrentPage={setRecycleBinCurrentPage}
          recycleBinPageSize={recycleBinPageSize}
          onRestore={handleRestoreExpense}
          onEmptyRecycleBin={handleEmptyRecycleBin}
          onSetExpenseToPermanentlyDelete={(id) => setExpenseToPermanentlyDelete(id)}
          expenseToPermanentlyDelete={expenseToPermanentlyDelete}
          onPermanentlyDelete={handlePermanentlyDeleteExpense}
          emptyRecycleBinModalOpen={emptyRecycleBinModalOpen}
          setEmptyRecycleBinModalOpen={setEmptyRecycleBinModalOpen}
          onConfirmEmptyRecycleBin={confirmEmptyRecycleBin}
        />

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
              <ExpenseFilters
                searchQuery={searchQuery}
                setSearchQuery={setSearchQuery}
                categoryFilter={categoryFilter}
                setCategoryFilter={setCategoryFilter}
                categoryOptions={categoryOptions}
                labelFilter={labelFilter}
                setLabelFilter={setLabelFilter}
                unlinkedOnly={unlinkedOnly}
                setUnlinkedOnly={setUnlinkedOnly}
                pageSize={pageSize}
                setPageSize={setPageSize}
                setPage={setPage}
                isVisible={isVisible}
                toggle={toggle}
                reset={reset}
                hiddenCount={hiddenCount}
              />
            </div>

          </div>

          <CardContent className="px-0">
            {/* Results Count and Selection Toolbar */}
            <div className="space-y-4 mb-6">
              <BulkActionsToolbar
                selectedIds={selectedIds}
                setSelectedIds={setSelectedIds}
                bulkLabel={bulkLabel}
                setBulkLabel={setBulkLabel}
                canPerformActionsResult={canPerformActions()}
                categoryFilter={categoryFilter}
                labelFilter={labelFilter}
                unlinkedOnly={unlinkedOnly}
                page={page}
                pageSize={pageSize}
                onExpensesChange={(expenses, total) => {
                  setExpenses(expenses);
                  setTotalExpenses(total);
                }}
                showRecycleBin={showRecycleBin}
                onRecycleBinRefresh={() => {
                  setRecycleBinCurrentPage(1);
                  fetchDeletedExpenses();
                }}
                onBulkRunReview={handleBulkRunReview}
                loading={loading}
              />
            </div>
            <ExpenseTable
              loading={loading}
              filteredExpenses={filteredExpenses}
              selectedIds={selectedIds}
              setSelectedIds={setSelectedIds}
              isVisible={isVisible}
              getLocale={getLocale}
              timezone={timezone}
              attachments={attachments}
              setAttachments={setAttachments}
              setAttachmentPreviewOpen={setAttachmentPreviewOpen}
              uploadingId={uploadingId}
              onUpload={handleUpload}
              onRequeue={handleRequeue}
              processingLocks={processingLocks}
              onReviewClick={handleReviewClick}
              onRunReview={handleRunReview}
              onCancelReview={handleCancelReview}
              newLabelValueById={newLabelValueById}
              setNewLabelValueById={setNewLabelValueById}
              onSetShareExpenseId={setShareExpenseId}
              onSetExpenseIdToDelete={setExpenseIdToDelete}
              setExpenses={setExpenses}
            />
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

        <ExpenseEditDialog
          isEditOpen={isEditOpen}
          setIsEditOpen={setIsEditOpen}
          editExpense={editExpense}
          setEditExpense={setEditExpense}
          isEditInventoryConsumption={isEditInventoryConsumption}
          setIsEditInventoryConsumption={setIsEditInventoryConsumption}
          editConsumptionItems={editConsumptionItems}
          setEditConsumptionItems={setEditConsumptionItems}
          setEditReceiptFile={setEditReceiptFile}
          onUpdate={handleUpdate}
          expenses={expenses}
          hasAIExpenseFeature={hasAIExpenseFeature}
          categoryOptions={categoryOptions}
        />

        <AttachmentPreviewDialog
          attachmentPreviewOpen={attachmentPreviewOpen}
          setAttachmentPreviewOpen={setAttachmentPreviewOpen}
          attachments={attachments}
          preview={preview}
          setPreview={setPreview}
          previewLoading={previewLoading}
          setPreviewLoading={setPreviewLoading}
        />

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

      {shareExpenseId !== null && (
        <ShareButton recordType="expense" recordId={shareExpenseId} open onOpenChange={(open) => { if (!open) setShareExpenseId(null); }} />
      )}

      {/* Delete confirmation dialog */}
      <AlertDialog open={expenseIdToDelete !== null} onOpenChange={(open) => { if (!open) setExpenseIdToDelete(null); }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('expenses.delete_confirm_title')}</AlertDialogTitle>
            <AlertDialogDescription>{t('expenses.delete_confirm_description')}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t('expenses.cancel')}</AlertDialogCancel>
            <AlertDialogAction onClick={() => { if (expenseIdToDelete !== null) { handleDelete(expenseIdToDelete); setExpenseIdToDelete(null); } }}>{t('expenses.delete')}</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
};

export default Expenses;
