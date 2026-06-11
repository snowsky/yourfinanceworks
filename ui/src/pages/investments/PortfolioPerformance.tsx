import React from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { useLocaleFormatter } from '@/i18n/formatters';
import {
  TrendingUp, TrendingDown, Wallet, Activity, Target,
  ArrowLeft, Calendar, Info, BarChart3, PieChart,
  ArrowUpRight, ArrowDownRight, LayoutGrid
} from 'lucide-react';
import { PageHeader, ContentSection } from '@/components/ui/professional-layout';
import { ProfessionalCard, MetricCard } from '@/components/ui/professional-card';
import { ProfessionalButton } from '@/components/ui/professional-button';
import { investmentApi, InvestmentPortfolio, PerformanceMetrics } from '@/lib/api';
import { cn } from '@/lib/utils';

const PortfolioPerformance: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const portfolioId = parseInt(id || '0', 10);
  const { t } = useTranslation();
  const formatter = useLocaleFormatter();

  const { data: portfolio, isLoading: portfolioLoading } = useQuery<InvestmentPortfolio>({
    queryKey: ['portfolio', portfolioId],
    queryFn: () => investmentApi.get(portfolioId),
    enabled: !!portfolioId,
  });

  const { data: performance, isLoading: performanceLoading } = useQuery<PerformanceMetrics>({
    queryKey: ['portfolio', portfolioId, 'performance'],
    queryFn: () => investmentApi.getPerformance(portfolioId),
    enabled: !!portfolioId,
  });

  const isLoading = portfolioLoading || performanceLoading;

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center p-12 min-h-[400px] space-y-4">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
        <p className="text-muted-foreground animate-pulse font-medium">{t('Calculating performance...')}</p>
      </div>
    );
  }

  const formatCurrency = (amount: number) => {
    return formatter.formatCurrency(amount, portfolio?.currency || 'USD');
  };

  const formatPercentage = (percentage: number) => {
    return formatter.formatPercent(percentage / 100, 2);
  };

  return (
    <div className="space-y-8 animate-in fade-in duration-700 pb-20">
      <div className="flex items-center gap-4 mb-2">
        <ProfessionalButton asChild variant="ghost" size="sm" className="rounded-full h-10 w-10 p-0 hover:bg-primary/10 hover:text-primary transition-all">
          <Link to={`/investments/portfolio/${portfolioId}`}>
            <ArrowLeft className="w-5 h-5" />
          </Link>
        </ProfessionalButton>
        <div className="flex items-center gap-2">
          <span className="text-muted-foreground font-medium">{t('Portfolio')}</span>
          <span className="text-muted-foreground/30 px-1">/</span>
          <span className="text-foreground font-semibold font-mono text-sm px-2 py-0.5 rounded-md bg-muted">{portfolio?.name}</span>
          <span className="text-muted-foreground/30 px-1">/</span>
          <span className="text-foreground font-semibold">{t('Performance')}</span>
        </div>
      </div>

      <PageHeader
        title={t('Performance Analysis')}
        description={t('Deep dive into your portfolio performance, cost basis, and gain metrics.')}
      />

      {performance && (
        <ContentSection>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <MetricCard
              title="Current Value"
              value={formatCurrency(performance.total_value)}
              icon={Wallet}
              description="Total market value today"
            />
            <MetricCard
              title="Total Return"
              value={formatPercentage(performance.total_return_percentage)}
              change={{
                value: performance.total_gain_loss,
                type: performance.total_gain_loss >= 0 ? 'increase' : 'decrease'
              }}
              icon={Activity}
              variant={performance.total_return_percentage >= 0 ? 'success' : 'danger'}
              description="Lifetime cumulative return"
            />
            <MetricCard
              title="Unrealized Gains"
              value={formatCurrency(performance.unrealized_gain_loss)}
              icon={TrendingUp}
              variant={performance.unrealized_gain_loss >= 0 ? 'success' : 'danger'}
              description="Embedded profit in open positions"
            />
            <MetricCard
              title="Realized Gains"
              value={formatCurrency(performance.realized_gain_loss)}
              icon={Target}
              variant={performance.realized_gain_loss >= 0 ? 'success' : 'danger'}
              description="Profit from completed trades"
            />
          </div>
        </ContentSection>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div className="lg:col-span-2 space-y-8">
          <ProfessionalCard title="Return Breakdown" variant="elevated" className="border-border/40">
            <div className="space-y-6 pt-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="p-6 rounded-2xl bg-muted/30 border border-border/50">
                  <p className="text-sm font-bold text-muted-foreground uppercase tracking-wider mb-2">{t('Total Gain/Loss')}</p>
                  <div className="flex items-baseline gap-2">
                    <h3 className={cn("text-3xl font-bold tracking-tight", (performance?.total_gain_loss || 0) >= 0 ? "text-emerald-600" : "text-rose-600")}>
                      {formatCurrency(performance?.total_gain_loss || 0)}
                    </h3>
                  </div>
                  <div className="mt-4 flex items-center gap-2 text-sm">
                    {(performance?.total_gain_loss || 0) >= 0 ? (
                      <div className="flex items-center text-emerald-600 font-semibold">
                        <ArrowUpRight className="w-4 h-4 mr-1" />
                        {formatPercentage(performance?.total_return_percentage || 0)}
                      </div>
                    ) : (
                      <div className="flex items-center text-rose-600 font-semibold">
                        <ArrowDownRight className="w-4 h-4 mr-1" />
                        {formatPercentage(performance?.total_return_percentage || 0)}
                      </div>
                    )}
                    <span className="text-muted-foreground">{t('since inception')}</span>
                  </div>
                </div>

                <div className="p-6 rounded-2xl bg-muted/30 border border-border/50">
                  <p className="text-sm font-bold text-muted-foreground uppercase tracking-wider mb-2">{t('Capital Invested')}</p>
                  <h3 className="text-3xl font-bold tracking-tight text-foreground">
                    {formatCurrency(performance?.total_cost || 0)}
                  </h3>
                  <div className="mt-4 flex items-center gap-2 text-sm text-muted-foreground">
                    <Calendar className="w-4 h-4 mr-1" />
                    <span>Started on {portfolio ? formatter.formatDate(new Date(portfolio.created_at), 'short') : '...'}</span>
                  </div>
                </div>
              </div>

              <div className="pt-4">
                <div className="space-y-4">
                  <h4 className="font-bold text-base flex items-center gap-2">
                    <BarChart3 className="w-4 h-4 text-primary" />
                    {t('Detailed Metrics')}
                  </h4>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                    <div className="p-4 rounded-xl border border-border/50 bg-background shadow-sm">
                      <p className="text-xs font-semibold text-muted-foreground mb-1">Unrealized</p>
                      <p className={cn("text-lg font-bold", (performance?.unrealized_gain_loss || 0) >= 0 ? "text-emerald-500" : "text-rose-500")}>
                        {formatCurrency(performance?.unrealized_gain_loss || 0)}
                      </p>
                    </div>
                    <div className="p-4 rounded-xl border border-border/50 bg-background shadow-sm">
                      <p className="text-xs font-semibold text-muted-foreground mb-1">Realized</p>
                      <p className={cn("text-lg font-bold", (performance?.realized_gain_loss || 0) >= 0 ? "text-emerald-500" : "text-rose-500")}>
                        {formatCurrency(performance?.realized_gain_loss || 0)}
                      </p>
                    </div>
                    <div className="p-4 rounded-xl border border-border/50 bg-background shadow-sm">
                      <p className="text-xs font-semibold text-muted-foreground mb-1">Total Impact</p>
                      <p className={cn("text-lg font-bold", (performance?.total_gain_loss || 0) >= 0 ? "text-emerald-500" : "text-rose-500")}>
                        {formatCurrency(performance?.total_gain_loss || 0)}
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </ProfessionalCard>

          <ProfessionalCard className="border-border/40">
            <h4 className="font-bold text-base mb-6 flex items-center gap-2">
              <PieChart className="w-4 h-4 text-primary" />
              {t('Growth Comparison')}
            </h4>
            <div className="h-64 flex flex-col items-center justify-center bg-muted/10 rounded-2xl border-2 border-dashed border-border/50">
              <BarChart3 className="w-12 h-12 text-muted-foreground opacity-20 mb-4" />
              <p className="text-muted-foreground font-medium">{t('Interactive charts coming soon...')}</p>
            </div>
          </ProfessionalCard>
        </div>

        <div className="space-y-6">
          <ProfessionalCard title={t('Portfolio Info')} className="border-border/40">
            <div className="space-y-4 pt-4">
              <div className="flex justify-between items-center py-2 border-b border-border/30">
                <span className="text-muted-foreground text-sm">{t('Portfolio Name')}</span>
                <span className="font-bold text-sm text-primary">{portfolio?.name}</span>
              </div>
              <div className="flex justify-between items-center py-2 border-b border-border/30">
                <span className="text-muted-foreground text-sm">{t('Type')}</span>
                <span className="font-semibold text-xs py-0.5 px-2 rounded bg-muted uppercase">{portfolio?.portfolio_type}</span>
              </div>
              <div className="flex justify-between items-center py-2 border-b border-border/30">
                <span className="text-muted-foreground text-sm">{t('Holdings')}</span>
                <div className="flex items-center font-bold text-sm">
                  <LayoutGrid className="w-3.5 h-3.5 mr-1.5 opacity-60" />
                  {portfolio?.holdings_count || 0}
                </div>
              </div>
              <div className="flex justify-between items-center pt-2">
                <span className="text-muted-foreground text-sm">{t('Currency')}</span>
                <span className="font-bold text-sm">{portfolio?.currency}</span>
              </div>
            </div>
          </ProfessionalCard>

          <div className="p-6 rounded-2xl bg-warning/10 border border-warning/30 text-warning">
            <div className="flex gap-4 items-start">
              <Info className="w-5 h-5 flex-shrink-0 mt-0.5" />
              <div className="space-y-2">
                <p className="font-bold text-sm">{t('About Performance tracking')}</p>
                <p className="text-xs leading-relaxed opacity-80">
                  {t('Performance is calculated using the First-In, First-Out (FIFO) cost basis method. This follows standard accounting practices for realized and unrealized gains.')}
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default PortfolioPerformance;
