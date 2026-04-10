import { useEffect, useState, useRef, useCallback, useMemo } from 'react';
import { useLocation, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '@/components/ui/alert-dialog';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { RotateCcw, Trash2, ChevronDown, ChevronUp, Plus, X, ArrowLeft } from 'lucide-react';
import JSZip from 'jszip';
import { toast } from 'sonner';
import {
  bankStatementApi, BankTransactionEntry, BankStatementDetail, BankStatementSummary,
  expenseApi, clientApi, DeletedBankStatement, settingsApi
} from '@/lib/api';
import { TransactionLinkInfo } from '@/lib/api/bank-statements';
import { LinkTransferModal } from '@/components/statements/LinkTransferModal';
import { InvoiceForm } from '@/components/invoices/InvoiceForm';
import { useFeatures } from '@/contexts/FeatureContext';
import { ProfessionalCard } from '@/components/ui/professional-card';
import { ProfessionalButton } from '@/components/ui/professional-button';
import { LicenseAlert } from '@/components/ui/license-alert';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { ReviewDiffModal } from '@/components/ReviewDiffModal';
import { usePageContext } from '@/contexts/PageContext';
import { useColumnVisibility } from '@/hooks/useColumnVisibility';

import { BankRow, STATEMENT_COLUMNS, formatDateToISO } from './types';
import { StatementUploadButton } from './StatementUploadButton';
import { RecycleBinSection } from './RecycleBinSection';
import { StatementsListView } from './StatementsListView';
import { StatementDetailView } from './StatementDetailView';
import { UploadModal } from './UploadModal';
import { DuplicateTransactionPanel } from './DuplicateTransactionPanel';

export default function Statements() {
  const { t } = useTranslation();
  const { isFeatureEnabled } = useFeatures();
  const { isVisible, toggle, reset, hiddenCount } = useColumnVisibility('statements', STATEMENT_COLUMNS);
  const queryClient = useQueryClient();
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
  const [unlinkModalOpen, setUnlinkModalOpen] = useState(false);
  const [rowToUnlink, setRowToUnlink] = useState<number | null>(null);
  const [highlightedBackendId, setHighlightedBackendId] = useState<number | null>(null);
  const highlightTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const readOnly = detail?.status === 'processing' || detail?.status === 'merged';

  // Selection and filtering
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [statusFilter, setStatusFilter] = useState('all');
  const [labelFilter, setLabelFilter] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [bulkLabel, setBulkLabel] = useState('');
  const [bulkDeleteModalOpen, setBulkDeleteModalOpen] = useState(false);
  const [bulkMergeModalOpen, setBulkMergeModalOpen] = useState(false);
  const [deleteTransactionModalOpen, setDeleteTransactionModalOpen] = useState(false);
  const [transactionToDelete, setTransactionToDelete] = useState<{ idx: number; backendId: number } | null>(null);

  // Review Mode State
  const [reviewModalOpen, setReviewModalOpen] = useState(false);
  const [selectedReviewStatement, setSelectedReviewStatement] = useState<BankStatementSummary | null>(null);
  const [isAcceptingReview, setIsAcceptingReview] = useState(false);
  const [isRejectingReview, setIsRejectingReview] = useState(false);
  const [isRetriggeringReview, setIsRetriggeringReview] = useState(false);

  // Pagination
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [totalStatements, setTotalStatements] = useState(0);
  const [newLabelValueById, setNewLabelValueById] = useState<Record<number, string>>({});
  const [bankNameValueById, setBankNameValueById] = useState<Record<number, string>>({});

  // Recycle bin state
  const [showRecycleBin, setShowRecycleBin] = useState(false);
  const [deletedStatements, setDeletedStatements] = useState<DeletedBankStatement[]>([]);
  const [recycleBinLoading, setRecycleBinLoading] = useState(false);
  const prevDeletedCount = useRef<number>(0);
  const [emptyRecycleBinModalOpen, setEmptyRecycleBinModalOpen] = useState(false);
  const [recycleBinCurrentPage, setRecycleBinCurrentPage] = useState(1);
  const [recycleBinPageSize] = useState(10);
  const [recycleBinTotalCount, setRecycleBinTotalCount] = useState(0);

  const { data: settings } = useQuery({
    queryKey: ['settings'],
    queryFn: () => settingsApi.getSettings(),
    staleTime: 5 * 60 * 1000,
    refetchOnWindowFocus: false,
  });
  const timezone = settings?.timezone || 'UTC';

  const { data: txnDuplicateData } = useQuery({
    queryKey: ['duplicate-transactions'],
    queryFn: () => bankStatementApi.getDuplicateTransactionGroups(),
    staleTime: 2 * 60 * 1000,
    refetchOnWindowFocus: false,
    enabled: isFeatureEnabled('ai_bank_statement'),
  });
  const txnDuplicateCount = txnDuplicateData?.count ?? 0;

  const getLocale = useMemo(() => {
    const language = t('language', { defaultValue: 'en' });
    switch (language) {
      case 'es': return 'es-ES';
      case 'fr': return 'fr-FR';
      case 'de': return 'de-DE';
      default: return 'en-US';
    }
  }, [t]);

  useEffect(() => {
    if (location.pathname === '/statements' && !searchParams.get('id')) {
      setSelected(null);
      setDetail(null);
      setRows([]);
      setIsSplitView(false);
    }
  }, [location.key, location.pathname]);

  useEffect(() => {
    return () => {
      if (splitViewPdfObjectUrl) URL.revokeObjectURL(splitViewPdfObjectUrl);
    };
  }, [splitViewPdfObjectUrl]);

  useEffect(() => {
    let active = true;
    const updateSplitViewPdf = async () => {
      if (!isSplitView || !selected) return;
      try {
        setDetailLoading(true);
        const { blob } = await bankStatementApi.fetchFileBlob(selected, true);
        if (!active) return;
        const objectUrl = URL.createObjectURL(blob);
        setSplitViewPdfObjectUrl(prev => { if (prev) URL.revokeObjectURL(prev); return objectUrl; });
        setSplitViewPdfUrl(objectUrl);
      } catch (e: any) {
        if (active) console.error('Failed to update parallel view PDF:', e);
      } finally {
        if (active) setDetailLoading(false);
      }
    };
    updateSplitViewPdf();
    return () => { active = false; };
  }, [selected, isSplitView]);

  const toggleSplitView = () => setIsSplitView(prev => !prev);

  useEffect(() => {
    if (!selected || !detail) {
      setPageContext({ title: t('navigation.bank_statements', { defaultValue: 'Statements' }), entity: undefined, metadata: undefined });
      return;
    }
    setPageContext({
      title: t('navigation.bank_statements', { defaultValue: 'Statements' }),
      entity: { type: 'bank_statement', id: selected },
      metadata: { status: detail.status, labels: detail.labels || [], extracted_count: detail.extracted_count, original_filename: detail.original_filename }
    });
  }, [detail, selected, setPageContext, t]);

  useEffect(() => {
    const loadClients = async () => {
      try { await clientApi.getClients(); } catch (e) { console.error('Failed to load clients:', e); }
    };
    loadClients();
  }, []);

  // Review handlers
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
      loadList();
    } catch { toast.error(t('statements.review.accept_failed', { defaultValue: 'Failed to accept review' })); }
    finally { setIsAcceptingReview(false); }
  };

  const handleRejectReview = async () => {
    if (!selectedReviewStatement) return;
    try {
      setIsRejectingReview(true);
      await bankStatementApi.rejectReview(selectedReviewStatement.id);
      toast.success(t('statements.review.dismissed', { defaultValue: 'Review dismissed' }));
      setReviewModalOpen(false);
      loadList();
    } catch { toast.error(t('statements.review.dismiss_failed', { defaultValue: 'Failed to dismiss review' })); }
    finally { setIsRejectingReview(false); }
  };

  const handleRetriggerReview = async () => {
    if (!selectedReviewStatement) return;
    try {
      setIsRetriggeringReview(true);
      await bankStatementApi.reReview(selectedReviewStatement.id);
      toast.success(t('statements.review.retriggered', { defaultValue: 'Review re-triggered' }));
      setReviewModalOpen(false);
      loadList();
    } catch { toast.error(t('statements.review.retrigger_failed', { defaultValue: 'Failed to re-trigger review' })); }
    finally { setIsRetriggeringReview(false); }
  };

  const handleRunReview = async (statementId: number) => {
    try {
      await bankStatementApi.reReview(statementId);
      toast.success(t('statements.review.triggered', { defaultValue: 'Review triggered. The agent will process it shortly.' }));
      loadList();
    } catch (error: any) {
      toast.error(error?.message || t('statements.review.trigger_failed', { defaultValue: 'Failed to trigger review' }));
    }
  };

  const handleCancelReview = async (statementId: number) => {
    try {
      await bankStatementApi.cancelReview(statementId);
      toast.success(t('statements.review.cancelled', { defaultValue: 'Review cancelled.' }));
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
    } finally { setLoading(false); }
  };

  // Data loading
  const loadList = useCallback(async () => {
    try {
      const skip = (page - 1) * pageSize;
      const status = statusFilter !== 'all' ? statusFilter : undefined;
      const data = await bankStatementApi.list(skip, pageSize, labelFilter || undefined, searchQuery || undefined, status);
      setStatements(data.statements);
      setTotalStatements(data.total);
      const processingIds = data.statements.filter(s => s.status === 'processing' || s.status === 'uploaded').map(s => s.id);
      if (processingIds.length > 0) {
        const startPolling = (window as any).startStatementPolling;
        if (typeof startPolling === 'function') startPolling(processingIds);
      }
    } catch (e: any) {
      toast.error(e?.message || t('statements.load_failed', { defaultValue: 'Failed to load statements' }));
    }
  }, [statusFilter, labelFilter, searchQuery, page, pageSize]);

  useEffect(() => { loadList(); }, [statusFilter, labelFilter, searchQuery, page, pageSize]);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const idParam = params.get('id');
    const txnParam = params.get('txn');
    if (idParam) {
      const id = parseInt(idParam, 10);
      const txnId = txnParam ? parseInt(txnParam, 10) : undefined;
      if (!isNaN(id)) openStatement(id, !txnId || isNaN(txnId) ? undefined : txnId);
    }
  }, []);

  useEffect(() => {
    const handleRefresh = (e: any) => {
      loadList();
      if (selected && e?.detail?.id === selected) openStatement(selected);
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
    if (showRecycleBin) fetchDeletedStatements();
  }, [showRecycleBin, recycleBinCurrentPage]);

  const openStatement = async (id: number, highlightBackendId?: number) => {
    setSelected(id);
    if (searchParams.get('id') !== String(id)) setSearchParams({ id: String(id) }, { replace: true });
    setDetailLoading(true);
    setHighlightedBackendId(null);
    if (highlightTimerRef.current) clearTimeout(highlightTimerRef.current);
    try {
      const s = await bankStatementApi.get(id);
      setDetail(s);
      setStatementLabels(Array.isArray((s as any).labels) ? ((s as any).labels as string[]).slice(0, 10) : []);
      setStatementNotes(s.notes || '');
      const transactionsWithIds = (s.transactions || []).map((t: BankTransactionEntry, index: number) => ({
        id: index + 1,
        date: t.date,
        description: t.description,
        amount: t.amount,
        transaction_type: (t.transaction_type === 'debit' || t.transaction_type === 'credit') ? t.transaction_type : (t.amount < 0 ? 'debit' : 'credit'),
        balance: t.balance ?? null,
        category: t.category ?? null,
        notes: (t as any).notes ?? null,
        invoice_id: (t as any).invoice_id ?? null,
        expense_id: (t as any).expense_id ?? null,
        linked_transfer: (t as any).linked_transfer ?? null,
        backend_id: (t as any).id,
      }));
      setRows(transactionsWithIds);
      if (highlightBackendId) {
        setHighlightedBackendId(highlightBackendId);
        highlightTimerRef.current = setTimeout(() => setHighlightedBackendId(null), 3000);
      }
    } catch (e: any) {
      toast.error(e?.message || t('statements.detail_load_failed', { defaultValue: 'Failed to load statement' }));
      setSelected(null);
    } finally { setDetailLoading(false); }
  };

  const addFiles = useCallback((newFiles: File[]) => {
    setFiles(prev => {
      const combined = [...prev, ...newFiles];
      if (combined.length > 12) {
        toast.warning(t('statements.max_files_warning', { defaultValue: 'Maximum 12 files allowed. Some files were ignored.' }));
        return combined.slice(0, 12);
      }
      return combined;
    });
  }, [t]);

  const onUpload = async () => {
    const addNotification = (window as any).addAINotification;
    try {
      if (files.length === 0) { toast.error(t('statements.select_files')); return; }
      setLoading(true);
      addNotification?.('processing', t('statements.processing'), `Analyzing ${files.length} statement files with AI...`);
      const resp = await bankStatementApi.uploadAndExtract(files, cardType);
      if (resp.statements && resp.statements.length > 0) {
        const startPolling = (window as any).startStatementPolling;
        if (typeof startPolling === 'function') startPolling(resp.statements.map((s: any) => s.id));
      }
      addNotification?.('success', t('statements.upload'), `Successfully uploaded ${files.length} statement files.`);
      resp.statements
        .filter((s: any) => s.duplicate_of)
        .forEach((s: any) => {
          toast.warning(
            `"${s.original_filename}" may be a duplicate of statement #${s.duplicate_of.id} uploaded on ${
              s.duplicate_of.created_at ? new Date(s.duplicate_of.created_at).toLocaleDateString() : 'a previous date'
            }.`,
            { duration: 8000 }
          );
        });
      toast.success(`Uploaded ${files.length} ${t('statements.statements').toLowerCase()}`);
      setFiles([]);
      setUploadModalOpen(false);
      await loadList();
    } catch (e: any) {
      addNotification?.('error', t('statements.failed_to_delete'), `Failed to process statements: ${e?.message || 'Unknown error'}`);
      toast.error(e?.message || t('statements.extract_failed', { defaultValue: 'Failed to extract transactions' }));
    } finally { setLoading(false); }
  };

  const addEmptyRow = () => {
    const today = new Date();
    const iso = formatDateToISO(today);
    setRows(prev => {
      const newRowsWithoutIds = [{ date: iso, description: '', amount: 0, transaction_type: 'debit' as 'debit', balance: null, category: 'Other', backend_id: null }, ...prev];
      const newRowsWithIds = newRowsWithoutIds.map((row, index) => ({ ...row, id: index + 1 }));
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
        id: (r as any).backend_id || undefined,
        balance: r.balance === undefined ? null : r.balance,
        category: r.category || null,
        notes: (r as any).notes || null,
        invoice_id: r.invoice_id ?? null,
        expense_id: r.expense_id ?? null,
      }));
      await bankStatementApi.replaceTransactions(selected, cleaned);
      toast.success(t('statements.transactions_saved', { defaultValue: 'Transactions saved' }));
      await openStatement(selected);
      await loadList();
    } catch (e: any) {
      toast.error(e?.message || t('statements.save_transactions_failed', { defaultValue: 'Failed to save transactions' }));
    } finally { setDetailLoading(false); }
  };

  const saveMeta = async () => {
    if (!selected) return;
    try {
      setDetailLoading(true);
      const updates = { labels: (statementLabels || []).filter((x) => (x || '').trim()).slice(0, 10), notes: statementNotes || null };
      const resp = await bankStatementApi.updateMeta(selected, updates);
      setDetail(prev => prev ? { ...prev, notes: resp.statement.notes || null, labels: (resp.statement as any).labels || [] } : prev);
      await loadList();
      toast.success(t('statements.update_success', { defaultValue: 'Statement updated' }));
    } catch (e: any) {
      toast.error(e?.message || t('statements.update_failed', { defaultValue: 'Failed to update statement' }));
    } finally { setDetailLoading(false); }
  };

  const confirmDeleteStatement = async () => {
    if (!statementToDelete) return;
    try {
      await bankStatementApi.delete(statementToDelete);
      toast.success(t('statements.statement_deleted'));
      await loadList();
      queryClient.invalidateQueries({ queryKey: ['duplicate-transactions'] });
      if (showRecycleBin) fetchDeletedStatements();
      if (selected === statementToDelete) {
        setSelected(null); setDetail(null); setRows([]);
        setSearchParams({}, { replace: true });
      }
    } catch (e: any) {
      toast.error(e?.message || t('statements.failed_to_delete'));
    } finally { setDeleteModalOpen(false); setStatementToDelete(null); }
  };

  const handleBulkDelete = async () => {
    setLoading(true);
    try {
      for (const id of selectedIds) await bankStatementApi.delete(id);
      toast.success(t('statements.bulk_delete_success', { count: selectedIds.length, defaultValue: 'Statements deleted successfully' }));
      await loadList();
      queryClient.invalidateQueries({ queryKey: ['duplicate-transactions'] });
      if (showRecycleBin) { setRecycleBinCurrentPage(1); await fetchDeletedStatements(); }
      setSelectedIds([]); setBulkDeleteModalOpen(false);
    } catch (e: any) {
      toast.error(e?.message || t('statements.delete_failed', { defaultValue: 'Failed to delete statements' }));
    } finally { setLoading(false); }
  };

  const handleBulkMerge = async () => {
    setLoading(true);
    try {
      const resp = await bankStatementApi.merge(selectedIds);
      toast.success(resp.message || t('statements.merge_success', { defaultValue: 'Statements merged successfully' }));
      await loadList();
      queryClient.invalidateQueries({ queryKey: ['duplicate-transactions'] });
      setSelectedIds([]); setBulkMergeModalOpen(false);
      if (resp.id) openStatement(resp.id);
    } catch (e: any) {
      toast.error(e?.message || t('statements.merge_failed', { defaultValue: 'Failed to merge statements' }));
    } finally { setLoading(false); }
  };

  const fetchDeletedStatements = async () => {
    try {
      setRecycleBinLoading(true);
      const skip = (recycleBinCurrentPage - 1) * recycleBinPageSize;
      const response = await bankStatementApi.getDeletedStatements(skip, recycleBinPageSize);
      setDeletedStatements(response.items);
      setRecycleBinTotalCount(response.total);
    } catch { toast.error(t('recycleBin.load_failed', { defaultValue: 'Failed to load recycle bin' })); }
    finally { setRecycleBinLoading(false); }
  };

  const handleRestoreStatement = async (statementId: number) => {
    try {
      await bankStatementApi.restoreStatement(statementId, 'processed');
      toast.success(t('statements.restore_success', { defaultValue: 'Statement restored successfully' }));
      fetchDeletedStatements(); loadList();
    } catch (error: any) {
      toast.error(error?.message || t('statements.restore_failed', { defaultValue: 'Failed to restore statement' }));
    }
  };

  const handlePermanentlyDeleteStatement = async (statementId: number) => {
    try {
      await bankStatementApi.permanentlyDeleteStatement(statementId);
      toast.success(t('statements.permanent_delete_success', { defaultValue: 'Statement permanently deleted' }));
      fetchDeletedStatements();
    } catch (error: any) {
      toast.error(error?.message || t('statements.permanent_delete_failed', { defaultValue: 'Failed to permanently delete statement' }));
    }
  };

  const handleEmptyRecycleBin = () => setEmptyRecycleBinModalOpen(true);

  const confirmEmptyRecycleBin = async () => {
    const addNotification = (window as any).addAINotification;
    try {
      const response = await bankStatementApi.emptyRecycleBin() as { message: string; deleted_count: number; status?: string };
      toast.success(response.message || t('statementRecycleBin.deletion_initiated', { count: response.deleted_count }));
      if (addNotification && response.status === 'processing') {
        addNotification('info', t('statementRecycleBin.deletion_title'), t('statementRecycleBin.deletion_processing', { count: response.deleted_count }));
        setTimeout(() => {
          addNotification('success', t('statementRecycleBin.deletion_completed_title'), t('statementRecycleBin.deletion_completed', { count: response.deleted_count }));
          fetchDeletedStatements();
        }, 2000);
      } else { fetchDeletedStatements(); }
      setEmptyRecycleBinModalOpen(false);
    } catch (error: any) {
      toast.error(error?.message || t('statementRecycleBin.failed_to_empty_recycle_bin'));
    }
  };

  const handleToggleRecycleBin = () => {
    const willShow = !showRecycleBin;
    setShowRecycleBin(willShow);
    if (willShow) { setRecycleBinCurrentPage(1); fetchDeletedStatements(); }
  };

  const handlePreview = async (id: number) => {
    try {
      setPreviewLoading(id);
      const { blob, contentType } = await bankStatementApi.fetchFileBlob(id, true);
      const type = contentType || blob.type || 'application/pdf';
      setPreviewType(type);
      if (previewObjectUrl) URL.revokeObjectURL(previewObjectUrl);
      if (type.includes('text/csv')) {
        const text = await blob.text();
        setPreviewText(text); setPreviewUrl(null); setPreviewObjectUrl(null);
      } else {
        const objectUrl = URL.createObjectURL(blob);
        setPreviewObjectUrl(objectUrl); setPreviewUrl(objectUrl); setPreviewText(null);
      }
      setPreviewOpen(true);
    } catch (e: any) {
      toast.error(e?.message || t('statements.failed_to_preview'));
    } finally { setPreviewLoading(null); }
  };

  const handleDownload = async (id: number, defaultName?: string) => {
    try {
      const { blob, filename } = await bankStatementApi.fetchFileBlob(id, false);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = filename || defaultName || `statement-${id}.pdf`;
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e: any) { toast.error(e?.message || t('statements.failed_to_download')); }
  };

  const exportToCSV = () => {
    if (rows.length === 0) { toast.error(t('statements.export.no_transactions', { defaultValue: 'No transactions to export' })); return; }
    const headers = ['Date', 'Description', 'Amount', 'Type', 'Balance', 'Category', 'Notes', 'Reference'];
    let csvContent = [
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
        return [row.date, `"${row.description.replace(/"/g, '""')}"`, row.amount, row.transaction_type, row.balance ?? '', row.category ?? '', `"${((row as any).notes || '').replace(/"/g, '""')}"`, refs.join('; ')].join(',');
      })
    ].join('\n');
    if (statementNotes) csvContent += `\n\n"Notes: ${statementNotes.replace(/"/g, '""')}"`;
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    link.setAttribute('href', url);
    link.setAttribute('download', `transactions-${detail?.original_filename?.replace('.pdf', '') || 'export'}.csv`);
    link.style.visibility = 'hidden';
    document.body.appendChild(link); link.click(); document.body.removeChild(link);
    URL.revokeObjectURL(url);
    toast.success(t('statements.export.csv_success', { defaultValue: 'CSV exported successfully' }));
  };

  const exportSelectedAsZip = async () => {
    if (selectedIds.length === 0) return;
    setLoading(true);
    try {
      const zip = new JSZip();
      const details = await Promise.all(selectedIds.map(id => bankStatementApi.get(id)));
      for (const s of details) {
        const txns = s.transactions ?? [];
        const headers = ['Date', 'Description', 'Amount', 'Type', 'Balance', 'Category', 'Notes', 'Reference'];
        let csvContent = [
          headers.join(','),
          ...txns.map(row => {
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
            return [row.date, `"${row.description.replace(/"/g, '""')}"`, row.amount, row.transaction_type, row.balance ?? '', row.category ?? '', `"${((row as any).notes || '').replace(/"/g, '""')}"`, refs.join('; ')].join(',');
          })
        ].join('\n');
        if (s.notes) csvContent += `\n\n"Notes: ${s.notes.replace(/"/g, '""')}"`;
        const safeName = (s.original_filename || `statement-${s.id}`).replace(/\.pdf$/i, '');
        zip.file(`${safeName}.csv`, csvContent);
      }
      const blob = await zip.generateAsync({ type: 'blob' });
      const link = document.createElement('a');
      link.href = URL.createObjectURL(blob);
      link.download = `statements-export-${new Date().toISOString().slice(0, 10)}.zip`;
      document.body.appendChild(link); link.click(); document.body.removeChild(link);
      URL.revokeObjectURL(link.href);
      toast.success(`${selectedIds.length} CSV file${selectedIds.length !== 1 ? 's' : ''} exported as ZIP`);
    } catch (e: any) { toast.error(e?.message || 'Failed to export ZIP'); }
    finally { setLoading(false); }
  };

  const createExpenseFromTransaction = async (rowIndex: number) => {
    const transaction = rows[rowIndex];
    if (transaction.transaction_type !== 'debit') { toast.error(t('statements.expense.create_only_debit', { defaultValue: 'Can only create expenses from debit transactions' })); return; }
    if ((transaction as any).expense_id) { toast.error(t('statements.expense.already_created', { defaultValue: 'An expense has already been created for this transaction' })); return; }
    try {
      const categoryMap: Record<string, string> = { 'Transportation': 'Transportation', 'Food': 'Meals', 'Travel': 'Travel', 'Other': 'General' };
      const expenseCategory = categoryMap[transaction.category || 'Other'] || 'General';
      const expenseData = { amount: Math.abs(transaction.amount), expense_date: transaction.date, category: expenseCategory, vendor: transaction.description, notes: `Created from bank statement: ${detail?.original_filename}`, payment_method: 'Bank Transfer', status: 'recorded', analysis_status: 'done' };
      const created = await expenseApi.createExpense(expenseData as any);
      toast.success(t('statements.expense.create_success', { defaultValue: 'Expense created successfully' }));
      setRows(prev => prev.map((r, i) => i === rowIndex ? { ...r, expense_id: created.id } : r));
      const backendId = (transaction as any).backend_id;
      if (selected && backendId) {
        try {
          await bankStatementApi.patchTransaction(selected, backendId, { expense_id: created.id });
          await openStatement(selected);
        } catch (linkErr: any) { console.error('Failed to persist expense link:', linkErr); }
      }
    } catch (e: any) { toast.error(e?.message || t('statements.expense.create_failed', { defaultValue: 'Failed to create expense' })); }
  };

  const createInvoiceFromTransaction = (rowIndex: number) => {
    const transaction = rows[rowIndex];
    if (transaction.transaction_type !== 'credit') { toast.error(t('statements.invoice.create_only_credit', { defaultValue: 'Can only create invoices from credit transactions' })); return; }
    if ((transaction as any).invoice_id) { toast.error(t('statements.invoice.already_created', { defaultValue: 'An invoice has already been created for this transaction' })); return; }
    const [y, m, d] = transaction.date.split('-').map(n => parseInt(n, 10));
    const utcMidnightMs = Date.UTC(y, (m || 1) - 1, d || 1);
    const transactionDate = new Date(utcMidnightMs);
    const dueDateLocal = new Date(utcMidnightMs);
    dueDateLocal.setUTCDate(dueDateLocal.getUTCDate() + 30);
    setInvoiceInitialData({
      date: transactionDate, dueDate: dueDateLocal, status: 'paid',
      paidAmount: transaction.amount,
      notes: `Created from bank statement: ${detail?.original_filename}`,
      items: [{ description: transaction.description, quantity: 1, price: transaction.amount }],
      client: '', bank_transaction_id: (transaction as any).id || undefined,
    });
    setShowInvoiceForm(true);
  };

  const closeLinkTransferModal = () => {
    setLinkTransferModalOpen(false);
    setTimeout(() => { setLinkTransferModalMounted(false); setLinkingRowIdx(null); }, 300);
  };

  const handleTransactionLinked = (rowIdx: number, link: TransactionLinkInfo) => {
    setRows(prev => prev.map((r, i) => i === rowIdx ? { ...r, linked_transfer: link } : r));
    closeLinkTransferModal();
    if (selected) { const id = selected; setTimeout(() => openStatement(id), 350); }
  };

  const confirmUnlinkTransfer = async () => {
    if (rowToUnlink === null) return;
    const row = rows[rowToUnlink];
    const linkId = row.linked_transfer?.id;
    if (!linkId) return;
    try {
      await bankStatementApi.deleteTransactionLink(linkId);
      toast.success('Transfer link removed');
      queryClient.invalidateQueries({ queryKey: ['duplicate-transactions'] });
      if (selected) await openStatement(selected);
    } catch (e: any) { toast.error(e?.message || 'Failed to remove transfer link'); }
    finally { setUnlinkModalOpen(false); setRowToUnlink(null); }
  };

  const handleBack = () => {
    setSelected(null); setDetail(null); setRows([]);
    setIsSplitView(false);
    setSearchParams({}, { replace: true });
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

        {/* Hero Header - list view */}
        {!selected && (
          <div className="bg-gradient-to-r from-primary/10 via-primary/5 to-transparent rounded-2xl border border-primary/20 p-8 backdrop-blur-sm">
            <div className="flex items-center justify-between gap-6">
              <div className="space-y-2">
                <h1 className="text-4xl font-bold tracking-tight">{t('navigation.bank_statements')}</h1>
                <p className="text-lg text-muted-foreground">{t('statements.description')}</p>
              </div>
              <div className="flex gap-3 items-center flex-wrap justify-end">
                <ProfessionalButton variant="outline" size="default" onClick={() => { loadList(); queryClient.invalidateQueries({ queryKey: ['duplicate-transactions'] }); }} className="whitespace-nowrap" disabled={loading}>
                  <RotateCcw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
                  {t('common.refresh', { defaultValue: 'Refresh' })}
                </ProfessionalButton>
                <ProfessionalButton variant="outline" size="default" onClick={handleToggleRecycleBin} className="whitespace-nowrap">
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

        {/* Recycle Bin */}
        {!selected && showRecycleBin && (
          <RecycleBinSection
            showRecycleBin={showRecycleBin}
            setShowRecycleBin={setShowRecycleBin}
            deletedStatements={deletedStatements}
            recycleBinLoading={recycleBinLoading}
            recycleBinTotalCount={recycleBinTotalCount}
            recycleBinCurrentPage={recycleBinCurrentPage}
            recycleBinPageSize={recycleBinPageSize}
            setRecycleBinCurrentPage={setRecycleBinCurrentPage}
            onRestore={handleRestoreStatement}
            onPermanentlyDelete={handlePermanentlyDeleteStatement}
            onEmptyRecycleBin={handleEmptyRecycleBin}
          />
        )}

        {/* Duplicate transaction warning banner — expandable */}
        {!selected && txnDuplicateCount > 0 && (
          <DuplicateTransactionPanel
            groups={txnDuplicateData?.duplicate_groups ?? []}
            onViewTransaction={openStatement}
          />
        )}

        {/* Statements List */}
        {!selected && (
          <StatementsListView
            searchQuery={searchQuery} setSearchQuery={setSearchQuery}
            statusFilter={statusFilter} setStatusFilter={setStatusFilter}
            labelFilter={labelFilter} setLabelFilter={setLabelFilter}
            pageSize={pageSize} setPageSize={setPageSize}
            page={page} setPage={setPage}
            isVisible={isVisible} toggle={toggle} reset={reset} hiddenCount={hiddenCount}
            statements={statements} setStatements={setStatements} loading={loading} totalStatements={totalStatements}
            selectedIds={selectedIds} setSelectedIds={setSelectedIds}
            bulkLabel={bulkLabel} setBulkLabel={setBulkLabel}
            newLabelValueById={newLabelValueById} setNewLabelValueById={setNewLabelValueById}
            bankNameValueById={bankNameValueById} setBankNameValueById={setBankNameValueById}
            handleReviewClick={handleReviewClick} handleRunReview={handleRunReview} handleCancelReview={handleCancelReview}
            handleBulkRunReview={handleBulkRunReview}
            exportSelectedAsZip={exportSelectedAsZip}
            setBulkDeleteModalOpen={setBulkDeleteModalOpen} setBulkMergeModalOpen={setBulkMergeModalOpen}
            openStatement={openStatement} handlePreview={handlePreview} handleDownload={handleDownload}
            setStatementToDelete={setStatementToDelete} setDeleteModalOpen={setDeleteModalOpen}
            reprocessingLocks={reprocessingLocks} setReprocessingLocks={setReprocessingLocks}
            previewLoading={previewLoading}
            shareStatementId={shareStatementId} setShareStatementId={setShareStatementId}
            getLocale={getLocale} timezone={timezone} loadList={loadList}
          />
        )}

        {/* Review Diff Modal */}
        {selectedReviewStatement && (
          <ReviewDiffModal
            isOpen={reviewModalOpen}
            onClose={() => setReviewModalOpen(false)}
            originalData={{
              filename: selectedReviewStatement.original_filename,
              extracted_count: selectedReviewStatement.extracted_count,
              formatted_extracted_count: selectedReviewStatement.extracted_count,
              transaction_count: selectedReviewStatement.extracted_count,
              status: selectedReviewStatement.status,
            }}
            reviewResult={{ ...(selectedReviewStatement.review_result || {}), transaction_count: selectedReviewStatement.review_result?.transactions?.length ?? 0 }}
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

        {/* Preview Dialog */}
        <Dialog open={previewOpen} onOpenChange={(open) => {
          setPreviewOpen(open);
          if (!open) {
            if (previewObjectUrl) URL.revokeObjectURL(previewObjectUrl);
            setPreviewObjectUrl(null); setPreviewUrl(null); setPreviewText(null); setPreviewType(null);
          }
        }}>
          <DialogContent className="max-w-5xl w-full h-[80vh] flex flex-col">
            <DialogHeader>
              <DialogTitle>{t('statements.preview_title')}</DialogTitle>
            </DialogHeader>
            <div className="w-full flex-1 min-h-0 mt-2">
              {previewText && (
                <div className="w-full h-full overflow-auto rounded-md border p-3 bg-muted/40 whitespace-pre text-xs font-mono">{previewText}</div>
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

        {/* Detail View */}
        {selected && !showInvoiceForm && (
          <StatementDetailView
            selected={selected}
            detail={detail}
            rows={rows} setRows={setRows}
            editingRow={editingRow} setEditingRow={setEditingRow}
            readOnly={readOnly}
            detailLoading={detailLoading}
            statementLabels={statementLabels} setStatementLabels={setStatementLabels}
            statementNotes={statementNotes} setStatementNotes={setStatementNotes}
            newStatementLabel={newStatementLabel} setNewStatementLabel={setNewStatementLabel}
            isSplitView={isSplitView} splitViewPdfUrl={splitViewPdfUrl}
            highlightedBackendId={highlightedBackendId}
            reprocessingLocks={reprocessingLocks} setReprocessingLocks={setReprocessingLocks}
            previewLoading={previewLoading}
            loading={loading}
            getLocale={getLocale} timezone={timezone}
            saveRows={saveRows} saveMeta={saveMeta} addEmptyRow={addEmptyRow} exportToCSV={exportToCSV}
            createExpenseFromTransaction={createExpenseFromTransaction}
            createInvoiceFromTransaction={createInvoiceFromTransaction}
            openStatement={openStatement} handlePreview={handlePreview} handleDownload={handleDownload}
            toggleSplitView={toggleSplitView} onBack={handleBack}
            setStatementToDelete={setStatementToDelete} setDeleteModalOpen={setDeleteModalOpen}
            setDeleteTransactionModalOpen={setDeleteTransactionModalOpen}
            setTransactionToDelete={setTransactionToDelete}
            setLinkingRowIdx={setLinkingRowIdx}
            setLinkTransferModalOpen={setLinkTransferModalOpen}
            setLinkTransferModalMounted={setLinkTransferModalMounted}
            setRowToUnlink={setRowToUnlink} setUnlinkModalOpen={setUnlinkModalOpen}
          />
        )}

        {/* Invoice Form Overlay */}
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
                  setShowInvoiceForm(false); setInvoiceInitialData(null);
                  toast.success(t('invoices.create_success', { defaultValue: 'Invoice created successfully!' }));
                  if (selected) await openStatement(selected);
                }}
              />
            </CardContent>
          </ProfessionalCard>
        )}

        {/* Upload Modal */}
        <UploadModal
          open={uploadModalOpen}
          onClose={() => { setUploadModalOpen(false); setFiles([]); setSelectedProvider('bank'); }}
          files={files}
          onAddFiles={addFiles}
          onRemoveFile={(index) => setFiles(prev => prev.filter((_, i) => i !== index))}
          selectedProvider={selectedProvider} setSelectedProvider={setSelectedProvider}
          cardType={cardType} setCardType={setCardType}
          dragActive={dragActive} setDragActive={setDragActive}
          loading={loading}
          onUpload={onUpload}
        />

        {/* Empty Recycle Bin Modal */}
        <AlertDialog open={emptyRecycleBinModalOpen} onOpenChange={setEmptyRecycleBinModalOpen}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>{t('statementRecycleBin.empty_recycle_bin_confirm_title', { defaultValue: 'Empty Recycle Bin' })}</AlertDialogTitle>
              <AlertDialogDescription>{t('statementRecycleBin.empty_recycle_bin_confirm_description', { defaultValue: 'Are you sure you want to permanently delete all statements in the recycle bin? This action cannot be undone.' })}</AlertDialogDescription>
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
              <AlertDialogDescription>{t('statements.delete_confirm_description')}</AlertDialogDescription>
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

        {/* Delete Transaction Modal */}
        <AlertDialog open={deleteTransactionModalOpen} onOpenChange={setDeleteTransactionModalOpen}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Delete Transaction</AlertDialogTitle>
              <AlertDialogDescription>Are you sure you want to delete this transaction? This action cannot be undone.</AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel onClick={() => setTransactionToDelete(null)}>{t('common.cancel', 'Cancel')}</AlertDialogCancel>
              <AlertDialogAction
                className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                onClick={async () => {
                  if (!transactionToDelete) return;
                  try {
                    await bankStatementApi.deleteTransaction(selected!, transactionToDelete.backendId);
                    setRows(prev => prev.filter((_, i) => i !== transactionToDelete.idx));
                    toast.success('Transaction deleted');
                  } catch (e: any) { toast.error(e?.message || 'Failed to delete transaction'); }
                  finally { setTransactionToDelete(null); setDeleteTransactionModalOpen(false); }
                }}
              >
                <Trash2 className="mr-2 h-4 w-4" />
                Delete
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>

        {/* Bulk Delete Modal */}
        <AlertDialog open={bulkDeleteModalOpen} onOpenChange={setBulkDeleteModalOpen}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>{t('statements.bulk_delete_confirm_title', { count: selectedIds.length, defaultValue: 'Delete Selected Statements' })}</AlertDialogTitle>
              <AlertDialogDescription>{t('statements.bulk_delete_confirm_description', { count: selectedIds.length, defaultValue: `Are you sure you want to delete ${selectedIds.length} statements? This action will move them to the recycle bin.` })}</AlertDialogDescription>
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
              <AlertDialogDescription>{t('statements.bulk_merge_confirm_description', { count: selectedIds.length, defaultValue: `Are you sure you want to merge ${selectedIds.length} statements?` })}</AlertDialogDescription>
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

        {/* Unlink Transfer Modal */}
        <AlertDialog open={unlinkModalOpen} onOpenChange={setUnlinkModalOpen}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Remove Transfer Link</AlertDialogTitle>
              <AlertDialogDescription>Are you sure you want to remove this transfer link? This will unlink the transaction from the other statement, but will not delete the transaction itself.</AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel onClick={() => setRowToUnlink(null)}>{t('common.cancel', 'Cancel')}</AlertDialogCancel>
              <AlertDialogAction onClick={confirmUnlinkTransfer} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">
                <X className="mr-2 h-4 w-4" />
                Unlink
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>

        {/* Link Transfer Modal */}
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
