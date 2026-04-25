import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { cn } from '@/lib/utils';
import { Link } from 'react-router-dom';
import { format } from 'date-fns';
import { Button } from '@/components/ui/button';
import { CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Calendar } from '@/components/ui/calendar';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { ContextMenu, ContextMenuContent, ContextMenuItem, ContextMenuTrigger, ContextMenuSeparator } from '@/components/ui/context-menu';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { ProfessionalCard } from '@/components/ui/professional-card';
import { ProfessionalButton } from '@/components/ui/professional-button';
import { CurrencyDisplay } from '@/components/ui/currency-display';
import {
  CalendarIcon, ArrowLeft, Eye, Download, Trash2, FileText, Plus, Copy, X, Edit,
  MoreHorizontal, Loader2, RotateCcw, Save, AlertCircle, Columns, ArrowLeftRight
} from 'lucide-react';
import { toast } from 'sonner';
import { bankStatementApi, expenseApi, invoiceApi, BankStatementDetail } from '@/lib/api';
import { BankRow, CATEGORY_OPTIONS, formatDateToISO, safeParseDateString } from './types';
import { CardTypeBadge } from './CardTypeBadge';
import { PdfHighlightViewer } from '@/components/pdf/PdfHighlightViewer';

interface StatementDetailViewProps {
  selected: number;
  detail: BankStatementDetail | null;
  rows: BankRow[];
  setRows: (fn: (prev: BankRow[]) => BankRow[]) => void;
  editingRow: number | null;
  setEditingRow: (idx: number | null) => void;
  readOnly: boolean;
  detailLoading: boolean;
  statementLabels: string[];
  setStatementLabels: (labels: string[]) => void;
  statementNotes: string;
  setStatementNotes: (v: string) => void;
  statementBankName: string;
  setStatementBankName: (v: string) => void;
  newStatementLabel: string;
  setNewStatementLabel: (v: string) => void;
  isSplitView: boolean;
  splitViewPdfUrl: string | null;
  highlightedBackendId: number | null;
  reprocessingLocks: Set<number>;
  setReprocessingLocks: (fn: (prev: Set<number>) => Set<number>) => void;
  previewLoading: number | null;
  loading: boolean;
  getLocale: string;
  timezone: string;
  // Handlers
  saveRows: () => void;
  saveMeta: () => void;
  addEmptyRow: () => void;
  exportToCSV: () => void;
  createExpenseFromTransaction: (idx: number) => void;
  createInvoiceFromTransaction: (idx: number) => void;
  openStatement: (id: number, highlightId?: number) => void;
  handlePreview: (id: number) => void;
  handleDownload: (id: number, filename?: string) => void;
  toggleSplitView: () => void;
  onBack: () => void;
  // Modal setters
  setStatementToDelete: (id: number) => void;
  setDeleteModalOpen: (v: boolean) => void;
  setDeleteTransactionModalOpen: (v: boolean) => void;
  setTransactionToDelete: (v: { idx: number; backendId: number } | null) => void;
  setLinkingRowIdx: (idx: number | null) => void;
  setLinkTransferModalOpen: (v: boolean) => void;
  setLinkTransferModalMounted: (v: boolean) => void;
  setRowToUnlink: (idx: number | null) => void;
  setUnlinkModalOpen: (v: boolean) => void;
}

