import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Checkbox } from '@/components/ui/checkbox';
import { CurrencyDisplay } from '@/components/ui/currency-display';
import { Input } from '@/components/ui/input';
import {
  AlertCircle, CheckCircle2, Clock3, FileSearch, Loader2, Eye, Upload,
  MoreHorizontal, Edit, RotateCcw, Receipt,
  Trash2, X
} from 'lucide-react';
import { Share2 } from 'lucide-react';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { Link } from 'react-router-dom';
import { expenseApi, type Expense, type ExpenseAttachmentMeta } from '@/lib/api';
import { Badge } from '@/components/ui/badge';
import { canPerformActions, canEditExpense, canDeleteExpense } from '@/utils/auth';
import { ExpenseApprovalStatus } from '@/components/approvals/ExpenseApprovalStatus';
import { ReviewStatusCell } from '@/components/ReviewStatusCell';
import { CreatedAtByCell } from '@/components/CreatedAtByCell';
import { toast } from 'sonner';

interface ExpenseTableProps {
  loading: boolean;
  filteredExpenses: Expense[];
  selectedIds: number[];
  setSelectedIds: (ids: number[] | ((prev: number[]) => number[])) => void;
  isVisible: (key: string) => boolean;
  getLocale: () => string;
  timezone: string;
  attachments: Record<number, ExpenseAttachmentMeta[]>;
  setAttachments: (fn: (prev: Record<number, ExpenseAttachmentMeta[]>) => Record<number, ExpenseAttachmentMeta[]>) => void;
  setAttachmentPreviewOpen: (state: { expenseId: number | null }) => void;
  uploadingId: number | null;
  onUpload: (id: number, file: File) => Promise<void>;
  onRequeue: (expenseId: number) => Promise<void>;
  processingLocks: Set<number>;
  onReviewClick: (expense: Expense) => void;
  onRunReview: (expenseId: number) => Promise<void>;
  onCancelReview: (expenseId: number) => Promise<void>;
  newLabelValueById: Record<number, string>;
  setNewLabelValueById: (fn: (prev: Record<number, string>) => Record<number, string>) => void;
  onSetShareExpenseId: (id: number) => void;
  onSetExpenseIdToDelete: (id: number) => void;
  setExpenses: (fn: (prev: Expense[]) => Expense[]) => void;
}

