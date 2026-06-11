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
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { AlertTriangle, Loader2, Tag as TagIcon, X } from 'lucide-react';
import { toast } from 'sonner';
import {
  expenseApi,
  MergeErrorDetail,
  MergePreviewResult,
  MergeResult,
} from '@/lib/api/expenses';
import { MarkdownView } from '@/components/markdown/MarkdownView';
import { MarkdownEditor } from '@/components/markdown/MarkdownEditor';

const KEEP_SOURCES_STORAGE_KEY = 'expense-merge-keep-sources';

function loadKeepSourcesPref(): boolean {
  try {
    return window.localStorage.getItem(KEEP_SOURCES_STORAGE_KEY) === 'true';
  } catch {
    return false;
  }
}

function saveKeepSourcesPref(value: boolean): void {
  try {
    window.localStorage.setItem(KEEP_SOURCES_STORAGE_KEY, value ? 'true' : 'false');
  } catch {
    /* localStorage unavailable (private mode / quota) — fine to ignore */
  }
}

interface MergeExpensesModalProps {
  isOpen: boolean;
  expenseIds: number[];
  onClose: () => void;
  onMerged: (result: MergeResult) => void;
}

const formatAmount = (amount: number, currency: string) =>
  `${currency} ${amount.toFixed(2)}`;