export function StatementDetailView({
  selected, detail, rows, setRows,
  editingRow, setEditingRow,
  readOnly, detailLoading,
  statementLabels, setStatementLabels,
  statementNotes, setStatementNotes,
  statementBankName, setStatementBankName,
  newStatementLabel, setNewStatementLabel,
  isSplitView, splitViewPdfUrl,
  highlightedBackendId,
  reprocessingLocks, setReprocessingLocks,
  previewLoading, loading,
  getLocale, timezone,
  saveRows, saveMeta, addEmptyRow, exportToCSV,
  createExpenseFromTransaction, createInvoiceFromTransaction,
  openStatement, handlePreview, handleDownload, toggleSplitView, onBack,
  setStatementToDelete, setDeleteModalOpen,
  setDeleteTransactionModalOpen, setTransactionToDelete,
  setLinkingRowIdx, setLinkTransferModalOpen, setLinkTransferModalMounted,
  setRowToUnlink, setUnlinkModalOpen,
}: StatementDetailViewProps) {
  const { t } = useTranslation();
  const [hoveredRowIdx, setHoveredRowIdx] = useState<number | null>(null);

  // Derive search data from the hovered transaction
  const hoveredTransaction = hoveredRowIdx !== null ? rows[hoveredRowIdx] : null;

  const isCompleted = (s: { status?: string }) =>
    s.status === 'processed' || s.status === 'done' || s.status === 'failed' || s.status === 'uploaded' || s.status === 'merged';

  const totalIncome = rows.filter(r => r.transaction_type === 'credit').reduce((sum, r) => sum + r.amount, 0);
  const totalExpense = rows.filter(r => r.transaction_type === 'debit').reduce((sum, r) => sum + Math.abs(r.amount), 0);
  const netAmount = totalIncome - totalExpense;

  const copyToClipboard = async (value: string, successMsg: string) => {
    try {
      await navigator.clipboard.writeText(value);
      toast.success(successMsg);
    } catch {
      toast.error(t('common.copy_failed', { defaultValue: 'Failed to copy' }));
    }
  };

  return (
    <div className="space-y-6 overflow-visible">
      {/* Hero Header */}
      <div className="bg-gradient-to-r from-primary/10 via-primary/5 to-transparent rounded-2xl border border-primary/20 p-8 backdrop-blur-sm">
        <div className="flex items-center justify-between gap-6">
          <div className="space-y-2">
            <div className="flex items-center gap-3">
              <ProfessionalButton
                variant="outline"
                size="icon-sm"
                onClick={onBack}
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
              onClick={() => handlePreview(selected)}
              disabled={previewLoading === selected || detail?.status === 'merged'}
              leftIcon={previewLoading === selected ? <Loader2 className="h-4 w-4 animate-spin" /> : <Eye className="h-4 w-4" />}
            >
              {t('statements.preview')}
            </ProfessionalButton>

            <ProfessionalButton
              variant="outline"
              onClick={() => handleDownload(selected, detail?.original_filename)}
              disabled={detail?.status === 'merged'}
              leftIcon={<Download className="h-4 w-4" />}
            >
              {t('statements.download')}
            </ProfessionalButton>

            {detail && isCompleted(detail) && detail.status !== 'merged' && (
              <ProfessionalButton
                variant="outline"
                onClick={async () => {
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
                      setReprocessingLocks(prev => { const next = new Set(prev); next.delete(selected); return next; });
                    }, 30000);
                  } catch (e: any) {
                    setReprocessingLocks(prev => { const next = new Set(prev); next.delete(selected); return next; });
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
              className="text-destructive border-destructive/30 hover:bg-destructive/10"
              leftIcon={<Trash2 className="h-4 w-4" />}
              disabled={readOnly}
              onClick={() => { setStatementToDelete(selected); setDeleteModalOpen(true); }}
            >
              {t('common.delete', 'Delete')}
            </ProfessionalButton>

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

      <div className={cn("flex flex-col gap-6", isSplitView && "lg:flex-row lg:items-stretch")}>
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
                  <ProfessionalButton variant="ghost" size="icon-sm" onClick={toggleSplitView}>
                    <X className="h-4 w-4" />
                  </ProfessionalButton>
                </div>
                <div className="flex-1 min-h-0 bg-muted/10">
                  <PdfHighlightViewer
                    key={splitViewPdfUrl}
                    pdfUrl={splitViewPdfUrl}
                    searchText={hoveredTransaction?.description ?? null}
                    searchAmount={hoveredTransaction?.amount ?? null}
                    searchDate={hoveredTransaction?.date ?? null}
                  />
                </div>
                <div className="p-2 border-t text-[10px] text-muted-foreground bg-muted/30 text-center">
                  {t('statements.split_view_hint', 'Hover a transaction to highlight it in the PDF')}
                </div>
              </ProfessionalCard>
            </div>
          </div>
        )}

        {/* Transactions/Details Pane */}
        <div className={cn("space-y-6", isSplitView ? "lg:w-[55%] flex-1" : "w-full")}>

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

          {/* Receipt Detection Banner */}
          {detail?.is_possible_receipt && detail.status === 'processed' && (() => {
            const allConverted = rows.filter(r => r.transaction_type === 'debit').every(r => !!(r as any).expense_id);
            return (
              <div className={`border rounded-xl p-4 flex items-start gap-3 slide-in ${allConverted ? 'bg-green-500/10 border-green-500/30 text-green-800 dark:text-green-300' : 'bg-amber-500/10 border-amber-500/30 text-amber-800 dark:text-amber-300'}`}>
                <AlertCircle className="h-5 w-5 mt-0.5 flex-shrink-0" />
                <div className="flex-1 text-sm">
                  <span className="font-bold">
                    {allConverted
                      ? t('statements.receipt_converted_title', { defaultValue: 'Converted to expense' })
                      : t('statements.receipt_detected_title', { defaultValue: 'Looks like a receipt' })}
                  </span>
                  <span className="ml-1">
                    {allConverted
                      ? t('statements.receipt_converted_message', { defaultValue: 'This receipt has been saved as an expense.' })
                      : t('statements.receipt_detected_message', { defaultValue: 'AI detected this file may be a receipt, not a bank statement. Would you like to convert the transaction(s) to expenses?' })}
                  </span>
                </div>
                {!allConverted && (
                  <ProfessionalButton
                    variant="outline"
                    size="sm"
                    className="flex-shrink-0 border-amber-500/50 text-amber-800 dark:text-amber-300 hover:bg-amber-500/20"
                    onClick={async () => {
                      const debitIndices = rows
                        .map((r, i) => ({ r, i }))
                        .filter(({ r }) => r.transaction_type === 'debit' && !(r as any).expense_id)
                        .map(({ i }) => i);
                      for (const idx of debitIndices) {
                        await createExpenseFromTransaction(idx);
                      }
                    }}
                  >
                    <Plus className="h-4 w-4 mr-1" />
                    {t('statements.receipt_convert_all', { defaultValue: 'Convert to Expense' })}
                  </ProfessionalButton>
                )}
              </div>
            );
          })()}

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
                <div className="text-2xl font-black text-success"><CurrencyDisplay amount={totalIncome} currency="USD" /></div>
              </div>
            </ProfessionalCard>
            <ProfessionalCard variant="elevated" className="p-0 overflow-hidden border-none shadow-sm">
              <div className="p-5 flex flex-col items-center justify-center bg-background border-b-4 border-destructive/20">
                <span className="text-xs font-bold text-muted-foreground uppercase tracking-wider mb-1">{t('statements.total_expenses', { defaultValue: 'Total Expenses' })}</span>
                <div className="text-2xl font-black text-destructive"><CurrencyDisplay amount={totalExpense} currency="USD" /></div>
              </div>
            </ProfessionalCard>
            <ProfessionalCard variant="elevated" className="p-0 overflow-hidden border-none shadow-sm">
              <div className="p-5 flex flex-col items-center justify-center bg-background border-b-4 border-blue-500/20">
                <span className="text-xs font-bold text-muted-foreground uppercase tracking-wider mb-1">{t('statements.net_amount', { defaultValue: 'Net Amount' })}</span>
                <div className={`text-2xl font-black ${netAmount >= 0 ? 'text-success' : 'text-destructive'}`}><CurrencyDisplay amount={netAmount} currency="USD" /></div>
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
                <Input value={detail?.created_at ? new Date(detail.created_at).toLocaleString(getLocale, {
                  timeZone: timezone, year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
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
              <div>
                <label className="text-sm">{t('statements.bank_name', { defaultValue: 'Bank Name' })}</label>
                <Input
                  placeholder={t('statements.bank_name_placeholder', { defaultValue: 'Bank Name...' })}
                  value={statementBankName}
                  onChange={(e) => setStatementBankName(e.target.value)}
                  onBlur={saveMeta}
                  disabled={readOnly}
                />
              </div>
            </CardContent>
          </ProfessionalCard>

          {/* Labels & Notes */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Labels Card */}
            <ProfessionalCard className="lg:col-span-1">
              <CardHeader className="pb-3 border-b border-border/50 mb-4 px-0">
                <div className="flex items-center gap-2">
                  <FileText className="w-4 h-4 text-primary" />
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
                                  const resp = await bankStatementApi.updateMeta(selected, { labels: next });
                                  setStatementLabels((resp.statement as any).labels || []);
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
                    <FileText className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground group-focus-within:text-primary transition-colors" />
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
                            const next = [...existing, raw];
                            const resp = await bankStatementApi.updateMeta(selected, { labels: next });
                            setStatementLabels((resp.statement as any).labels || []);
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
                  onBlur={saveMeta}
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
                    <TableHead className="w-[180px] font-bold text-foreground">{t('statements.table_notes', { defaultValue: 'Notes' })}</TableHead>
                    <TableHead className="w-[120px] font-bold text-foreground text-center">{t('common.reference', { defaultValue: 'Reference' })}</TableHead>
                    <TableHead className="w-[80px] text-right font-bold text-foreground sticky right-0 bg-muted/30 z-10 shadow-[-4px_0_8px_-2px_hsl(var(--border)/0.5)]">{t('statements.table_actions', { defaultValue: 'Actions' })}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {rows.map((r, idx) => (
                    <ContextMenu key={idx}>
                      <ContextMenuTrigger asChild>
                        <TableRow
                          className={cn(
                            'hover:bg-muted/20 transition-colors border-b border-border/30 statement-row-hoverable',
                            (r as any).backend_id && (r as any).backend_id === highlightedBackendId && 'ring-2 ring-inset ring-blue-400 bg-blue-50/50 dark:bg-blue-950/20',
                            isSplitView && hoveredRowIdx === idx && 'is-hovered-for-pdf'
                          )}
                          onMouseEnter={isSplitView ? () => setHoveredRowIdx(idx) : undefined}
                          onMouseLeave={isSplitView ? () => setHoveredRowIdx(null) : undefined}
                        >
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
                              <Textarea
                                value={r.description}
                                onChange={(e) => setRows(prev => prev.map((x, i) => i === idx ? { ...x, description: e.target.value } : x))}
                                rows={2}
                                maxLength={500}
                                className="w-full border-border/50 bg-muted/20 focus:bg-background text-sm min-h-[60px]"
                              />
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
                              <span className="text-sm font-mono opacity-80">{r.balance !== null ? <CurrencyDisplay amount={r.balance!} currency="USD" /> : '-'}</span>
                            )}
                          </TableCell>
                          <TableCell>
                            {editingRow === idx ? (
                              <Select
                                value={r.transaction_type}
                                onValueChange={(v) => setRows(prev => prev.map((x, i) => i === idx ? { ...x, transaction_type: v as 'debit' | 'credit', amount: v !== x.transaction_type ? -x.amount : x.amount } : x))}
                              >
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
                          <TableCell>
                            {editingRow === idx ? (
                              <Input
                                value={(r as any).notes || ''}
                                onChange={(e) => setRows(prev => prev.map((x, i) => i === idx ? { ...x, notes: e.target.value } : x))}
                                className="h-9 border-border/50 bg-muted/20 w-full"
                                placeholder={t('statements.notes_placeholder', { defaultValue: 'Notes...' })}
                              />
                            ) : (
                              <span className="text-sm truncate max-w-[150px] inline-block" title={(r as any).notes || ''}>
                                {(r as any).notes || <span className="text-muted-foreground/50 italic">-</span>}
                              </span>
                            )}
                          </TableCell>
                          <TableCell className="text-center">
                            <div className="flex flex-col gap-1">
                              {Boolean((r as any).expense_id) && (
                                <Link to={`/expenses/view/${(r as any).expense_id}`}>
                                  <Badge className="bg-destructive/5 text-destructive border-destructive/20 border text-[10px] h-5 justify-center cursor-pointer hover:bg-destructive/10 transition-colors">
                                    EXP #{(r as any).expense_id}
                                  </Badge>
                                </Link>
                              )}
                              {Boolean((r as any).invoice_id) && (
                                <Link to={`/invoices/view/${(r as any).invoice_id}`}>
                                  <Badge className="bg-success/5 text-success border-success/20 border text-[10px] h-5 justify-center cursor-pointer hover:bg-success/10 transition-colors">
                                    INV #{(r as any).invoice_id}
                                  </Badge>
                                </Link>
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
                          <TableCell className="text-right sticky right-0 bg-background z-10 shadow-[-4px_0_8px_-2px_hsl(var(--border)/0.5)]">
                            <div className="flex items-center justify-end gap-2">
                              {editingRow === idx ? (
                                <ProfessionalButton
                                  size="sm"
                                  onClick={async () => { setEditingRow(null); await saveRows(); }}
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
                                      onSelect={() => {
                                        setTimeout(() => {
                                          setLinkingRowIdx(idx);
                                          setLinkTransferModalOpen(true);
                                          setLinkTransferModalMounted(true);
                                        }, 100);
                                      }}
                                      disabled={readOnly || Boolean((r as any).linked_transfer) || !(r as any).backend_id}
                                    >
                                      <ArrowLeftRight className="w-4 h-4 mr-2 text-blue-500" />
                                      {Boolean((r as any).linked_transfer) ? 'Transfer linked' : 'Link Transfer'}
                                    </DropdownMenuItem>
                                    {Boolean((r as any).linked_transfer) && (
                                      <DropdownMenuItem
                                        onSelect={() => {
                                          setTimeout(() => {
                                            setRowToUnlink(idx);
                                            setUnlinkModalOpen(true);
                                          }, 100);
                                        }}
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
                                            <DropdownMenuItem onClick={() => copyToClipboard(String((r as any).expense_id), `Copied Expense ID ${(r as any).expense_id}`)}>
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
                                                  if (backendId) {
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
                                                  await copyToClipboard(inv.number || String(invId), `Copied Invoice No ${inv.number || invId}`);
                                                } catch {
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
                                                  if (backendId) {
                                                    await bankStatementApi.patchTransaction(selected, backendId, { invoice_id: null });
                                                    await openStatement(selected);
                                                  }
                                                } catch (e: any) {
                                                  let errorMessage = e?.message || t('invoices.delete_failed', { defaultValue: 'Failed to delete invoice' });
                                                  if (errorMessage.includes('linked expenses')) errorMessage = t('invoices.delete_error_linked_expenses');
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
                                    <DropdownMenuSeparator />
                                    <DropdownMenuItem
                                      disabled={readOnly}
                                      onClick={() => {
                                        const backendId = (r as any).backend_id;
                                        if (!backendId) { toast.error('Transaction has not been saved yet'); return; }
                                        setTransactionToDelete({ idx, backendId });
                                        setDeleteTransactionModalOpen(true);
                                      }}
                                      className="text-destructive focus:text-destructive"
                                    >
                                      <Trash2 className="w-4 h-4 mr-2" />
                                      Delete Transaction
                                    </DropdownMenuItem>
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
                        <ContextMenuItem
                          onSelect={() => {
                            setTimeout(() => {
                              setLinkingRowIdx(idx);
                              setLinkTransferModalOpen(true);
                              setLinkTransferModalMounted(true);
                            }, 100);
                          }}
                          disabled={readOnly || Boolean((r as any).linked_transfer) || !(r as any).backend_id}
                        >
                          <ArrowLeftRight className="w-4 h-4 mr-2 text-blue-500" />
                          {Boolean((r as any).linked_transfer) ? 'Transfer linked' : 'Link Transfer'}
                        </ContextMenuItem>
                        {Boolean((r as any).linked_transfer) && (
                          <ContextMenuItem
                            onSelect={() => {
                              setTimeout(() => {
                                setRowToUnlink(idx);
                                setUnlinkModalOpen(true);
                              }, 100);
                            }}
                            className="text-destructive focus:text-destructive"
                            disabled={readOnly}
                          >
                            <X className="w-4 h-4 mr-2" />
                            Unlink Transfer
                          </ContextMenuItem>
                        )}
                        <ContextMenuSeparator />
                        {r.transaction_type === 'debit' && (
                          <>
                            <ContextMenuItem onClick={() => createExpenseFromTransaction(idx)} disabled={readOnly || Boolean((r as any).expense_id)}>
                              <Plus className="w-4 h-4 mr-2 text-success" />
                              {Boolean((r as any).expense_id) ? `Expense linked` : t('statements.add_to_expense', { defaultValue: 'Add to Expense' })}
                            </ContextMenuItem>
                            {Boolean((r as any).expense_id) && (
                              <>
                                <ContextMenuItem onClick={() => copyToClipboard(String((r as any).expense_id), `Copied Expense ID ${(r as any).expense_id}`)}>
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
                                      if (backendId) {
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
                            <ContextMenuItem onClick={() => createInvoiceFromTransaction(idx)} disabled={readOnly || Boolean((r as any).invoice_id)}>
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
                                      await copyToClipboard(inv.number || String(invId), `Copied Invoice No ${inv.number || invId}`);
                                    } catch {
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
                                      if (backendId) {
                                        await bankStatementApi.patchTransaction(selected, backendId, { invoice_id: null });
                                        await openStatement(selected);
                                      }
                                    } catch (e: any) {
                                      let errorMessage = e?.message || t('invoices.delete_failed', { defaultValue: 'Failed to delete invoice' });
                                      if (errorMessage.includes('linked expenses')) errorMessage = t('invoices.delete_error_linked_expenses');
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
                        <ContextMenuSeparator />
                        <ContextMenuItem
                          disabled={readOnly}
                          onClick={() => {
                            const backendId = (r as any).backend_id;
                            if (!backendId) { toast.error('Transaction has not been saved yet'); return; }
                            setTransactionToDelete({ idx, backendId });
                            setDeleteTransactionModalOpen(true);
                          }}
                          className="text-destructive focus:text-destructive"
                        >
                          <Trash2 className="w-4 h-4 mr-2" />
                          Delete Transaction
                        </ContextMenuItem>
                      </ContextMenuContent>
                    </ContextMenu>
                  ))}
                  {rows.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={10} className="h-32 text-center text-muted-foreground italic">
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
  );
}
