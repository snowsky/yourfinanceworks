import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Copy, ChevronDown, ChevronUp, Trash2, FileText } from 'lucide-react';
import { toast } from 'sonner';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { bankStatementApi, type FileDuplicateEntry } from '@/lib/api/bank-statements';

interface DuplicateStatementPanelProps {
  groups: FileDuplicateEntry[][];
  onViewStatement: (id: number) => void;
}

// ── Per-group Delete Modal ────────────────────────────────────────────────────

interface DeleteModalProps {
  group: FileDuplicateEntry[];
  groupIndex: number;
  onClose: () => void;
  onDeleted: () => void;
}

function DeleteModal({ group, groupIndex, onClose, onDeleted }: DeleteModalProps) {
  // Default: keep the oldest (first uploaded), delete the rest
  const [keepId, setKeepId] = useState<number>(group[0].id);
  const [confirmed, setConfirmed] = useState(false);
  const queryClient = useQueryClient();

  const toDelete = group.filter(s => s.id !== keepId);

  const mutation = useMutation({
    mutationFn: async () => {
      for (const s of toDelete) {
        await bankStatementApi.delete(s.id);
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['file-duplicate-statements'] });
      queryClient.invalidateQueries({ queryKey: ['statements'] });
      toast.success(
        toDelete.length === 1
          ? 'Duplicate statement moved to recycle bin.'
          : `${toDelete.length} duplicate statements moved to recycle bin.`
      );
      onDeleted();
    },
    onError: (err: any) => {
      toast.error(err?.message || 'Failed to delete statement.');
    },
  });

  return (
    <Dialog open onOpenChange={open => { if (!open) onClose(); }}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Remove Duplicate Statement — Group {groupIndex + 1}</DialogTitle>
        </DialogHeader>

        {!confirmed ? (
          <>
            <p className="text-sm text-muted-foreground mb-3">
              These statements are <span className="font-semibold text-foreground">identical files</span> (same checksum).
              Select the one to <span className="font-semibold text-foreground">keep</span>; the others will be moved to the recycle bin.
            </p>

            <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
              {group.map(s => {
                const isKept = s.id === keepId;
                return (
                  <label
                    key={s.id}
                    className={`flex items-start gap-3 rounded-lg border p-3 cursor-pointer transition-colors ${
                      isKept
                        ? 'border-primary bg-primary/5'
                        : 'border-border bg-muted/30 hover:bg-muted/50'
                    }`}
                  >
                    <input
                      type="radio"
                      name={`keep-statement-${groupIndex}`}
                      value={s.id}
                      checked={isKept}
                      onChange={() => setKeepId(s.id)}
                      className="mt-0.5 accent-primary"
                    />
                    <div className="flex-1 min-w-0 text-sm">
                      <p className="font-medium text-foreground truncate flex items-center gap-1.5">
                        <FileText className="h-3.5 w-3.5 flex-shrink-0 text-muted-foreground" />
                        {s.original_filename}
                      </p>
                      <p className="text-muted-foreground text-xs mt-0.5">
                        {s.extracted_count} transactions
                        {s.created_at && (
                          <> · uploaded {new Date(s.created_at).toLocaleDateString()}</>
                        )}
                        {' · '}
                        <span className="capitalize">{s.status}</span>
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
              <p className="font-semibold mb-1">Move to recycle bin</p>
              <p>
                The following {toDelete.length} statement{toDelete.length !== 1 ? 's' : ''} will be
                moved to the recycle bin (can be restored later):
              </p>
              <ul className="mt-2 space-y-1 list-disc list-inside text-xs">
                {toDelete.map(s => (
                  <li key={s.id}>{s.original_filename}</li>
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

// ── Main Panel ────────────────────────────────────────────────────────────────

export function DuplicateStatementPanel({ groups, onViewStatement }: DuplicateStatementPanelProps) {
  const [expanded, setExpanded] = useState(false);
  const [expandedGroups, setExpandedGroups] = useState<Set<number>>(new Set([0]));
  const [deleteGroupIndex, setDeleteGroupIndex] = useState<number | null>(null);

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
      <div className="rounded-xl border border-orange-300 bg-orange-50 dark:bg-orange-950/20 dark:border-orange-800 mb-3 overflow-hidden shadow-sm">
        {/* Header */}
        <button
          className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-orange-100 dark:hover:bg-orange-900/30 transition-colors"
          onClick={() => setExpanded(v => !v)}
          aria-expanded={expanded}
        >
          <Copy className="h-4 w-4 text-orange-600 dark:text-orange-400 flex-shrink-0" />
          <span className="flex-1 text-sm font-medium text-orange-800 dark:text-orange-300">
            <span className="font-bold">{count}</span>{' '}
            duplicate statement {count !== 1 ? 'files' : 'file'} detected (identical checksums).{' '}
            <span className="font-normal opacity-80">Click to {expanded ? 'hide' : 'review'}.</span>
          </span>
          {expanded
            ? <ChevronUp className="h-4 w-4 text-orange-600 dark:text-orange-400 flex-shrink-0" />
            : <ChevronDown className="h-4 w-4 text-orange-600 dark:text-orange-400 flex-shrink-0" />
          }
        </button>

        {/* Expandable body */}
        {expanded && (
          <div className="border-t border-orange-200 dark:border-orange-800 divide-y divide-orange-200 dark:divide-orange-800">
            {groups.map((group, gi) => (
              <div key={gi} className="bg-white dark:bg-background">
                {/* Group header */}
                <div className="flex items-center gap-2 px-4 py-2.5">
                  <button
                    className="flex items-center gap-2 flex-1 text-left hover:bg-orange-50 dark:hover:bg-orange-950/10 transition-colors rounded"
                    onClick={() => toggleGroup(gi)}
                  >
                    <span className="text-xs font-bold uppercase tracking-wider text-orange-700 dark:text-orange-400 min-w-[60px]">
                      Group {gi + 1}
                    </span>
                    <span className="flex-1 text-xs text-muted-foreground truncate">
                      <span className="font-medium text-foreground mr-2">{group[0].original_filename}</span>
                      <span className="text-orange-600 dark:text-orange-500">
                        · {group.length} identical copies
                      </span>
                    </span>
                    {expandedGroups.has(gi)
                      ? <ChevronUp className="h-3.5 w-3.5 text-muted-foreground flex-shrink-0" />
                      : <ChevronDown className="h-3.5 w-3.5 text-muted-foreground flex-shrink-0" />
                    }
                  </button>

                  <button
                    onClick={e => { e.stopPropagation(); setDeleteGroupIndex(gi); }}
                    className="flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400 hover:bg-red-200 dark:hover:bg-red-800/40 transition-colors flex-shrink-0 whitespace-nowrap"
                  >
                    <Trash2 className="h-3 w-3" />
                    Delete Duplicate
                  </button>
                </div>

                {/* Statement rows */}
                {expandedGroups.has(gi) && (
                  <div className="px-4 pb-3 space-y-1.5">
                    {group.map((s, si) => (
                      <div
                        key={si}
                        className="flex items-center gap-3 rounded-lg border border-orange-100 dark:border-orange-900/40 bg-orange-50/50 dark:bg-orange-950/10 px-3 py-2 text-xs"
                      >
                        <FileText className="h-3.5 w-3.5 text-orange-600 dark:text-orange-400 flex-shrink-0" />
                        <div className="flex-1 min-w-0">
                          <span className="font-medium text-foreground truncate block">{s.original_filename}</span>
                          <span className="text-muted-foreground">
                            {s.extracted_count} transactions
                            {s.created_at && <> · {new Date(s.created_at).toLocaleDateString()}</>}
                            {' · '}
                            <span className="capitalize">{s.status}</span>
                          </span>
                        </div>
                        <button
                          onClick={() => onViewStatement(s.id)}
                          className="flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium bg-orange-200 dark:bg-orange-800/40 text-orange-800 dark:text-orange-300 hover:bg-orange-300 dark:hover:bg-orange-700/50 transition-colors flex-shrink-0 whitespace-nowrap"
                        >
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

      {deleteGroupIndex !== null && groups[deleteGroupIndex] && (
        <DeleteModal
          group={groups[deleteGroupIndex]}
          groupIndex={deleteGroupIndex}
          onClose={() => setDeleteGroupIndex(null)}
          onDeleted={() => setDeleteGroupIndex(null)}
        />
      )}
    </>
  );
}