export function MergeExpensesModal({
  isOpen,
  expenseIds,
  onClose,
  onMerged,
}: MergeExpensesModalProps) {
  const [preview, setPreview] = useState<MergePreviewResult | null>(null);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [userTagInput, setUserTagInput] = useState('');
  const [userTags, setUserTags] = useState<string[]>([]);
  const [notesPrefix, setNotesPrefix] = useState('');
  const [errorDetail, setErrorDetail] = useState<MergeErrorDetail | null>(null);
  // Persisted per-user choice: remember whether they want to keep originals.
  const [keepSources, setKeepSources] = useState<boolean>(() => loadKeepSourcesPref());

  // Fetch preview when modal opens or selection changes
  useEffect(() => {
    if (!isOpen) return;
    setPreview(null);
    setUserTagInput('');
    setUserTags([]);
    setNotesPrefix('');
    setErrorDetail(null);
    // Re-read persisted choice in case another tab changed it while this one was idle
    const persistedKeep = loadKeepSourcesPref();
    setKeepSources(persistedKeep);
    setLoadingPreview(true);
    expenseApi
      .getMergePreview({ expense_ids: expenseIds, keep_sources: persistedKeep })
      .then((p) => setPreview(p))
      .catch((err: any) => {
        const detail = err?.response?.data?.detail;
        if (detail && typeof detail === 'object' && 'code' in detail) {
          setErrorDetail(detail as MergeErrorDetail);
        } else {
          toast.error(err?.message || 'Failed to load merge preview');
        }
      })
      .finally(() => setLoadingPreview(false));
  }, [isOpen, expenseIds]);

  // Refresh preview when tags/notes/keepSources change so user sees the updated payload
  useEffect(() => {
    if (!isOpen || !preview || errorDetail) return;
    const handle = setTimeout(() => {
      expenseApi
        .getMergePreview({
          expense_ids: expenseIds,
          user_tags: userTags,
          notes_prefix: notesPrefix,
          keep_sources: keepSources,
        })
        .then(setPreview)
        .catch(() => {
          /* keep current preview on transient failure */
        });
    }, 300);
    return () => clearTimeout(handle);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userTags, notesPrefix, keepSources]);

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

  const allLabels = useMemo(() => {
    if (!preview) return [] as { label: string; isUser: boolean }[];
    const seen = new Set<string>();
    const out: { label: string; isUser: boolean }[] = [];
    preview.labels.forEach((label) => {
      const key = label.toLowerCase();
      if (!seen.has(key)) {
        seen.add(key);
        out.push({ label, isUser: userTags.some((t) => t.toLowerCase() === key) });
      }
    });
    return out;
  }, [preview, userTags]);

  const submit = async () => {
    setSubmitting(true);
    try {
      const result = await expenseApi.mergeExpenses({
        expense_ids: expenseIds,
        user_tags: userTags,
        notes_prefix: notesPrefix || null,
        keep_sources: keepSources,
      });
      // Persist the choice now that it's been used successfully.
      saveKeepSourcesPref(keepSources);
      toast.success(
        `Merged ${result.source_count} expenses into Expense #${result.expense_id}`
      );
      onMerged(result);
      onClose();
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      if (detail && typeof detail === 'object' && 'code' in detail) {
        setErrorDetail(detail as MergeErrorDetail);
      } else {
        toast.error(err?.message || 'Failed to merge expenses');
      }
    } finally {
      setSubmitting(false);
    }
  };

  const canSubmit = preview != null && !errorDetail && !loadingPreview && !submitting;

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && !submitting && onClose()}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Merge {expenseIds.length} expenses</DialogTitle>
          <DialogDescription>
            Creates one consolidated expense. Sources are moved to the recycle bin
            (restorable), and their attachments are re-linked to the merged expense.
          </DialogDescription>
        </DialogHeader>

        {loadingPreview && !preview && (
          <div className="flex items-center justify-center py-12 text-muted-foreground">
            <Loader2 className="w-5 h-5 mr-2 animate-spin" />
            Loading preview…
          </div>
        )}

        {errorDetail && (
          <div className="rounded-lg border border-destructive/60 bg-destructive/10 p-3 text-sm">
            <div className="flex items-start gap-2">
              <AlertTriangle className="w-4 h-4 mt-0.5 text-destructive" />
              <div>
                <div className="font-semibold text-destructive">Cannot merge</div>
                <div className="mt-1 text-destructive/90">{errorDetail.message}</div>
              </div>
            </div>
          </div>
        )}

        {preview && !errorDetail && (
          <div className="space-y-4">
            {/* Summary */}
            <div className="grid grid-cols-3 gap-3 rounded-lg border bg-muted/30 p-3 text-sm">
              <div>
                <div className="text-xs text-muted-foreground">Sources</div>
                <div className="font-semibold">{preview.count}</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">Total</div>
                <div className="font-semibold">{formatAmount(preview.total, preview.currency)}</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">Latest date</div>
                <div className="font-semibold">{preview.latest_date || '—'}</div>
              </div>
            </div>

            {/* Auto-derived locked fields */}
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div>
                <div className="text-xs text-muted-foreground">Category</div>
                <div className="font-medium">{preview.category || '—'}</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">Vendor</div>
                <div className="font-medium">{preview.vendor || '—'}</div>
              </div>
            </div>

            {/* Sources list */}
            <div>
              <Label className="text-xs">Source expenses</Label>
              <ScrollArea className="mt-1 h-40 rounded-md border">
                <ul className="divide-y text-sm">
                  {preview.sources.map((s) => (
                    <li key={s.id} className="flex items-center justify-between gap-2 px-3 py-2">
                      <div className="min-w-0 flex-1">
                        <div className="truncate">
                          <Badge variant="outline" className="mr-2 text-[10px]">#{s.id}</Badge>
                          {s.vendor || '—'}
                        </div>
                        <div className="text-xs text-muted-foreground">
                          {s.expense_date || '—'}
                          {s.category && <> · {s.category}</>}
                        </div>
                      </div>
                      <span className="font-mono text-sm">
                        {s.amount.toFixed(2)} {s.currency}
                      </span>
                    </li>
                  ))}
                </ul>
              </ScrollArea>
            </div>

            {/* Labels */}
            <div>
              <Label className="text-xs">Labels</Label>
              <div className="mt-1 flex flex-wrap items-center gap-1">
                {allLabels.map(({ label, isUser }) => (
                  <Badge
                    key={label}
                    variant={isUser ? 'default' : 'outline'}
                    className="text-xs gap-1"
                  >
                    <TagIcon className="w-3 h-3" />
                    {label}
                    {isUser && (
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
                ))}
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
                  placeholder="Add a tag"
                  disabled={submitting}
                />
                <Button type="button" variant="outline" onClick={addTag} disabled={submitting}>
                  Add
                </Button>
              </div>
            </div>

            {/* Notes prefix (free text) */}
            <div>
              <Label className="text-xs">Notes (optional prefix)</Label>
              <MarkdownEditor
                value={notesPrefix}
                onChange={setNotesPrefix}
                placeholder="Why are these expenses being merged?"
                rows={3}
                hideHint
              />
            </div>

            {/* Auto notes preview */}
            <div>
              <Label className="text-xs">Notes preview</Label>
              <div className="mt-1 max-h-40 overflow-auto rounded-md border bg-muted/30 p-3">
                <MarkdownView source={preview.notes_preview} proseSize="prose-xs" />
              </div>
            </div>

            {/* Warning banner + disposition picker */}
            <div className="rounded-lg border border-warning/30 bg-warning/10 p-3 text-sm">
              <div className="flex items-start gap-2">
                <AlertTriangle className="w-4 h-4 mt-0.5 text-warning" />
                <div className="flex-1">
                  <div className="font-semibold text-warning">
                    What should happen to the {preview.count} source expenses?
                  </div>
                  <RadioGroup
                    value={keepSources ? 'keep' : 'consolidate'}
                    onValueChange={(v) => setKeepSources(v === 'keep')}
                    className="mt-2 gap-2"
                    aria-label="Source disposition"
                  >
                    <label className="flex items-start gap-2 cursor-pointer">
                      <RadioGroupItem
                        value="consolidate"
                        id="merge-disposition-consolidate"
                        className="mt-1"
                      />
                      <div className="text-warning">
                        <div className="font-medium">Move sources to recycle bin</div>
                        <div className="text-xs text-warning/80">
                          Attachments are re-linked to the merged expense.
                          Sources are restorable from the recycle bin.
                        </div>
                      </div>
                    </label>
                    <label className="flex items-start gap-2 cursor-pointer">
                      <RadioGroupItem
                        value="keep"
                        id="merge-disposition-keep"
                        className="mt-1"
                      />
                      <div className="text-warning">
                        <div className="font-medium">
                          Keep sources visible alongside the merged expense
                        </div>
                        <div className="text-xs text-warning/80">
                          Source expenses stay active. Attachments are duplicated
                          (same files, separate records) so they appear on both.
                        </div>
                      </div>
                    </label>
                  </RadioGroup>
                </div>
              </div>
            </div>
          </div>
        )}

        <DialogFooter>
          <Button type="button" variant="ghost" onClick={onClose} disabled={submitting}>
            Cancel
          </Button>
          <Button type="button" onClick={submit} disabled={!canSubmit}>
            {submitting && <Loader2 className="w-4 h-4 mr-1 animate-spin" />}
            Merge expenses
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
