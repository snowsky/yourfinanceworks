import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { CalendarIcon, TrendingUp, TrendingDown, DollarSign, Calendar, BarChart3, RefreshCw } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { expenseApi } from '@/lib/api';
import { Loader2 } from 'lucide-react';
import { format } from 'date-fns';

interface ExpenseSummaryProps {
  className?: string;
}

interface SummaryData {
  period: {
    start_date: string;
    end_date: string;
    period_type: string;
  };
  current_period: {
    total_amount: number;
    total_count: number;
    average_amount: number;
  };
  previous_period?: {
    total_amount: number;
    total_count: number;
    average_amount: number;
  };
  changes?: {
    total_amount_change_percent: number | null;
    count_change_percent: number | null;
  };
  category_breakdown: Array<{
    category: string;
    amount: number;
    percentage: number;
  }>;
  daily_totals: Array<{
    date: string;
    amount: number;
  }>;
}

const ExpenseSummary: React.FC<ExpenseSummaryProps> = ({ className }) => {
  const { t } = useTranslation();
  const [summaryData, setSummaryData] = useState<SummaryData | null>(null);
  const [loading, setLoading] = useState(true);
  const [period, setPeriod] = useState('month');
  const [error, setError] = useState<string | null>(null);

  const loadSummary = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await expenseApi.getExpenseSummary({
        period,
        compare_with_previous: true
      });
      setSummaryData(data as SummaryData);
    } catch (err) {
      console.error('Failed to load expense summary:', err);
      setError('Failed to load expense summary');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadSummary();
  }, [period]);

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(amount);
  };

  const formatDate = (dateString: string) => {
    try {
      return format(new Date(dateString), 'MMM dd, yyyy');
    } catch {
      return dateString;
    }
  };

  if (loading) {
    return (
      <Card className={className}>
        <CardContent className="flex items-center justify-center p-8">
          <Loader2 className="h-6 w-6 animate-spin mr-2" />
          Loading expense summary...
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className={className}>
        <CardContent className="flex items-center justify-center p-8">
          <div className="text-center">
            <p className="text-red-600 mb-4">{error}</p>
            <Button onClick={loadSummary} size="sm">
              <RefreshCw className="h-4 w-4 mr-2" />
              Try Again
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (!summaryData) return null;

  return (
    <div className={`space-y-6 ${className}`}>
      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="bg-gradient-to-br from-blue-50 to-blue-100 border-blue-200">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-blue-600">{t('expenses.total_expenses')}</p>
                <p className="text-2xl font-bold text-blue-900">
                  {formatCurrency(summaryData.current_period.total_amount)}
                </p>
                {summaryData.changes?.total_amount_change_percent !== null && (
                  <div className="flex items-center gap-1 mt-1">
                    {summaryData.changes.total_amount_change_percent >= 0 ? (
                      <TrendingUp className="h-3 w-3 text-red-500" />
                    ) : (
                      <TrendingDown className="h-3 w-3 text-green-500" />
                    )}
                    <span className={`text-xs ${summaryData.changes.total_amount_change_percent >= 0 ? 'text-red-500' : 'text-green-500'}`}>
                      {Math.abs(summaryData.changes.total_amount_change_percent).toFixed(1)}%
                    </span>
                  </div>
                )}
              </div>
              <DollarSign className="h-8 w-8 text-blue-500" />
            </div>
          </CardContent>
        </Card>

        <Card className="bg-gradient-to-br from-green-50 to-green-100 border-green-200">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-green-600">{t('expenses.total_transactions')}</p>
                <p className="text-2xl font-bold text-green-900">
                  {summaryData.current_period.total_count}
                </p>
                {summaryData.changes?.count_change_percent !== null && (
                  <div className="flex items-center gap-1 mt-1">
                    {summaryData.changes.count_change_percent >= 0 ? (
                      <TrendingUp className="h-3 w-3 text-red-500" />
                    ) : (
                      <TrendingDown className="h-3 w-3 text-green-500" />
                    )}
                    <span className={`text-xs ${summaryData.changes.count_change_percent >= 0 ? 'text-red-500' : 'text-green-500'}`}>
                      {Math.abs(summaryData.changes.count_change_percent).toFixed(1)}%
                    </span>
                  </div>
                )}
              </div>
              <BarChart3 className="h-8 w-8 text-green-500" />
            </div>
          </CardContent>
        </Card>

        <Card className="bg-gradient-to-br from-purple-50 to-purple-100 border-purple-200">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-purple-600">{t('expenses.average_expense')}</p>
                <p className="text-2xl font-bold text-purple-900">
                  {formatCurrency(summaryData.current_period.average_amount)}
                </p>
              </div>
              <Calendar className="h-8 w-8 text-purple-500" />
            </div>
          </CardContent>
        </Card>

        <Card className="bg-gradient-to-br from-orange-50 to-orange-100 border-orange-200">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-orange-600">{t('expenses.date_range')}</p>
                <p className="text-xs font-medium text-orange-900">
                  {formatDate(summaryData.period.start_date)} - {formatDate(summaryData.period.end_date)}
                </p>
                <p className="text-xs text-orange-700 mt-1 capitalize">
                  {summaryData.period.period_type} view
                </p>
              </div>
              <CalendarIcon className="h-8 w-8 text-orange-500" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Controls */}
      <Card>
        <CardContent className="p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <label className="text-sm font-medium">Period:</label>
                <Select value={period} onValueChange={setPeriod}>
                  <SelectTrigger className="w-[120px]">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="day">Daily</SelectItem>
                    <SelectItem value="week">Weekly</SelectItem>
                    <SelectItem value="month">Monthly</SelectItem>
                    <SelectItem value="quarter">Quarterly</SelectItem>
                    <SelectItem value="year">Yearly</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <Button onClick={loadSummary} size="sm" variant="outline">
              <RefreshCw className="h-4 w-4 mr-2" />
              Refresh
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Category Breakdown */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <BarChart3 className="h-5 w-5" />
            {t('expenses.expense_categories', { defaultValue: 'Expense Categories' })}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {summaryData.category_breakdown.map((category) => (
              <div key={category.category} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                <div className="flex items-center gap-3">
                  <div className="w-3 h-3 bg-blue-500 rounded-full"></div>
                  <div>
                    <p className="font-medium">{category.category}</p>
                    <p className="text-sm text-gray-500">
                      {category.percentage.toFixed(1)}% of total
                    </p>
                  </div>
                </div>
                <div className="text-right">
                  <p className="font-bold text-lg">{formatCurrency(category.amount)}</p>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default ExpenseSummary;
