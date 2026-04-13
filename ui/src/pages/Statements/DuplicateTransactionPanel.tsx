import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { AlertTriangle, ChevronDown, ChevronUp, ExternalLink, Trash2, Archive, FileText } from 'lucide-react';
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

// ── Single-group Review Modal (statement-level) ───────────────────────────────

interface ReviewModalProps {
  group: DuplicateTxnEntry[];
  groupIndex: number;
  onClose: () => void;
  onDeleted: () => void;
}

function ReviewModal({ group, groupIndex, onClose, onDeleted }: ReviewModalProps) {
  // Derive unique statements from the transaction group
  const statements = Array.from(
    new Map(group.map(t => [t.statement_id, t])).values()
  );
  const [keepStatementId, setKeepStatementId] = useState<number>(statements[0]?.statement_id);
  const [confirmed, setConfirmed] = useState(false);
  const queryClient = useQueryClient();

  const toDeleteStatements = statements.filter(s => s.statement_id !== keepStatementId);
  // Count transactions per statement for display
  const txnCountByStatement = group.reduce<Record<number, number>>((acc, t) => {
    acc[t.statement_id] = (acc[t.statement_id] ?? 0) + 1;
    return acc;
  }, {});

  const mutation = useMutation({
    mutationFn: async () => {
      for (const s of toDeleteStatements) {
        await bankStatementApi.delete(s.statement_id);
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['duplicate-transactions'] });
      queryClient.invalidateQueries({ queryKey: ['statements'] });
      toast.success(
        toDeleteStatements.length === 1
          ? 'Statement moved to recycle bin.'
          : `${toDeleteStatements.length} statements moved to recycle bin.`
      );
      onDeleted();
    },
    onError: (err: any) => {
      toast.error(err?.message || 'Failed to delete statement.');
    },
  });

  if (statements.length < 2) {
    return (
      <Dialog open onOpenChange={open => { if (!open) onClose(); }}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Review Duplicate Group {groupIndex + 1}</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground py-4">
            All duplicate transactions belong to the same statement — no statement to delete.
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={onClose}>Close</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    );
  }

  return (
    <Dialog open onOpenChange={open => { if (!open) onClose(); }}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Review Duplicate Group {groupIndex + 1}</DialogTitle>
        </DialogHeader>

        {!confirmed ? (
          <>
            <p className="text-sm text-muted-foreground mb-3">
              These duplicate transactions appear across multiple statements.
              Select the <span className="font-semibold text-foreground">statement to keep</span>;
              the others will be moved to the recycle bin.
            </p>
            <p className="text-xs text-muted-foreground mb-3 font-mono bg-muted/30 rounded px-2 py-1 truncate">
              {group[0]?.description} · {group[0]?.date} · {formatAmount(group[0]?.amount)}
            </p>

            <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
              {statements.map(s => {
                const isKept = s.statement_id === keepStatementId;
                return (
                  <label
                    key={s.statement_id}
                    className={`flex items-start gap-3 rounded-lg border p-3 cursor-pointer transition-colors ${
                      isKept
                        ? 'border-primary bg-primary/5'
                        : 'border-border bg-muted/30 hover:bg-muted/50'
                    }`}
                  >
                    <input
                      type="radio"
                      name={`keep-statement-${groupIndex}`}
                      value={s.statement_id}
                      checked={isKept}
                      onChange={() => setKeepStatementId(s.statement_id)}
                      className="mt-0.5 accent-primary"
                    />
                    <div className="flex-1 min-w-0 text-sm">
                      <p className="font-medium text-foreground truncate flex items-center gap-1.5">
                        <FileText className="h-3.5 w-3.5 flex-shrink-0 text-muted-foreground" />
                        {s.statement_filename}
                      </p>
                      <p className="text-muted-foreground text-xs mt-0.5">
                        {txnCountByStatement[s.statement_id]} duplicate transaction{txnCountByStatement[s.statement_id] !== 1 ? 's' : ''} in this group
                      </p>
                    </div>
                    {isKept && (
                      <span className="text-xs font-medium text-primary mt-0.5 flex-shrink-0">Keep</span>
                    )}
                  </label>
                );
              })}
            </div>

            <DialogFooter className="mt-4 gap-2">
              <Button variant="outline" onClick={onClose}>Cancel</Button>
              <Button
                variant="destructive"
                onClick={() => setConfirmed(true)}
                disabled={toDeleteStatements.length === 0}
              >
                <Trash2 className="h-4 w-4 mr-1.5" />
                Delete {toDeleteStatements.length} statement{toDeleteStatements.length !== 1 ? 's' : ''}
              </Button>
            </DialogFooter>
          </>
        ) : (
          <>
            <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive mb-4">
              <p className="font-semibold mb-1">Move to recycle bin</p>
              <p>
                The following {toDeleteStatements.length} statement{toDeleteStatements.length !== 1 ? 's' : ''} will be moved to the recycle bin:
              </p>
              <ul className="mt-2 space-y-1 list-disc list-inside text-xs">
                {toDeleteStatements.map(s => (
                  <li key={s.statement_id}>{s.statement_filename}</li>
                ))}
              </ul>
            </div>

            <DialogFooter className="gap-2">
              <Button variant="outline" onClick={() => setConfirmed(false)} disabled={mutation.isPending}>
                Back
              </Button>
              <Button
                variant="destructive"
                onClick={() => mutation.mutate()}
                disabled={mutation.isPending}
              >
                {mutation.isPending ? 'Moving to recycle bin…' : 'Confirm'}
              </Button>
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}

// ── Bulk "Review All Groups" Modal (statement-level) ─────────────────────────

interface BulkReviewModalProps {
  groups: DuplicateTxnEntry[][];
  onClose: () => void;
  onDone: () => void;
}

function BulkReviewModal({ groups, onClose, onDone }: BulkReviewModalProps) {
  // For each group, derive unique statements and track which statement to keep
  const groupStatements = groups.map(g =>
    Array.from(new Map(g.map(t => [t.statement_id, t])).values())
  );
  const [keepStatementIds, setKeepStatementIds] = useState<Record<number, number>>(
    Object.fromEntries(groupStatements.map((stmts, i) => [i, stmts[0]?.statement_id]))
  );
  const [step, setStep] = useState<'select' | 'confirm'>('select');
  const queryClient = useQueryClient();

  // Collect unique statement IDs to delete across all groups (deduplicated)
  const allToDeleteMap = new Map<number, string>();
  groupStatements.forEach((stmts, gi) => {
    stmts
      .filter(s => s.statement_id !== keepStatementIds[gi])
      .forEach(s => allToDeleteMap.set(s.statement_id, s.statement_filename));
  });
  const allToDelete = Array.from(allToDeleteMap.entries()).map(([id, filename]) => ({ id, filename }));

  const mutation = useMutation({
    mutationFn: async () => {
      for (const s of allToDelete) {
        await bankStatementApi.delete(s.id);
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['duplicate-transactions'] });
      queryClient.invalidateQueries({ queryKey: ['statements'] });
      toast.success(
        `${allToDelete.length} statement${allToDelete.length !== 1 ? 's' : ''} moved to recycle bin.`
      );
      onDone();
    },
    onError: (err: any) => {
      toast.error(err?.message || 'Failed to delete statements.');
    },
  });

  // Filter to groups that actually span multiple statements
  const multiStatementGroups = groupStatements.filter(stmts => stmts.length > 1);

  return (
    <Dialog open onOpenChange={open => { if (!open) onClose(); }}>
      <DialogContent className="max-w-2xl max-h-[85vh] flex flex-col">
        <DialogHeader>
          <DialogTitle>Review All {groups.length} Duplicate Groups</DialogTitle>
        </DialogHeader>

        {step === 'select' ? (
          <>
            <p className="text-sm text-muted-foreground mb-3">
              For each group, select the <span className="font-semibold text-foreground">statement to keep</span>.
              The others will be moved to the recycle bin.
            </p>

            {multiStatementGroups.length === 0 ? (
              <p className="text-sm text-muted-foreground py-4 text-center">
                All duplicate transactions belong to the same statement in every group — nothing to delete.
              </p>
            ) : (
              <div className="flex-1 overflow-y-auto space-y-4 pr-1">
                {groups.map((group, gi) => {
                  const stmts = groupStatements[gi];
                  if (stmts.length < 2) return null;
                  const txnCountByStatement = group.reduce<Record<number, number>>((acc, t) => {
                    acc[t.statement_id] = (acc[t.statement_id] ?? 0) + 1;
                    return acc;
                  }, {});
                  return (
                    <div key={gi} className="rounded-lg border border-border p-3">
                      <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground mb-1">
                        Group {gi + 1}
                      </p>
                      <p className="text-xs text-muted-foreground font-mono mb-2 truncate">
                        {group[0]?.description} · {group[0]?.date} · {formatAmount(group[0]?.amount)}
                      </p>
                      <div className="space-y-1.5">
                        {stmts.map(s => {
                          const isKept = s.statement_id === keepStatementIds[gi];
                          return (
                            <label
                              key={s.statement_id}
                              className={`flex items-start gap-3 rounded-md border p-2.5 cursor-pointer transition-colors ${
                                isKept
                                  ? 'border-primary bg-primary/5'
                                  : 'border-border bg-muted/20 hover:bg-muted/40'
                              }`}
                            >
                              <input
                                type="radio"
                                name={`keep-stmt-group-${gi}`}
                                value={s.statement_id}
                                checked={isKept}
                                onChange={() => setKeepStatementIds(prev => ({ ...prev, [gi]: s.statement_id }))}
                                className="mt-0.5 accent-primary"
                              />
                              <div className="flex-1 min-w-0 text-xs">
                                <p className="font-medium text-foreground truncate flex items-center gap-1.5">
                                  <FileText className="h-3 w-3 flex-shrink-0 text-muted-foreground" />
                                  {s.statement_filename}
                                </p>
                                <p className="text-muted-foreground mt-0.5">
                                  {txnCountByStatement[s.statement_id]} duplicate transaction{txnCountByStatement[s.statement_id] !== 1 ? 's' : ''} in this group
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
                  );
                })}
              </div>
            )}

            <DialogFooter className="mt-4 gap-2 border-t pt-4">
              <Button variant="outline" onClick={onClose}>Cancel</Button>
              <Button
                variant="destructive"
                onClick={() => setStep('confirm')}
                disabled={allToDelete.length === 0}
              >
                <Trash2 className="h-4 w-4 mr-1.5" />
                Delete {allToDelete.length} statement{allToDelete.length !== 1 ? 's' : ''}
              </Button>
            </DialogFooter>
          </>
        ) : (
          <>
            <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive mb-4 max-h-72 overflow-y-auto">
              <p className="font-semibold mb-1">Move to recycle bin</p>
              <p>
                The following {allToDelete.length} statement{allToDelete.length !== 1 ? 's' : ''} will be moved to the recycle bin:
              </p>
              <ul className="mt-2 space-y-1 list-disc list-inside text-xs">
                {allToDelete.map(s => (
                  <li key={s.id}>{s.filename}</li>
                ))}
              </ul>
            </div>

            <DialogFooter className="gap-2">
              <Button variant="outline" onClick={() => setStep('select')} disabled={mutation.isPending}>
                Back
              </Button>
              <Button
                variant="destructive"
                onClick={() => mutation.mutate()}
                disabled={mutation.isPending}
              >
                {mutation.isPending ? 'Moving to recycle bin…' : 'Confirm'}
              </Button>
            </DialogFooter>
          </>
        )}
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

    </>
  );
}
