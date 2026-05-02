import React, { useEffect, useState } from 'react';
import { Link as RouterLink } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import {
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  DollarSign,
  Calendar,
  Activity,
  Shield,
  Zap,
  FileText,
  Landmark,
  Save,
} from 'lucide-react';

import {
  cashflowApi,
  type ForecastPeriod,
  type CashFlowForecastResponse,
  type CashRunwayResponse,
  type CashFlowAlertResponse,
  type ScenarioInput,
  type ScenarioResult,
  type CashFlowEntry,
  type CashFlowThresholdSettings,
} from '@/lib/api/cashflow';
import { getErrorMessage } from '@/lib/api';
import { FeatureGate } from '@/components/FeatureGate';
import { useFeatures } from '@/contexts/FeatureContext';
import { PageHeader } from '@/components/ui/professional-layout';
import {
  ProfessionalCard,
  ProfessionalCardContent,
  ProfessionalCardHeader,
  ProfessionalCardTitle,
  MetricCard,
} from '@/components/ui/professional-card';
import { ProfessionalButton } from '@/components/ui/professional-button';
import { ProfessionalInput } from '@/components/ui/professional-input';
import { Badge } from '@/components/ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Area,
  AreaChart,
  ReferenceLine,
} from 'recharts';

// Milliseconds per day constant
const MS_PER_DAY = 86_400_000;

const parseOptionalScenarioNumber = (value: string, label: string): number | null => {
  if (!value.trim()) return null;

  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    throw new Error(`${label} must be a valid number`);
  }

  return parsed;
};

const clampStatementLookbackDays = (value: number): number => {
  if (!Number.isFinite(value)) return 120;
  return Math.max(30, Math.min(365, Math.round(value)));
};

