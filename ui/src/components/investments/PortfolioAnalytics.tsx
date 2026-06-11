import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { useLocaleFormatter } from '@/i18n/formatters';
import {
  PieChart, AlertCircle, Info
} from 'lucide-react';
import { ProfessionalCard } from '@/components/ui/professional-card';
import { investmentApi } from '@/lib/api';
import { cn } from '@/lib/utils';

interface PortfolioAnalyticsProps {
  portfolioId: number;
}

const PortfolioAnalytics: React.FC<PortfolioAnalyticsProps> = ({ portfolioId }) => {
  const { t } = useTranslation();
  const formatter = useLocaleFormatter();
  const [forecastMonths, setForecastMonths] = useState(12);

  // Fetch diversification analysis
  const { data: diversification, isLoading: diversificationLoading } = useQuery({
    queryKey: ['portfolio', portfolioId, 'diversification'],
    queryFn: () => investmentApi.getDiversificationAnalysis(portfolioId),
    enabled: !!portfolioId
  });

  // Fetch dividend yields
  const { data: dividendYields, isLoading: yieldsLoading } = useQuery({
    queryKey: ['portfolio', portfolioId, 'dividend-yields'],
    queryFn: () => investmentApi.getDividendYields(portfolioId),
    enabled: !!portfolioId
  });

  // Fetch dividend frequency
  const { data: dividendFrequency, isLoading: frequencyLoading } = useQuery({
    queryKey: ['portfolio', portfolioId, 'dividend-frequency'],
    queryFn: () => investmentApi.getDividendFrequency(portfolioId),
    enabled: !!portfolioId
  });

  // Fetch dividend forecast
  const { data: dividendForecast, isLoading: forecastLoading } = useQuery({
    queryKey: ['portfolio', portfolioId, 'dividend-forecast', forecastMonths],
    queryFn: () => investmentApi.getDividendForecast(portfolioId, forecastMonths),
    enabled: !!portfolioId
  });

  const isLoading = diversificationLoading || yieldsLoading || frequencyLoading || forecastLoading;

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center p-12 space-y-4">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
        <p className="text-muted-foreground text-sm">{t('Loading analytics...')}</p>
      </div>
    );
  }

  const getDiversificationColor = (score: number) => {
    if (score >= 80) return 'text-success';
    if (score >= 60) return 'text-warning';
    return 'text-destructive';
  };

  const getDiversificationLabel = (score: number) => {
    if (score >= 80) return 'Well Diversified';
    if (score >= 60) return 'Moderately Diversified';
    return 'Concentrated';
  };

  return (
    <div className="space-y-6">
      {/* Diversification Section */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <ProfessionalCard title="Diversification Analysis" variant="elevated" className="border-border/40">
          <div className="space-y-6 pt-4">
            {diversification ? (
              <>
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-muted-foreground mb-1">Diversification Score</p>
                    <div className="flex items-baseline gap-2">
                      <h3 className={cn("text-4xl font-bold", getDiversificationColor(diversification.diversification_score))}>
                        {diversification.diversification_score.toFixed(0)}
                      </h3>
                      <span className="text-sm text-muted-foreground">/100</span>
                    </div>
                  </div>
                  <PieChart className={cn("w-12 h-12 opacity-20", getDiversificationColor(diversification.diversification_score))} />
                </div>

                <div className="p-3 rounded-lg bg-muted/30 border border-border/50">
                  <p className="text-sm font-semibold text-foreground">
                    {getDiversificationLabel(diversification.diversification_score)}
                  </p>
                  <p className="text-xs text-muted-foreground mt-1">
                    {diversification.diversification_score >= 80
                      ? 'Your portfolio has good exposure across multiple asset classes.'
                      : diversification.diversification_score >= 60
                      ? 'Consider adding more asset classes to reduce concentration risk.'
                      : 'Your portfolio is concentrated. Diversification could reduce risk.'}
                  </p>
                </div>

                <div className="space-y-3">
                  <div className="flex justify-between items-center py-2 border-b border-border/30">
                    <span className="text-sm text-muted-foreground">Largest Holding</span>
                    <span className={cn("font-bold text-sm", diversification.concentration_risk.largest_holding_percentage > 30 ? 'text-destructive' : 'text-foreground')}>
                      {formatter.formatPercent(diversification.concentration_risk.largest_holding_percentage / 100, 1)}
                    </span>
                  </div>
                  {diversification.concentration_risk.largest_holding_percentage > 30 && (
                    <div className="flex gap-2 p-3 rounded-lg bg-destructive/10 border border-destructive/30 text-destructive">
                      <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
                      <p className="text-xs">High concentration risk detected</p>
                    </div>
                  )}
                </div>
              </>
            ) : (
              <p className="text-muted-foreground text-sm">{t('No diversification data available')}</p>
            )}
          </div>
        </ProfessionalCard>

        {/* Dividend Yield Summary */}
        <ProfessionalCard title="Dividend Yields" variant="elevated" className="border-border/40">
          <div className="space-y-4 pt-4">
            {dividendYields && Object.keys(dividendYields).length > 0 ? (
              <>
                <div className="space-y-3 max-h-64 overflow-y-auto">
                  {Object.entries(dividendYields).map(([symbol, yield_value]) => {
                    const yieldNum = typeof yield_value === 'number' ? yield_value : parseFloat(String(yield_value)) || 0;
                    return (
                      <div key={symbol} className="flex justify-between items-center p-3 rounded-lg bg-muted/30 border border-border/50">
                        <span className="font-mono text-sm font-semibold">{symbol}</span>
                        <span className={cn("font-bold text-sm", yieldNum > 0 ? 'text-success' : 'text-muted-foreground')}>
                          {formatter.formatPercent(yieldNum / 100, 2)}
                        </span>
                      </div>
                    );
                  })}
                </div>
                <div className="pt-2 border-t border-border/30">
                  <p className="text-xs text-muted-foreground">
                    {t('Based on last 12 months of dividend payments')}
                  </p>
                </div>
              </>
            ) : (
              <p className="text-muted-foreground text-sm">{t('No dividend-paying holdings')}</p>
            )}
          </div>
        </ProfessionalCard>
      </div>

      {/* Dividend Frequency & Forecast */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <ProfessionalCard title="Dividend Payment Frequency" className="border-border/40">
            <div className="space-y-3 pt-4">
              {dividendFrequency && Object.keys(dividendFrequency).length > 0 ? (
                <div className="space-y-3 max-h-96 overflow-y-auto">
                  {Object.entries(dividendFrequency).map(([symbol, data]: [string, any]) => (
                    <div key={symbol} className="p-4 rounded-lg border border-border/50 bg-background">
                      <div className="flex items-start justify-between mb-3">
                        <div>
                          <p className="font-mono font-bold text-sm">{symbol}</p>
                          <p className="text-xs text-muted-foreground mt-1">{data.frequency}</p>
                        </div>
                        <div className="text-right">
                          <p className="text-sm font-bold text-foreground">{data.payment_count} payments</p>
                          <p className="text-xs text-muted-foreground">{data.average_interval_days}d avg interval</p>
                        </div>
                      </div>
                      <div className="flex items-center justify-between pt-3 border-t border-border/30">
                        <span className="text-xs text-muted-foreground">Avg Amount</span>
                        <span className="font-semibold text-sm">{formatter.formatCurrency(typeof data.average_amount === 'number' ? data.average_amount : parseFloat(String(data.average_amount)) || 0)}</span>
                      </div>
                      {data.last_payment_date && (
                        <div className="flex items-center justify-between pt-2 text-xs text-muted-foreground">
                          <span>Last Payment</span>
                          <span>{formatter.formatDate(new Date(data.last_payment_date), 'short')}</span>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-muted-foreground text-sm">{t('No dividend payment history')}</p>
              )}
            </div>
          </ProfessionalCard>
        </div>

        {/* Dividend Forecast */}
        <ProfessionalCard title="Dividend Forecast" className="border-border/40">
          <div className="space-y-4 pt-4">
            <div className="flex items-center gap-2 mb-4">
              <select
                value={forecastMonths}
                onChange={(e) => setForecastMonths(parseInt(e.target.value))}
                className="text-xs px-2 py-1 rounded border border-border/50 bg-background"
              >
                <option value={3}>3 months</option>
                <option value={6}>6 months</option>
                <option value={12}>12 months</option>
                <option value={24}>24 months</option>
              </select>
            </div>

            {dividendForecast ? (
              <>
                <div className="p-4 rounded-lg bg-success/10 border border-success/30">
                  <p className="text-xs font-semibold text-success mb-1">
                    {t('Projected Income')}
                  </p>
                  <p className="text-2xl font-bold text-success">
                    {formatter.formatCurrency(typeof dividendForecast.total_forecast === 'number' ? dividendForecast.total_forecast : parseFloat(String(dividendForecast.total_forecast)) || 0)}
                  </p>
                  <p className="text-xs text-success/70 mt-2">
                    {t('Next')} {forecastMonths} {t('months')}
                  </p>
                </div>

                {dividendForecast.holding_forecasts && Object.keys(dividendForecast.holding_forecasts).length > 0 && (
                  <div className="space-y-2">
                    <p className="text-xs font-semibold text-muted-foreground">By Holding</p>
                    <div className="space-y-2 max-h-48 overflow-y-auto">
                      {Object.entries(dividendForecast.holding_forecasts).map(([symbol, forecast]: [string, any]) => {
                        const expectedIncome = typeof forecast.expected_income === 'number' ? forecast.expected_income : parseFloat(String(forecast.expected_income)) || 0;
                        return (
                          <div key={symbol} className="flex justify-between items-center text-xs p-2 rounded bg-muted/30">
                            <span className="font-mono font-semibold">{symbol}</span>
                            <span className="text-success font-bold">{formatter.formatCurrency(expectedIncome)}</span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
              </>
            ) : (
              <p className="text-muted-foreground text-sm">{t('No forecast data available')}</p>
            )}
          </div>
        </ProfessionalCard>
      </div>

      {/* Info Box */}
      <div className="p-4 rounded-2xl bg-primary/10 border border-primary/30 text-primary">
        <div className="flex gap-3 items-start">
          <Info className="w-5 h-5 flex-shrink-0 mt-0.5" />
          <div className="space-y-2 text-sm">
            <p className="font-semibold">{t('About Portfolio Analytics')}</p>
            <ul className="text-xs space-y-1 opacity-80">
              <li>• <strong>Diversification Score:</strong> Measures how well your holdings are spread across asset classes (0-100)</li>
              <li>• <strong>Dividend Yields:</strong> Annual dividend income as a percentage of current holding value</li>
              <li>• <strong>Payment Frequency:</strong> Historical pattern of dividend payments for each holding</li>
              <li>• <strong>Forecast:</strong> Projected dividend income based on historical payment patterns</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
};

export default PortfolioAnalytics;
