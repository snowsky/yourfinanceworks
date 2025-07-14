import * as React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { TrendingUp, DollarSign, Calendar, CreditCard } from 'lucide-react';

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
        return 'bg-blue-100 text-blue-800';
      case 'cash':
        return 'bg-green-100 text-green-800';
      case 'check':
      case 'bank_transfer':
        return 'bg-purple-100 text-purple-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  return (
    <div className="space-y-6">
      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="bg-gradient-to-br from-blue-50 to-blue-100 border-blue-200">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-blue-600">Total Amount</p>
                <p className="text-2xl font-bold text-blue-900">
                  {formatCurrency(chartData.summary.total_amount)}
                </p>
              </div>
              <DollarSign className="h-8 w-8 text-blue-500" />
            </div>
          </CardContent>
        </Card>

        <Card className="bg-gradient-to-br from-green-50 to-green-100 border-green-200">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-green-600">Total Payments</p>
                <p className="text-2xl font-bold text-green-900">
                  {chartData.summary.total_payments}
                </p>
              </div>
              <TrendingUp className="h-8 w-8 text-green-500" />
            </div>
          </CardContent>
        </Card>

        <Card className="bg-gradient-to-br from-purple-50 to-purple-100 border-purple-200">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-purple-600">Average Payment</p>
                <p className="text-2xl font-bold text-purple-900">
                  {formatCurrency(chartData.summary.average_amount)}
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
                <p className="text-sm font-medium text-orange-600">Date Range</p>
                <p className="text-xs font-medium text-orange-900">
                  {chartData.summary.date_range.earliest && chartData.summary.date_range.latest
                    ? `${formatDate(chartData.summary.date_range.earliest)} - ${formatDate(chartData.summary.date_range.latest)}`
                    : 'N/A'}
                </p>
              </div>
              <Calendar className="h-8 w-8 text-orange-500" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Payment Methods Chart */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <CreditCard className="h-5 w-5" />
            Payment Methods Distribution
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {chartData.by_method.map((method, index) => (
              <div key={method.method} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                <div className="flex items-center gap-3">
                  {getMethodIcon(method.method)}
                  <div>
                    <p className="font-medium capitalize">
                      {method.method.replace('_', ' ')}
                    </p>
                    <p className="text-sm text-gray-500">
                      {((method.amount / chartData.summary.total_amount) * 100).toFixed(1)}% of total
                    </p>
                  </div>
                </div>
                <div className="text-right">
                  <p className="font-bold text-lg">{formatCurrency(method.amount)}</p>
                  <Badge className={getMethodColor(method.method)}>
                    {method.method.replace('_', ' ')}
                  </Badge>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Timeline Chart */}
      {chartData.timeline.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <TrendingUp className="h-5 w-5" />
              Payment Timeline
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {chartData.timeline.map((item, index) => (
                <div key={item.date} className="flex items-center justify-between p-3 bg-gradient-to-r from-blue-50 to-purple-50 rounded-lg border border-blue-100">
                  <div className="flex items-center gap-3">
                    <div className="w-3 h-3 bg-blue-500 rounded-full"></div>
                    <div>
                      <p className="font-medium">{formatDate(item.date)}</p>
                      <p className="text-sm text-gray-500">
                        {(paymentsArray || []).filter(p => 
                          new Date(p.payment_date).toDateString() === new Date(item.date).toDateString()
                        ).length} payments
                      </p>
                    </div>
                  </div>
                  <p className="font-bold text-lg text-blue-700">
                    {formatCurrency(item.amount)}
                  </p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Recent Payments List */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <DollarSign className="h-5 w-5" />
            Recent Payments
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {paymentsArray.slice(0, 5).map((payment) => (
              <div key={payment.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg border border-gray-200">
                <div className="flex items-center gap-3">
                  {getMethodIcon(payment.payment_method)}
                  <div>
                    <p className="font-medium">
                      Payment #{payment.id} - Invoice #{payment.invoice_id}
                    </p>
                    <p className="text-sm text-gray-500">
                      {formatDate(payment.payment_date)} • {payment.payment_method}
                    </p>
                  </div>
                </div>
                <div className="text-right">
                  <p className="font-bold text-lg">{formatCurrency(payment.amount)}</p>
                  <Badge className={getMethodColor(payment.payment_method)}>
                    {payment.payment_method}
                  </Badge>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default PaymentCharts; 