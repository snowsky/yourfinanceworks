import React, { useState, useEffect, useRef } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { loadPluginTranslations, arePluginTranslationsLoaded } from '@/i18n';
import {
  TrendingUp, TrendingDown, PieChart, Plus, BarChart3, Calendar,
  Wallet, Target, Activity, Archive, Trash2, RotateCcw,
  Search, List, Grid, ChevronDown, ChevronUp, RefreshCw,
  MoreHorizontal, Eye, Filter, LayoutGrid, Layers
} from 'lucide-react';
import { CardContent, CardDescription, CardHeader, CardTitle, Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import {
  Pagination, PaginationContent, PaginationItem, PaginationLink,
  PaginationNext, PaginationPrevious
} from '@/components/ui/pagination';
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger
} from '@/components/ui/dropdown-menu';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle
} from '@/components/ui/alert-dialog';
import { PageHeader, ContentSection, EmptyState } from '@/components/ui/professional-layout';
import { ProfessionalCard, MetricCard } from '@/components/ui/professional-card';
import { ProfessionalButton } from '@/components/ui/professional-button';
import { investmentApi, InvestmentPortfolio, DeletedPortfolio } from '@/lib/api';
import { toast } from 'sonner';
import { cn, formatDate } from '@/lib/utils';

const InvestmentDashboard: React.FC = () => {
  const { t } = useTranslation('investments');
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const [translationsReady, setTranslationsReady] = useState(false);

  // Ensure plugin translations are loaded
  useEffect(() => {
    const loadTranslations = async () => {
      if (!arePluginTranslationsLoaded('investments')) {
        try {
          await loadPluginTranslations('investments');
          console.log('Investment translations loaded on page mount');
          setTranslationsReady(true);
        } catch (error) {
          console.warn('Failed to load investment translations:', error);
          setTranslationsReady(true); // Still mark as ready to avoid infinite loading
        }
      } else {
        setTranslationsReady(true);
      }
    };

    loadTranslations();
  }, []);

  // Parse search params for initial state
  const pageParam = parseInt(searchParams.get('page') || '1', 10);
  const pageSizeParam = parseInt(searchParams.get('pageSize') || '12', 10);
  const typeFilterParam = searchParams.get('type') || 'all';
  const labelFilterParam = searchParams.get('label') || '';
  const searchQueryParam = searchParams.get('search') || '';
  const viewModeParam = (searchParams.get('view') as 'grid' | 'table') || 'grid';

  // Component State
  const [page, setPage] = useState(pageParam);
  const [pageSize, setPageSize] = useState(pageSizeParam);
  const [searchQuery, setSearchQuery] = useState(searchQueryParam);
  const [typeFilter, setTypeFilter] = useState(typeFilterParam);
  const [labelFilter, setLabelFilter] = useState(labelFilterParam);
  const [viewMode, setViewMode] = useState<'grid' | 'table'>(viewModeParam);
  const [selectedPortfolio, setSelectedPortfolio] = useState<InvestmentPortfolio | null>(null);

  // Recycle Bin State
  const [showRecycleBin, setShowRecycleBin] = useState(false);
  const [recycleBinPage, setRecycleBinPage] = useState(1);
  const [recycleBinPageSize] = useState(10);
  const prevDeletedCount = useRef<number>(0);

  // Confirmation dialog state
  const [deleteId, setDeleteId] = useState<number | null>(null);
  const [permanentDeleteId, setPermanentDeleteId] = useState<number | null>(null);
  const [emptyBinDialogOpen, setEmptyBinDialogOpen] = useState(false);

  // Reset page when search or filters change
  useEffect(() => {
    setPage(1);
  }, [searchQuery, typeFilter, labelFilter]);

  // Update URL when filters change
  useEffect(() => {
    const params = new URLSearchParams();
    if (page > 1) params.set('page', page.toString());
    if (pageSize !== 12) params.set('pageSize', pageSize.toString());
    if (typeFilter !== 'all') params.set('type', typeFilter);
    if (labelFilter) params.set('label', labelFilter);
    if (searchQuery) params.set('search', searchQuery);
    if (viewMode !== 'grid') params.set('view', viewMode);
    setSearchParams(params, { replace: true });
  }, [page, pageSize, typeFilter, labelFilter, searchQuery, viewMode, setSearchParams]);

  // Fetch active portfolios - get all without search filter
  const {
    data: portfolioData,
    isLoading: portfoliosLoading,
    isFetching: portfoliosFetching,
    refetch: refetchPortfolios
  } = useQuery({
    queryKey: ['portfolios', page, pageSize, typeFilter, labelFilter],
    queryFn: () => investmentApi.list({
      skip: (page - 1) * pageSize,
      limit: pageSize,
      portfolio_type: typeFilter === 'all' ? undefined : typeFilter,
      label: labelFilter || undefined
    }),
  });

  // Filter portfolios on the client side based on search query
  const filteredPortfolios = (portfolioData?.items || []).filter(portfolio => {
    if (!searchQuery) return true;
    return portfolio.name.toLowerCase().includes(searchQuery.toLowerCase());
  });

  const portfolios = filteredPortfolios;
  const totalPortfolios = filteredPortfolios.length;

  // Fetch deleted portfolios
  const {
    data: deletedData,
    isLoading: recycleBinLoading,
    refetch: refetchDeleted
  } = useQuery({
    queryKey: ['portfolios', 'deleted', recycleBinPage, recycleBinPageSize],
    queryFn: () => investmentApi.getDeleted((recycleBinPage - 1) * recycleBinPageSize, recycleBinPageSize),
  });

  const deletedPortfolios = deletedData?.items || [];
  const totalDeletedCount = deletedData?.total || 0;

  // Auto-close recycle bin if it becomes empty
  useEffect(() => {
    if (showRecycleBin && totalDeletedCount === 0 && prevDeletedCount.current > 0) {
      setShowRecycleBin(false);
    }
    prevDeletedCount.current = totalDeletedCount;
  }, [showRecycleBin, totalDeletedCount]);

  // Handle Portfolio Actions
  const handleDelete = async (id: number) => {
    try {
      await investmentApi.delete(id);
      toast.success(t('portfolio.portfolio_deleted_successfully'));
      queryClient.invalidateQueries({ queryKey: ['portfolios'] });
    } catch (error: any) {
      const message = error instanceof Error ? error.message : t('portfolio.failed_to_delete_portfolio');
      // If the message is a generic code or contains "Error:", it's already processed by api.ts
      toast.error(message);
    } finally {
      setDeleteId(null);
    }
  };

  const handleRestore = async (id: number) => {
    try {
      await investmentApi.restore(id);
      toast.success(t('portfolio.portfolio_restored_successfully'));
      queryClient.invalidateQueries({ queryKey: ['portfolios'] });
    } catch (error: any) {
      const message = error instanceof Error ? error.message : t('portfolio.failed_to_restore_portfolio');
      toast.error(message);
    }
  };

  const handlePermanentDelete = async (id: number) => {
    try {
      await investmentApi.permanentDelete(id);
      toast.success(t('portfolio.portfolio_permanently_deleted'));
      queryClient.invalidateQueries({ queryKey: ['portfolios'] });
    } catch (error: any) {
      const message = error instanceof Error ? error.message : t('portfolio.failed_to_delete_permanently');
      toast.error(message);
    } finally {
      setPermanentDeleteId(null);
    }
  };

  const handleEmptyBin = async () => {
    try {
      await investmentApi.emptyRecycleBin();
      toast.success(t('portfolio.recycle_bin_emptied_successfully'));
      queryClient.invalidateQueries({ queryKey: ['portfolios'] });
    } catch (error: any) {
      const message = error instanceof Error ? error.message : t('portfolio.failed_to_empty_recycle_bin');
      toast.error(message);
    } finally {
      setEmptyBinDialogOpen(false);
    }
  };

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD'
    }).format(amount);
  };

  const formatPercentage = (percentage: number) => {
    return `${percentage >= 0 ? '+' : ''}${percentage.toFixed(2)}%`;
  };

  const getPortfolioTypeColor = (type: string) => {
    switch (type) {
      case 'taxable': return 'bg-blue-100/50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300 border-blue-200/50';
      case 'retirement': return 'bg-emerald-100/50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300 border-emerald-200/50';
      case 'business': return 'bg-amber-100/50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300 border-amber-200/50';
      default: return 'bg-slate-100/50 text-slate-700 dark:bg-slate-800 dark:text-slate-300 border-slate-200/50';
    }
  };

  const getPortfolioTypeLabel = (type: string) => {
    switch (type) {
      case 'taxable': return 'Taxable';
      case 'retirement': return 'Retirement';
      case 'business': return 'Business';
      default: return type.charAt(0).toUpperCase() + type.slice(1);
    }
  };

  // Fetch aggregated analytics
  const {
    data: aggregatedData,
    isLoading: analyticsLoading
  } = useQuery({
    queryKey: ['portfolios', 'analytics', typeFilter],
    queryFn: () => investmentApi.getAggregatedAnalytics(typeFilter === 'all' ? undefined : typeFilter),
  });

  const performanceStats = aggregatedData || {
    total_value: 0,
    total_gain_loss: 0,
    total_return_percentage: 0,
    realized_gain_loss: 0,
    unrealized_gain_loss: 0
  };

  const totalPages = Math.ceil(totalPortfolios / pageSize);

  if (!translationsReady) {
    return (
      <div className="flex flex-col items-center justify-center p-12 min-h-[400px] space-y-4">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
        <p className="text-muted-foreground animate-pulse font-medium">{t('Loading portfolio details...')}</p>
      </div>
    );
  }

  return (
    <div className="space-y-8 animate-in fade-in duration-700 pb-20">
      {/* Hero Header - Refined to match Expenses page */}
      <div className="bg-gradient-to-r from-primary/10 via-primary/5 to-transparent rounded-2xl border border-primary/20 p-8 backdrop-blur-sm">
        <div className="flex items-center justify-between gap-6">
          <div className="space-y-2">
            <h1 className="font-display text-4xl font-normal tracking-tight">{t('portfolio.investment_portfolio')}</h1>
            <p className="text-lg text-muted-foreground">{t('portfolio.track_wealth_performance')}</p>
          </div>
          <div className="flex flex-wrap gap-3 items-center justify-end">
            <ProfessionalButton
              variant="outline"
              size="default"
              onClick={() => refetchPortfolios()}
              className="bg-background/50 border-border/50 backdrop-blur-sm hover:bg-background transition-colors"
            >
              <RefreshCw className={cn("w-4 h-4 mr-2", portfoliosFetching && "animate-spin")} />
              {t('portfolio.refresh')}
            </ProfessionalButton>
            <ProfessionalButton
              variant="outline"
              className="bg-background/50 border-border/50 backdrop-blur-sm hover:bg-background transition-colors"
              onClick={() => setShowRecycleBin(!showRecycleBin)}
            >
              <Trash2 className="w-4 h-4 mr-2" />
              {t('portfolio.recycle_bin')}
              {totalDeletedCount > 0 && (
                <Badge variant="destructive" className="ml-2 h-5 w-5 p-0 flex items-center justify-center rounded-full text-[10px]">
                  {totalDeletedCount}
                </Badge>
              )}
            </ProfessionalButton>
            <ProfessionalButton
              asChild
              variant="outline"
              className="bg-background/50 border-border/50 backdrop-blur-sm hover:bg-background transition-colors"
            >
              <Link to="/investments/analytics">
                <BarChart3 className="w-4 h-4 mr-2" />
                {t('portfolio.analytics')}
              </Link>
            </ProfessionalButton>
            <ProfessionalButton asChild variant="default" className="shadow-lg shadow-primary/20 font-bold px-6">
              <Link to="/investments/portfolio/new">
                <Plus className="w-4 h-4 mr-2" />
                {t('portfolio.new_portfolio')}
              </Link>
            </ProfessionalButton>
          </div>
        </div>
      </div>

      {/* Recycle Bin Collapsible Section - Match Expenses Style */}
      <Collapsible open={showRecycleBin} onOpenChange={setShowRecycleBin}>
        <CollapsibleContent>
          <ProfessionalCard className="slide-in mb-8 border-l-4 border-l-destructive overflow-hidden bg-card/50 backdrop-blur-sm" variant="elevated">
            <div className="absolute top-0 right-0 w-40 h-40 bg-destructive/5 rounded-full -mr-20 -mt-20 blur-3xl"></div>
            <div className="relative space-y-6 p-6">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <div className="p-3 rounded-xl bg-destructive/10 border border-destructive/20 shadow-sm">
                    <Trash2 className="h-6 w-6 text-destructive" />
                  </div>
                  <div>
                    <h3 className="font-bold text-xl tracking-tight">{t('portfolio.recycle_bin')}</h3>
                    <p className="text-sm text-muted-foreground flex items-center">
                      <Trash2 className="h-3 w-3 mr-1 opacity-60" />
                      {totalDeletedCount} {t('portfolio.items_found')} • {t('portfolio.restore_or_permanently_erase')}
                    </p>
                  </div>
                </div>
                {totalDeletedCount > 0 && (
                  <Button
                    variant="outline"
                    size="sm"
                    className="text-destructive hover:bg-destructive/10 border-destructive/30 hover:border-destructive font-semibold rounded-xl"
                    onClick={() => setEmptyBinDialogOpen(true)}
                  >
                    <Trash2 className="h-4 w-4 mr-2" />
                    {t('portfolio.empty_bin')}
                  </Button>
                )}
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {recycleBinLoading ? (
                  <div className="col-span-full flex items-center justify-center py-12">
                    <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
                  </div>
                ) : deletedPortfolios.length === 0 ? (
                  <div className="col-span-full flex flex-col items-center justify-center py-12 text-center space-y-3 bg-muted/20 rounded-2xl border-2 border-dashed border-border/50">
                    <div className="h-12 w-12 rounded-full bg-muted/30 flex items-center justify-center">
                      <Archive className="h-6 w-6 text-muted-foreground/30" />
                    </div>
                    <div>
                      <h4 className="font-bold">{t('portfolio.your_bin_is_empty')}</h4>
                      <p className="text-xs text-muted-foreground">{t('portfolio.deleted_portfolios_will_appear_here')}</p>
                    </div>
                  </div>
                ) : (
                  deletedPortfolios.map((portfolio) => (
                    <div
                      key={portfolio.id}
                      className="flex flex-col p-4 rounded-xl bg-background/50 border border-border/50 hover:border-primary/20 transition-all hover:shadow-md group"
                    >
                      <div className="flex items-start justify-between mb-3">
                        <div className="space-y-1">
                          <h4 className="font-bold text-sm tracking-tight">{portfolio.name}</h4>
                          <Badge variant="outline" className={cn("text-[9px] h-4 rounded-md uppercase", getPortfolioTypeColor(portfolio.portfolio_type))}>
                            {getPortfolioTypeLabel(portfolio.portfolio_type)}
                          </Badge>
                        </div>
                        <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-7 w-7 rounded-lg hover:bg-primary/10 hover:text-primary"
                            onClick={() => handleRestore(portfolio.id)}
                            title={t('Restore')}
                          >
                            <RotateCcw className="h-3.5 w-3.5" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-7 w-7 rounded-lg hover:bg-destructive/10 hover:text-destructive"
                            onClick={() => setPermanentDeleteId(portfolio.id)}
                            title={t('portfolio.delete_permanently')}
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </Button>
                        </div>
                      </div>
                      <div className="mt-auto pt-3 border-t border-border/10 flex items-center justify-between">
                        <span className="text-[10px] text-muted-foreground font-medium">
                          {t('portfolio.deleted_on')} {new Date(portfolio.updated_at).toLocaleDateString()}
                        </span>
                        <div className="flex items-center gap-1 text-[10px] font-bold text-foreground/70">
                          {formatCurrency(portfolio.total_value || 0)}
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>

              {totalDeletedCount > recycleBinPageSize && (
                <div className="pt-4 border-t border-border/10 flex justify-between items-center">
                  <span className="text-xs text-muted-foreground">{t('Page {{page}} of {{total}}', { page: recycleBinPage, total: Math.ceil(totalDeletedCount / recycleBinPageSize) })}</span>
                  <div className="flex gap-2">
                    <Button variant="ghost" size="sm" className="h-8 rounded-xl px-4" disabled={recycleBinPage === 1} onClick={() => setRecycleBinPage(p => p - 1)}>
                      {t('Previous')}
                    </Button>
                    <Button variant="ghost" size="sm" className="h-8 rounded-xl px-4" disabled={deletedPortfolios.length < recycleBinPageSize} onClick={() => setRecycleBinPage(p => p + 1)}>
                      {t('Next')}
                    </Button>
                  </div>
                </div>
              )}
            </div>
          </ProfessionalCard>
        </CollapsibleContent>
      </Collapsible>

      {/* Metric Cards - Detailed Overview */}
      <ContentSection>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <MetricCard
            title={t('portfolio.total_value')}
            value={formatCurrency(performanceStats.total_value)}
            icon={Wallet}
            description={t('portfolio.total_market_value')}
          />
          <MetricCard
            title={t('portfolio.total_return')}
            value={formatPercentage(performanceStats.total_return_percentage)}
            icon={TrendingUp}
            description={t('portfolio.total_return_description')}
            variant={performanceStats.total_return_percentage >= 0 ? 'success' : 'danger'}
          />
          <MetricCard
            title={t('portfolio.holdings_count')}
            value={portfolios.reduce((acc, p) => acc + (p.holdings_count || 0), 0)}
            icon={Target}
            description={t('portfolio.currently_tracked_securities')}
          />
          <MetricCard
            title="Total Gain/Loss"
            value={formatCurrency(performanceStats.total_gain_loss)}
            icon={TrendingUp}
            description="Combined realized and unrealized"
            variant={performanceStats.total_gain_loss >= 0 ? 'success' : 'danger'}
          />
        </div>
      </ContentSection>

      {/* Main Content Area */}
      <ContentSection>
        <div className="space-y-6">
          {/* Filter Bar */}
          <div className="flex flex-col lg:flex-row gap-4 items-center justify-between bg-card/50 backdrop-blur-sm p-4 rounded-2xl border border-border/50 shadow-sm">
            <div className="flex flex-1 items-center gap-3 w-full">
              <div className="relative flex-1 max-w-md group">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground group-focus-within:text-primary transition-colors" />
                <Input
                  placeholder={t('portfolio.search_portfolios_placeholder')}
                  className="pl-10 h-10 bg-background/50 border-border/50 focus-visible:ring-primary/20 focus-visible:border-primary transition-all rounded-xl"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
              </div>

              <Select value={typeFilter} onValueChange={setTypeFilter}>
                <SelectTrigger className="w-[180px] h-10 rounded-xl bg-background/50 border-border/50">
                  <div className="flex items-center gap-2">
                    <Filter className="w-4 h-4 text-muted-foreground" />
                    <SelectValue placeholder={t('portfolio.all_types')} />
                  </div>
                </SelectTrigger>
                <SelectContent className="rounded-xl border-border/50 shadow-xl">
                  <SelectItem value="all">{t('portfolio.all_types')}</SelectItem>
                  <SelectItem value="taxable">Taxable</SelectItem>
                  <SelectItem value="retirement">Retirement</SelectItem>
                  <SelectItem value="business">Business</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="flex items-center gap-2 bg-background/50 p-1.5 rounded-xl border border-border/50 shadow-inner">
              <Button
                variant={viewMode === 'grid' ? 'secondary' : 'ghost'}
                size="sm"
                className={cn(
                  "h-8 px-3 rounded-lg font-medium transition-all duration-200",
                  viewMode === 'grid' && "bg-white dark:bg-slate-800 shadow-sm text-primary"
                )}
                onClick={() => setViewMode('grid')}
              >
                <LayoutGrid className="h-4 w-4 mr-2" />
                {t('portfolio.grid_view')}
              </Button>
              <Button
                variant={viewMode === 'table' ? 'secondary' : 'ghost'}
                size="sm"
                className={cn(
                  "h-8 px-3 rounded-lg font-medium transition-all duration-200",
                  viewMode === 'table' && "bg-white dark:bg-slate-800 shadow-sm text-primary"
                )}
                onClick={() => setViewMode('table')}
              >
                <List className="h-4 w-4 mr-2" />
                {t('portfolio.table_view')}
              </Button>
            </div>
          </div>

          {/* Table/Grid View */}
          {portfoliosLoading ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {[1, 2, 3, 4, 5, 6].map((i) => (
                <div key={i} className="h-48 rounded-2xl bg-muted/50 animate-pulse border border-border/50 shadow-sm"></div>
              ))}
            </div>
          ) : portfolios.length === 0 ? (
            <EmptyState
              title="No portfolios found"
              description={searchQuery || typeFilter !== 'all'
                ? "No portfolios match your current filter criteria. Try adjusting your search."
                : "It looks like you haven't created any portfolios yet."}
              icon={<PieChart className="w-12 h-12" />}
              action={searchQuery || typeFilter !== 'all' ? (
                <Button variant="outline" onClick={() => { setSearchQuery(''); setTypeFilter('all'); }}>
                  Clear Filters
                </Button>
              ) : (
                <Button asChild>
                  <Link to="/investments/portfolio/new">
                    <Plus className="w-4 h-4 mr-2" />
                    Create Your First Portfolio
                  </Link>
                </Button>
              )}
            />
          ) : viewMode === 'grid' ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {portfolios.map((portfolio) => (
                <ProfessionalCard
                  key={portfolio.id}
                  variant="elevated"
                  interactive
                  className="group relative overflow-hidden border-border/40 hover:border-primary/30"
                >
                  <div className="absolute top-0 right-0 p-4 opacity-0 group-hover:opacity-100 transition-opacity">
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon" className="h-8 w-8 rounded-full bg-background/80 backdrop-blur-sm border border-border/50">
                          <MoreHorizontal className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end" className="rounded-xl border-border/50 shadow-xl w-48">
                        <DropdownMenuItem asChild className="cursor-pointer rounded-lg m-1">
                          <Link to={`/investments/portfolio/${portfolio.id}`}>
                            <Eye className="w-4 h-4 mr-2 opacity-60" /> View Details
                          </Link>
                        </DropdownMenuItem>
                        <DropdownMenuItem asChild className="cursor-pointer rounded-lg m-1">
                          <Link to={`/investments/portfolio/${portfolio.id}/performance`}>
                            <BarChart3 className="w-4 h-4 mr-2 opacity-60" /> Analytics
                          </Link>
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          className="cursor-pointer text-destructive focus:text-destructive rounded-lg m-1"
                          onClick={() => setDeleteId(portfolio.id)}
                        >
                          <Trash2 className="w-4 h-4 mr-2 opacity-60" /> Delete
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>

                  <CardHeader className="p-6">
                    <div className="flex items-center justify-between mb-4">
                      <div className="p-2 rounded-xl bg-primary/5 text-primary group-hover:bg-primary group-hover:text-white transition-all duration-300 shadow-sm border border-primary/10">
                        <Wallet className="w-5 h-5" />
                      </div>
                      <Badge variant="outline" className={cn("px-2.5 py-0.5 rounded-full border border-border/50 font-medium", getPortfolioTypeColor(portfolio.portfolio_type))}>
                        {getPortfolioTypeLabel(portfolio.portfolio_type)}
                      </Badge>
                    </div>
                    <div>
                      <CardTitle className="text-xl font-bold group-hover:text-primary transition-colors line-clamp-1">{portfolio.name}</CardTitle>
                      <CardDescription className="flex items-center mt-1 text-muted-foreground/80">
                        <Calendar className="w-3.5 h-3.5 mr-1.5 opacity-60" />
                        Added on {new Date(portfolio.created_at).toLocaleDateString()}
                      </CardDescription>
                    </div>
                  </CardHeader>
                  <CardContent className="p-6 pt-0">
                    <div className="flex items-end justify-between mt-2">
                      <div>
                        <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1">{t('portfolio.total_value')}</p>
                        <p className="text-2xl font-bold tracking-tight">{formatCurrency(portfolio.total_value || 0)}</p>
                      </div>
                      <div className="text-right">
                        <div className="flex items-center justify-end gap-1 text-emerald-600 dark:text-emerald-400 font-semibold mb-1">
                          {portfolio.total_cost && portfolio.total_value ? (
                            <>
                              <TrendingUp className="w-4 h-4" />
                              <span>{formatPercentage(((portfolio.total_value - portfolio.total_cost) / portfolio.total_cost) * 100)}</span>
                            </>
                          ) : (
                            <span className="text-muted-foreground">{t('portfolio.no_performance_data')}</span>
                          )}
                        </div>
                        <p className="text-xs text-muted-foreground font-medium">{portfolio.holdings_count || 0} {t('portfolio.holdings_count')}</p>
                      </div>
                    </div>

                    <div className="mt-6 pt-6 border-t border-border/30">
                      <ProfessionalButton
                        asChild
                        variant="outline"
                        className="w-full rounded-xl font-semibold shadow-sm border-secondary/30 text-secondary hover:bg-secondary/5 group-hover:bg-primary group-hover:text-white group-hover:border-primary transition-all duration-300"
                      >
                        <Link to={`/investments/portfolio/${portfolio.id}`}>
                          Manage Portfolio
                        </Link>
                      </ProfessionalButton>
                    </div>
                  </CardContent>
                </ProfessionalCard>
              ))}
            </div>
          ) : (
            <Card className="overflow-hidden border-border/50 shadow-lg rounded-2xl">
              <Table>
                <TableHeader className="bg-muted/30">
                  <TableRow className="hover:bg-transparent border-border/50">
                    <TableHead className="py-4 pl-6 font-semibold">{t('portfolio.portfolio_name')}</TableHead>
                    <TableHead className="font-semibold">{t('portfolio.type')}</TableHead>
                    <TableHead className="font-semibold">{t('portfolio.holdings')}</TableHead>
                    <TableHead className="text-right font-semibold">{t('portfolio.value')}</TableHead>
                    <TableHead className="text-right pr-6 font-semibold">{t('portfolio.actions')}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {portfolios.map((portfolio) => (
                    <TableRow key={portfolio.id} className="group hover:bg-primary/5 transition-colors border-border/50">
                      <TableCell className="py-4 pl-6">
                        <div className="flex items-center gap-3">
                          <div className="p-2 rounded-lg bg-primary/5 text-primary group-hover:bg-primary group-hover:text-white transition-colors">
                            <Wallet className="w-4 h-4" />
                          </div>
                          <span className="font-bold text-base">{portfolio.name}</span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline" className={cn("rounded-full border border-border/50 font-medium", getPortfolioTypeColor(portfolio.portfolio_type))}>
                          {getPortfolioTypeLabel(portfolio.portfolio_type)}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center text-muted-foreground font-medium">
                          <LayoutGrid className="w-3.5 h-3.5 mr-1.5 opacity-60" />
                          {portfolio.holdings_count || 0} {t('portfolio.securities')}
                        </div>
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="font-bold text-base tracking-tight">
                          {formatCurrency(portfolio.total_value || 0)}
                        </div>
                        {portfolio.total_cost && portfolio.total_value ? (
                          <div className="text-[10px] text-emerald-600 font-bold">
                            {formatPercentage(((portfolio.total_value - portfolio.total_cost) / portfolio.total_cost) * 100)} today
                          </div>
                        ) : null}
                      </TableCell>
                      <TableCell className="text-right pr-6">
                        <div className="flex items-center justify-end gap-1">
                          <ProfessionalButton variant="ghost" size="icon" className="h-9 w-9 rounded-xl hover:bg-primary/10 hover:text-primary" asChild>
                            <Link to={`/investments/portfolio/${portfolio.id}`}>
                              <Eye className="w-4 h-4" />
                            </Link>
                          </ProfessionalButton>
                          <ProfessionalButton variant="ghost" size="icon" className="h-9 w-9 rounded-xl hover:bg-primary/10 hover:text-primary" asChild>
                            <Link to={`/investments/portfolio/${portfolio.id}/performance`}>
                              <BarChart3 className="w-4 h-4" />
                            </Link>
                          </ProfessionalButton>
                          <ProfessionalButton
                            variant="ghost"
                            size="icon"
                            className="h-9 w-9 rounded-xl hover:bg-destructive/10 hover:text-destructive"
                            onClick={() => setDeleteId(portfolio.id)}
                          >
                            <Trash2 className="w-4 h-4" />
                          </ProfessionalButton>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </Card>
          )}

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between bg-card/50 p-4 rounded-2xl border border-border/50 shadow-sm mt-6">
              <p className="text-sm text-muted-foreground font-medium">
                Showing {portfolios.length} of {totalPortfolios} portfolios
              </p>
              <Pagination>
                <PaginationContent>
                  <PaginationItem>
                    <PaginationPrevious
                      onClick={() => setPage(p => Math.max(1, p - 1))}
                      className={cn("cursor-pointer rounded-xl", page === 1 && "pointer-events-none opacity-50")}
                    />
                  </PaginationItem>
                  {[...Array(totalPages)].map((_, i) => (
                    <PaginationItem key={i + 1} className="hidden sm:inline-block">
                      <PaginationLink
                        onClick={() => setPage(i + 1)}
                        isActive={page === i + 1}
                        className="cursor-pointer rounded-xl font-semibold"
                      >
                        {i + 1}
                      </PaginationLink>
                    </PaginationItem>
                  ))}
                  <PaginationItem>
                    <PaginationNext
                      onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                      className={cn("cursor-pointer rounded-xl", page === totalPages && "pointer-events-none opacity-50")}
                    />
                  </PaginationItem>
                </PaginationContent>
              </Pagination>
            </div>
          )}
        </div>
      </ContentSection>


      {/* Quick Actions Footer */}
      <ContentSection>
        <div className="mt-8">
          <h2 className="text-2xl font-bold mb-6 tracking-tight flex items-center gap-2">
            <Target className="w-6 h-6 text-primary" />
            {t('portfolio.strategic_actions')}
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <ProfessionalCard variant="elevated" className="group p-6 border-l-4 border-l-primary hover:border-l-primary/100 transition-all shadow-md">
              <Link to="/investments/portfolio/new" className="flex flex-col gap-4">
                <div className="p-3 rounded-2xl bg-primary/10 text-primary w-fit group-hover:bg-primary group-hover:text-white transition-all shadow-sm">
                  <Plus className="w-6 h-6" />
                </div>
                <div>
                  <h3 className="font-bold text-lg mb-1 group-hover:text-primary transition-colors">{t('portfolio.expand_portfolio')}</h3>
                  <p className="text-sm text-muted-foreground leading-relaxed">{t('portfolio.expand_portfolio_description')}</p>
                </div>
              </Link>
            </ProfessionalCard>

            <ProfessionalCard variant="elevated" className="group p-6 border-l-4 border-l-violet-500 hover:border-l-violet-500/100 transition-all shadow-md">
              <Link to="/investments/analytics" className="flex flex-col gap-4">
                <div className="p-3 rounded-2xl bg-violet-100/50 text-violet-600 w-fit group-hover:bg-violet-600 group-hover:text-white transition-all shadow-sm">
                  <BarChart3 className="w-6 h-6" />
                </div>
                <div>
                  <h3 className="font-bold text-lg mb-1 group-hover:text-violet-600 transition-colors">{t('portfolio.advanced_analysis')}</h3>
                  <p className="text-sm text-muted-foreground leading-relaxed">{t('portfolio.advanced_analysis_description')}</p>
                </div>
              </Link>
            </ProfessionalCard>

            <ProfessionalCard variant="elevated" className="group p-6 border-l-4 border-l-emerald-500 hover:border-l-emerald-500/100 transition-all shadow-md">
              <Link to="/investments/tax-export" className="flex flex-col gap-4">
                <div className="p-3 rounded-2xl bg-emerald-100/50 text-emerald-600 w-fit group-hover:bg-emerald-600 group-hover:text-white transition-all shadow-sm">
                  <Calendar className="w-6 h-6" />
                </div>
                <div>
                  <h3 className="font-bold text-lg mb-1 group-hover:text-emerald-600 transition-colors">{t('portfolio.tax_efficiency')}</h3>
                  <p className="text-sm text-muted-foreground leading-relaxed">{t('portfolio.tax_efficiency_description')}</p>
                </div>
              </Link>
            </ProfessionalCard>

            <ProfessionalCard variant="elevated" className="group p-6 border-l-4 border-l-cyan-500 hover:border-l-cyan-500/100 transition-all shadow-md">
              <Link to="/investments/cross-portfolio" className="flex flex-col gap-4">
                <div className="p-3 rounded-2xl bg-cyan-100/50 text-cyan-600 w-fit group-hover:bg-cyan-600 group-hover:text-white transition-all shadow-sm">
                  <Layers className="w-6 h-6" />
                </div>
                <div>
                  <h3 className="font-bold text-lg mb-1 group-hover:text-cyan-600 transition-colors">Cross-Portfolio Analysis</h3>
                  <p className="text-sm text-muted-foreground leading-relaxed">Compare stocks across portfolios, find overlaps, and monitor concentration risk.</p>
                </div>
              </Link>
            </ProfessionalCard>
          </div>
        </div>
      </ContentSection>

      {/* Confirmation Dialogs */}
      <AlertDialog open={!!deleteId} onOpenChange={(open) => !open && setDeleteId(null)}>
        <AlertDialogContent className="rounded-3xl border-border/50 shadow-2xl scale-in duration-300">
          <AlertDialogHeader>
            <AlertDialogTitle className="text-2xl font-bold tracking-tight">{t('portfolio.delete_portfolio_question')}</AlertDialogTitle>
            <AlertDialogDescription className="text-muted-foreground leading-relaxed">
              This will move the portfolio to the recycle bin. You can restore it later if needed. All active holdings will be hidden.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter className="gap-2">
            <AlertDialogCancel className="rounded-xl font-semibold">Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="rounded-xl font-semibold bg-destructive hover:bg-destructive/90 shadow-lg shadow-destructive/20"
              onClick={() => deleteId && handleDelete(deleteId)}
            >
              Delete Portfolio
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog open={!!permanentDeleteId} onOpenChange={(open) => !open && setPermanentDeleteId(null)}>
        <AlertDialogContent className="rounded-3xl border-border/50 shadow-2xl scale-in duration-300">
          <AlertDialogHeader>
            <AlertDialogTitle className="text-2xl font-bold tracking-tight text-destructive">Destroy Portfolio?</AlertDialogTitle>
            <AlertDialogDescription className="text-muted-foreground leading-relaxed">
              This action <span className="font-bold underline">cannot be undone</span>. All associated holdings, transactions, and performance history will be permanently erased.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter className="gap-2">
            <AlertDialogCancel className="rounded-xl font-semibold">Keep Portfolio</AlertDialogCancel>
            <AlertDialogAction
              className="rounded-xl font-semibold bg-destructive hover:bg-destructive/90 shadow-lg shadow-destructive/20"
              onClick={() => permanentDeleteId && handlePermanentDelete(permanentDeleteId)}
            >
              Permanently Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog open={emptyBinDialogOpen} onOpenChange={setEmptyBinDialogOpen}>
        <AlertDialogContent className="rounded-3xl border-border/50 shadow-2xl scale-in duration-300">
          <AlertDialogHeader>
            <AlertDialogTitle className="text-2xl font-bold tracking-tight">Empty Recycle Bin?</AlertDialogTitle>
            <AlertDialogDescription className="text-muted-foreground leading-relaxed font-medium">
              Are you sure you want to permanently delete <span className="font-bold text-destructive">{totalDeletedCount} archived portfolios</span>? This action is irreversible.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter className="gap-2">
            <AlertDialogCancel className="rounded-xl font-semibold">Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="rounded-xl font-semibold bg-destructive hover:bg-destructive/90 shadow-lg shadow-destructive/20"
              onClick={handleEmptyBin}
            >
              Empty Everything
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
};

export default InvestmentDashboard;
