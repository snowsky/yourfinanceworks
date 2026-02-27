import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import {
  Layers, GitCompare, Search, ShieldAlert, BarChart3,
  TrendingUp, TrendingDown, ArrowLeft, AlertTriangle,
  Eye, ChevronDown, ChevronUp, Activity, Target
} from 'lucide-react';
import { PageHeader, ContentSection } from '@/components/ui/professional-layout';
import { ProfessionalCard, MetricCard } from '@/components/ui/professional-card';
import { investmentApi } from '@/lib/api';
import { cn } from '@/lib/utils';

// ──────────────────────────────────────────────
// Helpers
// ──────────────────────────────────────────────
const fmt = (n: number) =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(n);

const pct = (n: number) => `${n >= 0 ? '+' : ''}${n.toFixed(2)}%`;

const GainPill: React.FC<{ value: number; label?: string }> = ({ value, label }) => (
  <span
    className={cn(
      'inline-flex items-center gap-1 text-xs font-bold px-2 py-0.5 rounded-full',
      value > 0
        ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300'
        : value < 0
        ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300'
        : 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400'
    )}
  >
    {value > 0 ? <TrendingUp className="w-3 h-3" /> : value < 0 ? <TrendingDown className="w-3 h-3" /> : null}
    {label ?? pct(value)}
  </span>
);

// ──────────────────────────────────────────────
// Sub-sections
// ──────────────────────────────────────────────

