import { useTranslation } from 'react-i18next';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Filter, Tag, Search, X } from 'lucide-react';
import { ColumnPicker } from '@/components/ui/column-picker';
import { EXPENSE_COLUMNS } from './types';
import { EXPENSE_STATUS_OPTIONS } from '@/constants/expenses';

interface ExpenseFiltersProps {
  searchQuery: string;
  setSearchQuery: (v: string) => void;
  categoryFilter: string;
  setCategoryFilter: (v: string) => void;
  categoryOptions: string[];
  labelFilter: string;
  setLabelFilter: (v: string) => void;
  statusFilter: string;
  setStatusFilter: (v: string) => void;
  unlinkedOnly: boolean;
  setUnlinkedOnly: (v: boolean) => void;
  pageSize: number;
  setPageSize: (v: number) => void;
  setPage: (v: number) => void;
  isVisible: (key: string) => boolean;
  toggle: (key: string) => void;
  reset: () => void;
  hiddenCount: number;
}

export function ExpenseFilters({
  searchQuery,
  setSearchQuery,
  categoryFilter,
  setCategoryFilter,
  categoryOptions,
  labelFilter,
  setLabelFilter,
  statusFilter,
  setStatusFilter,
  unlinkedOnly,
  setUnlinkedOnly,
  pageSize,
  setPageSize,
  setPage,
  isVisible,
  toggle,
  reset,
  hiddenCount,
}: ExpenseFiltersProps) {
  const { t } = useTranslation();

  return (
    <div className="flex flex-col sm:flex-row gap-3 items-start sm:items-center">
      {/* Search */}
      <div className="relative w-full sm:w-auto">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder={t('expenses.search_placeholder')}
          className="pl-9 w-full sm:w-[240px] h-10 rounded-lg border-border/50 bg-muted/30 focus:bg-background transition-colors"
          value={searchQuery}
          onChange={(e) => { setSearchQuery(e.target.value); setPage(1); }}
        />
      </div>

      {/* Category Filter */}
      <div className="flex items-center gap-2">
        <Filter className="h-4 w-4 text-muted-foreground" />
        <Select value={categoryFilter} onValueChange={setCategoryFilter}>
          <SelectTrigger className="w-full sm:w-[170px] h-10 rounded-lg border-border/50 bg-muted/30">
            <SelectValue placeholder={t('expenses.filter_by_category')} />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{t('expenses.all_categories')}</SelectItem>
            {categoryOptions.map((c) => (
              <SelectItem key={c} value={c}>{t(`expenses.categories.${c}`)}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Status Filter */}
      <Select value={statusFilter} onValueChange={(v) => { setStatusFilter(v); setPage(1); }}>
        <SelectTrigger className="w-full sm:w-[170px] h-10 rounded-lg border-border/50 bg-muted/30">
          <SelectValue placeholder={t('expenses.status_filter_label')} />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">{t('expenses.status_filter_label')}: {t('common.all', { defaultValue: 'All' })}</SelectItem>
          {EXPENSE_STATUS_OPTIONS.map(opt => (
            <SelectItem key={opt.value} value={opt.value}>{t(opt.labelKey)}</SelectItem>
          ))}
        </SelectContent>
      </Select>

      {/* Label Filter */}
      <div className="relative">
        <Tag className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder={t('expenses.filter_by_label', { defaultValue: 'Filter by label' })}
          className="pl-9 w-full sm:w-[150px] h-10 rounded-lg border-border/50 bg-muted/30 focus:bg-background transition-colors"
          value={labelFilter}
          onChange={(e) => { setLabelFilter(e.target.value); setPage(1); }}
        />
        {labelFilter && (
          <button
            aria-label="Clear label filter"
            className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
            onClick={() => { setLabelFilter(''); setPage(1); }}
          >
            <X className="w-4 h-4" />
          </button>
        )}
      </div>

      {/* Unlinked Only Checkbox */}
      <label className="inline-flex items-center gap-2 text-sm text-muted-foreground">
        <input type="checkbox" checked={unlinkedOnly} onChange={(e) => { setUnlinkedOnly(e.target.checked); setPage(1); }} />
        {t('expenses.unlinked_only', { defaultValue: 'Unlinked only' })}
      </label>

      {/* Page Size */}
      <div className="flex items-center gap-2">
        <span className="text-sm text-muted-foreground">{t('common.page_size', { defaultValue: 'Page Size' })}</span>
        <Select value={String(pageSize)} onValueChange={(v) => { setPageSize(Number(v)); setPage(1); }}>
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

      <ColumnPicker columns={EXPENSE_COLUMNS} isVisible={isVisible} onToggle={toggle} onReset={reset} hiddenCount={hiddenCount} />
    </div>
  );
}
