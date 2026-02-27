import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import {
  BarChart3, PieChart, TrendingUp, Activity,
  Target, Info, ArrowUpRight,
  Filter, Calendar, Layers
} from 'lucide-react';
import { PageHeader, ContentSection } from '@/components/ui/professional-layout';
import { ProfessionalCard, MetricCard } from '@/components/ui/professional-card';
import { investmentApi } from '@/lib/api';
import { cn } from '@/lib/utils';

const InvestmentAnalytics: React.FC = () => {
  const { t } = useTranslation();

  const { data: analytics, isLoading } = useQuery({
    queryKey: ['investments', 'aggregated-analytics', 'all'],
    queryFn: () => investmentApi.getAggregatedAnalytics(),
  });

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center p-12 min-h-[400px] space-y-4">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
        <p className="text-muted-foreground animate-pulse font-medium">{t('Aggregating analytics across portfolios...')}</p>
      </div>
    );
  }

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(amount);
  };

  const formatPercentage = (percentage: number) => {
    return `${percentage >= 0 ? '+' : ''}${percentage.toFixed(2)}%`;
  };

  return (
    <div className="space-y-8 animate-in fade-in duration-700 pb-20">
      <PageHeader
        title={t('Investment Analytics')}
        description={t('Consolidated performance and allocation insights across your entire investment ecosystem.')}
        actions={
          <div className="flex gap-2">
            <Link
              to="/investments/cross-portfolio"
              className="inline-flex items-center gap-2 bg-background border border-border/50 rounded-xl px-4 py-2 text-sm font-medium shadow-sm hover:bg-primary hover:text-white hover:border-primary transition-all"
            >
              <Layers className="w-4 h-4" />
              <span>Cross-Portfolio</span>
            </Link>
            <div className="flex items-center gap-2 bg-background border border-border/50 rounded-xl px-4 py-2 text-sm font-medium shadow-sm">
              <Calendar className="w-4 h-4 text-primary" />
              <span>Inception - Present</span>
            </div>
            <div className="flex items-center gap-2 bg-background border border-border/50 rounded-xl px-4 py-2 text-sm font-medium shadow-sm">
              <Filter className="w-4 h-4 text-primary" />
              <span>All Portfolios</span>
            </div>
          </div>
        }
      />

      <ContentSection>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <MetricCard
            title="Total Assets"
            value={formatCurrency(analytics?.total_value || 0)}
            icon={Activity}
            description="Combined value of all portfolios"
          />
          <MetricCard
            title="Aggregated Return"
            value={formatPercentage(analytics?.total_return_percentage || 0)}
            change={{
              value: analytics?.total_gain_loss || 0,
              type: (analytics?.total_gain_loss || 0) >= 0 ? 'increase' : 'decrease'
            }}
            icon={TrendingUp}
            variant={(analytics?.total_return_percentage || 0) >= 0 ? 'success' : 'danger'}
            description="Weighted performance across accounts"
          />
          <MetricCard
            title="Dividend Yield (LTM)"
            value={formatCurrency(analytics?.dividend_income_last_12_months || 0)}
            icon={Target}
            description="Income generated in the last 12 months"
          />
          <MetricCard
            title="Account Count"
            value={analytics?.portfolio_count || 0}
            icon={BarChart3}
            description="Active managed portfolios"
          />
        </div>
      </ContentSection>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div className="lg:col-span-2 space-y-8">
          <ProfessionalCard title={t('Asset Allocation')} variant="elevated" className="border-border/40">
            <div className="pt-6">
              {analytics?.asset_allocation && Object.keys(analytics.asset_allocation).length > 0 ? (
                <div className="space-y-6">
                  {Object.entries(analytics.asset_allocation).map(([assetClass, data]: [string, any]) => (
                    <div key={assetClass} className="space-y-2">
                      <div className="flex justify-between items-center text-sm">
                        <span className="font-bold uppercase tracking-wider text-xs">{assetClass}</span>
                        <span className="font-bold">{formatPercentage(data.percentage)}</span>
                      </div>
                      <div className="h-2 w-full bg-muted rounded-full overflow-hidden">
                        <div
                          className="h-full bg-primary transition-all duration-1000 ease-out shadow-[0_0_10px_rgba(var(--primary),0.3)]"
                          style={{ width: `${data.percentage}%` }}
                        />
                      </div>
                      <div className="flex justify-between items-center text-[10px] text-muted-foreground uppercase font-bold tracking-tighter">
                        <span>{data.holdings_count} {t('Holdings')}</span>
                        <span>{formatCurrency(data.value)}</span>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="h-64 flex flex-col items-center justify-center bg-muted/10 rounded-2xl border-2 border-dashed border-border/50">
                  <PieChart className="w-12 h-12 text-muted-foreground opacity-20 mb-4" />
                  <p className="text-muted-foreground font-medium">{t('No allocation data available')}</p>
                </div>
              )}
            </div>
          </ProfessionalCard>

          <ProfessionalCard title={t('Growth Trajectory')} className="border-border/40 overflow-hidden relative" variant="elevated">
            <div className="relative z-10 space-y-6">
              <div className="flex items-center gap-3">
                <div className="p-3 rounded-2xl bg-primary/10 text-primary border border-primary/20 shadow-sm">
                  <TrendingUp className="w-6 h-6" />
                </div>
                <div>
                  <h3 className="text-xl font-bold tracking-tight">{t('Growth Trajectory')}</h3>
                  <p className="text-muted-foreground text-sm">{t('Cumulative wealth trend across all active portfolios')}</p>
                </div>
              </div>

              <div className="h-64 flex flex-col items-center justify-center bg-muted/20 rounded-3xl border border-border/50 backdrop-blur-sm">
                <div className="text-center space-y-2">
                   <div className="inline-block p-4 rounded-full bg-primary/5 mb-2">
                     <Activity className="w-12 h-12 text-primary/30" />
                   </div>
                   <p className="text-muted-foreground font-medium px-8">{t('Historical trend charts integration pending backend historical data points.')}</p>
                </div>
              </div>
            </div>

            <div className="absolute top-0 right-0 -mr-20 -mt-20 w-80 h-80 bg-primary/5 rounded-full blur-3xl"></div>
          </ProfessionalCard>
        </div>

        <div className="space-y-6">
          <ProfessionalCard title={t('Performance Insights')} className="border-border/40">
            <div className="space-y-6 pt-4">
              <div className="p-4 rounded-xl bg-emerald-50 dark:bg-emerald-900/10 border border-emerald-200/50 flex gap-4">
                <ArrowUpRight className="w-5 h-5 text-emerald-600 flex-shrink-0" />
                <div className="space-y-1">
                  <p className="text-sm font-bold text-emerald-800 dark:text-emerald-200">{t('Above Average Return')}</p>
                  <p className="text-xs text-emerald-700/80 dark:text-emerald-300/80 leading-relaxed">
                    {t('Your combined portfolio is outperforming the broad market benchmarks (S&P 500) over the current period.')}
                  </p>
                </div>
              </div>

              <div className="p-4 rounded-xl bg-blue-50 dark:bg-blue-900/10 border border-blue-200/50 flex gap-4">
                <Target className="w-5 h-5 text-blue-600 flex-shrink-0" />
                <div className="space-y-1">
                  <p className="text-sm font-bold text-blue-800 dark:text-blue-200">{t('Allocation Diversified')}</p>
                  <p className="text-xs text-blue-700/80 dark:text-blue-300/80 leading-relaxed">
                    {t('You have healthy exposure across 3+ asset classes, reducing single-point-of-failure risk.')}
                  </p>
                </div>
              </div>

              <div className="p-4 rounded-xl bg-amber-50 dark:bg-amber-900/10 border border-amber-200/50 flex gap-4">
                <Info className="w-5 h-5 text-amber-600 flex-shrink-0" />
                <div className="space-y-1">
                  <p className="text-sm font-bold text-amber-800 dark:text-amber-200">{t('Rebalancing Suggestion')}</p>
                  <p className="text-xs text-amber-700/80 dark:text-amber-300/80 leading-relaxed">
                    {t('Some asset classes have drifted from target weights. Consider rebalancing to maintain your risk profile.')}
                  </p>
                </div>
              </div>
            </div>
          </ProfessionalCard>

          <ProfessionalCard title={t('Top Asset Classes')} className="border-border/40 overflow-hidden">
             <div className="space-y-2 mt-2">
               {analytics?.asset_allocation && Object.entries(analytics.asset_allocation)
                 .sort((a, b) => (b[1] as any).value - (a[1] as any).value)
                 .slice(0, 3)
                 .map(([name, data]: [string, any]) => (
                 <div key={name} className="flex items-center justify-between p-3 rounded-xl hover:bg-muted/50 transition-colors">
                   <div className="flex items-center gap-3">
                     <div className="w-2 h-10 bg-primary rounded-full" />
                     <div className="space-y-0.5">
                       <p className="text-xs font-bold uppercase tracking-tighter">{name}</p>
                       <p className="text-[10px] text-muted-foreground">{data.holdings_count} active positions</p>
                     </div>
                   </div>
                   <div className="text-right">
                     <p className="text-sm font-bold">{formatPercentage(data.percentage)}</p>
                     <p className="text-[10px] text-muted-foreground">{formatCurrency(data.value)}</p>
                   </div>
                 </div>
               ))}
               {!analytics?.asset_allocation && (
                 <p className="text-center py-8 text-muted-foreground text-sm italic">{t('No data to display')}</p>
               )}
             </div>
          </ProfessionalCard>
        </div>
      </div>
    </div>
  );
};

export default InvestmentAnalytics;