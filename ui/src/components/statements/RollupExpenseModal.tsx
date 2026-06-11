import { useEffect, useMemo, useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Loader2, Tag as TagIcon, X, ExternalLink } from 'lucide-react';
import { toast } from 'sonner';
import {
  bankStatementApi,
  RollupPreview,
  RollupCreateResult,
  RollupConflictDetail,
} from '@/lib/api/bank-statements';
import { MarkdownView } from '@/components/markdown/MarkdownView';
import { formatMoney } from '@/lib/money';

interface RollupExpenseModalProps {
  isOpen: boolean;
  statementId: number | null;
  onClose: () => void;
  onCreated: (result: RollupCreateResult) => void;
  onOpenExpense?: (expenseId: number) => void;
}

const formatAmount = (amount: number, currency: string) =>
  `${currency} ${formatMoney(amount)}`;

export function RollupExpenseModal({
  isOpen,
  statementId,
  onClose,
  onCreated,
  onOpenExpense,
}: RollupExpenseModalProps) {
  const [preview, setPreview] = useState<RollupPreview | null>(null);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [userTagInput, setUserTagInput] = useState('');
  const [userTags, setUserTags] = useState<string[]>([]);
  const [conflict, setConflict] = useState<RollupConflictDetail | null>(null);

  // Reset state when modal opens for a different statement
  useEffect(() => {
    if (!isOpen || statementId == null) return;
    setPreview(null);
    setUserTagInput('');
    setUserTags([]);
    setConflict(null);
    setLoadingPreview(true);
    bankStatementApi
      .getRollupPreview(statementId)
      .then((p: RollupPreview) => {
        setPreview(p);
        if (p.existing_rollup_id) {
          setConflict({
            message: 'A rollup expense already exists for this statement.',
            existing_expense_id: p.existing_rollup_id,
          });
        }
      })
      .catch((err: { message?: string }) => toast.error(err?.message || 'Failed to load preview'))
      .finally(() => setLoadingPreview(false));
  }, [isOpen, statementId]);

  const addTag = () => {
    const v = userTagInput.trim();
    if (!v) return;
    if (userTags.some((t) => t.toLowerCase() === v.toLowerCase())) {
      setUserTagInput('');
      return;
    }
    setUserTags([...userTags, v]);
    setUserTagInput('');
  };

  const removeTag = (tag: string) => {
    setUserTags(userTags.filter((t) => t !== tag));
  };

  // Auto labels + user tags combined preview (matches backend cap of 10)
  const allLabels = useMemo(() => {
    if (!preview) return [] as string[];
    const seen = new Set<string>();
    const out: string[] = [];
    [...preview.auto_labels, ...userTags].forEach((label) => {
      const key = label.toLowerCase();
      if (!seen.has(key) && out.length < 10) {
        seen.add(key);
        out.push(label);
      }
    });
    return out;
  }, [preview, userTags]);

  const submit = async (replace: boolean) => {
    if (statementId == null) return;
    setSubmitting(true);
    try {
      const result = await bankStatementApi.createRollupExpense(statementId, {
        user_tags: userTags,
        replace,
      });
      toast.success(`Rollup expense #${result.expense_id} created`);
      onCreated(result);
      onClose();
    } catch (err: any) {
      if (err?.status === 409 && err?.response?.data?.detail) {
        const detail = err.response.data.detail as RollupConflictDetail;
        setConflict(detail);
      } else {
        toast.error(err?.message || 'Failed to create rollup expense');
      }
    } finally {
      setSubmitting(false);
    }
  };

  const handleCreate = () => submit(false);
  const handleReplace = () => submit(true);

  const noDebits = preview != null && preview.count === 0;
  const blockedByConflict = conflict != null;

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && !submitting && onClose()}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Create rollup expense</DialogTitle>
          <DialogDescription>
            One bookkeeping expense that sums every debit transaction on this statement.
          </DialogDescription>
        </DialogHeader>

        {loadingPreview && (
          <div className="flex items-center justify-center py-12 text-muted-foreground">
            <Loader2 className="w-5 h-5 mr-2 animate-spin" />
            Loading preview…
          </div>
        )}

        {!loadingPreview && preview && (
          <div className="space-y-4">
            {/* Summary */}
            <div className="grid grid-cols-3 gap-3 rounded-lg border bg-muted/30 p-3 text-sm">
              <div>
                <div className="text-xs text-muted-foreground">Debits</div>
                <div className="font-semibold">{preview.count}</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">Total</div>
                <div className="font-semibold">{formatAmount(preview.total, preview.currency)}</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">Latest date</div>
                <div className="font-semibold">
                  {preview.latest_date ? preview.latest_date.slice(0, 10) : '—'}
                </div>
              </div>
            </div>

            {/* Conflict banner */}
            {blockedByConflict && (
              <div className="rounded-lg border border-warning/30 bg-warning/10 p-3 text-sm">
                <div className="font-semibold text-warning">
                  {conflict!.message}
                </div>
                <div className="mt-1 text-warning">
                  Existing rollup: Expense #{conflict!.existing_expense_id}
                </div>
                <div className="mt-2 flex gap-2">
                  {onOpenExpense && (
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => onOpenExpense(conflict!.existing_expense_id)}
                    >
                      <ExternalLink className="w-3.5 h-3.5 mr-1" /> Open
                    </Button>
                  )}
                  <Button
                    type="button"
                    variant="destructive"
                    size="sm"
                    onClick={handleReplace}
                    disabled={submitting || noDebits}
                  >
                    {submitting && <Loader2 className="w-3.5 h-3.5 mr-1 animate-spin" />}
                    Replace
                  </Button>
                </div>
              </div>
            )}

            {/* Debits list */}
            <div>
              <Label className="text-xs">Debit transactions included</Label>
              <ScrollArea className="mt-1 h-48 rounded-md border">
                {noDebits ? (
                  <div className="p-4 text-sm text-muted-foreground">
                    This statement has no debit transactions to roll up.
                  </div>
                ) : (
                  <ul className="divide-y text-sm">
                    {preview.debits.map((d) => (
                      <li
                        key={d.transaction_id}
                        className="flex items-center justify-between gap-2 px-3 py-2"
                      >
                        <div className="min-w-0 flex-1">
                          <div className="truncate">{d.description}</div>
                          <div className="text-xs text-muted-foreground">
                            {d.date.slice(0, 10)}
                            {d.category && <> · {d.category}</>}
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          {d.linked_expense_id != null && (
                            <Badge variant="secondary" className="text-[10px]">
                              linked #{d.linked_expense_id}
                            </Badge>
                          )}
                          <span className="font-mono text-sm">
                            {formatMoney(d.amount)}
                          </span>
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </ScrollArea>
            </div>

            {/* Tags */}
            <div>
              <Label className="text-xs">Tags</Label>
              <div className="mt-1 flex flex-wrap items-center gap-1">
                {allLabels.map((label) => {
                  const isAuto = !userTags.includes(label);
                  return (
                    <Badge
                      key={label}
                      variant={isAuto ? 'outline' : 'default'}
                      className="text-xs gap-1"
                    >
                      <TagIcon className="w-3 h-3" />
                      {label}
                      {!isAuto && (
                        <button
                          type="button"
                          onClick={() => removeTag(label)}
                          className="ml-1 rounded hover:bg-background/30"
                          aria-label={`Remove ${label}`}
                        >
                          <X className="w-3 h-3" />
                        </button>
                      )}
                    </Badge>
                  );
                })}
              </div>
              <div className="mt-2 flex gap-2">
                <Input
                  value={userTagInput}
                  onChange={(e) => setUserTagInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault();
                      addTag();
                    }
                  }}
                  placeholder="Add a tag (e.g. q1-trip)"
                  disabled={submitting}
                />
                <Button type="button" variant="outline" onClick={addTag} disabled={submitting}>
                  Add
                </Button>
              </div>
              <p className="mt-1 text-xs text-muted-foreground">
                Auto tags include the statement filename, distinct transaction categories, and
                an &ldquo;auto-imported&rdquo; marker. Up to 10 tags total.
              </p>
            </div>

            {/* Notes preview */}
            <div>
              <Label className="text-xs">Notes preview</Label>
              <div className="mt-1 max-h-48 overflow-auto rounded-md border bg-muted/30 p-3">
                <MarkdownView source={preview.notes_preview} proseSize="prose-xs" />
              </div>
            </div>
          </div>
        )}

        <DialogFooter>
          <Button type="button" variant="ghost" onClick={onClose} disabled={submitting}>
            Cancel
          </Button>
          {!blockedByConflict && (
            <Button
              type="button"
              onClick={handleCreate}
              disabled={submitting || loadingPreview || noDebits}
            >
              {submitting && <Loader2 className="w-4 h-4 mr-1 animate-spin" />}
              Create rollup expense
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
