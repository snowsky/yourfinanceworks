import React, { useState, useEffect } from 'react';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { DatePickerWithRange } from '@/components/ui/date-range-picker';
import { Alert, AlertDescription } from '@/components/ui/alert';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
} from 'recharts';
import {
  Clock,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Users,
  FileText,
  Download,
  RefreshCw,
} from 'lucide-react';
import { DateRange } from 'react-day-picker';
import { addDays, format } from 'date-fns';
import { apiRequest, API_BASE_URL } from '@/lib/api';
import { useTranslation } from 'react-i18next';

interface ApprovalMetrics {
  total_approvals: number;
  pending_approvals: number;
  approved_count: number;
  rejected_count: number;
  average_approval_time: number;
  median_approval_time: number;
  approval_rate: number;
  rejection_rate: number;
  bottlenecks: BottleneckInfo[];
  approver_performance: ApproverPerformance[];
  category_breakdown: Record<string, CategoryBreakdown>;
  monthly_trends: Record<string, MonthlyTrend>;
  compliance_issues: ComplianceIssue[];
}

interface BottleneckInfo {
  approver_id: number;
  approver_name: string;
  average_time_hours: number;
  approval_count: number;
  is_bottleneck: boolean;
}

interface ApproverPerformance {
  approver_id: number;
  approver_name: string;
  total_assigned: number;
  approved: number;
  rejected: number;
  pending: number;
  approval_rate: number;
  average_time_hours: number;
  efficiency_score: number;
}

interface CategoryBreakdown {
  total: number;
  approved: number;
  rejected: number;
  pending: number;
  approval_rate: number;
  average_time_hours: number;
  total_amount: number;
  average_amount: number;
}

interface MonthlyTrend {
  total_submitted: number;
  approved: number;
  rejected: number;
  pending: number;
  approval_rate: number;
  average_time_hours: number;
  total_amount: number;
}

interface ComplianceIssue {
  type: string;
  approval_id?: number;
  expense_id?: number;
  approver_id?: number;
  delay_hours?: number;
  description: string;
}

interface PatternAnalysis {
  common_rejection_reasons: RejectionReason[];
  approval_time_by_amount: Record<string, number>;
  approval_time_by_category: Record<string, number>;
  peak_submission_times: PeakSubmissionTimes;
  escalation_patterns: EscalationPattern[];
  recommendations: ProcessRecommendation[];
}

interface RejectionReason {
  reason: string;
  count: number;
  total_amount: number;
}

interface PeakSubmissionTimes {
  by_hour: Record<string, number>;
  by_day: Record<string, number>;
}

interface EscalationPattern {
  expense_id: number;
  levels: number;
  total_time_hours: number;
  level_times: Array<{
    level: number;
    time_hours: number;
    approver_id: number;
  }>;
}

interface ProcessRecommendation {
  type: string;
  priority: string;
  title: string;
  description: string;
  impact: string;
}

interface ComplianceReport {
  total_expenses: number;
  expenses_requiring_approval: number;
  expenses_bypassed_approval: number;
  compliance_rate: number;
  policy_violations: PolicyViolation[];
  rule_effectiveness: RuleEffectiveness[];
  delegation_usage: DelegationUsage;
}

interface PolicyViolation {
  expense_id: number;
  amount: number;
  category?: string;
  expense_date: string;
  violation_type: string;
  description: string;
}

interface RuleEffectiveness {
  rule_id: number;
  rule_name: string;
  approval_count: number;
  is_active: boolean;
  effectiveness_score: number;
}

interface DelegationUsage {
  total_delegations: number;
  active_delegations: number;
  average_duration_days: number;
  most_delegating_approvers: Array<{
    approver_id: number;
    delegation_count: number;
  }>;
}

const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#8884D8'];

