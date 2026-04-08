import { useTranslation } from 'react-i18next';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Checkbox } from '@/components/ui/checkbox';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import {
  Eye, Download, ExternalLink, Trash2, Plus, X, MoreHorizontal, Loader2,
  RotateCcw, Search, Tag, Minus, Filter, Share2, Archive
} from 'lucide-react';
import { Wand } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { ProfessionalCard } from '@/components/ui/professional-card';
import { ProfessionalButton } from '@/components/ui/professional-button';
import { ShareButton } from '@/components/sharing/ShareButton';
import { ColumnPicker } from '@/components/ui/column-picker';
import { bankStatementApi, BankStatementSummary, formatStatus } from '@/lib/api';
import { toast } from 'sonner';
import { StatusBadge } from './StatusBadge';
import { CardTypeBadge } from './CardTypeBadge';
import { STATEMENT_COLUMNS, STATEMENT_STATUSES } from './types';

interface StatementsListViewProps {
  // Filters
  searchQuery: string;
  setSearchQuery: (v: string) => void;
  statusFilter: string;
  setStatusFilter: (v: string) => void;
  labelFilter: string;
  setLabelFilter: (v: string) => void;
  pageSize: number;
  setPageSize: (v: number) => void;
  page: number;
  setPage: (fn: (prev: number) => number) => void;
  // Column visibility
  isVisible: (key: string) => boolean;
  toggle: (key: string) => void;
  reset: () => void;
  hiddenCount: number;
  // Data
  statements: BankStatementSummary[];
  setStatements: (fn: (prev: BankStatementSummary[]) => BankStatementSummary[]) => void;
  loading: boolean;
  totalStatements: number;
  // Selection
  selectedIds: number[];
  setSelectedIds: (fn: (prev: number[]) => number[]) => void;
  // Labels
  bulkLabel: string;
  setBulkLabel: (v: string) => void;
  newLabelValueById: Record<number, string>;
  setNewLabelValueById: (fn: (prev: Record<number, string>) => Record<number, string>) => void;
  // Review
  handleReviewClick: (s: BankStatementSummary) => void;
  handleRunReview: (id: number) => void;
  handleCancelReview: (id: number) => void;
  handleBulkRunReview: () => void;
  // Bulk
  exportSelectedAsZip: () => void;
  setBulkDeleteModalOpen: (v: boolean) => void;
  setBulkMergeModalOpen: (v: boolean) => void;
  // Row actions
  openStatement: (id: number) => void;
  handlePreview: (id: number) => void;
  handleDownload: (id: number, filename?: string) => void;
  // Delete
  setStatementToDelete: (id: number) => void;
  setDeleteModalOpen: (v: boolean) => void;
  // Misc
  reprocessingLocks: Set<number>;
  setReprocessingLocks: (fn: (prev: Set<number>) => Set<number>) => void;
  previewLoading: number | null;
  shareStatementId: number | null;
  setShareStatementId: (id: number | null) => void;
  getLocale: string;
  timezone: string;
  loadList: () => void;
}