/* ── Consolidated Holdings Table ───────────── */
const ConsolidatedHoldings: React.FC<{ data: any }> = ({ data }) => {
  const [expanded, setExpanded] = useState<string | null>(null);
  if (!data?.consolidated_holdings?.length) return null;

  return (
    <ProfessionalCard
      title="Consolidated Holdings"
      className="border-border/40"
      variant="elevated"
    >
      <p className="text-xs text-muted-foreground mb-4">
        Same stocks combined across {data.portfolio_count} portfolios — {data.total_unique_securities} unique securities
      </p>
      <div className="space-y-2">
        {data.consolidated_holdings.map((h: any) => (
          <div key={h.security_symbol} className="rounded-xl border border-border/40 overflow-hidden">
            <button
              className="w-full flex items-center justify-between px-4 py-3 hover:bg-muted/30 transition-colors text-left"
              onClick={() => setExpanded(expanded === h.security_symbol ? null : h.security_symbol)}
            >
              <div className="flex items-center gap-3 min-w-0">
                <div className="w-9 h-9 rounded-lg bg-primary/10 border border-primary/20 flex items-center justify-center text-xs font-bold text-primary shrink-0">
                  {h.security_symbol.slice(0, 3)}
                </div>
                <div className="min-w-0">
                  <p className="text-sm font-bold truncate">{h.security_symbol}</p>
                  <p className="text-[10px] text-muted-foreground truncate">{h.security_name}</p>
                </div>
              </div>
              <div className="flex items-center gap-4 shrink-0">
                <div className="text-right hidden sm:block">
                  <p className="text-sm font-bold">{fmt(h.total_current_value)}</p>
                  <p className="text-[10px] text-muted-foreground">{h.total_quantity.toLocaleString()} shares</p>
                </div>
                <GainPill value={h.gain_loss_pct} />
                <span className="text-xs bg-primary/10 text-primary px-2 py-0.5 rounded-full font-medium">
                  {h.portfolio_count} {h.portfolio_count === 1 ? 'portfolio' : 'portfolios'}
                </span>
                {expanded === h.security_symbol ? <ChevronUp className="w-4 h-4 text-muted-foreground" /> : <ChevronDown className="w-4 h-4 text-muted-foreground" />}
              </div>
            </button>

            {expanded === h.security_symbol && (
              <div className="border-t border-border/30 bg-muted/10 px-4 py-3 space-y-2 animate-in slide-in-from-top-2 duration-200">
                <div className="grid grid-cols-3 gap-4 text-[10px] text-muted-foreground uppercase font-bold tracking-wider px-1 mb-1">
                  <span>Portfolio</span>
                  <span className="text-right">Value</span>
                  <span className="text-right">Gain/Loss</span>
                </div>
                {h.portfolios.map((p: any) => (
                  <div key={p.portfolio_id} className="grid grid-cols-3 gap-4 items-center px-1 py-1.5 rounded-lg hover:bg-muted/20">
                    <div>
                      <p className="text-xs font-medium">{p.portfolio_name}</p>
                      <p className="text-[10px] text-muted-foreground">{p.quantity} shares · {p.portfolio_type}</p>
                    </div>
                    <p className="text-xs font-bold text-right">{fmt(p.current_value)}</p>
                    <div className="text-right">
                      <GainPill value={p.gain_loss_pct} />
                    </div>
                  </div>
                ))}
                <div className="flex justify-between items-center pt-2 border-t border-border/20 px-1">
                  <span className="text-[10px] text-muted-foreground">Weighted avg cost: {fmt(h.weighted_avg_cost)}/share</span>
                  <span className="text-[10px] text-muted-foreground">Cost basis: {fmt(h.total_cost_basis)}</span>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </ProfessionalCard>
  );
};

/* ── Overlap Analysis ──────────────────────── */
const OverlapSection: React.FC<{ data: any }> = ({ data }) => {
  if (!data) return null;

  return (
    <ProfessionalCard title="Portfolio Overlap" className="border-border/40" variant="elevated">
      <div className="flex items-center gap-4 mb-4">
        <div className="flex-1">
          <div className="flex justify-between text-xs mb-1">
            <span className="text-muted-foreground">Overlap</span>
            <span className="font-bold">{data.overlap_percentage}%</span>
          </div>
          <div className="h-2 bg-muted rounded-full overflow-hidden">
            <div
              className={cn(
                'h-full rounded-full transition-all duration-1000',
                data.overlap_percentage > 50 ? 'bg-amber-500' : 'bg-primary'
              )}
              style={{ width: `${Math.min(data.overlap_percentage, 100)}%` }}
            />
          </div>
        </div>
        <div className="text-right shrink-0">
          <p className="text-lg font-bold">{data.overlapping_securities_count}</p>
          <p className="text-[10px] text-muted-foreground">of {data.total_unique_securities} overlap</p>
        </div>
      </div>

      {data.overlap_details?.length > 0 ? (
        <div className="space-y-2">
          {data.overlap_details.map((d: any) => (
            <div key={d.security_symbol} className="flex items-center justify-between p-3 rounded-xl border border-border/30 hover:bg-muted/20 transition-colors">
              <div className="flex items-center gap-3">
                <GitCompare className="w-4 h-4 text-primary" />
                <div>
                  <p className="text-xs font-bold">{d.security_symbol}</p>
                  <p className="text-[10px] text-muted-foreground">In {d.portfolio_names.join(', ')}</p>
                </div>
              </div>
              <div className="text-right">
                <p className="text-xs font-bold">{fmt(d.total_value)}</p>
                <p className="text-[10px] text-muted-foreground">{d.total_quantity} shares</p>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="text-center py-6 text-muted-foreground text-sm">
          <GitCompare className="w-8 h-8 mx-auto mb-2 opacity-20" />
          No overlapping securities found
        </div>
      )}
    </ProfessionalCard>
  );
};

/* ── Exposure / Concentration ──────────────── */
const ExposureSection: React.FC<{ data: any }> = ({ data }) => {
  if (!data) return null;

  return (
    <ProfessionalCard title="Concentration Risk" className="border-border/40" variant="elevated">
      {data.concentration_warnings?.length > 0 && (
        <div className="mb-4 p-3 rounded-xl bg-amber-50 dark:bg-amber-900/10 border border-amber-200/50 flex gap-3">
          <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
          <div>
            <p className="text-xs font-bold text-amber-800 dark:text-amber-200">
              {data.concentration_warnings.length} concentration {data.concentration_warnings.length === 1 ? 'warning' : 'warnings'}
            </p>
            <p className="text-[10px] text-amber-700/80 dark:text-amber-300/80 mt-0.5">
              Securities above 20% of total portfolio value may increase risk.
            </p>
          </div>
        </div>
      )}

      <div className="space-y-3">
        {data.exposures?.slice(0, 10).map((e: any) => (
          <div key={e.security_symbol} className="space-y-1">
            <div className="flex justify-between items-center text-xs">
              <span className="font-medium">{e.security_symbol}</span>
              <span className="font-bold">{e.pct_of_total.toFixed(1)}%</span>
            </div>
            <div className="h-1.5 bg-muted rounded-full overflow-hidden">
              <div
                className={cn(
                  'h-full rounded-full transition-all duration-700',
                  e.pct_of_total > 20 ? 'bg-amber-500' : 'bg-primary/70'
                )}
                style={{ width: `${Math.min(e.pct_of_total, 100)}%` }}
              />
            </div>
            <div className="flex justify-between text-[10px] text-muted-foreground">
              <span>{fmt(e.total_value)}</span>
              <span>{e.portfolio_count} {e.portfolio_count === 1 ? 'portfolio' : 'portfolios'}</span>
            </div>
          </div>
        ))}
      </div>
    </ProfessionalCard>
  );
};

/* ── Monthly Comparison ────────────────────── */
const MonthlySection: React.FC<{ data: any }> = ({ data }) => {
  if (!data?.portfolios?.length) return null;

  return (
    <ProfessionalCard title="Monthly Activity" className="border-border/40" variant="elevated">
      <p className="text-xs text-muted-foreground mb-4">
        Last {data.months_analyzed} months of buys, sells, and dividends
      </p>

      {data.portfolios.map((p: any) => (
        <div key={p.portfolio_id} className="mb-6 last:mb-0">
          <div className="flex justify-between items-center mb-2">
            <div>
              <p className="text-xs font-bold">{p.portfolio_name}</p>
              <p className="text-[10px] text-muted-foreground">{p.portfolio_type}</p>
            </div>
            <div className="text-right">
              <p className="text-sm font-bold">{fmt(p.current_value)}</p>
              <GainPill value={p.current_cost_basis > 0 ? ((p.current_gain_loss / p.current_cost_basis) * 100) : 0} />
            </div>
          </div>

          <div className="grid grid-cols-3 sm:grid-cols-6 gap-2">
            {p.months.map((m: any) => (
              <div key={m.month} className="text-center p-2 rounded-lg bg-muted/20 border border-border/20">
                <p className="text-[10px] text-muted-foreground font-medium mb-1">{m.month}</p>
                {m.buys > 0 && <p className="text-[9px] text-red-500">↓{fmt(m.buys)}</p>}
                {m.sells > 0 && <p className="text-[9px] text-green-500">↑{fmt(m.sells)}</p>}
                {m.dividends > 0 && <p className="text-[9px] text-blue-500">💰{fmt(m.dividends)}</p>}
                {m.buys === 0 && m.sells === 0 && m.dividends === 0 && (
                  <p className="text-[9px] text-muted-foreground/50">—</p>
                )}
              </div>
            ))}
          </div>
        </div>
      ))}

      {/* Aggregate totals */}
      <div className="mt-4 pt-4 border-t border-border/30">
        <p className="text-[10px] text-muted-foreground uppercase font-bold tracking-wider mb-2">Aggregate</p>
        <div className="grid grid-cols-3 sm:grid-cols-6 gap-2">
          {data.aggregate_months?.map((m: any) => (
            <div key={m.month} className="text-center p-2 rounded-lg bg-primary/5 border border-primary/10">
              <p className="text-[10px] font-medium mb-1">{m.month}</p>
              <p className={cn('text-[10px] font-bold', m.net_flow >= 0 ? 'text-green-600' : 'text-red-600')}>
                {fmt(m.net_flow)}
              </p>
            </div>
          ))}
        </div>
      </div>
    </ProfessionalCard>
  );
};

// ──────────────────────────────────────────────
// Main Page
// ──────────────────────────────────────────────
const CrossPortfolioAnalysis: React.FC = () => {
  // Fetch all data in parallel
  const { data: summary, isLoading: summaryLoading } = useQuery({
    queryKey: ['cross-portfolio', 'summary'],
    queryFn: () => investmentApi.getCrossPortfolioSummary(),
  });

  const { data: consolidated, isLoading: consolidatedLoading } = useQuery({
    queryKey: ['cross-portfolio', 'consolidated'],
    queryFn: () => investmentApi.getConsolidatedHoldings(),
  });

  const { data: overlap } = useQuery({
    queryKey: ['cross-portfolio', 'overlap'],
    queryFn: () => investmentApi.getOverlapAnalysis(),
  });

  const { data: exposure } = useQuery({
    queryKey: ['cross-portfolio', 'exposure'],
    queryFn: () => investmentApi.getExposureReport(),
  });

  const { data: monthly } = useQuery({
    queryKey: ['cross-portfolio', 'monthly'],
    queryFn: () => investmentApi.getMonthlyComparison(6),
  });

  const isLoading = summaryLoading || consolidatedLoading;

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center p-12 min-h-[400px] space-y-4">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary" />
        <p className="text-muted-foreground animate-pulse font-medium">Analyzing across portfolios…</p>
      </div>
    );
  }

  return (
    <div className="space-y-8 animate-in fade-in duration-700 pb-20">
      <PageHeader
        title="Cross-Portfolio Analysis"
        description="Consolidated insights across all your investment portfolios — find overlaps, compare stocks, and monitor concentration risk."
        actions={
          <Link
            to="/investments"
            className="inline-flex items-center gap-2 text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Portfolios
          </Link>
        }
      />

      {/* ── KPI Cards ─────────────────────────── */}
      <ContentSection>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <MetricCard
            title="Total Combined Value"
            value={fmt(summary?.total_combined_value ?? 0)}
            icon={Activity}
            description={`Across ${summary?.portfolio_count ?? 0} portfolios`}
          />
          <MetricCard
            title="Total Gain / Loss"
            value={pct(summary?.total_gain_loss_pct ?? 0)}
            change={{
              value: summary?.total_gain_loss ?? 0,
              type: (summary?.total_gain_loss ?? 0) >= 0 ? 'increase' : 'decrease',
            }}
            icon={TrendingUp}
            variant={(summary?.total_gain_loss_pct ?? 0) >= 0 ? 'success' : 'danger'}
            description="Unrealised across all portfolios"
          />
          <MetricCard
            title="Unique Securities"
            value={summary?.total_unique_securities ?? 0}
            icon={Layers}
            description={`${summary?.overlapping_securities_count ?? 0} overlap between portfolios`}
          />
          <MetricCard
            title="Concentration Alerts"
            value={summary?.concentration_warnings?.length ?? 0}
            icon={ShieldAlert}
            variant={(summary?.concentration_warnings?.length ?? 0) > 0 ? 'warning' : 'default'}
            description="Stocks above 20% exposure"
          />
        </div>
      </ContentSection>

      {/* ── Main Content ──────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left column — 2/3 */}
        <div className="lg:col-span-2 space-y-8">
          <ConsolidatedHoldings data={consolidated} />
          <MonthlySection data={monthly} />
        </div>

        {/* Right column — 1/3 */}
        <div className="space-y-8">
          <OverlapSection data={overlap} />
          <ExposureSection data={exposure} />
        </div>
      </div>
    </div>
  );
};

export default CrossPortfolioAnalysis;