export default function ApprovalReportsPage() {
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState('overview');
  const [dateRange, setDateRange] = useState<DateRange | undefined>({
    from: addDays(new Date(), -30),
    to: new Date(),
  });
  const [selectedApprover, setSelectedApprover] = useState<string>('all');
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Data states
  const [metrics, setMetrics] = useState<ApprovalMetrics | null>(null);
  const [patterns, setPatterns] = useState<PatternAnalysis | null>(null);
  const [compliance, setCompliance] = useState<ComplianceReport | null>(null);

  useEffect(() => {
    loadReportData();
  }, [dateRange, selectedApprover, selectedCategory]);

  const loadReportData = async () => {
    setLoading(true);
    setError(null);

    try {
      const params = new URLSearchParams();
      if (dateRange?.from) {
        params.append('date_from', dateRange.from.toISOString());
      }
      if (dateRange?.to) {
        params.append('date_to', dateRange.to.toISOString());
      }
      if (selectedApprover !== 'all') {
        params.append('approver_ids', selectedApprover);
      }
      if (selectedCategory !== 'all') {
        params.append('categories', selectedCategory);
      }

      // Load metrics
      const metricsData = await apiRequest<ApprovalMetrics>(`/approval-reports/metrics?${params}`);
      setMetrics(metricsData);

      // Load patterns
      const patternsData = await apiRequest<PatternAnalysis>(`/approval-reports/patterns?${params}`);
      setPatterns(patternsData);

      // Load compliance (if user has permission)
      try {
        const complianceData = await apiRequest<ComplianceReport>(`/approval-reports/compliance?${params}`);
        setCompliance(complianceData);
      } catch (e) {
        // User might not have compliance permissions
        console.log('Compliance data not available');
      }

    } catch (err) {
      setError(t('approvalReports.failed_to_load'));
      console.error('Error loading report data:', err);
    } finally {
      setLoading(false);
    }
  };

  const exportReport = async (format: string) => {
    try {
      const params = new URLSearchParams();
      if (dateRange?.from) {
        params.append('date_from', dateRange.from.toISOString());
      }
      if (dateRange?.to) {
        params.append('date_to', dateRange.to.toISOString());
      }

      const response = await fetch(`${API_BASE_URL}/approval-reports/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          report_type: 'metrics',
          filters: {
            date_from: dateRange?.from?.toISOString(),
            date_to: dateRange?.to?.toISOString(),
            approver_ids: selectedApprover !== 'all' ? [parseInt(selectedApprover)] : null,
            categories: selectedCategory !== 'all' ? [selectedCategory] : null,
          },
          export_format: format,
        }),
      });

      if (response.ok) {
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `approval-report-${format}.${format}`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
      }
    } catch (err) {
      console.error('Error exporting report:', err);
    }
  };

  const formatHours = (hours: number) => {
    if (hours < 1) {
      return `${Math.round(hours * 60)}m`;
    } else if (hours < 24) {
      return `${Math.round(hours * 10) / 10}h`;
    } else {
      return `${Math.round(hours / 24 * 10) / 10}d`;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'approved':
        return 'bg-green-100 text-green-800';
      case 'rejected':
        return 'bg-red-100 text-red-800';
      case 'pending':
        return 'bg-yellow-100 text-yellow-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'high':
        return 'bg-red-100 text-red-800';
      case 'medium':
        return 'bg-yellow-100 text-yellow-800';
      case 'low':
        return 'bg-blue-100 text-blue-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  if (loading && !metrics) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="h-8 w-8 animate-spin" />
        <span className="ml-2">{t('approvalReports.loading')}</span>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">{t('approvalReports.title')}</h1>
          <p className="text-muted-foreground">
            {t('approvalReports.description')}
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={() => exportReport('pdf')}
            disabled={loading}
          >
            <Download className="h-4 w-4 mr-2" />
            {t('approvalReports.export_pdf')}
          </Button>
          <Button
            variant="outline"
            onClick={() => exportReport('excel')}
            disabled={loading}
          >
            <Download className="h-4 w-4 mr-2" />
            {t('approvalReports.export_excel')}
          </Button>
          <Button onClick={loadReportData} disabled={loading}>
            <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
            {t('approvalReports.refresh')}
          </Button>
        </div>
      </div>

      {/* Filters */}
      <Card>
        <CardHeader>
          <CardTitle>{t('approvalReports.filters.title')}</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex gap-4 items-end">
            <div className="flex-1">
              <label className="text-sm font-medium mb-2 block">{t('approvalReports.filters.date_range')}</label>
              <DatePickerWithRange
                date={dateRange}
                onDateChange={setDateRange}
              />
            </div>
            <div>
              <label className="text-sm font-medium mb-2 block">{t('approvalReports.filters.approver')}</label>
              <Select value={selectedApprover} onValueChange={setSelectedApprover}>
                <SelectTrigger className="w-48">
                  <SelectValue placeholder={t('approvalReports.filters.select_approver')} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">{t('approvalReports.filters.all_approvers')}</SelectItem>
                  {/* Add dynamic approver options here */}
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="text-sm font-medium mb-2 block">{t('approvalReports.filters.category')}</label>
              <Select value={selectedCategory} onValueChange={setSelectedCategory}>
                <SelectTrigger className="w-48">
                  <SelectValue placeholder={t('approvalReports.filters.select_category')} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">{t('approvalReports.filters.all_categories')}</SelectItem>
                  <SelectItem value="travel">{t('approvalReports.filters.travel')}</SelectItem>
                  <SelectItem value="meals">{t('approvalReports.filters.meals')}</SelectItem>
                  <SelectItem value="office">{t('approvalReports.filters.office_supplies')}</SelectItem>
                  <SelectItem value="equipment">{t('approvalReports.filters.equipment')}</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardContent>
      </Card>

      {error && (
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="overview">{t('approvalReports.tabs.overview')}</TabsTrigger>
          <TabsTrigger value="performance">{t('approvalReports.tabs.performance')}</TabsTrigger>
          <TabsTrigger value="patterns">{t('approvalReports.tabs.patterns')}</TabsTrigger>
          <TabsTrigger value="compliance">{t('approvalReports.tabs.compliance')}</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-6">
          {metrics && (
            <>
              {/* Key Metrics Cards */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                <Card>
                  <CardContent className="p-6">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm font-medium text-muted-foreground">
                          {t('approvalReports.metrics.total_approvals')}
                        </p>
                        <p className="text-2xl font-bold">{metrics.total_approvals}</p>
                      </div>
                      <FileText className="h-8 w-8 text-muted-foreground" />
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardContent className="p-6">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm font-medium text-muted-foreground">
                          {t('approvalReports.metrics.approval_rate')}
                        </p>
                        <p className="text-2xl font-bold">
                          {Math.round(metrics.approval_rate)}%
                        </p>
                      </div>
                      <CheckCircle className="h-8 w-8 text-green-500" />
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardContent className="p-6">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm font-medium text-muted-foreground">
                          {t('approvalReports.metrics.avg_approval_time')}
                        </p>
                        <p className="text-2xl font-bold">
                          {formatHours(metrics.average_approval_time)}
                        </p>
                      </div>
                      <Clock className="h-8 w-8 text-blue-500" />
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardContent className="p-6">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm font-medium text-muted-foreground">
                          {t('approvalReports.metrics.pending_approvals')}
                        </p>
                        <p className="text-2xl font-bold">{metrics.pending_approvals}</p>
                      </div>
                      <Clock className="h-8 w-8 text-yellow-500" />
                    </div>
                  </CardContent>
                </Card>
              </div>

              {/* Monthly Trends Chart */}
              <Card>
                <CardHeader>
                  <CardTitle>{t('approvalReports.overview.monthly_trends.title')}</CardTitle>
                  <CardDescription>
                    {t('approvalReports.overview.monthly_trends.description')}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="h-80">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart
                        data={Object.entries(metrics.monthly_trends).map(([month, data]) => ({
                          month,
                          submitted: data.total_submitted,
                          approved: data.approved,
                          rejected: data.rejected,
                          approval_rate: data.approval_rate,
                        }))}
                      >
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="month" />
                        <YAxis yAxisId="left" />
                        <YAxis yAxisId="right" orientation="right" />
                        <Tooltip />
                        <Bar yAxisId="left" dataKey="submitted" fill="#8884d8" name="Submitted" />
                        <Bar yAxisId="left" dataKey="approved" fill="#82ca9d" name="Approved" />
                        <Bar yAxisId="left" dataKey="rejected" fill="#ffc658" name="Rejected" />
                        <Line
                          yAxisId="right"
                          type="monotone"
                          dataKey="approval_rate"
                          stroke="#ff7300"
                          name="Approval Rate %"
                        />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </CardContent>
              </Card>

              {/* Category Breakdown */}
              <Card>
                <CardHeader>
                  <CardTitle>{t('approvalReports.overview.category_breakdown.title')}</CardTitle>
                  <CardDescription>
                    {t('approvalReports.overview.category_breakdown.description')}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    {Object.entries(metrics.category_breakdown).map(([category, data]) => (
                      <div key={category} className="space-y-2">
                        <div className="flex justify-between items-center">
                          <span className="font-medium capitalize">{category}</span>
                          <div className="flex gap-4 text-sm text-muted-foreground">
                            <span>{data.total} {t('approvalReports.overview.category_breakdown.total')}</span>
                            <span>{Math.round(data.approval_rate)}% {t('approvalReports.overview.category_breakdown.approved')}</span>
                            <span>{formatHours(data.average_time_hours)} {t('approvalReports.overview.category_breakdown.avg_time')}</span>
                          </div>
                        </div>
                        <Progress
                          value={data.approval_rate}
                          className="h-2"
                        />
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </>
          )}
        </TabsContent>

        <TabsContent value="performance" className="space-y-6">
          {metrics && (
            <>
              {/* Bottlenecks */}
              <Card>
                <CardHeader>
                  <CardTitle>{t('approvalReports.performance.bottlenecks.title')}</CardTitle>
                  <CardDescription>
                    {t('approvalReports.performance.bottlenecks.description')}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    {metrics.bottlenecks.map((bottleneck) => (
                      <div
                        key={bottleneck.approver_id}
                        className="flex items-center justify-between p-4 border rounded-lg"
                      >
                        <div className="flex items-center gap-3">
                          <Users className="h-5 w-5 text-muted-foreground" />
                          <div>
                            <p className="font-medium">{bottleneck.approver_name}</p>
                            <p className="text-sm text-muted-foreground">
                              {bottleneck.approval_count} {t('approvalReports.performance.bottlenecks.approvals')}
                            </p>
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          <Badge
                            variant={bottleneck.is_bottleneck ? "destructive" : "secondary"}
                          >
                            {formatHours(bottleneck.average_time_hours)} {t('approvalReports.performance.bottlenecks.avg')}
                          </Badge>
                          {bottleneck.is_bottleneck && (
                            <AlertTriangle className="h-4 w-4 text-red-500" />
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>

              {/* Approver Performance */}
              <Card>
                <CardHeader>
                  <CardTitle>{t('approvalReports.performance.approver_performance.title')}</CardTitle>
                  <CardDescription>
                    {t('approvalReports.performance.approver_performance.description')}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="overflow-x-auto">
                    <table className="w-full">
                      <thead>
                        <tr className="border-b">
                          <th className="text-left p-2">{t('approvalReports.performance.approver_performance.approver')}</th>
                          <th className="text-right p-2">{t('approvalReports.performance.approver_performance.assigned')}</th>
                          <th className="text-right p-2">{t('approvalReports.performance.approver_performance.approved')}</th>
                          <th className="text-right p-2">{t('approvalReports.performance.approver_performance.rejected')}</th>
                          <th className="text-right p-2">{t('approvalReports.performance.approver_performance.pending')}</th>
                          <th className="text-right p-2">{t('approvalReports.performance.approver_performance.rate')}</th>
                          <th className="text-right p-2">{t('approvalReports.performance.approver_performance.avg_time')}</th>
                          <th className="text-right p-2">{t('approvalReports.performance.approver_performance.score')}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {metrics.approver_performance.map((perf) => (
                          <tr key={perf.approver_id} className="border-b">
                            <td className="p-2 font-medium">{perf.approver_name}</td>
                            <td className="p-2 text-right">{perf.total_assigned}</td>
                            <td className="p-2 text-right text-green-600">{perf.approved}</td>
                            <td className="p-2 text-right text-red-600">{perf.rejected}</td>
                            <td className="p-2 text-right text-yellow-600">{perf.pending}</td>
                            <td className="p-2 text-right">{Math.round(perf.approval_rate)}%</td>
                            <td className="p-2 text-right">{formatHours(perf.average_time_hours)}</td>
                            <td className="p-2 text-right">
                              <Badge
                                variant={perf.efficiency_score > 80 ? "default" : "secondary"}
                              >
                                {Math.round(perf.efficiency_score)}
                              </Badge>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </CardContent>
              </Card>
            </>
          )}
        </TabsContent>

        <TabsContent value="patterns" className="space-y-6">
          {patterns && (
            <>
              {/* Common Rejection Reasons */}
              <Card>
                <CardHeader>
                  <CardTitle>{t('approvalReports.patterns.rejection_reasons.title')}</CardTitle>
                  <CardDescription>
                    {t('approvalReports.patterns.rejection_reasons.description')}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    {patterns.common_rejection_reasons.map((reason, index) => (
                      <div key={index} className="flex items-center justify-between p-3 border rounded">
                        <div className="flex-1">
                          <p className="font-medium">{reason.reason}</p>
                          <p className="text-sm text-muted-foreground">
                            ${reason.total_amount.toLocaleString()} {t('approvalReports.patterns.rejection_reasons.total_amount')}
                          </p>
                        </div>
                        <Badge variant="outline">{reason.count} {t('approvalReports.patterns.rejection_reasons.cases')}</Badge>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>

              {/* Approval Time by Amount */}
              <Card>
                <CardHeader>
                  <CardTitle>{t('approvalReports.patterns.approval_time_by_amount.title')}</CardTitle>
                  <CardDescription>
                    {t('approvalReports.patterns.approval_time_by_amount.description')}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="h-64">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart
                        data={Object.entries(patterns.approval_time_by_amount).map(([range, time]) => ({
                          range,
                          time: Math.round(time * 10) / 10,
                        }))}
                      >
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="range" />
                        <YAxis />
                        <Tooltip formatter={(value) => [`${value} hours`, t('approvalReports.patterns.approval_time_by_amount.avg_time')]} />
                        <Bar dataKey="time" fill="#8884d8" />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </CardContent>
              </Card>

              {/* Peak Submission Times */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <Card>
                  <CardHeader>
                    <CardTitle>{t('approvalReports.patterns.peak_hours.title')}</CardTitle>
                    <CardDescription>{t('approvalReports.patterns.peak_hours.description')}</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="h-48">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart
                          data={Object.entries(patterns.peak_submission_times.by_hour).map(([hour, count]) => ({
                            hour: `${hour}:00`,
                            count,
                          }))}
                        >
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis dataKey="hour" />
                          <YAxis />
                          <Tooltip />
                          <Bar dataKey="count" fill="#82ca9d" />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle>{t('approvalReports.patterns.peak_days.title')}</CardTitle>
                    <CardDescription>{t('approvalReports.patterns.peak_days.description')}</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="h-48">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart
                          data={Object.entries(patterns.peak_submission_times.by_day).map(([day, count]) => ({
                            day,
                            count,
                          }))}
                        >
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis dataKey="day" />
                          <YAxis />
                          <Tooltip />
                          <Bar dataKey="count" fill="#ffc658" />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  </CardContent>
                </Card>
              </div>

              {/* Recommendations */}
              <Card>
                <CardHeader>
                  <CardTitle>{t('approvalReports.patterns.recommendations.title')}</CardTitle>
                  <CardDescription>
                    {t('approvalReports.patterns.recommendations.description')}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    {patterns.recommendations.map((rec, index) => (
                      <div key={index} className="p-4 border rounded-lg">
                        <div className="flex items-start justify-between mb-2">
                          <h4 className="font-medium">{rec.title}</h4>
                          <Badge className={getPriorityColor(rec.priority)}>
                            {rec.priority}
                          </Badge>
                        </div>
                        <p className="text-sm text-muted-foreground mb-2">
                          {rec.description}
                        </p>
                        <p className="text-sm font-medium text-green-600">
                          {t('approvalReports.patterns.recommendations.impact')}: {rec.impact}
                        </p>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </>
          )}
        </TabsContent>

        <TabsContent value="compliance" className="space-y-6">
          {compliance ? (
            <>
              {/* Compliance Overview */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <Card>
                  <CardContent className="p-6">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm font-medium text-muted-foreground">
                          {t('approvalReports.compliance.compliance_rate')}
                        </p>
                        <p className="text-2xl font-bold">
                          {Math.round(compliance.compliance_rate)}%
                        </p>
                      </div>
                      <CheckCircle className="h-8 w-8 text-green-500" />
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardContent className="p-6">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm font-medium text-muted-foreground">
                          {t('approvalReports.compliance.bypassed_approvals')}
                        </p>
                        <p className="text-2xl font-bold">
                          {compliance.expenses_bypassed_approval}
                        </p>
                      </div>
                      <AlertTriangle className="h-8 w-8 text-red-500" />
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardContent className="p-6">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm font-medium text-muted-foreground">
                          {t('approvalReports.compliance.policy_violations')}
                        </p>
                        <p className="text-2xl font-bold">
                          {compliance.policy_violations.length}
                        </p>
                      </div>
                      <XCircle className="h-8 w-8 text-red-500" />
                    </div>
                  </CardContent>
                </Card>
              </div>

              {/* Policy Violations */}
              <Card>
                <CardHeader>
                  <CardTitle>{t('approvalReports.compliance.violations.title')}</CardTitle>
                  <CardDescription>
                    {t('approvalReports.compliance.violations.description')}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="overflow-x-auto">
                    <table className="w-full">
                      <thead>
                        <tr className="border-b">
                          <th className="text-left p-2">{t('approvalReports.compliance.violations.expense_id')}</th>
                          <th className="text-right p-2">{t('approvalReports.compliance.violations.amount')}</th>
                          <th className="text-left p-2">{t('approvalReports.compliance.violations.category')}</th>
                          <th className="text-left p-2">{t('approvalReports.compliance.violations.date')}</th>
                          <th className="text-left p-2">{t('approvalReports.compliance.violations.violation')}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {compliance.policy_violations.map((violation) => (
                          <tr key={violation.expense_id} className="border-b">
                            <td className="p-2 font-mono">{violation.expense_id}</td>
                            <td className="p-2 text-right">${violation.amount.toLocaleString()}</td>
                            <td className="p-2 capitalize">{violation.category || 'N/A'}</td>
                            <td className="p-2">
                              {format(new Date(violation.expense_date), 'MMM dd, yyyy')}
                            </td>
                            <td className="p-2">
                              <Badge variant="destructive">
                                {violation.violation_type.replace('_', ' ')}
                              </Badge>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </CardContent>
              </Card>

              {/* Rule Effectiveness */}
              <Card>
                <CardHeader>
                  <CardTitle>{t('approvalReports.compliance.rule_effectiveness.title')}</CardTitle>
                  <CardDescription>
                    {t('approvalReports.compliance.rule_effectiveness.description')}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    {compliance.rule_effectiveness.map((rule) => (
                      <div key={rule.rule_id} className="flex items-center justify-between p-3 border rounded">
                        <div className="flex-1">
                          <p className="font-medium">{rule.rule_name}</p>
                          <p className="text-sm text-muted-foreground">
                            {rule.approval_count} {t('approvalReports.compliance.rule_effectiveness.approvals_triggered')}
                          </p>
                        </div>
                        <div className="flex items-center gap-2">
                          <Badge
                            variant={rule.is_active ? "default" : "secondary"}
                          >
                            {rule.is_active ? t('approvalReports.compliance.rule_effectiveness.active') : t('approvalReports.compliance.rule_effectiveness.inactive')}
                          </Badge>
                          <Badge variant="outline">
                            {t('approvalReports.compliance.rule_effectiveness.score')}: {Math.round(rule.effectiveness_score)}
                          </Badge>
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </>
          ) : (
            <Card>
              <CardContent className="p-6 text-center">
                <AlertTriangle className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                <h3 className="text-lg font-medium mb-2">{t('approvalReports.compliance.unavailable.title')}</h3>
                <p className="text-muted-foreground">
                  {t('approvalReports.compliance.unavailable.description')}
                </p>
              </CardContent>
            </Card>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}