export function StatementsListView({
  searchQuery, setSearchQuery,
  statusFilter, setStatusFilter,
  labelFilter, setLabelFilter,
  pageSize, setPageSize,
  page, setPage,
  isVisible, toggle, reset, hiddenCount,
  statements, setStatements, loading, totalStatements,
  selectedIds, setSelectedIds,
  bulkLabel, setBulkLabel,
  newLabelValueById, setNewLabelValueById,
  handleReviewClick, handleRunReview, handleCancelReview, handleBulkRunReview,
  exportSelectedAsZip, setBulkDeleteModalOpen, setBulkMergeModalOpen,
  openStatement, handlePreview, handleDownload,
  setStatementToDelete, setDeleteModalOpen,
  reprocessingLocks, setReprocessingLocks,
  previewLoading, shareStatementId, setShareStatementId,
  getLocale, timezone, loadList,
}: StatementsListViewProps) {
  const { t } = useTranslation();

  const isCompleted = (s: { status?: string }) =>
    s.status === 'processed' || s.status === 'done' || s.status === 'failed' || s.status === 'uploaded' || s.status === 'merged';

  const totalPages = Math.ceil(totalStatements / pageSize);

  return (
    <ProfessionalCard className="slide-in" variant="elevated">
      <div className="space-y-6">
        {/* Header with filters */}
        <div className="flex flex-col lg:flex-row justify-between gap-6 pb-6 border-b border-border/50">
          <div>
            <h2 className="text-2xl font-bold text-foreground">{t('statements.list_title')}</h2>
          </div>
          <div className="flex flex-col sm:flex-row gap-3 items-start sm:items-center">
            {/* Search */}
            <div className="relative w-full sm:w-auto">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder={t('statements.search_placeholder')}
                className="pl-9 w-full sm:w-[240px] h-10 rounded-lg border-border/50 bg-muted/30 focus:bg-background transition-colors"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
              {searchQuery && (
                <button
                  aria-label="Clear search"
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                  onClick={() => setSearchQuery('')}
                >
                  <X className="w-4 h-4" />
                </button>
              )}
            </div>

            {/* Status Filter */}
            <div className="flex items-center gap-2">
              <Filter className="h-4 w-4 text-muted-foreground" />
              <Select value={statusFilter} onValueChange={setStatusFilter}>
                <SelectTrigger className="w-full sm:w-[170px] h-10 rounded-lg border-border/50 bg-muted/30">
                  <SelectValue placeholder={t('statements.filter_by_status', { defaultValue: 'Filter by status' })} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">{t('statements.all_statuses', { defaultValue: 'All Statuses' })}</SelectItem>
                  {STATEMENT_STATUSES.map((status) => (
                    <SelectItem key={status} value={status}>
                      {t(`statements.status.${status}`, { defaultValue: formatStatus(status) })}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Label Filter */}
            <div className="relative">
              <Tag className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder={t('statements.filter_by_label', { defaultValue: 'Filter by label' })}
                className="pl-9 w-full sm:w-[150px] h-10 rounded-lg border-border/50 bg-muted/30 focus:bg-background transition-colors"
                value={labelFilter}
                onChange={(e) => setLabelFilter(e.target.value)}
              />
              {labelFilter && (
                <button
                  aria-label="Clear label filter"
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                  onClick={() => setLabelFilter('')}
                >
                  <X className="w-4 h-4" />
                </button>
              )}
            </div>

            {/* Page Size */}
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground">{t('common.page_size', { defaultValue: 'Page Size' })}</span>
              <Select value={String(pageSize)} onValueChange={(v) => { setPageSize(Number(v)); setPage(() => 1); }}>
                <SelectTrigger className="w-[100px] h-10 rounded-lg border-border/50 bg-muted/30">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {[10, 20, 50, 100].map(n => (
                    <SelectItem key={n} value={String(n)}>{n}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <ColumnPicker
              columns={STATEMENT_COLUMNS}
              isVisible={isVisible}
              onToggle={toggle}
              onReset={reset}
              hiddenCount={hiddenCount}
            />
          </div>
        </div>

        {/* Selection Toolbar */}
        {selectedIds.length > 0 && (
          <div className="flex flex-col md:flex-row items-center justify-between p-4 mb-6 bg-gradient-to-r from-primary/10 to-primary/5 border border-primary/30 rounded-xl shadow-sm gap-4 slide-in">
            <div className="flex items-center gap-3">
              <div className="h-2 w-2 rounded-full bg-primary animate-pulse shadow-[0_0_8px_rgba(var(--primary),0.5)]"></div>
              <span className="text-sm font-bold text-foreground">
                {selectedIds.length} {t('statements.title', { defaultValue: 'statement' })}{selectedIds.length !== 1 ? 's' : ''} {t('common.selected', { defaultValue: 'selected' })}
              </span>
              <ProfessionalButton
                variant="ghost"
                size="sm"
                onClick={() => setSelectedIds(() => [])}
                className="h-8 text-xs hover:bg-primary/10 transition-colors"
              >
                {t('common.clear')}
              </ProfessionalButton>
            </div>

            <div className="flex flex-wrap items-center gap-3 w-full md:w-auto justify-end">
              <div className="relative group flex-1 md:flex-initial min-w-[200px]">
                <Tag className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
                <Input
                  placeholder={t('statements.bulk_label_placeholder', { defaultValue: 'Add or remove label' })}
                  value={bulkLabel}
                  onChange={(e) => setBulkLabel(e.target.value)}
                  className="pl-8 h-9 text-sm border-primary/20 focus:border-primary/40 bg-background/50"
                />
              </div>

              <div className="flex items-center gap-1.5">
                <ProfessionalButton
                  variant="outline"
                  size="sm"
                  disabled={!bulkLabel.trim()}
                  onClick={async () => {
                    try {
                      await bankStatementApi.bulkLabels(selectedIds, 'add', bulkLabel.trim());
                      loadList();
                      setSelectedIds(() => []);
                      setBulkLabel('');
                      toast.success(t('statements.labels.added', { defaultValue: 'Labels added' }));
                    } catch (e: any) {
                      toast.error(e?.message || t('statements.labels.add_failed', { defaultValue: 'Failed to add label' }));
                    }
                  }}
                  className="h-9 px-3 gap-1.5"
                >
                  <Plus className="h-3.5 w-3.5" />
                  {t('common.add')}
                </ProfessionalButton>

                <ProfessionalButton
                  variant="outline"
                  size="sm"
                  disabled={!bulkLabel.trim()}
                  onClick={async () => {
                    try {
                      await bankStatementApi.bulkLabels(selectedIds, 'remove', bulkLabel.trim());
                      await loadList();
                      setSelectedIds(() => []);
                      setBulkLabel('');
                      toast.success(t('statements.labels.removed', { defaultValue: 'Labels removed' }));
                    } catch (e: any) {
                      toast.error(e?.message || t('statements.labels.remove_failed', { defaultValue: 'Failed to remove label' }));
                    }
                  }}
                  className="h-9 px-3 gap-1.5"
                >
                  <Minus className="h-3.5 w-3.5" />
                  {t('common.remove')}
                </ProfessionalButton>
              </div>

              <div className="w-px h-6 bg-primary/10 hidden md:block mx-1"></div>

              <div className="flex items-center gap-2">
                <ProfessionalButton
                  variant="outline"
                  size="sm"
                  onClick={handleBulkRunReview}
                  disabled={loading}
                  className="h-9 px-3 gap-1.5 shadow-sm border-primary/20 bg-primary/5 hover:bg-primary/10 text-primary whitespace-nowrap"
                >
                  <Wand className="w-3.5 h-3.5" />
                  Run Review
                </ProfessionalButton>

                <ProfessionalButton
                  variant="outline"
                  size="sm"
                  onClick={() => setBulkMergeModalOpen(true)}
                  disabled={selectedIds.length < 2 || statements.some(s => selectedIds.includes(s.id) && s.status === 'merged')}
                  className="h-9 px-3 gap-1.5 shadow-sm border-primary/20 hover:bg-primary/10 transition-colors"
                >
                  <Plus className="w-3.5 h-3.5" />
                  {t('statements.merge_transactions')}
                </ProfessionalButton>

                <ProfessionalButton
                  variant="outline"
                  size="sm"
                  onClick={exportSelectedAsZip}
                  disabled={loading}
                  className="h-9 px-3 gap-1.5 shadow-sm border-primary/20 hover:bg-primary/10 transition-colors"
                >
                  <Archive className="w-3.5 h-3.5" />
                  Export CSV (ZIP)
                </ProfessionalButton>

                <ProfessionalButton
                  variant="destructive"
                  size="sm"
                  onClick={() => setBulkDeleteModalOpen(true)}
                  className="h-9 px-3 gap-1.5 shadow-sm"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                  {t('statements.delete_selected')}
                </ProfessionalButton>
              </div>
            </div>
          </div>
        )}

        <div className="rounded-xl border border-border/50 overflow-x-auto shadow-sm">
          <Table>
            <TableHeader>
              <TableRow className="bg-gradient-to-r from-muted/50 to-muted/30 hover:bg-gradient-to-r hover:from-muted/50 hover:to-muted/30 border-b border-border/50">
                <TableHead className="w-[40px]">
                  <Checkbox
                    checked={statements.length > 0 && selectedIds.length === statements.length}
                    onCheckedChange={(checked) => {
                      if (checked) {
                        setSelectedIds(() => statements.map(s => s.id));
                      } else {
                        setSelectedIds(() => []);
                      }
                    }}
                  />
                </TableHead>
                {isVisible('id') && <TableHead className="font-bold text-foreground">{t('common.id', { defaultValue: 'ID' })}</TableHead>}
                <TableHead className="font-bold text-foreground">{t('statements.filename')}</TableHead>
                {isVisible('labels') && <TableHead className="font-bold text-foreground">{t('statements.labels')}</TableHead>}
                {isVisible('type') && <TableHead className="font-bold text-foreground">{t('statements.card_type.label', 'Type')}</TableHead>}
                <TableHead className="font-bold text-foreground">{t('statements.status.label')}</TableHead>
                {isVisible('review_status') && <TableHead className="font-bold text-foreground">{t('statements.review_status.label')}</TableHead>}
                {isVisible('transactions') && <TableHead className="font-bold text-foreground">{t('statements.transactions')}</TableHead>}
                {isVisible('created_at_by') && <TableHead className="font-bold text-foreground">{t('statements.created_at_by', { defaultValue: 'Created at / by' })}</TableHead>}
                <TableHead className="w-[100px] text-right font-bold text-foreground">{t('statements.actions', { defaultValue: 'Actions' })}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {statements.map((s) => (
                <TableRow key={s.id} className="hover:bg-muted/60 transition-all duration-200 border-b border-border/30">
                  <TableCell>
                    <Checkbox
                      checked={selectedIds.includes(s.id)}
                      onCheckedChange={(checked) => {
                        if (checked) {
                          setSelectedIds(prev => [...prev, s.id]);
                        } else {
                          setSelectedIds(prev => prev.filter(id => id !== s.id));
                        }
                      }}
                    />
                  </TableCell>
                  {isVisible('id') && <TableCell className="font-mono text-sm text-muted-foreground">#{s.id}</TableCell>}
                  <TableCell className="font-semibold text-foreground">{s.original_filename}</TableCell>
                  {isVisible('labels') && (
                    <TableCell>
                      <div className="flex flex-wrap gap-1 items-center min-w-[200px]">
                        {Array.isArray((s as any).labels) && (s as any).labels.map((label: string, idx: number) => (
                          <Badge
                            key={idx}
                            variant="secondary"
                            className="text-[10px] px-1.5 py-0 h-5 bg-primary/10 text-primary border-primary/20 flex items-center gap-1 group/badge"
                          >
                            {label}
                            <button
                              className="hover:text-destructive transition-colors"
                              onClick={() => {
                                const next = (s as any).labels?.filter((_: string, i: number) => i !== idx) || [];
                                bankStatementApi.updateMeta(s.id, { labels: next }).then(() => {
                                  setStatements((prev) => prev.map((x) => (x.id === s.id ? { ...x, labels: next } : x)));
                                }).catch((err: any) => {
                                  toast.error(err?.message || t('statements.labels.remove_failed', { defaultValue: 'Failed to remove label' }));
                                });
                              }}
                            >
                              <X className="h-2.5 w-2.5" />
                            </button>
                          </Badge>
                        ))}
                        <Input
                          placeholder={t('expenses.labels.label_placeholder', { defaultValue: 'Add label...' })}
                          className="w-[100px] h-7 text-[10px] px-2 bg-muted/20 border-border/40 focus:bg-background transition-all"
                          value={newLabelValueById[s.id] || ''}
                          onChange={(ev) => setNewLabelValueById((prev) => ({ ...prev, [s.id]: ev.target.value }))}
                          onKeyDown={(ev) => {
                            if (ev.key === 'Enter' && newLabelValueById[s.id]?.trim()) {
                              const raw = newLabelValueById[s.id].trim();
                              const existing = (s as any).labels || [];
                              if (existing.includes(raw)) {
                                setNewLabelValueById((prev) => ({ ...prev, [s.id]: '' }));
                                return;
                              }
                              const next = [...existing, raw].slice(0, 10);
                              bankStatementApi.updateMeta(s.id, { labels: next }).then(() => {
                                setStatements((prev) => prev.map((x) => (x.id === s.id ? { ...x, labels: next } : x)));
                                setNewLabelValueById((prev) => ({ ...prev, [s.id]: '' }));
                              }).catch((err: any) => {
                                toast.error(err?.message || t('statements.labels.add_failed', { defaultValue: 'Failed to add label' }));
                              });
                            }
                          }}
                        />
                      </div>
                    </TableCell>
                  )}
                  {isVisible('type') && (
                    <TableCell>
                      <CardTypeBadge type={(s as any).card_type} />
                    </TableCell>
                  )}
                  <TableCell>
                    <StatusBadge
                      status={s.status}
                      extraction_method={s.extraction_method}
                      analysis_error={s.analysis_error}
                    />
                  </TableCell>
                  {isVisible('review_status') && (
                    <TableCell>
                      {s.review_status === 'diff_found' ? (
                        <Button
                          size="sm"
                          variant="outline"
                          className="h-7 text-xs border-amber-500/50 text-amber-600 hover:bg-amber-50"
                          onClick={() => handleReviewClick(s)}
                        >
                          <Wand className="h-3 w-3 mr-1" />
                          Review Diff
                        </Button>
                      ) : (s.review_status === 'reviewed' || s.review_status === 'no_diff') ? (
                        <div className="flex flex-col gap-1 items-start">
                          <Badge variant="outline" className={cn(
                            "font-medium shadow-none",
                            s.review_status === 'reviewed' ? "bg-green-50 text-green-700 border-green-200" : "bg-blue-50 text-blue-700 border-blue-200"
                          )}>
                            {s.review_status === 'reviewed' ? t('statements.review_status.reviewed') : 'Verified'}
                          </Badge>
                          <Button
                            size="sm"
                            variant="ghost"
                            className="h-6 text-[10px] px-2 text-muted-foreground hover:text-foreground"
                            onClick={() => handleReviewClick(s)}
                          >
                            <Eye className="w-3 h-3 mr-1" />
                            View Report
                          </Button>
                        </div>
                      ) : (
                        <div className="flex flex-col gap-1 items-start">
                          <Badge variant="outline" className={cn(
                            "font-medium shadow-none",
                            s.review_status === 'pending'
                              ? "bg-blue-50 text-blue-700 border-blue-200"
                              : s.review_status === 'rejected'
                              ? "bg-amber-50 text-amber-700 border-amber-200"
                              : s.review_status === 'failed'
                              ? "bg-red-50 text-red-700 border-red-200"
                              : "bg-muted/50 text-muted-foreground border-transparent"
                          )}>
                            {s.review_status === 'pending' ? t('statements.review_status.pending', { defaultValue: 'Review Pending' }) :
                             s.review_status === 'rejected' ? 'Review Dismissed' :
                             s.review_status === 'failed' ? 'Review Failed' :
                             t('common.not_started', { defaultValue: 'Not Started' })}
                          </Badge>
                          {(!s.review_status || s.review_status === 'not_started' || s.review_status === 'failed' || s.review_status === 'rejected') && (
                            <Button
                              size="sm"
                              variant="ghost"
                              className="h-6 text-[10px] text-primary hover:bg-primary/5 p-0 px-1"
                              onClick={() => handleRunReview(s.id)}
                            >
                              <RotateCcw className="h-2.5 w-2.5 mr-1" />
                              Trigger Review
                            </Button>
                          )}
                          {(s.review_status === 'pending' || s.review_status === 'rejected' || s.review_status === 'failed') && (
                            <Button
                              size="sm"
                              variant="ghost"
                              className="h-6 text-[10px] text-destructive hover:bg-destructive/5 p-0 px-1"
                              onClick={() => handleCancelReview(s.id)}
                            >
                              <X className="h-2.5 w-2.5 mr-1" />
                              {s.review_status === 'pending' ? 'Cancel Review' : 'Clear Status'}
                            </Button>
                          )}
                        </div>
                      )}
                    </TableCell>
                  )}
                  {isVisible('transactions') && <TableCell className="text-center font-medium">{s.extracted_count}</TableCell>}
                  {isVisible('created_at_by') && (
                    <TableCell>
                      <div className="text-sm">
                        <div className="text-muted-foreground">
                          {s.created_at ? new Date(s.created_at).toLocaleString(getLocale, {
                            timeZone: timezone,
                            year: 'numeric',
                            month: 'short',
                            day: 'numeric',
                            hour: '2-digit',
                            minute: '2-digit'
                          }) : ''}
                        </div>
                        <div className="text-xs text-muted-foreground">
                          {s.created_by_username || s.created_by_email || t('common.unknown')}
                        </div>
                      </div>
                    </TableCell>
                  )}
                  <TableCell className="text-right">
                    <div className="flex items-center gap-1 justify-end">
                      <ShareButton
                        recordType="bank_statement"
                        recordId={s.id}
                        open={shareStatementId === s.id}
                        onOpenChange={(isOpen: boolean) => { if (!isOpen) setShareStatementId(null); }}
                      />
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="icon">
                            <MoreHorizontal className="w-4 h-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem onClick={() => openStatement(s.id)}>
                            <Eye className="mr-2 w-4 h-4" /> {t('common.view', 'View')}
                          </DropdownMenuItem>
                          <DropdownMenuItem onClick={() => setShareStatementId(s.id)}>
                            <Share2 className="mr-2 w-4 h-4" /> Share
                          </DropdownMenuItem>
                          {isCompleted(s) && s.status !== 'merged' && (
                            <DropdownMenuItem
                              disabled={reprocessingLocks.has(s.id)}
                              onClick={async () => {
                                if (reprocessingLocks.has(s.id)) return;
                                try {
                                  setReprocessingLocks(prev => new Set([...prev, s.id]));
                                  await bankStatementApi.reprocess(s.id);
                                  const startPolling = (window as any).startStatementPolling;
                                  if (typeof startPolling === 'function') startPolling([s.id]);
                                  toast.success(t('statements.reprocess.started', { defaultValue: 'Reprocessing started' }));
                                  await loadList();
                                  setTimeout(() => {
                                    setReprocessingLocks(prev => { const next = new Set(prev); next.delete(s.id); return next; });
                                  }, 30000);
                                } catch (err: any) {
                                  setReprocessingLocks(prev => { const next = new Set(prev); next.delete(s.id); return next; });
                                  toast.error(err?.message || t('statements.reprocess.failed', { defaultValue: 'Failed to reprocess' }));
                                }
                              }}
                            >
                              {reprocessingLocks.has(s.id) ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RotateCcw className="mr-2 h-4 w-4" />}
                              {t('statements.reprocess.label', 'Reprocess')}
                            </DropdownMenuItem>
                          )}
                          <DropdownMenuItem
                            disabled={previewLoading === s.id || s.status === 'merged'}
                            onClick={() => handlePreview(s.id)}
                          >
                            {previewLoading === s.id ? <Loader2 className="mr-2 w-4 h-4 animate-spin" /> : <ExternalLink className="mr-2 w-4 h-4" />}
                            {t('common.preview', 'Preview')}
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            disabled={s.status === 'merged'}
                            onClick={() => handleDownload(s.id, s.original_filename)}
                          >
                            <Download className="mr-2 w-4 h-4" /> {t('common.download', 'Download')}
                          </DropdownMenuItem>
                          <DropdownMenuSeparator />
                          <DropdownMenuItem
                            className="text-destructive focus:text-destructive"
                            onClick={() => { setStatementToDelete(s.id); setDeleteModalOpen(true); }}
                          >
                            <Trash2 className="mr-2 w-4 h-4" /> {t('common.delete', 'Delete')}
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
              {statements.length === 0 && (
                <TableRow>
                  <TableCell
                    colSpan={4 + (isVisible('id') ? 1 : 0) + (isVisible('labels') ? 1 : 0) + (isVisible('type') ? 1 : 0) + (isVisible('review_status') ? 1 : 0) + (isVisible('transactions') ? 1 : 0) + (isVisible('created_at_by') ? 1 : 0)}
                    className="h-auto p-0 border-none"
                  >
                    <div className="text-center py-20 bg-muted/5 rounded-xl border-2 border-dashed border-muted-foreground/20 m-4">
                      <div className="bg-primary/10 w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-4">
                        <Search className="h-8 w-8 text-primary" />
                      </div>
                      <h3 className="text-xl font-bold mb-2">{t('statements.no_statements', 'No statements yet')}</h3>
                      <p className="text-muted-foreground max-w-sm mx-auto">
                        {t('statements.no_statements_description', 'Upload your bank statements to automatically extract transactions and link them to invoices or expenses.')}
                      </p>
                    </div>
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>

        {/* Pagination */}
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4 mt-6 pt-6 border-t border-border/50">
          <div className="text-sm text-muted-foreground">
            Showing <span className="font-medium text-foreground">{statements.length}</span> of <span className="font-medium text-foreground">{totalStatements}</span> statements
          </div>
          <div className="flex items-center gap-2">
            <ProfessionalButton
              variant="outline"
              size="sm"
              onClick={() => setPage(prev => Math.max(1, prev - 1))}
              disabled={page === 1}
              className="h-9 px-4"
            >
              {t('common.previous')}
            </ProfessionalButton>
            <div className="flex items-center gap-1">
              {Array.from({ length: totalPages }, (_, i) => i + 1)
                .filter(p => p === 1 || p === totalPages || Math.abs(p - page) <= 1)
                .map((p, i, arr) => (
                  <div key={p} className="flex items-center">
                    {i > 0 && arr[i - 1] !== p - 1 && <span className="text-muted-foreground px-1">...</span>}
                    <ProfessionalButton
                      variant={page === p ? "default" : "outline"}
                      size="sm"
                      onClick={() => setPage(() => p)}
                      className={`h-9 w-9 p-0 ${page === p ? 'shadow-md shadow-primary/20' : ''}`}
                    >
                      {p}
                    </ProfessionalButton>
                  </div>
                ))}
            </div>
            <ProfessionalButton
              variant="outline"
              size="sm"
              onClick={() => setPage(prev => Math.min(totalPages, prev + 1))}
              disabled={page >= totalPages}
              className="h-9 px-4"
            >
              {t('common.next')}
            </ProfessionalButton>
          </div>
        </div>
      </div>
    </ProfessionalCard>
  );
}
