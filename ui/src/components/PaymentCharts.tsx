import * as React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { TrendingUp, DollarSign, Calendar, CreditCard } from 'lucide-react';
import { useTranslation } from 'react-i18next';

interface PaymentChartData {
  timeline: Array<{ date: string; amount: number }>;
  by_method: Array<{ method: string; amount: number }>;
  summary: {
    total_amount: number;
    total_payments: number;
    average_amount: number;
    date_range: {
      earliest: string | null;
      latest: string | null;
    };
  };
}

interface PaymentChartsProps {
  chartData: PaymentChartData;
  payments: any[];
}

const PaymentCharts: React.FC<PaymentChartsProps> = ({ chartData, payments }) => {
  const { t } = useTranslation();
  // Ensure payments is an array
  const paymentsArray = Array.isArray(payments) ? payments : [];

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(amount);
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

  const getMethodIcon = (method: string) => {
    switch (method.toLowerCase()) {
      case 'credit_card':
      case 'card':
        return <CreditCard className="h-4 w-4" />;
      case 'cash':
        return <DollarSign className="h-4 w-4" />;
      case 'check':
      case 'bank_transfer':
        return <TrendingUp className="h-4 w-4" />;
      default:
        return <Calendar className="h-4 w-4" />;
    }
  };

  const getMethodColor = (method: string) => {
    switch (method.toLowerCase()) {
      case 'credit_card':
      case 'card':
        return 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300';
      case 'cash':
        return 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300';
      case 'check':
      case 'bank_transfer':
        return 'bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-300';
      default:
        return 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-300';
    }
  };

  return (
    <div className="space-y-4 w-full">
      {/* Summary Cards - Grid optimized for chat width (2 cols) */}
      <div className="grid grid-cols-2 gap-3">
        <Card className="bg-gradient-to-br from-blue-50 to-blue-100 dark:from-blue-900/20 dark:to-blue-800/20 border-blue-200/50 dark:border-blue-700/30 backdrop-blur-sm shadow-none">
          <CardContent className="p-3">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-xs font-medium text-blue-600 dark:text-blue-400">Total Amount</p>
                <p className="text-lg font-bold text-blue-900 dark:text-blue-100 mt-1">
                  {formatCurrency(chartData.summary.total_amount)}
                </p>
              </div>
              <div className="bg-blue-200/50 dark:bg-blue-800/50 p-1.5 rounded-full shrink-0">
                <DollarSign className="h-4 w-4 text-blue-600 dark:text-blue-300" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-gradient-to-br from-green-50 to-green-100 dark:from-green-900/20 dark:to-green-800/20 border-green-200/50 dark:border-green-700/30 backdrop-blur-sm shadow-none">
          <CardContent className="p-3">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-xs font-medium text-green-600 dark:text-green-400">Total Payments</p>
                <p className="text-lg font-bold text-green-900 dark:text-green-100 mt-1">
                  {chartData.summary.total_payments}
                </p>
              </div>
              <div className="bg-green-200/50 dark:bg-green-800/50 p-1.5 rounded-full shrink-0">
                <TrendingUp className="h-4 w-4 text-green-600 dark:text-green-300" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-gradient-to-br from-purple-50 to-purple-100 dark:from-purple-900/20 dark:to-purple-800/20 border-purple-200/50 dark:border-purple-700/30 backdrop-blur-sm shadow-none">
          <CardContent className="p-3">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-xs font-medium text-purple-600 dark:text-purple-400">Average</p>
                <p className="text-lg font-bold text-purple-900 dark:text-purple-100 mt-1">
                  {formatCurrency(chartData.summary.average_amount)}
                </p>
              </div>
              <div className="bg-purple-200/50 dark:bg-purple-800/50 p-1.5 rounded-full shrink-0">
                <Calendar className="h-4 w-4 text-purple-600 dark:text-purple-300" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-gradient-to-br from-orange-50 to-orange-100 dark:from-orange-900/20 dark:to-orange-800/20 border-orange-200/50 dark:border-orange-700/30 backdrop-blur-sm shadow-none">
          <CardContent className="p-3">
            <div className="flex items-start justify-between">
              <div className="min-w-0">
                <p className="text-xs font-medium text-orange-600 dark:text-orange-400">Date Range</p>
                <p className="text-[10px] sm:text-xs font-medium text-orange-900 dark:text-orange-100 mt-1 truncate">
                  {chartData.summary.date_range.earliest && chartData.summary.date_range.latest
                    ? `${new Date(chartData.summary.date_range.earliest).toLocaleDateString(undefined, { month: 'numeric', day: 'numeric' })} - ${new Date(chartData.summary.date_range.latest).toLocaleDateString(undefined, { month: 'numeric', day: 'numeric', year: '2-digit' })}`
                    : 'N/A'}
                </p>
              </div>
              <div className="bg-orange-200/50 dark:bg-orange-800/50 p-1.5 rounded-full shrink-0 ml-1">
                <Calendar className="h-4 w-4 text-orange-600 dark:text-orange-300" />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Payment Methods Chart */}
      <div className="bg-white/50 dark:bg-gray-900/50 border border-white/20 dark:border-gray-800 backdrop-blur-sm rounded-xl overflow-hidden">
        <div className="px-4 py-3 border-b border-gray-100 dark:border-gray-800/50 flex items-center gap-2">
          <CreditCard className="h-4 w-4 text-muted-foreground" />
          <h3 className="font-semibold text-sm">{t('dashboard.paymentMethodsDistribution')}</h3>
        </div>
        <div className="p-3">
          <div className="space-y-2">
            {chartData.by_method.map((method, index) => (
              <div key={method.method} className="flex items-center justify-between p-2.5 bg-white/60 dark:bg-black/20 rounded-lg border border-gray-100 dark:border-gray-800/50">
                <div className="flex items-center gap-2">
                  <div className={`p-1.5 rounded-md ${getMethodColor(method.method).split(' ')[0]}`}>
                    {getMethodIcon(method.method)}
                  </div>
                  <div>
                    <p className="font-medium capitalize text-xs">
                      {method.method.replace('_', ' ')}
                    </p>
                    <div className="w-24 h-1.5 bg-gray-100 dark:bg-gray-800 rounded-full mt-1 overflow-hidden">
                      <div
                        className="h-full bg-indigo-500 rounded-full"
                        style={{ width: `${(method.amount / chartData.summary.total_amount) * 100}%` }}
                      />
                    </div>
                  </div>
                </div>
                <div className="text-right">
                  <p className="font-bold text-xs">{formatCurrency(method.amount)}</p>
                  <p className="text-[10px] text-muted-foreground">{((method.amount / chartData.summary.total_amount) * 100).toFixed(0)}%</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Timeline Chart - simplified for chat */}
      {chartData.timeline.length > 0 && (
        <div className="bg-white/50 dark:bg-gray-900/50 border border-white/20 dark:border-gray-800 backdrop-blur-sm rounded-xl overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-100 dark:border-gray-800/50 flex items-center gap-2">
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
            <h3 className="font-semibold text-sm">Recent Activity</h3>
          </div>
          <div className="p-3 max-h-[200px] overflow-y-auto custom-scrollbar">
            <div className="space-y-2">
              {chartData.timeline.slice(0, 5).map((item, index) => (
                <div key={item.date} className="flex items-center justify-between text-xs py-1">
                  <span className="text-muted-foreground">{formatDate(item.date)}</span>
                  <span className="font-medium">{formatCurrency(item.amount)}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default PaymentCharts;