// Format currency
const formatCurrency = (amount: number, currency = 'USD'): string => {
  return new Intl.NumberFormat(undefined, {
    style: 'currency',
    currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount);
};

// Format date for display
const formatDate = (dateStr: string): string => {
  return new Date(dateStr).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
};

const getSourceLabel = (entry: CashFlowEntry): string => {
  if (entry.source_label) return entry.source_label;
  return entry.category.replace(/_/g, ' ');
};

type CashFlowReferenceList = NonNullable<CashFlowEntry['references']>;

const ReferenceLinks: React.FC<{ references: CashFlowReferenceList; limit?: number }> = ({
  references,
  limit = 3,
}) => {
  if (references.length === 0) return null;

  const visibleReferences = references.slice(0, limit);
  const remainingCount = references.length - visibleReferences.length;

  return (
    <div className="mt-1 flex flex-wrap items-center gap-1.5">
      {visibleReferences.map((reference, index) => {
        const className = "inline-flex max-w-full items-center gap-1 rounded border bg-background/80 px-1.5 py-0.5 text-xs font-medium text-muted-foreground hover:text-foreground";
        const content = (
          <>
            <FileText className="h-3 w-3 flex-shrink-0" />
            <span className="truncate">{reference.label}</span>
          </>
        );

        if (reference.url) {
          return (
            <RouterLink key={`${reference.type}-${reference.id}-${index}`} to={reference.url} className={className}>
              {content}
            </RouterLink>
          );
        }

        return (
          <span key={`${reference.type}-${reference.id}-${index}`} className={className}>
            {content}
          </span>
        );
      })}
      {remainingCount > 0 && (
        <span className="text-xs text-muted-foreground">+{remainingCount} more</span>
      )}
    </div>
  );
};

const EntryReferences: React.FC<{ entry: CashFlowEntry }> = ({ entry }) => (
  <ReferenceLinks references={entry.references || []} />
);

const uniqueReferences = (entries: CashFlowEntry[]): CashFlowReferenceList => {
  const references = new Map<string, CashFlowReferenceList[number]>();
  entries.forEach((entry) => {
    (entry.references || []).forEach((reference) => {
      references.set(`${reference.type}-${reference.id}`, reference);
    });
  });
  return Array.from(references.values());
};

const buildSourceSummary = (entries: CashFlowEntry[]) => {
  const summary = new Map<string, { label: string; count: number; total: number }>();

  entries.forEach((entry) => {
    const key = entry.source || entry.category;
    const current = summary.get(key) || { label: getSourceLabel(entry), count: 0, total: 0 };
    current.count += 1;
    current.total += entry.amount;
    summary.set(key, current);
  });

  return Array.from(summary.values()).sort((a, b) => b.total - a.total);
};

type BreakdownGroup = {
  key: string;
  label: string;
  count: number;
  total: number;
  entries: CashFlowEntry[];
  references: CashFlowReferenceList;
  categories: Array<{ label: string; count: number; total: number }>;
};

const buildSourceBreakdown = (entries: CashFlowEntry[]): BreakdownGroup[] => {
  const groups = new Map<string, BreakdownGroup>();

  entries.forEach((entry) => {
    const key = entry.source || entry.category;
    const group = groups.get(key) || {
      key,
      label: getSourceLabel(entry),
      count: 0,
      total: 0,
      entries: [],
      references: [],
      categories: [],
    };

    group.count += 1;
    group.total += entry.amount;
    group.entries.push(entry);

    if (entry.source === 'bank_statement_pattern') {
      const categoryLabel = entry.description || entry.category || 'Bank statement category';
      const existingCategory = group.categories.find((item) => item.label === categoryLabel);
      if (existingCategory) {
        existingCategory.count += 1;
        existingCategory.total += entry.amount;
      } else {
        group.categories.push({ label: categoryLabel, count: 1, total: entry.amount });
      }
    }

    groups.set(key, group);
  });

  return Array.from(groups.values())
    .map((group) => ({
      ...group,
      references: uniqueReferences(group.entries),
      categories: group.categories.sort((a, b) => b.total - a.total),
    }))
    .sort((a, b) => b.total - a.total);
};

const SourceBreakdownPanel: React.FC<{
  title: string;
  entries: CashFlowEntry[];
  total: number;
  tone: 'income' | 'expense';
}> = ({ title, entries, total, tone }) => {
  const groups = buildSourceBreakdown(entries);
  const accentClass = tone === 'income' ? 'bg-green-600' : 'bg-red-600';
  const amountClass = tone === 'income' ? 'text-green-700 dark:text-green-400' : 'text-red-700 dark:text-red-400';

  return (
    <div className="rounded border bg-muted/20 p-4">
      <div className="flex items-center justify-between gap-3 mb-3">
        <p className="font-semibold">{title}</p>
        <p className={`text-sm font-semibold ${amountClass}`}>{formatCurrency(total)}</p>
      </div>
      {groups.length === 0 ? (
        <p className="text-sm text-muted-foreground">No projected entries</p>
      ) : (
        <div className="space-y-3">
          {groups.map((group) => {
            const percentage = total > 0 ? Math.round((group.total / total) * 100) : 0;

            return (
              <div key={group.key} className="space-y-2">
                <div className="flex items-center justify-between gap-3 text-sm">
                  <div className="min-w-0">
                    <p className="font-medium truncate">{group.label}</p>
                    <p className="text-xs text-muted-foreground">{group.count} projected item{group.count === 1 ? '' : 's'} · {percentage}%</p>
                  </div>
                  <p className={`font-semibold tabular-nums ${amountClass}`}>{formatCurrency(group.total)}</p>
                </div>
                <div className="h-1.5 rounded-full bg-muted overflow-hidden">
                  <div className={`h-full rounded-full ${accentClass}`} style={{ width: `${Math.min(percentage, 100)}%` }} />
                </div>
                {group.references.length > 0 && (
                  <div>
                    <p className="mb-1 text-xs font-medium text-muted-foreground">Related records</p>
                    <ReferenceLinks references={group.references} limit={5} />
                  </div>
                )}
                {group.categories.length > 0 && (
                  <div className="ml-3 space-y-1 border-l pl-3">
                    {group.categories.map((category) => (
                      <div key={category.label} className="flex items-center justify-between gap-3 text-xs">
                        <span className="text-muted-foreground truncate">{category.label} · {category.count}</span>
                        <span className={`font-medium tabular-nums ${amountClass}`}>{formatCurrency(category.total)}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

// ---- Alerts Banner ----
const AlertsBanner: React.FC<{ alerts: CashFlowAlertResponse | undefined }> = ({ alerts }) => {
  if (!alerts?.has_alerts) return null;

  return (
    <div className="mb-6 space-y-2">
      {alerts.alerts.map((alert, i) => (
        <div
          key={i}
          className={`flex items-center gap-2 p-3 rounded-lg border ${
            alert.includes('CRITICAL')
              ? 'bg-red-50 border-red-200 text-red-800 dark:bg-red-950 dark:border-red-800 dark:text-red-200'
              : alert.includes('WARNING')
              ? 'bg-yellow-50 border-yellow-200 text-yellow-800 dark:bg-yellow-950 dark:border-yellow-800 dark:text-yellow-200'
              : 'bg-blue-50 border-blue-200 text-blue-800 dark:bg-blue-950 dark:border-blue-800 dark:text-blue-200'
          }`}
        >
          <AlertTriangle className="w-4 h-4 flex-shrink-0" />
          <span className="text-sm">{alert}</span>
        </div>
      ))}
    </div>
  );
};

// ---- Runway Card ----
const RunwayCard: React.FC<{ runway: CashRunwayResponse | undefined; isLoading: boolean }> = ({
  runway,
  isLoading,
}) => {
  if (isLoading || !runway) return null;

  return (
    <ProfessionalCard>
      <ProfessionalCardHeader>
        <ProfessionalCardTitle className="flex items-center gap-2">
          <Activity className="w-5 h-5" />
          Cash Runway
        </ProfessionalCardTitle>
      </ProfessionalCardHeader>
      <ProfessionalCardContent>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="text-center">
            <p className="text-sm text-muted-foreground">Current Balance</p>
            <p className="text-2xl font-bold">{formatCurrency(runway.current_balance)}</p>
          </div>
          <div className="text-center">
            <p className="text-sm text-muted-foreground">Monthly Outflow</p>
            <p className="text-2xl font-bold text-red-600">{formatCurrency(runway.monthly_burn_rate)}</p>
          </div>
          <div className="text-center">
            <p className="text-sm text-muted-foreground">Monthly Inflow</p>
            <p className="text-2xl font-bold text-green-600">{formatCurrency(runway.monthly_income_rate)}</p>
          </div>
          <div className="text-center">
            <p className="text-sm text-muted-foreground">Runway</p>
            <div className="text-2xl font-bold">
              {runway.is_sustainable ? (
                <Badge variant="default" className="bg-green-600 text-lg px-3 py-1" aria-label="Cash flow is sustainable">Sustainable ✓</Badge>
              ) : runway.runway_days != null ? (
                <span className="text-orange-600">{runway.runway_days} days</span>
              ) : (
                <Badge variant="secondary">N/A</Badge>
              )}
            </div>
          </div>
        </div>
      </ProfessionalCardContent>
    </ProfessionalCard>
  );
};

// ---- Forecast Chart ----
const ForecastChart: React.FC<{ forecast: CashFlowForecastResponse | undefined; isLoading: boolean }> = ({
  forecast,
  isLoading,
}) => {
  if (isLoading || !forecast) return null;

  const chartData = forecast.daily_balances.map((d) => ({
    date: formatDate(d.date),
    balance: Math.round(d.projected_balance),
    inflows: Math.round(d.projected_inflows),
    outflows: Math.round(d.projected_outflows),
  }));

  return (
    <ProfessionalCard>
      <ProfessionalCardHeader>
        <ProfessionalCardTitle className="flex items-center gap-2">
          <TrendingUp className="w-5 h-5" />
          Projected Balance ({forecast.period})
        </ProfessionalCardTitle>
      </ProfessionalCardHeader>
      <ProfessionalCardContent>
        <div className="grid grid-cols-3 gap-4 mb-4">
          <div className="text-center p-3 bg-green-50 dark:bg-green-950 rounded-lg">
            <p className="text-xs text-muted-foreground">Projected Inflows</p>
            <p className="text-lg font-semibold text-green-700 dark:text-green-300">
              {formatCurrency(forecast.total_projected_inflows)}
            </p>
          </div>
          <div className="text-center p-3 bg-red-50 dark:bg-red-950 rounded-lg">
            <p className="text-xs text-muted-foreground">Projected Outflows</p>
            <p className="text-lg font-semibold text-red-700 dark:text-red-300">
              {formatCurrency(forecast.total_projected_outflows)}
            </p>
          </div>
          <div className="text-center p-3 bg-blue-50 dark:bg-blue-950 rounded-lg">
            <p className="text-xs text-muted-foreground">End Balance</p>
            <p className="text-lg font-semibold text-blue-700 dark:text-blue-300">
              {formatCurrency(forecast.projected_end_balance)}
            </p>
          </div>
        </div>

        {forecast.alerts.length > 0 && (
          <div className="mb-4 space-y-1">
            {forecast.alerts.map((a, i) => (
              <p key={i} className="text-sm text-orange-600 dark:text-orange-400">{a}</p>
            ))}
          </div>
        )}

        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="date" tick={{ fontSize: 11 }} interval="preserveStartEnd" />
              <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} />
              <Tooltip
                formatter={(value: number) => formatCurrency(value)}
                labelFormatter={(label) => `Date: ${label}`}
              />
              <Area
                type="monotone"
                dataKey="balance"
                stroke="#3b82f6"
                fill="#3b82f620"
                strokeWidth={2}
                name="Balance"
              />
              <Area
                type="monotone"
                dataKey="inflows"
                stroke="#16a34a"
                fill="#16a34a30"
                strokeWidth={1.5}
                name="Inflows"
              />
              <Area
                type="monotone"
                dataKey="outflows"
                stroke="#dc2626"
                fill="#dc262630"
                strokeWidth={1.5}
                name="Outflows"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </ProfessionalCardContent>
    </ProfessionalCard>
  );
};

// ---- Inflow & Outflow Breakdown ----
const InflowOutflowBreakdown: React.FC<{ forecast: CashFlowForecastResponse | undefined; isLoading: boolean }> = ({
  forecast,
  isLoading,
}) => {
  if (isLoading || !forecast) return null;

  const inflows = forecast.inflow_entries || [];
  const outflows = forecast.outflow_entries || [];
  const inflowSources = buildSourceSummary(inflows);
  const outflowSources = buildSourceSummary(outflows);

  if (inflows.length === 0 && outflows.length === 0) {
    return (
      <ProfessionalCard>
        <ProfessionalCardHeader>
          <ProfessionalCardTitle className="flex items-center gap-2">
            <DollarSign className="w-5 h-5" />
            Inflow &amp; Outflow Breakdown
          </ProfessionalCardTitle>
        </ProfessionalCardHeader>
        <ProfessionalCardContent>
          <p className="text-muted-foreground text-sm">No projected inflows or outflows found for this period. Add invoices, expenses, or bank statements to see projections here.</p>
        </ProfessionalCardContent>
      </ProfessionalCard>
    );
  }

  return (
    <ProfessionalCard>
      <ProfessionalCardHeader>
        <ProfessionalCardTitle className="flex items-center gap-2">
          <DollarSign className="w-5 h-5" />
          Inflow &amp; Outflow Breakdown
        </ProfessionalCardTitle>
      </ProfessionalCardHeader>
      <ProfessionalCardContent>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
          <div className="rounded border p-3 bg-muted/30">
            <p className="text-xs font-medium text-muted-foreground mb-2">Inflow sources</p>
            <div className="flex flex-wrap gap-2">
              {inflowSources.length === 0 ? (
                <span className="text-xs text-muted-foreground">No projected inflow sources</span>
              ) : inflowSources.map((source) => (
                <Badge key={source.label} variant="secondary" className="font-normal">
                  {source.label}: {source.count} · {formatCurrency(source.total)}
                </Badge>
              ))}
            </div>
          </div>
          <div className="rounded border p-3 bg-muted/30">
            <p className="text-xs font-medium text-muted-foreground mb-2">Outflow sources</p>
            <div className="flex flex-wrap gap-2">
              {outflowSources.length === 0 ? (
                <span className="text-xs text-muted-foreground">No projected outflow sources</span>
              ) : outflowSources.map((source) => (
                <Badge key={source.label} variant="secondary" className="font-normal">
                  {source.label}: {source.count} · {formatCurrency(source.total)}
                </Badge>
              ))}
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
          <SourceBreakdownPanel
            title="Inflow breakdown"
            entries={inflows}
            total={forecast.total_projected_inflows}
            tone="income"
          />
          <SourceBreakdownPanel
            title="Outflow breakdown"
            entries={outflows}
            total={forecast.total_projected_outflows}
            tone="expense"
          />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Inflows */}
          <div>
            <h4 className="flex items-center gap-2 font-semibold text-green-700 dark:text-green-400 mb-3">
              <TrendingUp className="w-4 h-4" />
              Inflows ({inflows.length} items) — {formatCurrency(forecast.total_projected_inflows)}
            </h4>
            {inflows.length === 0 ? (
              <p className="text-sm text-muted-foreground">No projected inflows</p>
            ) : (
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {inflows.map((entry, i) => (
                  <div key={i} className="flex items-center justify-between p-2 rounded border bg-green-50/50 dark:bg-green-950/30">
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate">{entry.description || entry.category}</p>
                      <p className="text-xs text-muted-foreground">
                        {formatDate(entry.date)} • {getSourceLabel(entry)}
                        {entry.source_details ? ` • ${entry.source_details}` : ''}
                      </p>
                      <EntryReferences entry={entry} />
                    </div>
                    <div className="text-right ml-2">
                      <p className="text-sm font-semibold text-green-700 dark:text-green-400">+{formatCurrency(entry.amount)}</p>
                      <p className="text-xs text-muted-foreground">{Math.round(entry.confidence * 100)}% conf.</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Outflows */}
          <div>
            <h4 className="flex items-center gap-2 font-semibold text-red-700 dark:text-red-400 mb-3">
              <TrendingDown className="w-4 h-4" />
              Outflows ({outflows.length} items) — {formatCurrency(forecast.total_projected_outflows)}
            </h4>
            {outflows.length === 0 ? (
              <p className="text-sm text-muted-foreground">No projected outflows</p>
            ) : (
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {outflows.map((entry, i) => (
                  <div key={i} className="flex items-center justify-between p-2 rounded border bg-red-50/50 dark:bg-red-950/30">
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate">{entry.description || entry.category}</p>
                      <p className="text-xs text-muted-foreground">
                        {formatDate(entry.date)} • {getSourceLabel(entry)}
                        {entry.source_details ? ` • ${entry.source_details}` : ''}
                      </p>
                      <EntryReferences entry={entry} />
                    </div>
                    <div className="text-right ml-2">
                      <p className="text-sm font-semibold text-red-700 dark:text-red-400">-{formatCurrency(entry.amount)}</p>
                      <p className="text-xs text-muted-foreground">{Math.round(entry.confidence * 100)}% conf.</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </ProfessionalCardContent>
    </ProfessionalCard>
  );
};

// ---- Scenario Builder ----
const ScenarioBuilder: React.FC = () => {
  const [description, setDescription] = useState('');
  const [revenueChange, setRevenueChange] = useState('');
  const [expenseChange, setExpenseChange] = useState('');
  const [additionalExpense, setAdditionalExpense] = useState('');
  const [result, setResult] = useState<ScenarioResult | null>(null);

  const scenarioMutation = useMutation({
    mutationFn: (scenario: ScenarioInput) => cashflowApi.runScenario(scenario, '30d'),
    onSuccess: (data) => {
      setResult(data);
      toast.success('Scenario analysis complete');
    },
    onError: () => {
      toast.error('Failed to run scenario');
    },
  });

  const handleRunScenario = () => {
    if (!description.trim()) {
      toast.error('Please provide a scenario description');
      return;
    }

    let parsedRevenueChange: number | null;
    let parsedExpenseChange: number | null;
    let parsedAdditionalExpense: number | null;

    try {
      parsedRevenueChange = parseOptionalScenarioNumber(revenueChange, 'Revenue change');
      parsedExpenseChange = parseOptionalScenarioNumber(expenseChange, 'Expense change');
      parsedAdditionalExpense = parseOptionalScenarioNumber(additionalExpense, 'Additional expense');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Please enter valid scenario values');
      return;
    }

    if (parsedRevenueChange != null && parsedRevenueChange < -100) {
      toast.error('Revenue change cannot reduce revenue below zero');
      return;
    }

    if (parsedExpenseChange != null && parsedExpenseChange < -100) {
      toast.error('Outflow change cannot reduce outflows below zero');
      return;
    }

    if (parsedAdditionalExpense != null && parsedAdditionalExpense < 0) {
      toast.error('Additional outflow cannot be negative');
      return;
    }

    const scenario: ScenarioInput = {
      description: description.trim(),
      revenue_change_percent: parsedRevenueChange,
      expense_change_percent: parsedExpenseChange,
      additional_expense: parsedAdditionalExpense,
      additional_expense_date: parsedAdditionalExpense != null
        ? new Date(Date.now() + 7 * MS_PER_DAY).toISOString().split('T')[0]
        : null,
    };

    scenarioMutation.mutate(scenario);
  };

  return (
    <ProfessionalCard>
      <ProfessionalCardHeader>
        <ProfessionalCardTitle className="flex items-center gap-2">
          <Zap className="w-5 h-5" />
          What-If Scenario
        </ProfessionalCardTitle>
      </ProfessionalCardHeader>
      <ProfessionalCardContent>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
          <div>
            <label className="text-sm font-medium">Scenario Description</label>
            <ProfessionalInput
              placeholder="e.g., Revenue drops 20%"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>
          <div>
            <label className="text-sm font-medium">Revenue Change (%)</label>
            <ProfessionalInput
              type="number"
              placeholder="-20 for 20% drop"
              value={revenueChange}
              onChange={(e) => setRevenueChange(e.target.value)}
            />
          </div>
          <div>
            <label className="text-sm font-medium">Outflow Change (%)</label>
            <ProfessionalInput
              type="number"
              placeholder="15 for 15% increase"
              value={expenseChange}
              onChange={(e) => setExpenseChange(e.target.value)}
            />
          </div>
          <div>
            <label className="text-sm font-medium">Additional One-Time Outflow ($)</label>
            <ProfessionalInput
              type="number"
              placeholder="10000"
              value={additionalExpense}
              onChange={(e) => setAdditionalExpense(e.target.value)}
            />
          </div>
        </div>

        <ProfessionalButton
          onClick={handleRunScenario}
          disabled={scenarioMutation.isPending}
        >
          {scenarioMutation.isPending ? 'Running...' : 'Run Scenario'}
        </ProfessionalButton>

        {result && (
          <div className="mt-4 p-4 border rounded-lg bg-muted/50">
            <h4 className="font-semibold mb-2">{result.scenario_description}</h4>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-3">
              <div>
                <p className="text-xs text-muted-foreground">Baseline End</p>
                <p className="font-medium">{formatCurrency(result.baseline_end_balance)}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Scenario End</p>
                <p className="font-medium">{formatCurrency(result.scenario_end_balance)}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Impact</p>
                <p className={`font-medium ${result.balance_impact < 0 ? 'text-red-600' : 'text-green-600'}`}>
                  {formatCurrency(result.balance_impact)}
                </p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Lowest Balance</p>
                <p className={`font-medium ${result.lowest_balance < 0 ? 'text-red-600' : ''}`}>
                  {formatCurrency(result.lowest_balance)}
                </p>
              </div>
            </div>
            {result.alerts.length > 0 && (
              <div className="space-y-1">
                {result.alerts.map((a, i) => (
                  <p key={i} className="text-sm text-orange-600">{a}</p>
                ))}
              </div>
            )}
          </div>
        )}
      </ProfessionalCardContent>
    </ProfessionalCard>
  );
};

const StatementPatternSidebar: React.FC<{ period: ForecastPeriod }> = ({ period }) => {
  const queryClient = useQueryClient();
  const [lookbackDays, setLookbackDays] = useState(120);

  const { data: settings, isLoading } = useQuery({
    queryKey: ['cashflow-settings'],
    queryFn: () => cashflowApi.getThresholds(),
  });

  useEffect(() => {
    if (!settings) return;
    setLookbackDays(clampStatementLookbackDays(settings.bank_statement_lookback_days));
  }, [settings]);

  const saveMutation = useMutation({
    mutationFn: (nextLookbackDays: number) =>
      cashflowApi.updateThresholds({
        bank_statement_lookback_days: clampStatementLookbackDays(nextLookbackDays),
      } satisfies Partial<CashFlowThresholdSettings>),
    onSuccess: (saved) => {
      setLookbackDays(clampStatementLookbackDays(saved.bank_statement_lookback_days));
      queryClient.invalidateQueries({ queryKey: ['cashflow-settings'] });
      queryClient.invalidateQueries({ queryKey: ['cashflow-forecast'] });
      toast.success('Statement pattern history saved');
    },
    onError: (error) => {
      toast.error(getErrorMessage(error));
    },
  });

  const effectiveLookbackDays = Math.max(lookbackDays, period === '365d' ? 365 : 0);
  const isDisabled = isLoading || saveMutation.isPending || settings?.include_bank_statement_patterns === false;

  return (
    <ProfessionalCard>
      <ProfessionalCardHeader>
        <ProfessionalCardTitle className="flex items-center gap-2 text-base">
          <Landmark className="h-4 w-4" />
          Statement Pattern History
        </ProfessionalCardTitle>
      </ProfessionalCardHeader>
      <ProfessionalCardContent className="space-y-4">
        <div className="space-y-2">
          <label htmlFor="cashflow-sidebar-lookback" className="text-sm font-medium">
            History used for pattern detection
          </label>
          <ProfessionalInput
            id="cashflow-sidebar-lookback"
            type="number"
            min={30}
            max={365}
            value={lookbackDays}
            onChange={(event) => setLookbackDays(clampStatementLookbackDays(Number(event.target.value)))}
            disabled={isDisabled}
          />
        </div>
        <div className="rounded border bg-muted/30 p-3 text-xs text-muted-foreground">
          Using {effectiveLookbackDays} days for this forecast. Yearly forecasts use up to 365 days so older statement
          sources can be detected.
        </div>
        {settings?.include_bank_statement_patterns === false && (
          <p className="text-xs text-muted-foreground">
            Bank statement patterns are disabled in Cash Flow settings.
          </p>
        )}
        <ProfessionalButton
          onClick={() => saveMutation.mutate(lookbackDays)}
          disabled={isDisabled}
          className="w-full gap-2"
        >
          <Save className="h-4 w-4" />
          {saveMutation.isPending ? 'Saving...' : 'Save History Window'}
        </ProfessionalButton>
      </ProfessionalCardContent>
    </ProfessionalCard>
  );
};

// ---- Main Page ----
const CashFlow: React.FC = () => {
  const { t } = useTranslation();
  const { isFeatureEnabled } = useFeatures();
  const cashflowEnabled = isFeatureEnabled('cash_flow');
  const [period, setPeriod] = useState<ForecastPeriod>('30d');

  const { data: forecast, isLoading: forecastLoading } = useQuery({
    queryKey: ['cashflow-forecast', period],
    queryFn: () => cashflowApi.getForecast(period),
    enabled: cashflowEnabled,
  });

  const { data: runway, isLoading: runwayLoading } = useQuery({
    queryKey: ['cashflow-runway'],
    queryFn: () => cashflowApi.getRunway(),
    enabled: cashflowEnabled,
  });

  const { data: alerts } = useQuery({
    queryKey: ['cashflow-alerts'],
    queryFn: () => cashflowApi.getAlerts(),
    enabled: cashflowEnabled,
  });

  return (
    <FeatureGate
      feature="cash_flow"
      showUpgradePrompt={true}
      upgradeMessage="Cash Flow forecasting requires a commercial license."
      showExpiredContent={false}
    >
      <div className="space-y-6">
      <PageHeader
        title={t('cashflow.title', { defaultValue: 'Cash Flow' })}
        subtitle={t('cashflow.subtitle', { defaultValue: 'Forecast, runway analysis, and scenario planning' })}
      />

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <div className="space-y-6">
          {/* Period selector */}
          <div className="flex items-center gap-3">
            <span className="text-sm font-medium text-muted-foreground">Forecast Period:</span>
            <Select value={period} onValueChange={(v) => setPeriod(v as ForecastPeriod)}>
              <SelectTrigger className="w-32">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="7d">7 Days</SelectItem>
                <SelectItem value="30d">30 Days</SelectItem>
                <SelectItem value="90d">90 Days</SelectItem>
                <SelectItem value="365d">365 Days</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Alerts */}
          <AlertsBanner alerts={alerts} />

          {/* Runway */}
          <RunwayCard runway={runway} isLoading={runwayLoading} />

          {/* Forecast chart */}
          <ForecastChart forecast={forecast} isLoading={forecastLoading} />

          {/* Inflow & Outflow breakdown */}
          <InflowOutflowBreakdown forecast={forecast} isLoading={forecastLoading} />

          {/* Scenario builder */}
          <ScenarioBuilder />
        </div>

        <aside className="space-y-4 lg:sticky lg:top-6 lg:self-start">
          <StatementPatternSidebar period={period} />
        </aside>
      </div>
      </div>
    </FeatureGate>
  );
};

export default CashFlow;
