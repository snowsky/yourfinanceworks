import { useState, useEffect } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { AlertTriangle, ChevronDown, ChevronUp, ExternalLink, Trash2, Archive, RotateCcw } from 'lucide-react';
import { toast } from 'sonner';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { bankStatementApi } from '@/lib/api/bank-statements';

interface DuplicateTxnEntry {
  id: number;
  statement_id: number;
  statement_filename: string;
  date: string;
  description: string;
  amount: number | string;
  transaction_type?: string;
}

interface DuplicateTransactionPanelProps {
  groups: DuplicateTxnEntry[][];
  onViewTransaction: (statementId: number, backendTxnId: number) => void;
}

function formatAmount(amount: number | string) {
  const n = typeof amount === 'string' ? parseFloat(amount) : amount;
  if (isNaN(n)) return String(amount);
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(Math.abs(n));
}

// ── Single-group Review Modal ─────────────────────────────────────────────────

interface ReviewModalProps {
  group: DuplicateTxnEntry[];
  groupIndex: number;
  onClose: () => void;
  onDeleted: () => void;
}

function ReviewModal({ group, groupIndex, onClose, onDeleted }: ReviewModalProps) {
  const [keepId, setKeepId] = useState<number>(group[0]?.id);
  const [confirmed, setConfirmed] = useState(false);
  const [deleteMode, setDeleteMode] = useState<'recycle' | 'permanent' | null>(null);
  const queryClient = useQueryClient();

  const toDelete = group.filter(t => t.id !== keepId);

  const mutation = useMutation({
    mutationFn: async (permanent: boolean) => {
      for (const txn of toDelete) {
        await bankStatementApi.deleteTransaction(txn.statement_id, txn.id, permanent);
      }
    },
    onSuccess: (_data, permanent) => {
      queryClient.invalidateQueries({ queryKey: ['duplicate-transactions'] });
      if (!permanent) queryClient.invalidateQueries({ queryKey: ['deleted-transactions'] });
      toast.success(
        permanent
          ? toDelete.length === 1
            ? 'Duplicate transaction permanently deleted.'
            : `${toDelete.length} duplicate transactions permanently deleted.`
          : toDelete.length === 1
            ? 'Duplicate transaction moved to recycle bin.'
            : `${toDelete.length} duplicate transactions moved to recycle bin.`
      );
      onDeleted();
    },
    onError: (err: any) => {
      toast.error(err?.message || 'Failed to process transactions.');
    },
  });

  const handleConfirm = (permanent: boolean) => {
    setDeleteMode(permanent ? 'permanent' : 'recycle');
    mutation.mutate(permanent);
  };

  return (
    <Dialog open onOpenChange={open => { if (!open) onClose(); }}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Review Duplicate Group {groupIndex + 1}</DialogTitle>
        </DialogHeader>

        {!confirmed ? (
          <>
            <p className="text-sm text-muted-foreground mb-3">
              Select the transaction to <span className="font-semibold text-foreground">keep</span>.
              The others will be removed.
            </p>

            <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
              {group.map(txn => {
                const isKept = txn.id === keepId;
                return (
                  <label
                    key={txn.id}
                    className={`flex items-start gap-3 rounded-lg border p-3 cursor-pointer transition-colors ${
                      isKept
                        ? 'border-primary bg-primary/5'
                        : 'border-border bg-muted/30 hover:bg-muted/50'
                    }`}
                  >
                    <input
                      type="radio"
                      name="keep-transaction"
                      value={txn.id}
                      checked={isKept}
                      onChange={() => setKeepId(txn.id)}
                      className="mt-0.5 accent-primary"
                    />
                    <div className="flex-1 min-w-0 text-sm">
                      <p className="font-medium text-foreground truncate">{txn.description}</p>
                      <p className="text-muted-foreground text-xs mt-0.5">
                        {txn.date}
                        {' · '}
                        <span className="font-mono font-semibold text-foreground">{formatAmount(txn.amount)}</span>
                        {' · '}
                        <span className="opacity-70">{txn.statement_filename}</span>
                      </p>
                    </div>
                    {isKept && (
                      <span className="text-xs font-medium text-primary mt-0.5 flex-shrink-0">Keep</span>
                    )}
                  </label>
                );
              })}
            </div>

            <DialogFooter className="mt-4 gap-2 flex-wrap">
              <Button variant="outline" onClick={onClose}>Cancel</Button>
              <Button
                variant="outline"
                className="border-amber-400 text-amber-700 hover:bg-amber-50 dark:border-amber-600 dark:text-amber-400 dark:hover:bg-amber-950/20"
                onClick={() => setConfirmed(true)}
                disabled={toDelete.length === 0}
              >
                <Archive className="h-4 w-4 mr-1.5" />
                Move {toDelete.length} to Recycle Bin
              </Button>
              <Button
                variant="destructive"
                onClick={() => { setConfirmed(true); }}
                disabled={toDelete.length === 0}
              >
                <Trash2 className="h-4 w-4 mr-1.5" />
                Permanently Delete {toDelete.length}
              </Button>
            </DialogFooter>
          </>
        ) : (
          <>
            <div className="rounded-lg border border-border bg-muted/30 p-3 text-sm mb-4">
              <p className="font-semibold mb-1 text-foreground">Confirm action</p>
              <p className="text-muted-foreground">
                The following {toDelete.length} transaction{toDelete.length !== 1 ? 's' : ''} will be removed:
              </p>
              <ul className="mt-2 space-y-1 list-disc list-inside text-xs text-muted-foreground">
                {toDelete.map(t => (
                  <li key={t.id}>
                    {t.description} · {t.date} · {formatAmount(t.amount)} — <span className="opacity-70">{t.statement_filename}</span>
                  </li>
                ))}
              </ul>
            </div>

            <DialogFooter className="gap-2 flex-wrap">
              <Button variant="outline" onClick={() => setConfirmed(false)} disabled={mutation.isPending}>
                Back
              </Button>
              <Button
                variant="outline"
                className="border-amber-400 text-amber-700 hover:bg-amber-50 dark:border-amber-600 dark:text-amber-400 dark:hover:bg-amber-950/20"
                onClick={() => handleConfirm(false)}
                disabled={mutation.isPending}
              >
                <Archive className="h-4 w-4 mr-1.5" />
                {mutation.isPending && deleteMode === 'recycle' ? 'Moving…' : 'Move to Recycle Bin'}
              </Button>
              <Button
                variant="destructive"
                onClick={() => handleConfirm(true)}
                disabled={mutation.isPending}
              >
                <Trash2 className="h-4 w-4 mr-1.5" />
                {mutation.isPending && deleteMode === 'permanent' ? 'Deleting…' : 'Permanently Delete'}
              </Button>
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}

// ── Bulk "Review All Groups" Modal ────────────────────────────────────────────

interface BulkReviewModalProps {
  groups: DuplicateTxnEntry[][];
  onClose: () => void;
  onDone: () => void;
}

function BulkReviewModal({ groups, onClose, onDone }: BulkReviewModalProps) {
  // For each group, track which transaction to keep (default: first)
  const [keepIds, setKeepIds] = useState<Record<number, number>>(
    Object.fromEntries(groups.map((g, i) => [i, g[0]?.id]))
  );
  const [step, setStep] = useState<'select' | 'confirm'>('select');
  const [deleteMode, setDeleteMode] = useState<'recycle' | 'permanent' | null>(null);
  const queryClient = useQueryClient();

  const allToDelete = groups.flatMap((g, gi) => g.filter(t => t.id !== keepIds[gi]));

  const mutation = useMutation({
    mutationFn: async (permanent: boolean) => {
      for (const txn of allToDelete) {
        await bankStatementApi.deleteTransaction(txn.statement_id, txn.id, permanent);
      }
    },
    onSuccess: (_data, permanent) => {
      queryClient.invalidateQueries({ queryKey: ['duplicate-transactions'] });
      if (!permanent) queryClient.invalidateQueries({ queryKey: ['deleted-transactions'] });
      toast.success(
        permanent
          ? `${allToDelete.length} duplicate transaction${allToDelete.length !== 1 ? 's' : ''} permanently deleted.`
          : `${allToDelete.length} duplicate transaction${allToDelete.length !== 1 ? 's' : ''} moved to recycle bin.`
      );
      onDone();
    },
    onError: (err: any) => {
      toast.error(err?.message || 'Failed to process transactions.');
    },
  });

  const handleAction = (permanent: boolean) => {
    setDeleteMode(permanent ? 'permanent' : 'recycle');
    mutation.mutate(permanent);
  };

  return (
    <Dialog open onOpenChange={open => { if (!open) onClose(); }}>
      <DialogContent className="max-w-2xl max-h-[85vh] flex flex-col">
        <DialogHeader>
          <DialogTitle>Review All {groups.length} Duplicate Groups</DialogTitle>
        </DialogHeader>

        {step === 'select' ? (
          <>
            <p className="text-sm text-muted-foreground mb-3">
              For each group, select the transaction to <span className="font-semibold text-foreground">keep</span>.
              All others will be removed.
            </p>

            <div className="flex-1 overflow-y-auto space-y-4 pr-1">
              {groups.map((group, gi) => (
                <div key={gi} className="rounded-lg border border-border p-3">
                  <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground mb-2">
                    Group {gi + 1} · {group.length} occurrences
                  </p>
                  <div className="space-y-1.5">
                    {group.map(txn => {
                      const isKept = txn.id === keepIds[gi];
                      return (
                        <label
                          key={txn.id}
                          className={`flex items-start gap-3 rounded-md border p-2.5 cursor-pointer transition-colors ${
                            isKept
                              ? 'border-primary bg-primary/5'
                              : 'border-border bg-muted/20 hover:bg-muted/40'
                          }`}
                        >
                          <input
                            type="radio"
                            name={`keep-group-${gi}`}
                            value={txn.id}
                            checked={isKept}
                            onChange={() => setKeepIds(prev => ({ ...prev, [gi]: txn.id }))}
                            className="mt-0.5 accent-primary"
                          />
                          <div className="flex-1 min-w-0 text-xs">
                            <p className="font-medium text-foreground truncate">{txn.description}</p>
                            <p className="text-muted-foreground mt-0.5">
                              {txn.date}
                              {' · '}
                              <span className="font-mono font-semibold text-foreground">{formatAmount(txn.amount)}</span>
                              {' · '}
                              <span className="opacity-70">{txn.statement_filename}</span>
                            </p>
                          </div>
                          {isKept && (
                            <span className="text-xs font-medium text-primary mt-0.5 flex-shrink-0">Keep</span>
                          )}
                        </label>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>

            <DialogFooter className="mt-4 gap-2 flex-wrap border-t pt-4">
              <Button variant="outline" onClick={onClose}>Cancel</Button>
              <Button
                variant="outline"
                className="border-amber-400 text-amber-700 hover:bg-amber-50 dark:border-amber-600 dark:text-amber-400 dark:hover:bg-amber-950/20"
                onClick={() => setStep('confirm')}
                disabled={allToDelete.length === 0}
              >
                <Archive className="h-4 w-4 mr-1.5" />
                Review {allToDelete.length} to Remove
              </Button>
            </DialogFooter>
          </>
        ) : (
          <>
            <div className="rounded-lg border border-border bg-muted/20 p-3 text-sm mb-4 max-h-72 overflow-y-auto">
              <p className="font-semibold mb-2 text-foreground">
                {allToDelete.length} transaction{allToDelete.length !== 1 ? 's' : ''} will be removed:
              </p>
              <ul className="space-y-1 list-disc list-inside text-xs text-muted-foreground">
                {allToDelete.map(t => (
                  <li key={t.id}>
                    {t.description} · {t.date} · {formatAmount(t.amount)} — <span className="opacity-70">{t.statement_filename}</span>
                  </li>
                ))}
              </ul>
            </div>
            <p className="text-sm text-muted-foreground mb-2">Choose how to remove them:</p>

            <DialogFooter className="gap-2 flex-wrap">
              <Button variant="outline" onClick={() => setStep('select')} disabled={mutation.isPending}>
                Back
              </Button>
              <Button
                variant="outline"
                className="border-amber-400 text-amber-700 hover:bg-amber-50 dark:border-amber-600 dark:text-amber-400 dark:hover:bg-amber-950/20"
                onClick={() => handleAction(false)}
                disabled={mutation.isPending}
              >
                <Archive className="h-4 w-4 mr-1.5" />
                {mutation.isPending && deleteMode === 'recycle' ? 'Moving…' : 'Move to Recycle Bin'}
              </Button>
              <Button
                variant="destructive"
                onClick={() => handleAction(true)}
                disabled={mutation.isPending}
              >
                <Trash2 className="h-4 w-4 mr-1.5" />
                {mutation.isPending && deleteMode === 'permanent' ? 'Deleting…' : 'Permanently Delete All'}
              </Button>
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}

// ── Transaction Recycle Bin Modal ─────────────────────────────────────────────

interface TxnRecycleBinModalProps {
  onClose: () => void;
}

function TxnRecycleBinModal({ onClose }: TxnRecycleBinModalProps) {
  const queryClient = useQueryClient();
  const [items, setItems] = useState<Array<{
    id: number; statement_id: number; date: string;
    description: string; amount: number; transaction_type: string; deleted_at?: string | null;
  }>>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    bankStatementApi.getDeletedTransactions().then(res => {
      setItems(res.items as any);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  const restoreMutation = useMutation({
    mutationFn: ({ statementId, txnId }: { statementId: number; txnId: number }) =>
      bankStatementApi.restoreTransaction(statementId, txnId),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['duplicate-transactions'] });
      toast.success('Transaction restored.');
      setItems(prev => prev.filter(t => t.id !== variables.txnId));
    },
    onError: () => toast.error('Failed to restore transaction.'),
  });

  const deleteMutation = useMutation({
    mutationFn: ({ statementId, txnId }: { statementId: number; txnId: number }) =>
      bankStatementApi.permanentlyDeleteTransaction(statementId, txnId),
    onSuccess: (_data, variables) => {
      toast.success('Transaction permanently deleted.');
      setItems(prev => prev.filter(t => t.id !== variables.txnId));
    },
    onError: () => toast.error('Failed to delete transaction.'),
  });

  return (
    <Dialog open onOpenChange={open => { if (!open) onClose(); }}>
      <DialogContent className="max-w-2xl max-h-[80vh] flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Trash2 className="h-4 w-4 text-destructive" />
            Transaction Recycle Bin
          </DialogTitle>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto">
          {loading ? (
            <p className="text-sm text-muted-foreground text-center py-8">Loading…</p>
          ) : items.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 gap-3">
              <div className="p-4 rounded-full bg-muted/50">
                <Trash2 className="h-8 w-8 text-muted-foreground/40" />
              </div>
              <p className="text-sm text-muted-foreground">Transaction recycle bin is empty</p>
            </div>
          ) : (
            <div className="space-y-2">
              {items.map(t => (
                <div
                  key={t.id}
                  className="flex items-center gap-3 rounded-lg border border-border bg-muted/20 px-3 py-2.5 text-sm"
                >
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-foreground truncate">{t.description}</p>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      {t.date}
                      {' · '}
                      <span className="font-mono font-semibold text-foreground">{formatAmount(t.amount)}</span>
                      {t.deleted_at && (
                        <span className="ml-2 opacity-60">
                          · deleted {new Date(t.deleted_at).toLocaleDateString()}
                        </span>
                      )}
                    </p>
                  </div>
                  <div className="flex gap-1.5 flex-shrink-0">
                    <button
                      onClick={() => restoreMutation.mutate({ statementId: t.statement_id, txnId: t.id })}
                      disabled={restoreMutation.isPending || deleteMutation.isPending}
                      className="flex items-center gap-1 px-2 py-1 rounded text-xs font-medium bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-400 hover:bg-emerald-200 dark:hover:bg-emerald-800/40 transition-colors"
                      title="Restore transaction"
                    >
                      <RotateCcw className="h-3 w-3" />
                      Restore
                    </button>
                    <button
                      onClick={() => deleteMutation.mutate({ statementId: t.statement_id, txnId: t.id })}
                      disabled={restoreMutation.isPending || deleteMutation.isPending}
                      className="flex items-center gap-1 px-2 py-1 rounded text-xs font-medium bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400 hover:bg-red-200 dark:hover:bg-red-800/40 transition-colors"
                      title="Permanently delete"
                    >
                      <Trash2 className="h-3 w-3" />
                      Delete
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <DialogFooter className="border-t pt-4">
          <Button variant="outline" onClick={onClose}>Close</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ── Main Panel ────────────────────────────────────────────────────────────────

export function DuplicateTransactionPanel({ groups, onViewTransaction }: DuplicateTransactionPanelProps) {
  const [expanded, setExpanded] = useState(false);
  const [expandedGroups, setExpandedGroups] = useState<Set<number>>(new Set([0]));
  const [reviewGroupIndex, setReviewGroupIndex] = useState<number | null>(null);
  const [showBulkReview, setShowBulkReview] = useState(false);
  const [showTxnRecycleBin, setShowTxnRecycleBin] = useState(false);

  const count = groups.length;

  const toggleGroup = (idx: number) => {
    setExpandedGroups(prev => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return next;
    });
  };

  return (
    <>
      <div className="rounded-xl border border-yellow-300 bg-yellow-50 dark:bg-yellow-950/20 dark:border-yellow-800 mb-3 overflow-hidden shadow-sm">
        {/* Header row — always visible */}
        <div className="flex items-center gap-2 px-4 py-3">
          <button
            className="flex items-center gap-3 flex-1 text-left hover:opacity-80 transition-opacity"
            onClick={() => setExpanded(v => !v)}
            aria-expanded={expanded}
          >
            <AlertTriangle className="h-4 w-4 text-yellow-600 dark:text-yellow-400 flex-shrink-0" />
            <span className="flex-1 text-sm font-medium text-yellow-800 dark:text-yellow-300">
              <span className="font-bold">{count}</span>{' '}
              potential duplicate transaction {count !== 1 ? 'groups' : 'group'} detected across statements.{' '}
              <span className="font-normal opacity-80">Click to {expanded ? 'hide' : 'review'}.</span>
            </span>
            {expanded
              ? <ChevronUp className="h-4 w-4 text-yellow-600 dark:text-yellow-400 flex-shrink-0" />
              : <ChevronDown className="h-4 w-4 text-yellow-600 dark:text-yellow-400 flex-shrink-0" />
            }
          </button>

          {/* Recycle bin button */}
          <button
            onClick={e => { e.stopPropagation(); setShowTxnRecycleBin(true); }}
            className="flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium bg-yellow-100 dark:bg-yellow-900/30 text-yellow-800 dark:text-yellow-300 hover:bg-yellow-200 dark:hover:bg-yellow-800/40 transition-colors flex-shrink-0 whitespace-nowrap"
            title="View transaction recycle bin"
          >
            <Trash2 className="h-3 w-3" />
            Recycle Bin
          </button>

          {/* Review All button */}
          <button
            onClick={e => { e.stopPropagation(); setShowBulkReview(true); }}
            className="flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium bg-amber-100 dark:bg-amber-900/30 text-amber-800 dark:text-amber-300 hover:bg-amber-200 dark:hover:bg-amber-800/40 transition-colors flex-shrink-0 whitespace-nowrap"
            title="Review all duplicate groups at once"
          >
            <Archive className="h-3 w-3" />
            Review All
          </button>
        </div>

        {/* Expandable body */}
        {expanded && (
          <div className="border-t border-yellow-200 dark:border-yellow-800 divide-y divide-yellow-200 dark:divide-yellow-800">
            {groups.map((group, gi) => (
              <div key={gi} className="bg-white dark:bg-background">
                {/* Group header */}
                <div className="flex items-center gap-2 px-4 py-2.5">
                  <button
                    className="flex items-center gap-2 flex-1 text-left hover:bg-yellow-50 dark:hover:bg-yellow-950/10 transition-colors rounded"
                    onClick={() => toggleGroup(gi)}
                  >
                    <span className="text-xs font-bold uppercase tracking-wider text-yellow-700 dark:text-yellow-400 min-w-[60px]">
                      Group {gi + 1}
                    </span>
                    <span className="flex-1 text-xs text-muted-foreground truncate">
                      {group[0]?.description && (
                        <span className="mr-2 font-medium text-foreground">{group[0].description}</span>
                      )}
                      {group[0]?.date && (
                        <span className="mr-2">{group[0].date}</span>
                      )}
                      {group[0]?.amount !== undefined && (
                        <span className="font-mono">{formatAmount(group[0].amount)}</span>
                      )}
                      <span className="ml-2 text-yellow-600 dark:text-yellow-500">
                        · {group.length} occurrences across {new Set(group.map(t => t.statement_id)).size} statements
                      </span>
                    </span>
                    {expandedGroups.has(gi)
                      ? <ChevronUp className="h-3.5 w-3.5 text-muted-foreground flex-shrink-0" />
                      : <ChevronDown className="h-3.5 w-3.5 text-muted-foreground flex-shrink-0" />
                    }
                  </button>

                  {/* Per-group Review & Delete button */}
                  <button
                    onClick={e => { e.stopPropagation(); setReviewGroupIndex(gi); }}
                    className="flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400 hover:bg-red-200 dark:hover:bg-red-800/40 transition-colors flex-shrink-0 whitespace-nowrap"
                    title="Review and delete duplicates in this group"
                  >
                    <Trash2 className="h-3 w-3" />
                    Review &amp; Delete
                  </button>
                </div>

                {/* Transaction rows within group */}
                {expandedGroups.has(gi) && (
                  <div className="px-4 pb-3 space-y-1.5">
                    {group.map((txn, ti) => (
                      <div
                        key={ti}
                        className="flex items-center gap-3 rounded-lg border border-yellow-100 dark:border-yellow-900/40 bg-yellow-50/50 dark:bg-yellow-950/10 px-3 py-2 text-xs"
                      >
                        <div className="flex-1 min-w-0">
                          <span className="font-medium text-foreground truncate block">{txn.description}</span>
                          <span className="text-muted-foreground">
                            {txn.date}
                            {' · '}
                            <span className="font-mono font-semibold text-foreground">{formatAmount(txn.amount)}</span>
                            {' · '}
                            <span className="opacity-70">{txn.statement_filename}</span>
                          </span>
                        </div>
                        <button
                          onClick={() => onViewTransaction(txn.statement_id, txn.id)}
                          className="flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium bg-yellow-200 dark:bg-yellow-800/40 text-yellow-800 dark:text-yellow-300 hover:bg-yellow-300 dark:hover:bg-yellow-700/50 transition-colors flex-shrink-0 whitespace-nowrap"
                          title={`Open statement: ${txn.statement_filename}`}
                        >
                          <ExternalLink className="h-3 w-3" />
                          View
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Single-group Review & Delete modal */}
      {reviewGroupIndex !== null && groups[reviewGroupIndex] && (
        <ReviewModal
          group={groups[reviewGroupIndex]}
          groupIndex={reviewGroupIndex}
          onClose={() => setReviewGroupIndex(null)}
          onDeleted={() => setReviewGroupIndex(null)}
        />
      )}

      {/* Bulk Review All modal */}
      {showBulkReview && (
        <BulkReviewModal
          groups={groups}
          onClose={() => setShowBulkReview(false)}
          onDone={() => setShowBulkReview(false)}
        />
      )}

      {/* Transaction Recycle Bin modal */}
      {showTxnRecycleBin && (
        <TxnRecycleBinModal
          onClose={() => setShowTxnRecycleBin(false)}
        />
      )}
    </>
  );
}
