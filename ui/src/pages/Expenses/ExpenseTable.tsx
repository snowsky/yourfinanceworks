import { useTranslation } from 'react-i18next';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Checkbox } from '@/components/ui/checkbox';
import { CurrencyDisplay } from '@/components/ui/currency-display';
import { Input } from '@/components/ui/input';
import {
  AlertCircle, Loader2, X, Eye, Upload,
  MoreHorizontal, Edit, RotateCcw, Receipt,
  Trash2
} from 'lucide-react';
import { Share2 } from 'lucide-react';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { Link } from 'react-router-dom';
import { expenseApi, type Expense, type ExpenseAttachmentMeta } from '@/lib/api';
import { Badge } from '@/components/ui/badge';
import { canPerformActions, canEditExpense, canDeleteExpense } from '@/utils/auth';
import { ExpenseApprovalStatus } from '@/components/approvals/ExpenseApprovalStatus';
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
                        onClick={() => onRequeue(e.id)}
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
                    <Button size="sm" variant="outline" className="border-amber-500 text-amber-600 hover:bg-amber-50" onClick={() => onReviewClick(e)}>
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
                        onClick={() => onReviewClick(e)}
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
                          onClick={() => onRunReview(e.id)}
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
                          onClick={() => onCancelReview(e.id)}
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
                          if (file) await onUpload(e.id, file);
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
                <TableCell className="text-right">
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
