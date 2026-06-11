import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { TrendingUp, BarChart3, LineChart, RefreshCw, LineChartIcon } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { expenseApi } from '@/lib/api';
import { Loader2 } from 'lucide-react';
import {
  LineChart as RechartsLineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart as RechartsBarChart,
  Bar,
  PieChart as RechartsPieChart,
  Pie,
  Cell
} from 'recharts';

interface ExpenseChartsProps {
  className?: string;
}

interface TrendsData {
  period: {
    start_date: string;
    end_date: string;
    days: number;
    group_by: string;
  };
  trends: Array<{
    period: string;
    total_amount: number;
    count: number;
    average_amount: number;
  }>;
  analysis: {
    trend_direction: string;
    volatility_percent: number;
    total_periods: number;
    total_amount: number;
    average_period_amount: number;
  };
}

const ExpenseCharts: React.FC<ExpenseChartsProps> = ({ className }) => {
  const { t } = useTranslation();
  const [trendsData, setTrendsData] = useState<TrendsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState(90);
  const [groupBy, setGroupBy] = useState('week');
  const [error, setError] = useState<string | null>(null);
  const [chartType, setChartType] = useState<'line' | 'bar'>('line');

  const loadTrends = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await expenseApi.getExpenseTrends({
        days,
        group_by: groupBy
      });
      setTrendsData(data as TrendsData);
    } catch (err) {
      console.error('Failed to load expense trends:', err);
      setError('Failed to load expense trends');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTrends();
  }, [days, groupBy]);

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(amount);
  };

  const formatTooltip = (value: any, name: string) => {
    if (name === 'total_amount') {
      return [formatCurrency(value), 'Amount'];
    }
    if (name === 'count') {
      return [value, 'Transactions'];
    }
    if (name === 'average_amount') {
      return [formatCurrency(value), 'Average'];
    }
    return [value, name];
  };

  const formatXAxisLabel = (value: string) => {
    // Format period labels based on groupBy
    if (groupBy === 'month') {
      try {
        const [year, month] = value.split('-');
        const date = new Date(parseInt(year), parseInt(month) - 1, 1);
        return date.toLocaleDateString('en-US', { month: 'short', year: 'numeric' });
      } catch {
        return value;
      }
    }
    return value;
  };

  const COLORS = [
    'hsl(var(--chart-1))',
    'hsl(var(--chart-2))',
    'hsl(var(--chart-3))',
    'hsl(var(--chart-4))',
    'hsl(var(--chart-5))',
    '#06B6D4',
    '#84CC16',
  ];

  if (loading) {
    return (
      <Card className={className}>
        <CardContent className="flex items-center justify-center p-8">
          <Loader2 className="h-6 w-6 animate-spin mr-2" />
          {t('expenses.loading_expense_charts', { defaultValue: 'Loading expense charts...'})}
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className={className}>
        <CardContent className="flex items-center justify-center p-8">
          <div className="text-center">
            <p className="text-destructive mb-4">{error}</p>
            <Button onClick={loadTrends} size="sm">
              <RefreshCw className="h-4 w-4 mr-2" />
              {t('expenses.try_again', { defaultValue: 'Try Again'})}
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (!trendsData) return null;

  return (
    <div className={`space-y-6 ${className}`}>
      {/* Controls */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <TrendingUp className="h-5 w-5" />
            {t('expenses.expense_trends', { defaultValue: 'Expense Trends' })}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap items-center gap-4">
            <div className="flex items-center gap-2">
              <label className="text-sm font-medium">{t('expenses.time_range')}:</label>
              <Select value={String(days)} onValueChange={v => setDays(parseInt(v))}>
                <SelectTrigger className="w-[120px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="30">30 days</SelectItem>
                  <SelectItem value="90">90 days</SelectItem>
                  <SelectItem value="180">6 months</SelectItem>
                  <SelectItem value="365">1 year</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="flex items-center gap-2">
              <label className="text-sm font-medium">{t('expenses.group_by')}:</label>
              <Select value={groupBy} onValueChange={setGroupBy}>
                <SelectTrigger className="w-[120px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="day">Day</SelectItem>
                  <SelectItem value="week">Week</SelectItem>
                  <SelectItem value="month">Month</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="flex items-center gap-2">
              <label className="text-sm font-medium">{t('expenses.chart_type')}:</label>
              <Select value={chartType} onValueChange={(v: 'line' | 'bar') => setChartType(v)}>
                <SelectTrigger className="w-[120px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="line">Line Chart</SelectItem>
                  <SelectItem value="bar">Bar Chart</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <Button onClick={loadTrends} size="sm" variant="outline">
              <RefreshCw className="h-4 w-4 mr-2" />
              {t('expenses.refresh', { defaultValue: 'Refresh' })}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Trend Analysis Summary */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">{t('expenses.trend_direction')}</p>
                <p className="text-lg font-bold text-foreground capitalize">
                  {trendsData.analysis.trend_direction.replace('_', ' ')}
                </p>
              </div>
              <TrendingUp className="h-8 w-8 text-muted-foreground" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">{t('expenses.total_amount')}</p>
                <p className="text-lg font-bold text-foreground">
                  {formatCurrency(trendsData.analysis.total_amount)}
                </p>
                <p className="text-xs text-muted-foreground mt-1">
                  {trendsData.analysis.total_periods} periods
                </p>
              </div>
              <BarChart3 className="h-8 w-8 text-muted-foreground" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">{t('expenses.volatility', { defaultValue: 'Volatility' })}</p>
                <p className="text-lg font-bold text-foreground">
                  {trendsData.analysis.volatility_percent.toFixed(1)}%
                </p>
                <p className="text-xs text-muted-foreground mt-1">
                  Average: {formatCurrency(trendsData.analysis.average_period_amount)}
                </p>
              </div>
              <LineChartIcon className="h-8 w-8 text-muted-foreground" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Main Chart */}
      <Card>
        <CardHeader>
          <CardTitle>{t('expenses.expense_trends_over_time')}</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="h-[400px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              {chartType === 'line' ? (
                <RechartsLineChart data={trendsData.trends}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--chart-grid))" />
                  <XAxis
                    dataKey="period"
                    tickFormatter={formatXAxisLabel}
                    fontSize={12}
                  />
                  <YAxis
                    tickFormatter={(value) => `$${value.toLocaleString()}`}
                    fontSize={12}
                  />
                  <Tooltip
                    formatter={formatTooltip}
                    labelFormatter={(label) => `Period: ${formatXAxisLabel(label)}`}
                    contentStyle={{
                      backgroundColor: 'hsl(var(--popover))',
                      color: 'hsl(var(--popover-foreground))',
                      border: '1px solid hsl(var(--border))',
                      borderRadius: 'var(--radius)',
                    }}
                  />
                  <Line
                    type="monotone"
                    dataKey="total_amount"
                    stroke="hsl(var(--chart-1))"
                    strokeWidth={3}
                    dot={{ fill: 'hsl(var(--chart-1))', strokeWidth: 2, r: 4 }}
                    activeDot={{ r: 6, stroke: 'hsl(var(--chart-1))', strokeWidth: 2 }}
                  />
                </RechartsLineChart>
              ) : (
                <RechartsBarChart data={trendsData.trends}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--chart-grid))" />
                  <XAxis
                    dataKey="period"
                    tickFormatter={formatXAxisLabel}
                    fontSize={12}
                  />
                  <YAxis
                    tickFormatter={(value) => `$${value.toLocaleString()}`}
                    fontSize={12}
                  />
                  <Tooltip
                    formatter={formatTooltip}
                    labelFormatter={(label) => `Period: ${formatXAxisLabel(label)}`}
                    contentStyle={{
                      backgroundColor: 'hsl(var(--popover))',
                      color: 'hsl(var(--popover-foreground))',
                      border: '1px solid hsl(var(--border))',
                      borderRadius: 'var(--radius)',
                    }}
                  />
                  <Bar
                    dataKey="total_amount"
                    fill="hsl(var(--chart-1))"
                    radius={[4, 4, 0, 0]}
                  />
                </RechartsBarChart>
              )}
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>

      {/* Trend Data Table */}
      <Card>
        <CardHeader>
          <CardTitle>{t('expenses.detailed_trend_data', { defaultValue: 'Detailed Trend Data' })}</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-border">
              <thead className="bg-muted">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                    Period
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                    Amount
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                    Transactions
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                    Average
                  </th>
                </tr>
              </thead>
              <tbody className="bg-card divide-y divide-border">
                {trendsData.trends.map((trend, index) => (
                  <tr key={trend.period} className={index % 2 === 0 ? 'bg-card' : 'bg-muted'}>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-foreground">
                      {formatXAxisLabel(trend.period)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-muted-foreground">
                      {formatCurrency(trend.total_amount)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-muted-foreground">
                      {trend.count}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-muted-foreground">
                      {formatCurrency(trend.average_amount)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default ExpenseCharts;
