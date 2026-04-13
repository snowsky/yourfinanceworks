import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { AlertTriangle, ChevronDown, ChevronUp, ExternalLink, Trash2 } from 'lucide-react';
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

interface ReviewModalProps {
  group: DuplicateTxnEntry[];
  groupIndex: number;
  onClose: () => void;
  onDeleted: () => void;
}

function ReviewModal({ group, groupIndex, onClose, onDeleted }: ReviewModalProps) {
  const [keepId, setKeepId] = useState<number>(group[0]?.id);
  const [confirmed, setConfirmed] = useState(false);
  const queryClient = useQueryClient();

  const toDelete = group.filter(t => t.id !== keepId);

  const mutation = useMutation({
    mutationFn: async () => {
      for (const txn of toDelete) {
        await bankStatementApi.deleteTransaction(txn.statement_id, txn.id);
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['duplicate-transactions'] });
      toast.success(
        toDelete.length === 1
          ? 'Duplicate transaction deleted.'
          : `${toDelete.length} duplicate transactions deleted.`
      );
      onDeleted();
    },
    onError: (err: any) => {
      toast.error(err?.message || 'Failed to delete transactions.');
    },
  });

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
              The others will be deleted.
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

            <DialogFooter className="mt-4 gap-2">
              <Button variant="outline" onClick={onClose}>Cancel</Button>
              <Button
                variant="destructive"
                onClick={() => setConfirmed(true)}
                disabled={toDelete.length === 0}
              >
                <Trash2 className="h-4 w-4 mr-1.5" />
                Delete {toDelete.length} duplicate{toDelete.length !== 1 ? 's' : ''}
              </Button>
            </DialogFooter>
          </>
        ) : (
          <>
            <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive mb-4">
              <p className="font-semibold mb-1">Confirm deletion</p>
              <p>
                The following {toDelete.length} transaction{toDelete.length !== 1 ? 's' : ''} will be
                permanently deleted:
              </p>
              <ul className="mt-2 space-y-1 list-disc list-inside text-xs">
                {toDelete.map(t => (
                  <li key={t.id}>
                    {t.description} · {t.date} · {formatAmount(t.amount)} — <span className="opacity-70">{t.statement_filename}</span>
                  </li>
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
                {mutation.isPending ? 'Deleting…' : 'Confirm Delete'}
              </Button>
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}

export function DuplicateTransactionPanel({ groups, onViewTransaction }: DuplicateTransactionPanelProps) {
  const [expanded, setExpanded] = useState(false);
  const [expandedGroups, setExpandedGroups] = useState<Set<number>>(new Set([0]));
  const [reviewGroupIndex, setReviewGroupIndex] = useState<number | null>(null);

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
        {/* Header row — always visible, click to expand */}
        <button
          className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-yellow-100 dark:hover:bg-yellow-900/30 transition-colors"
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

                  {/* Review & Delete button per group */}
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

      {/* Review & Delete modal */}
      {reviewGroupIndex !== null && groups[reviewGroupIndex] && (
        <ReviewModal
          group={groups[reviewGroupIndex]}
          groupIndex={reviewGroupIndex}
          onClose={() => setReviewGroupIndex(null)}
          onDeleted={() => setReviewGroupIndex(null)}
        />
      )}
    </>
  );
}