export function ExpenseTable({
  loading,
  filteredExpenses,
  selectedIds,
  setSelectedIds,
  isVisible,
  getLocale,
  timezone,
  attachments,
  setAttachments,
  setAttachmentPreviewOpen,
  uploadingId,
  onUpload,
  onRequeue,
  processingLocks,
  onReviewClick,
  onRunReview,
  onCancelReview,
  newLabelValueById,
  setNewLabelValueById,
  onSetShareExpenseId,
  onSetExpenseIdToDelete,
  setExpenses,
}: ExpenseTableProps) {
  const { t } = useTranslation();

  const renderAnalysisCell = (e: Expense) => {
    const status = e.analysis_status || (e.imported_from_attachment ? 'not_started' : undefined);
    const fileCount = Array.isArray(attachments[e.id]) ? attachments[e.id].length : e.attachments_count || 0;
    const canShowAction = Boolean(status || fileCount > 0 || e.imported_from_attachment) && canPerformActions() && e.status !== 'pending_approval' && e.status !== 'approved';
    const isActionDisabled = (!e.imported_from_attachment && fileCount === 0) || processingLocks.has(e.id) || uploadingId === e.id;
    const fileSummary = fileCount > 0
      ? `${fileCount} ${t('expenses.file_count', { defaultValue: 'file(s)', count: fileCount })}`
      : e.imported_from_attachment
        ? t('expenses.imported_receipt', { defaultValue: 'Imported receipt' })
        : t('expenses.no_receipt', { defaultValue: 'No receipt' });

    const statusMeta = (() => {
      switch (status) {
        case 'done':
          return {
            label: t('expenses.status_done'),
            icon: CheckCircle2,
            className: 'bg-green-50 text-green-700 border-green-200 dark:bg-green-950/30 dark:text-green-300 dark:border-green-800',
          };
        case 'processing':
          return {
            label: t('expenses.status_processing'),
            icon: Loader2,
            className: 'bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950/30 dark:text-blue-300 dark:border-blue-800',
          };
        case 'queued':
          return {
            label: t('expenses.status_queued'),
            icon: Clock3,
            className: 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/30 dark:text-amber-300 dark:border-amber-800',
          };
        case 'failed':
          return {
            label: t('common.failed', { defaultValue: 'Failed' }),
            icon: AlertCircle,
            className: 'bg-red-50 text-red-700 border-red-200 dark:bg-red-950/30 dark:text-red-300 dark:border-red-800',
          };
        case 'cancelled':
          return {
            label: t('common.cancelled', { defaultValue: 'Cancelled' }),
            icon: X,
            className: 'bg-muted/60 text-muted-foreground border-border',
          };
        case 'not_started':
          return {
            label: t('common.not_started', { defaultValue: 'Not Started' }),
            icon: FileSearch,
            className: 'bg-slate-50 text-slate-700 border-slate-200 dark:bg-slate-900/50 dark:text-slate-300 dark:border-slate-700',
          };
        default:
          return {
            label: t('common.not_available', { defaultValue: 'N/A' }),
            icon: FileSearch,
            className: 'bg-muted/50 text-muted-foreground border-transparent',
          };
      }
    })();

    const StatusIcon = statusMeta.icon;
    const isStatusSpinning = status === 'processing';

    return (
      <div className="flex min-w-[150px] items-center justify-start gap-1.5">
        <div className="min-w-0 space-y-1">
          <Badge variant="outline" className={`h-6 gap-1.5 whitespace-nowrap px-2 font-medium shadow-none ${statusMeta.className}`}>
            <StatusIcon className={`h-3 w-3 ${isStatusSpinning ? 'animate-spin' : ''}`} />
            {statusMeta.label}
          </Badge>
          <div className="max-w-[130px] truncate text-[11px] leading-none text-muted-foreground">
            {fileSummary}
          </div>
        </div>
        {canShowAction && (
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7 shrink-0"
            onClick={() => onRequeue(e.id)}
            disabled={isActionDisabled}
            title={t('expenses.process_again', { defaultValue: 'Process Again' })}
            aria-label={t('expenses.process_again', { defaultValue: 'Process Again' })}
          >
            {processingLocks.has(e.id) || uploadingId === e.id ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <RotateCcw className="h-3.5 w-3.5" />
            )}
          </Button>
        )}
      </div>
    );
  };

  const renderReceiptCell = (e: Expense) => {
    const fileCount = Array.isArray(attachments[e.id]) ? attachments[e.id].length : e.attachments_count || 0;
    const hasKnownFileCount = Array.isArray(attachments[e.id]) || typeof e.attachments_count === 'number';
    const isUploading = uploadingId === e.id;
    const fileSummary = fileCount > 0
      ? `${fileCount} ${t('expenses.file_count', { defaultValue: 'file(s)', count: fileCount })}`
      : t('expenses.no_receipt', { defaultValue: 'No receipt' });
    const canPreview = !hasKnownFileCount || fileCount > 0;

    const openPreview = async () => {
      const list = await expenseApi.listAttachments(e.id);
      setAttachments(prev => ({ ...prev, [e.id]: list }));
      setAttachmentPreviewOpen({ expenseId: e.id });
    };

    return (
      <div className="flex min-w-[150px] items-center justify-start gap-1.5">
        <div className="min-w-0 space-y-1">
          <Badge
            variant="outline"
            className={`h-6 gap-1.5 whitespace-nowrap px-2 font-medium shadow-none ${
              fileCount > 0
                ? 'bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950/30 dark:text-blue-300 dark:border-blue-800'
                : 'bg-muted/50 text-muted-foreground border-transparent'
            }`}
          >
            <Receipt className="h-3 w-3" />
            {fileSummary}
          </Badge>
          <div className="max-w-[130px] truncate text-[11px] leading-none text-muted-foreground">
            {isUploading ? t('expenses.uploading') : t('expenses.receipt_attachments', { defaultValue: 'Receipt attachments' })}
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-0.5">
          <Button
            asChild
            variant="ghost"
            size="icon"
            className={`h-7 w-7 ${isUploading ? 'pointer-events-none opacity-50' : ''}`}
            title={t('expenses.upload')}
            aria-label={t('expenses.upload')}
          >
            <label>
              {isUploading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Upload className="h-3.5 w-3.5" />}
              <input
                type="file"
                accept="application/pdf,image/jpeg,image/png"
                className="hidden"
                onChange={async (ev) => {
                  const file = ev.target.files?.[0];
                  if (!file) return;
                  await onUpload(e.id, file);
                  await openPreview();
                  ev.currentTarget.value = '';
                }}
              />
            </label>
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            onClick={openPreview}
            disabled={!canPreview}
            title={t('common.view')}
            aria-label={t('common.view')}
          >
            <Eye className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>
    );
  };

  return (
    <div className="rounded-xl border border-border/50 overflow-x-auto shadow-sm">
      <Table className="min-w-[1100px]">
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
            {isVisible('statement') && <TableHead className="font-bold text-foreground">{t('expenses.table.statement', { defaultValue: 'Statement' })}</TableHead>}
            {isVisible('approval_status') && <TableHead className="font-bold text-foreground">{t('expenses.table.approval_status', { defaultValue: 'Status' })}</TableHead>}
            {isVisible('created_at_by') && <TableHead className="font-bold text-foreground">{t('expenses.table.created_at_by', { defaultValue: 'Created at / by' })}</TableHead>}
            {isVisible('analyzed') && <TableHead className="font-bold text-foreground">{t('expenses.table.analyzed')}</TableHead>}
            {isVisible('review') && <TableHead className="font-bold text-foreground">{t('expenses.review.title', { defaultValue: 'Review' })}</TableHead>}
            {isVisible('receipt') && <TableHead className="font-bold text-foreground">{t('expenses.table.receipt')}</TableHead>}
            <TableHead className="sticky right-0 z-30 w-[88px] bg-muted/80 text-center font-bold text-foreground shadow-[-6px_0_10px_-6px_hsl(var(--foreground)/0.35)]">{t('expenses.table.actions')}</TableHead>
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
                {isVisible('statement') && <TableCell>
                  {typeof e.statement_id === 'number' && typeof e.statement_transaction_id === 'number' ? (
                    <Link to={`/statements?id=${e.statement_id}&txn=${e.statement_transaction_id}`} className="text-blue-600 hover:underline">#{e.statement_transaction_id}</Link>
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
                  <CreatedAtByCell
                    createdAt={e.created_at}
                    createdByUsername={e.created_by_username}
                    createdByEmail={e.created_by_email}
                    locale={getLocale()}
                    timezone={timezone}
                    unknownLabel={t('common.unknown')}
                  />
                </TableCell>}
                {isVisible('analyzed') && <TableCell>{renderAnalysisCell(e)}</TableCell>}
                {isVisible('review') && <TableCell>
                  <ReviewStatusCell
                    status={e.review_status}
                    reviewedAt={e.reviewed_at}
                    hasReport={Boolean(e.review_result)}
                    onView={() => onReviewClick(e)}
                    onRun={() => onRunReview(e.id)}
                    onCancel={() => onCancelReview(e.id)}
                    labels={{
                      view: t('expenses.review.view_report', { defaultValue: 'View review report' }),
                      run: t('expenses.review.trigger', { defaultValue: 'Run review' }),
                      cancel: t('expenses.review.cancel', { defaultValue: 'Cancel review' }),
                      clear: t('expenses.review.clear_status', { defaultValue: 'Clear review status' }),
                    }}
                  />
                </TableCell>}
                {isVisible('receipt') && <TableCell>{renderReceiptCell(e)}</TableCell>}
                <TableCell className="sticky right-0 z-20 bg-background text-center shadow-[-6px_0_10px_-6px_hsl(var(--foreground)/0.25)]">
                  {canPerformActions() && (
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon">
                          <MoreHorizontal className="w-4 h-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem onClick={() => window.location.href = `/expenses/view/${e.id}`}>
                          <Eye className="mr-2 w-4 h-4" /> {t('common.view', 'View')}
                        </DropdownMenuItem>
                        {canEditExpense(e) && (
                          <DropdownMenuItem onClick={() => window.location.href = `/expenses/edit/${e.id}`}>
                            <Edit className="mr-2 w-4 h-4" /> {t('common.edit', 'Edit')}
                          </DropdownMenuItem>
                        )}
                        <DropdownMenuItem onClick={() => onSetShareExpenseId(e.id)}>
                          <Share2 className="mr-2 w-4 h-4" /> Share
                        </DropdownMenuItem>
                        {canDeleteExpense(e) && (
                          <>
                            <DropdownMenuSeparator />
                            <DropdownMenuItem className="text-destructive focus:text-destructive" onClick={() => onSetExpenseIdToDelete(e.id)}>
                              <Trash2 className="mr-2 w-4 h-4" /> {t('expenses.delete', 'Delete')}
                            </DropdownMenuItem>
                          </>
                        )}
                      </DropdownMenuContent>
                    </DropdownMenu>
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
  );
}
