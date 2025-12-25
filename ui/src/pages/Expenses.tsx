import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useQuery } from '@tanstack/react-query';
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
import { CalendarIcon, X, Eye, AlertCircle } from 'lucide-react';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { useFeatures } from '@/contexts/FeatureContext';
import { BulkExpenseModal } from '@/components/BulkExpenseModal';
import { InventoryConsumptionForm } from '@/components/inventory/InventoryConsumptionForm';
import { ExpenseApprovalStatus } from '@/components/approvals/ExpenseApprovalStatus';
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
import { Loader2, Plus, Search, Trash2, Upload, ChevronDown, ChevronUp, MoreHorizontal, Edit, Package, RotateCcw, BarChart3, Receipt } from 'lucide-react';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { Link } from 'react-router-dom';
import { useSearchParams } from 'react-router-dom';
import { toast } from 'sonner';
import { expenseApi, approvalApi, Expense, ExpenseAttachmentMeta, api, linkApi, settingsApi, DeletedExpense } from '@/lib/api';
import { Badge } from '@/components/ui/badge';
import { CurrencySelector } from '@/components/ui/currency-selector';
import { Label } from '@/components/ui/label';
import { Users } from 'lucide-react';
import { EXPENSE_CATEGORY_OPTIONS } from '@/constants/expenses';
import { canPerformActions, canEditExpense, canDeleteExpense, getCurrentUser } from '@/utils/auth';
import { formatDate } from '@/lib/utils';
import { PageHeader, ContentSection } from "@/components/ui/professional-layout";
import { ProfessionalCard } from "@/components/ui/professional-card";
import { ProfessionalButton } from "@/components/ui/professional-button";


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
  const { isFeatureEnabled } = useFeatures();
  const hasAIExpenseFeature = isFeatureEnabled('ai_expense');
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

  // Approval workflow state for new expense modal
  const [submitNewForApproval, setSubmitNewForApproval] = useState(false);
  const [selectedNewApproverId, setSelectedNewApproverId] = useState<string>('');
  const [availableNewApprovers, setAvailableNewApprovers] = useState<Array<{ id: number; name: string; email: string }>>([]);
  const [approvalsNotLicensed, setApprovalsNotLicensed] = useState(false);
  const [preview, setPreview] = useState<{ open: boolean; url: string | null; contentType: string | null; filename: string | null }>({ open: false, url: null, contentType: null, filename: null });
  const [previewLoading, setPreviewLoading] = useState<{ expenseId: number; attachmentId: number } | null>(null);
  const [isBulkCreateOpen, setIsBulkCreateOpen] = useState(false);
  const [invoiceOptions, setInvoiceOptions] = useState<Array<{ id: number; number: string; client_name: string }>>([]);

  // Inventory consumption state for new expense
  const [isNewInventoryConsumption, setIsNewInventoryConsumption] = useState(false);
  const [newConsumptionItems, setNewConsumptionItems] = useState<any[]>([]);

  // Inventory consumption state for edit expense
  const [isEditInventoryConsumption, setIsEditInventoryConsumption] = useState(false);
  const [editConsumptionItems, setEditConsumptionItems] = useState<any[]>([]);

  // Processing lock state for expenses
  const [processingLocks, setProcessingLocks] = useState<Set<number>>(new Set());

  // Creating state for new expense modal
  const [creating, setCreating] = useState(false);

  // Recycle bin state
  const [showRecycleBin, setShowRecycleBin] = useState(false);
  const [deletedExpenses, setDeletedExpenses] = useState<DeletedExpense[]>([]);
  const [recycleBinLoading, setRecycleBinLoading] = useState(false);
  const [expenseToPermanentlyDelete, setExpenseToPermanentlyDelete] = useState<number | null>(null);
  const [emptyRecycleBinModalOpen, setEmptyRecycleBinModalOpen] = useState(false);

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

  // Calculate amount from consumption items for new expense
  useEffect(() => {
    if (isNewInventoryConsumption && newConsumptionItems.length > 0) {
      const total = newConsumptionItems.reduce((sum, item) => sum + (item.quantity * (item.unit_cost || 0)), 0);
      setNewExpense(prev => ({ ...prev, amount: total }));
    }
  }, [newConsumptionItems, isNewInventoryConsumption]);

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
    const fetchApprovers = async () => {
      try {
        const response = await approvalApi.getApprovers();
        setAvailableNewApprovers(response);
        setApprovalsNotLicensed(false);
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : String(error);
        // Check if it's a license error (402 Payment Required)
        if (errorMessage.includes('not included in your current license') || errorMessage.includes('requires a valid license')) {
          setApprovalsNotLicensed(true);
          setAvailableNewApprovers([]);
        } else {
          console.error('Failed to fetch approvers:', error);
          setAvailableNewApprovers([]);
        }
      }
    };
    fetchApprovers();
  }, []);

  const fetchExpenses = async () => {
    setLoading(true);
    try {
      const skip = (page - 1) * pageSize;
      const data = await expenseApi.getExpensesFiltered({
        category: categoryFilter,
        label: labelFilter || undefined,
        unlinkedOnly,
        skip,
        limit: pageSize,
        search: searchQuery || undefined,
        // Don't exclude pending_approval - users should see their own submitted expenses
      });

      // Reset to page 1 if current page has no results but we're not on page 1
      if (data.length === 0 && page > 1) {
        setPage(1);
        return;
      }

      setExpenses(data);

      // Determine if there's a next page based on the current page and total results
      // If we got exactly pageSize results, there might be more, so probe the next page
      if (data.length === pageSize) {
        // Probe next page existence precisely
        try {
          const probe = await expenseApi.getExpensesFiltered({
            category: categoryFilter,
            label: labelFilter || undefined,
            unlinkedOnly,
            skip: skip + pageSize,
            limit: 1,
            search: searchQuery || undefined,
          });
          const hasMore = Array.isArray(probe) && probe.length > 0;
          setHasNextPage(hasMore);
          console.log(`Pagination check: page=${page}, pageSize=${pageSize}, currentResults=${data.length}, probeResults=${probe.length}, hasMore=${hasMore}`);
          if (hasMore) {
            console.log('Probe found additional expenses:', probe);
          }
        } catch (error) {
          console.error('Error probing next page:', error);
          setHasNextPage(false);
        }
      } else {
        // If we got fewer results than pageSize, there's definitely no next page
        setHasNextPage(false);
        console.log(`Pagination: page=${page}, pageSize=${pageSize}, currentResults=${data.length}, hasNextPage=false (fewer than pageSize)`);
      }
    } catch (e) {
      toast.error('Failed to load expenses');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchExpenses();
  }, [categoryFilter, labelFilter, unlinkedOnly, page, pageSize, currentTenantId, searchQuery]);

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

  const openCreate = () => {
    setNewExpense(defaultNewExpense);
    setNewReceiptFile(null);
    setIsNewInventoryConsumption(false);
    setNewConsumptionItems([]);
    setSubmitNewForApproval(false);
    setSelectedNewApproverId('');
    setIsCreateOpen(true);
  };

  const handleCreate = async () => {
    // Prevent multiple submissions
    if (creating) return;

    setCreating(true);
    try {
      if ((!newExpense.amount || Number(newExpense.amount) === 0) && !newReceiptFile) {
        toast.error('Amount is required unless importing from a file');
        setCreating(false);
        return;
      }
      if (!newExpense.category) {
        toast.error('Category is required');
        setCreating(false);
        return;
      }
      if (isNewInventoryConsumption && (!newConsumptionItems || newConsumptionItems.length === 0)) {
        toast.error('Inventory consumption must include at least one item');
        setCreating(false);
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
        invoice_id: newExpense.invoice_id ?? null,
        is_inventory_consumption: isNewInventoryConsumption,
        consumption_items: isNewInventoryConsumption ? newConsumptionItems : null,
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
      // Submit for approval if requested
      if (submitNewForApproval && selectedNewApproverId) {
        try {
          await approvalApi.submitForApproval(createdWithReceipt.id, parseInt(selectedNewApproverId), undefined);
          toast.success('Expense created and submitted for approval');
        } catch (approvalError) {
          console.error('Approval submission failed:', approvalError);
          toast.error('Expense created but failed to submit for approval');
        }
      } else {
        toast.success('Expense created');
      }

      // Reset approval workflow state
      setSubmitNewForApproval(false);
      setSelectedNewApproverId('');
      setExpenses(prev => [createdWithReceipt, ...prev]);
      setIsCreateOpen(false);
    } catch (e: any) {
      toast.error(e?.message || 'Failed to create expense');
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await expenseApi.deleteExpense(id);
      setExpenses(prev => prev.filter(e => e.id !== id));
      // Refresh recycle bin if it's currently open
      if (showRecycleBin) {
        fetchDeletedExpenses();
      }
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
      toast.success('Expense reprocessing started');

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
      const errorMessage = e?.message || 'Failed to reprocess expense';
      if (errorMessage.includes('already being processed') || errorMessage.includes('processing lock')) {
        toast.error('This expense is currently being processed by another operation. Please try again in a few minutes.');
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
        toast.error('Amount and category are required');
        return;
      }
      if (isEditInventoryConsumption && (!editConsumptionItems || editConsumptionItems.length === 0)) {
        toast.error('Inventory consumption must include at least one item');
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

  // Recycle bin functions
  const fetchDeletedExpenses = async () => {
    try {
      setRecycleBinLoading(true);
      const data = await expenseApi.getDeletedExpenses();
      setDeletedExpenses(data);
    } catch (error) {
      console.error('Failed to fetch deleted expenses:', error);
      toast.error('Failed to load recycle bin');
    } finally {
      setRecycleBinLoading(false);
    }
  };

  const handleRestoreExpense = async (expenseId: number) => {
    try {
      await expenseApi.restoreExpense(expenseId, 'recorded');
      toast.success('Expense restored successfully');
      fetchDeletedExpenses();
      fetchExpenses(); // Refresh main list
    } catch (error: any) {
      console.error('Failed to restore expense:', error);
      toast.error(error?.message || 'Failed to restore expense');
    }
  };

  const handlePermanentlyDeleteExpense = async (expenseId: number) => {
    try {
      await expenseApi.permanentlyDeleteExpense(expenseId);
      toast.success('Expense permanently deleted');
      fetchDeletedExpenses();
      setExpenseToPermanentlyDelete(null);
    } catch (error: any) {
      console.error('Failed to permanently delete expense:', error);
      toast.error(error?.message || 'Failed to permanently delete expense');
    }
  };

  const handleEmptyRecycleBin = () => {
    setEmptyRecycleBinModalOpen(true);
  };

  const confirmEmptyRecycleBin = async () => {
    try {
      const response = await expenseApi.emptyRecycleBin();
      toast.success('Recycle bin emptied successfully');
      fetchDeletedExpenses();
      setEmptyRecycleBinModalOpen(false);
    } catch (error: any) {
      console.error('Failed to empty recycle bin:', error);
      toast.error(error?.message || 'Failed to empty recycle bin');
    }
  };

  const handleToggleRecycleBin = () => {
    setShowRecycleBin(!showRecycleBin);
    if (!showRecycleBin) {
      fetchDeletedExpenses();
    }
  };

  return (
    <AppLayout>
      <div className="h-full space-y-8 fade-in">
        {/* Hero Header */}
        <div className="bg-gradient-to-r from-primary/10 via-primary/5 to-transparent rounded-2xl border border-primary/20 p-8 backdrop-blur-sm">
          <div className="flex items-center justify-between gap-6">
            <div className="space-y-2">
              <h1 className="text-4xl font-bold tracking-tight text-foreground">{t('expenses.title')}</h1>
              <p className="text-lg text-muted-foreground">{t('expenses.description')}</p>
            </div>
            {canPerformActions() && (
              <div className="flex gap-2 items-center flex-wrap justify-end">
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
                  <ProfessionalButton onClick={openCreate} variant="default" size="default" className="shadow-lg">
                    <Plus className="w-4 h-4 mr-2" /> {t('expenses.new')}
                  </ProfessionalButton>
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
                          <span className="text-xs text-muted-foreground">Batch create expenses</span>
                        </div>
                      </DropdownMenuItem>
                      <DropdownMenuItem asChild>
                        <Link to="/expenses/import" className="flex items-center w-full cursor-pointer">
                          <Upload className="mr-2 h-4 w-4" />
                          <div className="flex flex-col">
                            <span>{t('expenses.import_from_pdf_images')}</span>
                            <span className="text-xs text-muted-foreground">Upload and extract</span>
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
                      <p className="text-sm text-muted-foreground">Recover or permanently delete expenses</p>
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
          <div className="flex flex-col sm:flex-row justify-between gap-4 mb-6">
            <h2 className="text-xl font-semibold tracking-tight">{t('expenses.list_title')}</h2>
            <div className="flex flex-col sm:flex-row gap-4">
              <div className="relative">
                <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder={t('expenses.search_placeholder')}
                  className="pl-8 w-full sm:w-[260px]"
                  value={searchQuery}
                  onChange={(e) => { setSearchQuery(e.target.value); setPage(1); }}
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
                <span className="text-sm text-muted-foreground">{t('expenses.page_size')}</span>
                <Select value={String(pageSize)} onValueChange={(v) => { setPageSize(Number(v)); setPage(1); }}>
                  <SelectTrigger className="w-[100px]">
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
                      const data = await expenseApi.getExpensesFiltered({ category: categoryFilter, label: labelFilter || undefined, unlinkedOnly, skip, limit: pageSize, excludeStatus: 'pending_approval' });
                      setExpenses(data);
                      setSelectedIds([]);
                      setBulkLabel('');
                      toast.success('Labels added');
                    } catch (e: any) {
                      toast.error(e?.message || 'Failed to add label');
                    }
                  }}
                >
                  {t('expenses.add')}
                </Button>
                <Button
                  variant="outline"
                  disabled={!canPerformActions() || selectedIds.length === 0 || !bulkLabel.trim()}
                  onClick={async () => {
                    try {
                      const skip = (page - 1) * pageSize;
                      await expenseApi.bulkLabels(selectedIds, 'remove', bulkLabel.trim());
                      const data = await expenseApi.getExpensesFiltered({ category: categoryFilter, label: labelFilter || undefined, unlinkedOnly, skip, limit: pageSize, excludeStatus: 'pending_approval' });
                      setExpenses(data);
                      setSelectedIds([]);
                      setBulkLabel('');
                      toast.success('Labels removed');
                    } catch (e: any) {
                      toast.error(e?.message || 'Failed to remove label');
                    }
                  }}
                >
                  {t('expenses.remove')}
                </Button>
                <AlertDialog>
                  <AlertDialogTrigger asChild>
                    <Button
                      variant="destructive"
                      disabled={!canPerformActions() || selectedIds.length === 0}
                    >
                      <Trash2 className="w-4 h-4 mr-2" />
                      {t('expenses.delete_selected', { defaultValue: 'Delete Selected' })}
                    </Button>
                  </AlertDialogTrigger>
                  <AlertDialogContent>
                    <AlertDialogHeader>
                      <AlertDialogTitle>{selectedIds.length === 1 ? t('expenses.delete_single_title', { defaultValue: 'Delete 1 Expense' }) : t('expenses.delete_multiple_title', { count: selectedIds.length, defaultValue: `Delete ${selectedIds.length} Expenses` })}</AlertDialogTitle>
                      <AlertDialogDescription>
                        {selectedIds.length === 1 ? t('expenses.delete_single_description', { defaultValue: 'Are you sure you want to delete 1 expense? This will move the selected expense to the recycle bin where it can be restored or permanently deleted later.' }) : t('expenses.delete_multiple_description', { count: selectedIds.length, defaultValue: `Are you sure you want to delete ${selectedIds.length} expenses? This will move the selected expenses to the recycle bin where they can be restored or permanently deleted later.` })}
                      </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                      <AlertDialogCancel>{t('common.cancel')}</AlertDialogCancel>
                      <AlertDialogAction
                        onClick={async () => {
                          try {
                            await expenseApi.bulkDelete(selectedIds);
                            const data = await expenseApi.getExpensesFiltered({ category: categoryFilter, label: labelFilter || undefined, unlinkedOnly, skip: (page - 1) * pageSize, limit: pageSize, excludeStatus: 'pending_approval' });
                            setExpenses(data);
                            setSelectedIds([]);
                            toast.success(`Successfully deleted ${selectedIds.length} expense${selectedIds.length > 1 ? 's' : ''}`);
                          } catch (e: any) {
                            toast.error(e?.message || 'Failed to delete expenses');
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
                    <TableHead>{t('expenses.table.id', { defaultValue: 'ID' })}</TableHead>
                    <TableHead>{t('expenses.table.date')}</TableHead>
                    <TableHead>{t('expenses.table.category')}</TableHead>
                    <TableHead>{t('expenses.table.vendor')}</TableHead>
                    <TableHead>{t('expenses.table.labels', { defaultValue: 'Labels' })}</TableHead>
                    <TableHead>{t('expenses.table.amount')}</TableHead>
                    <TableHead>{t('expenses.table.total')}</TableHead>
                    <TableHead>{t('expenses.table.invoice')}</TableHead>
                    <TableHead>{t('expenses.table.approval_status', { defaultValue: 'Approval Status' })}</TableHead>
                    <TableHead className="hidden xl:table-cell">{t('common.created_by')}</TableHead>
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
                        <TableCell>
                          <div className="flex flex-col">
                            <span>{e.expense_date ? new Date(e.expense_date).toLocaleDateString('en-US', { timeZone: timezone }) : 'N/A'}</span>
                            {e.receipt_timestamp && e.receipt_time_extracted && (
                              <span className="text-xs text-muted-foreground">
                                🕐 {new Date(e.receipt_timestamp).toLocaleTimeString('en-US', { timeZone: timezone, hour: '2-digit', minute: '2-digit' })}
                              </span>
                            )}
                          </div>
                        </TableCell>
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
                                    aria-label={t('expenses.remove')}
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
                          <ExpenseApprovalStatus
                            expense={{
                              id: e.id,
                              status: e.status,
                              amount: e.amount || 0,
                              currency: e.currency || 'USD'
                            }}
                            approvals={[]} // TODO: Fetch approvals data
                          />
                        </TableCell>
                        <TableCell className="hidden xl:table-cell text-sm text-muted-foreground">
                          {e.created_by_username || e.created_by_email || t('common.unknown')}
                        </TableCell>
                        <TableCell>
                          {e.analysis_status === 'done' ? (
                            <Badge variant="success">{t('expenses.status_done')}</Badge>
                          ) : e.analysis_status === 'processing' || e.analysis_status === 'queued' ? (
                            <Badge variant="warning" className="capitalize">{e.analysis_status === 'processing' ? t('expenses.status_processing') : t('expenses.status_queued')}</Badge>
                          ) : e.analysis_status === 'failed' ? (
                            <Badge variant="destructive">Failed</Badge>
                          ) : e.analysis_status === 'cancelled' ? (
                            <Badge variant="secondary">Cancelled</Badge>
                          ) : e.imported_from_attachment ? (
                            <Badge variant="info">Not Started</Badge>
                          ) : (
                            <span className="text-muted-foreground text-xs">—</span>
                          )}
                          {e.analysis_status && e.analysis_status !== 'done' && canPerformActions() && (
                            <Button
                              variant="ghost"
                              size="sm"
                              className="ml-2"
                              onClick={() => handleRequeue(e.id)}
                              disabled={
                                !e.imported_from_attachment &&
                                (!e.attachments_count || e.attachments_count === 0) ||
                                processingLocks.has(e.id) ||
                                uploadingId === e.id
                              }
                            >
                              {processingLocks.has(e.id) ? (
                                <div className="flex items-center gap-1">
                                  <div className="w-3 h-3 border-2 border-current border-t-transparent rounded-full animate-spin" />
                                  Processing...
                                </div>
                              ) : uploadingId === e.id ? (
                                'Uploading...'
                              ) : (
                                t('expenses.process_again', { defaultValue: 'Process Again' })
                              )}
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
                            {Array.isArray(attachments[e.id]) || typeof e.attachments_count === 'number' ? (
                              `${Array.isArray(attachments[e.id]) ? attachments[e.id].length : e.attachments_count} ${t('expenses.attachments_count', { defaultValue: 'attachments' })}`
                            ) : (
                              <>
                                <Eye className="w-4 h-4 mr-2" />
                              </>
                            )}
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
                                  <Link to={`/expenses/view/${e.id}`} className="flex items-center w-full">
                                    <Eye className="w-4 h-4 mr-2" />
                                    {t('common.view', { defaultValue: 'View' })}
                                  </Link>
                                </DropdownMenuItem>
                                {canEditExpense(e) && (
                                  <DropdownMenuItem asChild>
                                    <Link to={`/expenses/edit/${e.id}`} className="flex items-center w-full">
                                      <Edit className="w-4 h-4 mr-2" />
                                      {t('expenses.edit')}
                                    </Link>
                                  </DropdownMenuItem>
                                )}
                                {canDeleteExpense(e) && (
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
                                        <AlertDialogCancel>{t('expenses.cancel')}</AlertDialogCancel>
                                        <AlertDialogAction onClick={() => handleDelete(e.id)}>{t('expenses.delete')}</AlertDialogAction>
                                      </AlertDialogFooter>
                                    </AlertDialogContent>
                                  </AlertDialog>
                                )}
                              </DropdownMenuContent>
                            </DropdownMenu>
                          )}
                        </TableCell>
                      </TableRow>
                    ))
                  ) : (
                    <TableRow>
                      <TableCell colSpan={14} className="h-auto p-0 border-none">
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
        </ProfessionalCard>

        <Dialog open={isCreateOpen} onOpenChange={setIsCreateOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>{t('expenses.new_title')}</DialogTitle>
            </DialogHeader>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 p-4">
              <div>
                <label className="text-sm">{t('expenses.labels.amount')}</label>
                <Input
                  type="number"
                  value={Number(newExpense.amount || 0)}
                  onChange={e => setNewExpense({ ...newExpense, amount: Number(e.target.value) })}
                  disabled={isNewInventoryConsumption}
                  placeholder={isNewInventoryConsumption ? t('expenses.calculated_from_items') : ""}
                />
              </div>
              <div>
                <label className="text-sm">{t('expenses.labels.currency')}</label>
                <CurrencySelector
                  value={newExpense.currency || 'USD'}
                  onValueChange={(v) => setNewExpense({ ...newExpense, currency: v })}
                  placeholder={t('expenses.select_currency')}
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
                <label className="text-sm">{t('expenses.receipt_time', { defaultValue: 'Receipt Time (HH:MM)' })}</label>
                <Input
                  type="time"
                  value={newExpense.receipt_timestamp ? new Date(newExpense.receipt_timestamp as string).toISOString().substring(11, 16) : ''}
                  onChange={(e) => {
                    if (e.target.value && newExpense.expense_date) {
                      // Combine date with time
                      const timestamp = `${newExpense.expense_date}T${e.target.value}:00Z`;
                      setNewExpense({
                        ...newExpense,
                        receipt_timestamp: timestamp,
                        receipt_time_extracted: true
                      });
                    } else {
                      setNewExpense({
                        ...newExpense,
                        receipt_timestamp: null,
                        receipt_time_extracted: false
                      });
                    }
                  }}
                  placeholder="14:30"
                />
              </div>
              <div>
                <label className="text-sm">{t('expenses.link_to_invoice')}</label>
                <Select value={newExpense.invoice_id ? String(newExpense.invoice_id) : undefined} onValueChange={v => setNewExpense({ ...newExpense, invoice_id: v === 'none' ? undefined : Number(v) })}>
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder={t('expenses.select_invoice')} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">{t('expenses.none')}</SelectItem>
                    {invoiceOptions.map(inv => (
                      <SelectItem key={inv.id} value={String(inv.id)}>{inv.number} — {inv.client_name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <label className="text-sm">{t('expenses.labels.category')}</label>
                <Select
                  value={(newExpense.category as string) || 'General'}
                  onValueChange={(v) => setNewExpense({ ...newExpense, category: v })}
                >
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder={t('expenses.select_category') as string} />
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

              {/* Inventory Consumption Section */}
              <div className="sm:col-span-2">
                <div className="space-y-3 p-4 border rounded-lg bg-gray-50">
                  <div className="flex items-center gap-2">
                    <Package className="h-4 w-4" />
                    <span className="text-sm font-medium">{t('expenses.inventory_integration')}</span>
                  </div>

                  <div className="flex items-center space-x-2">
                    <Checkbox
                      id="is-new-inventory-consumption"
                      checked={isNewInventoryConsumption}
                      onCheckedChange={(checked) => setIsNewInventoryConsumption(checked as boolean)}
                    />
                    <label
                      htmlFor="is-new-inventory-consumption"
                      className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
                    >
                      {t('expenses.this_expense_is_for_consuming_inventory_items')}
                    </label>
                  </div>

                  {isNewInventoryConsumption && (
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
                          onConsumptionItemsChange={setNewConsumptionItems}
                          currency={newExpense.currency || 'USD'}
                        />
                      </div>

                      {newConsumptionItems.length > 0 && (
                        <div className="bg-green-50 border border-green-200 rounded-lg p-3">
                          <div className="flex items-center gap-2 text-green-800">
                            <Package className="h-4 w-4" />
                            <span className="text-sm font-medium">
                              {t('expenses.ready_to_process', { count: newConsumptionItems.length })}
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
                <Input value={newExpense.notes || ''} onChange={e => setNewExpense({ ...newExpense, notes: e.target.value })} />
              </div>
              <div className="sm:col-span-2">
                <label className="text-sm">{t('expenses.labels.receipt')}</label>
                {!hasAIExpenseFeature && (
                  <Alert className="mb-3 border-amber-200 bg-amber-50">
                    <AlertCircle className="h-4 w-4 text-amber-600" />
                    <AlertDescription className="text-amber-800 text-sm">
                      <strong>Note:</strong> AI-powered receipt analysis is not available.
                      Files will be uploaded as attachments only, without automatic data extraction.
                    </AlertDescription>
                  </Alert>
                )}
                <input
                  type="file"
                  accept="application/pdf,image/jpeg,image/png"
                  onChange={(ev) => setNewReceiptFile(ev.target.files?.[0] || null)}
                />
              </div>

              {/* Approval Workflow Section */}
              <div className="sm:col-span-2 border-t pt-4 mt-4">
                <h4 className="text-sm font-medium mb-3">{t('expenses.approval_workflow')}</h4>
                <div className="flex items-center space-x-2 mb-2">
                  <Checkbox
                    id="submit-new-for-approval"
                    checked={submitNewForApproval}
                    onCheckedChange={(checked) => setSubmitNewForApproval(checked as boolean)}
                  />
                  <label
                    htmlFor="submit-new-for-approval"
                    className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
                  >
                    {t('expenses.submit_this_expense_for_approval_after_creation')}
                  </label>
                </div>
                {submitNewForApproval && (
                  <div className="mt-3 space-y-3">
                    {approvalsNotLicensed ? (
                      <Alert className="border-amber-200 bg-amber-50">
                        <AlertCircle className="h-4 w-4 text-amber-600" />
                        <AlertDescription className="text-amber-800">
                          {t('common.feature_not_licensed', {
                            defaultValue: 'Approval workflows require a commercial license. Please upgrade your license to use this feature.'
                          })}
                        </AlertDescription>
                      </Alert>
                    ) : (
                      <>
                        <div className="p-3 bg-blue-50 dark:bg-blue-950/50 border border-blue-200 dark:border-blue-800/50 rounded-lg">
                          <p className="text-sm text-blue-700 dark:text-blue-200">
                            {t('expenses.this_expense_will_be_submitted_for_approval')}
                          </p>
                        </div>

                        <div className="space-y-2">
                          <Label htmlFor="new-approver-select" className="flex items-center gap-2 text-sm font-medium">
                            <Users className="h-4 w-4" />
                            {t('expenses.select_approver')} *
                          </Label>
                          <Select value={selectedNewApproverId} onValueChange={setSelectedNewApproverId}>
                            <SelectTrigger>
                              <SelectValue placeholder={t('expenses.choose_an_approver')} />
                            </SelectTrigger>
                            <SelectContent>
                              {availableNewApprovers.map((approver) => (
                                <SelectItem key={approver.id} value={approver.id.toString()}>
                                  {approver.name} ({approver.email})
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </div>
                      </>
                    )}
                  </div>
                )}
              </div>
            </div>
            <div className="p-4 flex justify-end gap-2">
              <Button
                variant="outline"
                onClick={() => setIsCreateOpen(false)}
                disabled={creating}
              >
                {t('expenses.cancel')}
              </Button>
              <Button
                onClick={handleCreate}
                disabled={creating || (submitNewForApproval && !selectedNewApproverId)}
                className={creating ? 'opacity-50 cursor-not-allowed pointer-events-none' : ''}
              >
                {creating ? t('common.saving') : (submitNewForApproval ? t('expenses.create_and_submit_for_approval') : t('expenses.buttons.create'))}
              </Button>
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
                      <strong>Note:</strong> AI-powered receipt analysis is not available.
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
                        {att.size_bytes ? <span className="ml-2 text-xs text-muted-foreground">({Math.round(att.size_bytes / 1024)} KB)</span> : null}
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
    </AppLayout>
  );
};

export default Expenses;
