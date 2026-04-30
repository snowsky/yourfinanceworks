import React, { useState } from 'react';
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
} from 'lucide-react';

import {
  cashflowApi,
  type ForecastPeriod,
  type CashFlowForecastResponse,
  type CashRunwayResponse,
  type CashFlowAlertResponse,
  type ScenarioInput,
  type ScenarioResult,
} from '@/lib/api/cashflow';
import { PageHeader, ContentSection } from '@/components/ui/professional-layout';
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
            <p className="text-sm text-muted-foreground">Monthly Burn</p>
            <p className="text-2xl font-bold text-red-600">{formatCurrency(runway.monthly_burn_rate)}</p>
          </div>
          <div className="text-center">
            <p className="text-sm text-muted-foreground">Monthly Income</p>
            <p className="text-2xl font-bold text-green-600">{formatCurrency(runway.monthly_income_rate)}</p>
          </div>
          <div className="text-center">
            <p className="text-sm text-muted-foreground">Runway</p>
            <p className="text-2xl font-bold">
              {runway.is_sustainable ? (
                <Badge variant="default" className="bg-green-600 text-lg px-3 py-1" aria-label="Cash flow is sustainable">Sustainable ✓</Badge>
              ) : runway.runway_days != null ? (
                <span className="text-orange-600">{runway.runway_days} days</span>
              ) : (
                <Badge variant="secondary">N/A</Badge>
              )}
            </p>
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

        <div className="h-64">
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
                fill="#3b82f680"
                strokeWidth={2}
                name="Balance"
              />
            </AreaChart>
          </ResponsiveContainer>
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

    const scenario: ScenarioInput = {
      description: description.trim(),
      revenue_change_percent: revenueChange ? parseFloat(revenueChange) : null,
      expense_change_percent: expenseChange ? parseFloat(expenseChange) : null,
      additional_expense: additionalExpense ? parseFloat(additionalExpense) : null,
      additional_expense_date: additionalExpense
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
            <label className="text-sm font-medium">Expense Change (%)</label>
            <ProfessionalInput
              type="number"
              placeholder="15 for 15% increase"
              value={expenseChange}
              onChange={(e) => setExpenseChange(e.target.value)}
            />
          </div>
          <div>
            <label className="text-sm font-medium">Additional One-Time Expense ($)</label>
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

// ---- Main Page ----
const CashFlow: React.FC = () => {
  const { t } = useTranslation();
  const [period, setPeriod] = useState<ForecastPeriod>('30d');

  const { data: forecast, isLoading: forecastLoading } = useQuery({
    queryKey: ['cashflow-forecast', period],
    queryFn: () => cashflowApi.getForecast(period),
  });

  const { data: runway, isLoading: runwayLoading } = useQuery({
    queryKey: ['cashflow-runway'],
    queryFn: () => cashflowApi.getRunway(),
  });

  const { data: alerts } = useQuery({
    queryKey: ['cashflow-alerts'],
    queryFn: () => cashflowApi.getAlerts(),
  });

  return (
    <div className="space-y-6">
      <PageHeader
        title={t('cashflow.title', { defaultValue: 'Cash Flow' })}
        subtitle={t('cashflow.subtitle', { defaultValue: 'Forecast, runway analysis, and scenario planning' })}
      />

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
          </SelectContent>
        </Select>
      </div>

      {/* Alerts */}
      <AlertsBanner alerts={alerts} />

      {/* Runway */}
      <RunwayCard runway={runway} isLoading={runwayLoading} />

      {/* Forecast chart */}
      <ForecastChart forecast={forecast} isLoading={forecastLoading} />

      {/* Scenario builder */}
      <ScenarioBuilder />
    </div>
  );
};

export default CashFlow;
