import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { useLocaleFormatter } from '@/i18n/formatters';
import {
  Plus, Edit2, Trash2, TrendingUp, TrendingDown,
  DollarSign, Percent, Calendar, AlertCircle,
  MoreHorizontal, Eye, ExternalLink, ArrowUpRight, ArrowDownRight,
  ArrowRight, RefreshCw
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { ProfessionalCard, ProfessionalCardHeader, ProfessionalCardTitle, ProfessionalCardDescription, ProfessionalCardContent, ProfessionalCardFooter } from '@/components/ui/professional-card';
import { ProfessionalButton } from '@/components/ui/professional-button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger
} from '@/components/ui/dropdown-menu';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { api, investmentApi } from '@/lib/api';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';
import CreateHoldingDialog from './CreateHoldingDialog';
import EditHoldingDialog from './EditHoldingDialog';

interface Holding {
  id: number;
  portfolio_id: number;
  security_symbol: string;
  security_name?: string;
  security_type: string;
  asset_class: string;
  quantity: number;
  cost_basis: number;
  purchase_date: string;
  currency?: string;
  current_price?: number;
  price_updated_at?: string;
  imported_price?: number;
  imported_price_date?: string;
  is_closed: boolean;
  average_cost_per_share: number;
  current_value: number;
  unrealized_gain_loss: number;
  created_at: string;
  updated_at: string;
}

interface HoldingsListProps {
  portfolioId: number;
}

