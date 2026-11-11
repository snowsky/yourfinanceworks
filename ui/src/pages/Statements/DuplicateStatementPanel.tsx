import { useState } from 'react';
import { useTranslation } from 'react-i18next';
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

type TFn = (key: string, options?: Record<string, unknown>) => string;
// Explicit `<key>One` / `<key>Many` pairs, as elsewhere in the app.
const pluralizer = (t: TFn) => (base: string, count: number) =>
  t(count === 1 ? `${base}One` : `${base}Many`, { count });

// ── Per-group Delete Modal ────────────────────────────────────────────────────

interface DeleteModalProps {
  group: FileDuplicateEntry[];
  groupIndex: number;
  onClose: () => void;
  onDeleted: () => void;
}

function DeleteModal({ group, groupIndex, onClose, onDeleted }: DeleteModalProps) {
  const { t } = useTranslation();
  const plural = pluralizer(t);
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
        plural('statements.duplicateFiles.moved', toDelete.length)
      );
      onDeleted();
    },
    onError: (err: any) => {
      toast.error(err?.message || t('statements.duplicateFiles.deleteFailed'));
    },
  });

  return (
    <Dialog open onOpenChange={open => { if (!open) onClose(); }}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>{t('statements.duplicateFiles.removeTitle', { group: groupIndex + 1 })}</DialogTitle>
        </DialogHeader>

        {!confirmed ? (
          <>
            <p className="text-sm text-muted-foreground mb-3">
              {t('statements.duplicateFiles.removeIntro')}
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
                        {plural('statements.duplicateFiles.transactionCount', s.extracted_count)}
                        {s.created_at && (
                          <> · {t('statements.duplicateFiles.uploadedOn', { date: new Date(s.created_at).toLocaleDateString() })}</>
                        )}
                        {' · '}
                        <span className="capitalize">{s.status}</span>
                      </p>
                    </div>
                    {isKept && (
                      <span className="text-xs font-medium text-primary mt-0.5 flex-shrink-0">{t('statements.duplicateFiles.keep')}</span>
                    )}
                  </label>
                );
              })}
            </div>

            <DialogFooter className="mt-4 gap-2">
              <Button variant="outline" onClick={onClose}>{t('common.cancel')}</Button>
              <Button
                variant="destructive"
                onClick={() => setConfirmed(true)}
                disabled={toDelete.length === 0}
              >
                <Trash2 className="h-4 w-4 mr-1.5" />
                {plural('statements.duplicateFiles.deleteCount', toDelete.length)}
              </Button>
            </DialogFooter>
          </>
        ) : (
          <>
            <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive mb-4">
              <p className="font-semibold mb-1">{t('statements.duplicateFiles.moveToBin')}</p>
              <p>
                {plural('statements.duplicateFiles.moveToBinBody', toDelete.length)}
              </p>
              <ul className="mt-2 space-y-1 list-disc list-inside text-xs">
                {toDelete.map(s => (
                  <li key={s.id}>{s.original_filename}</li>
                ))}
              </ul>
            </div>

            <DialogFooter className="gap-2">
              <Button variant="outline" onClick={() => setConfirmed(false)} disabled={mutation.isPending}>
                {t('statements.duplicateFiles.back')}
              </Button>
              <Button
                variant="destructive"
                onClick={() => mutation.mutate()}
                disabled={mutation.isPending}
              >
                {mutation.isPending ? t('statements.duplicateFiles.moving') : t('statements.duplicateFiles.confirm')}
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
  const { t } = useTranslation();
  const plural = pluralizer(t);
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
      <div className="rounded-xl border border-warning/30 bg-warning/10 mb-3 overflow-hidden shadow-sm">
        {/* Header */}
        <button
          className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-warning/20 transition-colors"
          onClick={() => setExpanded(v => !v)}
          aria-expanded={expanded}
        >
          <Copy className="h-4 w-4 text-warning flex-shrink-0" />
          <span className="flex-1 text-sm font-medium text-warning">
            {plural('statements.duplicateFiles.detected', count)}{' '}
            <span className="font-normal opacity-80">
              {expanded ? t('statements.duplicateFiles.clickToHide') : t('statements.duplicateFiles.clickToReview')}
            </span>
          </span>
          {expanded
            ? <ChevronUp className="h-4 w-4 text-warning flex-shrink-0" />
            : <ChevronDown className="h-4 w-4 text-warning flex-shrink-0" />
          }
        </button>

        {/* Expandable body */}
        {expanded && (
          <div className="border-t border-warning/30 divide-y divide-warning/30">
            {groups.map((group, gi) => (
              <div key={gi} className="bg-card">
                {/* Group header */}
                <div className="flex items-center gap-2 px-4 py-2.5">
                  <button
                    className="flex items-center gap-2 flex-1 text-left hover:bg-warning/10 transition-colors rounded"
                    onClick={() => toggleGroup(gi)}
                  >
                    <span className="text-xs font-bold uppercase tracking-wider text-warning min-w-[60px]">
                      {t('statements.duplicateFiles.group', { group: gi + 1 })}
                    </span>
                    <span className="flex-1 text-xs text-muted-foreground truncate">
                      <span className="font-medium text-foreground mr-2">{group[0].original_filename}</span>
                      <span className="text-warning">
                        · {plural('statements.duplicateFiles.identicalCopies', group.length)}
                      </span>
                    </span>
                    {expandedGroups.has(gi)
                      ? <ChevronUp className="h-3.5 w-3.5 text-muted-foreground flex-shrink-0" />
                      : <ChevronDown className="h-3.5 w-3.5 text-muted-foreground flex-shrink-0" />
                    }
                  </button>

                  <button
                    onClick={e => { e.stopPropagation(); setDeleteGroupIndex(gi); }}
                    className="flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium bg-destructive/10 text-destructive hover:bg-destructive/20 transition-colors flex-shrink-0 whitespace-nowrap"
                  >
                    <Trash2 className="h-3 w-3" />
                    {t('statements.duplicateFiles.deleteDuplicate')}
                  </button>
                </div>

                {/* Statement rows */}
                {expandedGroups.has(gi) && (
                  <div className="px-4 pb-3 space-y-1.5">
                    {group.map((s, si) => (
                      <div
                        key={si}
                        className="flex items-center gap-3 rounded-lg border border-warning/20 bg-warning/5 px-3 py-2 text-xs"
                      >
                        <FileText className="h-3.5 w-3.5 text-warning flex-shrink-0" />
                        <div className="flex-1 min-w-0">
                          <span className="font-medium text-foreground truncate block">{s.original_filename}</span>
                          <span className="text-muted-foreground">
                            {plural('statements.duplicateFiles.transactionCount', s.extracted_count)}
                            {s.created_at && <> · {new Date(s.created_at).toLocaleDateString()}</>}
                            {' · '}
                            <span className="capitalize">{s.status}</span>
                          </span>
                        </div>
                        <button
                          onClick={() => onViewStatement(s.id)}
                          className="flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium bg-warning/20 text-warning hover:bg-warning/30 transition-colors flex-shrink-0 whitespace-nowrap"
                        >
                          {t('statements.duplicateFiles.view')}
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