const HoldingsList: React.FC<HoldingsListProps> = ({ portfolioId }) => {
  const queryClient = useQueryClient();
  const { t } = useTranslation('investments');
  const formatter = useLocaleFormatter();
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [editingHolding, setEditingHolding] = useState<Holding | null>(null);
  const [deletingHolding, setDeletingHolding] = useState<Holding | null>(null);

  // Fetch holdings
  const { data: holdings = [], isLoading, error } = useQuery<Holding[]>({
    queryKey: ['holdings', portfolioId],
    queryFn: async () => {
      const response = await api.get(`/investments/portfolios/${portfolioId}/holdings`);
      return Array.isArray(response) ? response : [];
    }
  });

  // Fetch price status
  const { data: priceStatus } = useQuery({
    queryKey: ['holdings-price-status'],
    queryFn: () => investmentApi.getPriceStatus(),
    staleTime: 60_000,
  });

  // Refresh all prices mutation
  const refreshPricesMutation = useMutation({
    mutationFn: () => investmentApi.updatePrices(),
    onSuccess: (result) => {
      toast.success(
        `Prices updated: ${result.success} succeeded, ${result.failed} failed (${result.total} total)`
      );
      queryClient.invalidateQueries({ queryKey: ['holdings', portfolioId] });
      queryClient.invalidateQueries({ queryKey: ['portfolio', portfolioId] });
      queryClient.invalidateQueries({ queryKey: ['holdings-price-status'] });
    },
    onError: (error: any) => {
      toast.error(error instanceof Error ? error.message : 'Failed to refresh prices');
    },
  });

  // Delete holding mutation
  const deleteHoldingMutation = useMutation({
    mutationFn: (holdingId: number) => api.delete(`/investments/holdings/${holdingId}`),
    onSuccess: () => {
      toast.success(t('holdings.holding_deleted_successfully'));
      queryClient.invalidateQueries({ queryKey: ['holdings', portfolioId] });
      queryClient.invalidateQueries({ queryKey: ['portfolio', portfolioId] });
      setDeletingHolding(null);
    },
    onError: (error: any) => {
      const errorMessage = error instanceof Error ? error.message : t('holdings.failed_to_delete_holding');
      toast.error(errorMessage);
    }
  });

  const formatCurrency = (amount: number) => {
    return formatter.formatCurrency(amount, 'USD');
  };

  const formatPercentage = (percentage: number) => {
    return formatter.formatPercent(percentage / 100, 2);
  };

  const getAssetClassColor = (assetClass: string) => {
    const colors: Record<string, string> = {
      'stocks': 'bg-blue-100/50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300 border-blue-200/50',
      'bonds': 'bg-emerald-100/50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300 border-emerald-200/50',
      'cash': 'bg-slate-100/50 text-slate-700 dark:bg-slate-800 dark:text-slate-300 border-slate-200/50',
      'real_estate': 'bg-orange-100/50 text-orange-700 dark:bg-orange-900/30 dark:text-orange-300 border-orange-200/50',
      'commodities': 'bg-amber-100/50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300 border-amber-200/50',
    };
    return colors[assetClass] || 'bg-slate-100/50 text-slate-700 border-slate-200/50';
  };

  const calculateUnrealizedGainPercentage = (holding: Holding) => {
    if (holding.cost_basis === 0) return 0;
    return ((holding.unrealized_gain_loss / holding.cost_basis) * 100);
  };

  if (isLoading) {
    return (
      <div className="space-y-4">
        {[1, 2, 3].map(i => (
          <div key={i} className="h-20 w-full bg-muted/30 rounded-2xl animate-pulse" />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-8 text-center rounded-3xl bg-destructive/5 border-2 border-dashed border-destructive/20">
        <AlertCircle className="w-12 h-12 text-destructive mx-auto mb-4 opacity-50" />
        <h3 className="text-lg font-bold text-destructive">{t('holdings.failed_to_load_holdings')}</h3>
        <p className="text-muted-foreground">{t('holdings.error_fetching_holdings')}</p>
        <ProfessionalButton variant="outline" className="mt-4" onClick={() => queryClient.invalidateQueries({ queryKey: ['holdings', portfolioId] })}>
          {t('holdings.retry')}
        </ProfessionalButton>
      </div>
    );
  }

  const activeHoldings = holdings.filter(h => !h.is_closed);
  const closedHoldings = holdings.filter(h => h.is_closed);

  return (
    <div className="space-y-6">
      {/* Active Holdings List */}
      <ProfessionalCard
        variant="elevated"
        className="border-border/40 overflow-hidden"
      >
        <ProfessionalCardHeader className="flex-row items-center justify-between space-y-0 px-6 py-4 border-b border-border/10 bg-muted/5">
          <div className="space-y-1">
            <ProfessionalCardTitle className="text-xl font-bold tracking-tight">
              {t('holdings.active_holdings')}
            </ProfessionalCardTitle>
            {activeHoldings.length > 0 && (
              <ProfessionalCardDescription>
                {t('holdings.detailed_overview')}
                {priceStatus && (
                  <span className="ml-2 text-[10px] font-medium opacity-70">
                    · {priceStatus.fresh_prices} fresh · {priceStatus.stale_prices} stale · {priceStatus.without_prices} missing
                  </span>
                )}
              </ProfessionalCardDescription>
            )}
          </div>
          <div className="flex items-center gap-2">
            <ProfessionalButton
              onClick={() => refreshPricesMutation.mutate()}
              disabled={refreshPricesMutation.isPending}
              size="sm"
              variant="outline"
              className="rounded-lg"
            >
              <RefreshCw className={cn('w-4 h-4 mr-2', refreshPricesMutation.isPending && 'animate-spin')} />
              {refreshPricesMutation.isPending ? t('portfolio.refreshing') : t('portfolio.refresh_prices')}
            </ProfessionalButton>
            <ProfessionalButton onClick={() => setShowCreateDialog(true)} size="sm" variant="gradient" className="rounded-lg">
              <Plus className="w-4 h-4 mr-2" />
              {t('holdings.add_position')}
            </ProfessionalButton>
          </div>
        </ProfessionalCardHeader>
        <div className="p-0">
        {activeHoldings.length === 0 ? (
          <div className="text-center py-20 bg-muted/10 rounded-2xl border-2 border-dashed border-border/50 mx-2">
            <div className="p-4 rounded-full bg-primary/5 inline-block mb-4 shadow-inner">
              <DollarSign className="w-10 h-10 text-primary/40" />
            </div>
            <h3 className="text-xl font-bold mb-2">{t('holdings.no_active_holdings')}</h3>
            <p className="text-muted-foreground max-w-sm mx-auto mb-8">
              {t('holdings.start_building_portfolio')}
            </p>
            <ProfessionalButton onClick={() => setShowCreateDialog(true)} variant="secondary" className="rounded-xl px-8 shadow-md">
              <Plus className="w-4 h-4 mr-2" />
              {t('holdings.add_first_holding')}
            </ProfessionalButton>
          </div>
        ) : (
          <div className="mt-4 overflow-x-auto rounded-xl border border-border/50 shadow-inner bg-card/30">
            <Table className="min-w-[900px]">
              <TableHeader className="bg-muted/50">
                <TableRow className="hover:bg-transparent border-border/50">
                  <TableHead className="font-bold py-4 pl-6 uppercase tracking-wider text-[10px] text-muted-foreground">{t('holdings.security')}</TableHead>
                  <TableHead className="font-bold uppercase tracking-wider text-[10px] text-muted-foreground">{t('holdings.type')}</TableHead>
                  <TableHead className="text-right font-bold uppercase tracking-wider text-[10px] text-muted-foreground">{t('holdings.position')}</TableHead>
                  <TableHead className="text-right font-bold uppercase tracking-wider text-[10px] text-muted-foreground">{t('holdings.currency')}</TableHead>
                  <TableHead className="text-right font-bold uppercase tracking-wider text-[10px] text-muted-foreground">Statement Price</TableHead>
                  <TableHead className="text-right font-bold uppercase tracking-wider text-[10px] text-muted-foreground">Current Price</TableHead>
                  <TableHead className="text-right font-bold uppercase tracking-wider text-[10px] text-muted-foreground">Stmt / Current Value</TableHead>
                  <TableHead className="text-right font-bold uppercase tracking-wider text-[10px] text-muted-foreground">{t('holdings.total_gl')}</TableHead>
                  <TableHead className="text-right pr-6 font-bold uppercase tracking-wider text-[10px] text-muted-foreground">{t('holdings.actions')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {activeHoldings.map((holding) => {
                  const gainPercentage = calculateUnrealizedGainPercentage(holding);
                  const isPositive = holding.unrealized_gain_loss >= 0;
                  const statementValue = holding.imported_price != null
                    ? holding.imported_price * holding.quantity
                    : null;
                  const currentValue = holding.current_price != null
                    ? holding.current_price * holding.quantity
                    : null;

                  return (
                    <TableRow key={holding.id} className="group hover:bg-primary/5 transition-colors border-border/50">
                      <TableCell className="py-4 pl-6">
                        <div className="flex items-center gap-3">
                          <div className="flex flex-col">
                            <span className="font-black text-sm tracking-tight">{holding.security_symbol}</span>
                            <span className="text-[10px] text-muted-foreground font-medium truncate max-w-[120px]">{holding.security_name || t('holdings.custom_asset')}</span>
                          </div>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline" className={cn("px-2 py-0 rounded-md font-bold text-[9px] uppercase tracking-tighter border shadow-sm", getAssetClassColor(holding.asset_class))}>
                          {holding.asset_class.replace('_', ' ')}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right font-mono text-xs">
                        {formatter.formatNumber(holding.quantity, 4)}
                      </TableCell>
                      <TableCell className="text-right">
                        <Badge variant="outline" className="px-2 py-0 rounded-md font-bold text-[9px] uppercase tracking-tighter border shadow-sm bg-muted/50">
                          {holding.currency || 'USD'}
                        </Badge>
                      </TableCell>

                      {/* Statement Price (from imported file) */}
                      <TableCell className="text-right">
                        <div className="flex flex-col items-end">
                          {holding.imported_price != null ? (
                            <>
                              <span className="font-bold text-sm tracking-tight">{formatCurrency(holding.imported_price)}</span>
                              {holding.imported_price_date && (
                                <span className="text-[10px] text-muted-foreground opacity-60">{holding.imported_price_date}</span>
                              )}
                            </>
                          ) : (
                            <span className="text-[10px] text-muted-foreground opacity-40">—</span>
                          )}
                        </div>
                      </TableCell>

                      {/* Current Price (live from Yahoo Finance) */}
                      <TableCell className="text-right">
                        <div className="flex flex-col items-end">
                          {holding.current_price != null ? (
                            <>
                              <span className="font-bold text-sm tracking-tight">{formatCurrency(holding.current_price)}</span>
                              {holding.price_updated_at && (
                                <span className="text-[10px] text-muted-foreground opacity-60">Live</span>
                              )}
                            </>
                          ) : (
                            <span className="text-[10px] text-muted-foreground opacity-40">—</span>
                          )}
                        </div>
                      </TableCell>

                      {/* Statement Value / Current Value (merged column) */}
                      <TableCell className="text-right">
                        <div className="flex flex-col items-end gap-0.5">
                          {statementValue != null ? (
                            <span className="font-bold text-sm tracking-tight text-foreground">{formatCurrency(statementValue)}</span>
                          ) : (
                            <span className="text-[10px] text-muted-foreground opacity-40">—</span>
                          )}
                          {currentValue != null ? (
                            <span className="font-black text-sm tracking-tight text-primary">{formatCurrency(currentValue)}</span>
                          ) : (
                            <span className="text-[10px] text-muted-foreground opacity-40">—</span>
                          )}
                        </div>
                      </TableCell>

                      <TableCell className="text-right">
                        <div className={cn("flex flex-col items-end", isPositive ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400')}>
                          <div className="flex items-center gap-1 font-black text-sm">
                            {isPositive ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
                            {formatCurrency(Math.abs(holding.unrealized_gain_loss))}
                          </div>
                          <div className="text-[10px] font-bold opacity-80">{formatPercentage(gainPercentage)}</div>
                        </div>
                      </TableCell>
                      <TableCell className="text-right pr-6">
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button variant="ghost" size="icon" className="h-8 w-8 rounded-lg group-hover:bg-primary/10 group-hover:text-primary transition-all">
                              <MoreHorizontal className="h-4 w-4" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end" className="rounded-xl border-border/50 shadow-2xl w-48">
                            <DropdownMenuItem className="rounded-lg m-1 cursor-pointer" onClick={() => setEditingHolding(holding)}>
                              <Edit2 className="w-4 h-4 mr-2 opacity-60" /> {t('holdings.edit_position')}
                            </DropdownMenuItem>
                            <DropdownMenuItem className="rounded-lg m-1 cursor-pointer">
                              <ExternalLink className="w-4 h-4 mr-2 opacity-60" /> {t('holdings.market_insights')}
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              className="rounded-lg m-1 cursor-pointer text-destructive focus:text-destructive"
                              onClick={() => setDeletingHolding(holding)}
                            >
                              <Trash2 className="w-4 h-4 mr-2 opacity-60" /> {t('holdings.remove_position')}
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        )}
      </div>
    </ProfessionalCard>

      {/* Closed Holdings */}
      {closedHoldings.length > 0 && (
        <ProfessionalCard
          variant="default"
          className="border-border/40 opacity-80 grayscale hover:grayscale-0 transition-all p-0 overflow-hidden"
        >
          <ProfessionalCardHeader className="px-6 py-4 border-b border-border/10 bg-muted/5">
            <ProfessionalCardTitle className="text-lg font-bold">
              {t('holdings.closed_positions')}
            </ProfessionalCardTitle>
            <ProfessionalCardDescription>
              {t('holdings.history_exited_investments')}
            </ProfessionalCardDescription>
          </ProfessionalCardHeader>
          <div className="p-0">
          <div className="mt-4 overflow-hidden rounded-xl border border-border/50 bg-muted/5">
            <Table>
              <TableHeader className="bg-muted/10">
                <TableRow className="hover:bg-transparent border-border/50">
                  <TableHead className="font-bold py-3 pl-6 uppercase tracking-wider text-[10px] text-muted-foreground">{t('holdings.security')}</TableHead>
                  <TableHead className="font-bold uppercase tracking-wider text-[10px] text-muted-foreground">{t('holdings.asset_class')}</TableHead>
                  <TableHead className="text-right font-bold uppercase tracking-wider text-[10px] text-muted-foreground">{t('holdings.currency')}</TableHead>
                  <TableHead className="text-right font-bold uppercase tracking-wider text-[10px] text-muted-foreground">{t('holdings.closed_gl')}</TableHead>
                  <TableHead className="text-right pr-6 font-bold uppercase tracking-wider text-[10px] text-muted-foreground">{t('holdings.exit_date')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {closedHoldings.map((holding) => (
                  <TableRow key={holding.id} className="hover:bg-muted/10 border-border/50">
                    <TableCell className="py-3 pl-6">
                      <div className="flex flex-col">
                        <span className="font-bold text-sm text-foreground/70">{holding.security_symbol}</span>
                        <span className="text-[10px] text-muted-foreground">{holding.security_name}</span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline" className={cn("px-2 py-0 rounded-md font-bold text-[9px] uppercase tracking-tighter border opacity-60", getAssetClassColor(holding.asset_class))}>
                        {holding.asset_class.replace('_', ' ')}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      <Badge variant="outline" className="px-2 py-0 rounded-md font-bold text-[9px] uppercase tracking-tighter border opacity-60 bg-muted/50">
                        {holding.currency || 'USD'}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">
                       <span className={cn("font-bold text-sm", holding.unrealized_gain_loss >= 0 ? "text-emerald-600/70" : "text-rose-600/70")}>
                        {formatCurrency(holding.unrealized_gain_loss)}
                      </span>
                    </TableCell>
                    <TableCell className="text-right pr-6 text-xs text-muted-foreground font-medium">
                      {formatter.formatDate(new Date(holding.updated_at), 'short')}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
          </div>
        </ProfessionalCard>
      )}

      {/* Dialogs */}
      <CreateHoldingDialog
        portfolioId={portfolioId}
        open={showCreateDialog}
        onOpenChange={setShowCreateDialog}
      />

      {editingHolding && (
        <EditHoldingDialog
          holding={editingHolding}
          portfolioId={portfolioId}
          open={!!editingHolding}
          onOpenChange={(open) => !open && setEditingHolding(null)}
        />
      )}

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={!!deletingHolding} onOpenChange={(open) => !open && setDeletingHolding(null)}>
        <AlertDialogContent className="rounded-3xl border-border/50 shadow-2xl scale-in duration-300">
          <AlertDialogHeader>
            <AlertDialogTitle className="text-2xl font-bold tracking-tight">{t('Remove Position?')}</AlertDialogTitle>
            <AlertDialogDescription className="text-muted-foreground leading-relaxed">
              {t('Are you sure you want to remove {{symbol}} from your portfolio? This action will permanently delete all transaction history for this holding.', { symbol: deletingHolding?.security_symbol })}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter className="gap-2">
            <AlertDialogCancel className="rounded-xl font-semibold">{t('Cancel')}</AlertDialogCancel>
            <AlertDialogAction
              className="rounded-xl font-semibold bg-destructive hover:bg-destructive/90 shadow-lg shadow-destructive/20"
              onClick={() => deletingHolding && deleteHoldingMutation.mutate(deletingHolding.id)}
              disabled={deleteHoldingMutation.isPending}
            >
              {deleteHoldingMutation.isPending ? t('Removing...') : t('Remove Position')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
};

export default HoldingsList;
