import { useState, useEffect } from "react";
import { CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PageHeader } from "@/components/ui/professional-layout";
import { ProfessionalCard, MetricCard } from "@/components/ui/professional-card";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, LineChart, Line, PieChart, Pie, Cell } from 'recharts';
import { BarChart3, TrendingUp, Users, Clock, RefreshCw, Bot, Activity } from "lucide-react";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { formatDate } from '@/lib/utils';

interface AnalyticsData {
  path_stats: Array<{
    path: string;
    views: number;
    avg_response_time: number;
  }>;
  daily_stats: Array<{
    date: string;
    views: number;
  }>;
  user_stats: Array<{
    user: string;
    views: number;
  }>;
  total_views: number;
}

interface AIProviderData {
  ai_configs: Array<{
    id: number;
    provider_name: string;
    usage_count: number;
    last_used_at?: string;
    is_active: boolean;
    is_default: boolean;
  }>;
  total_usage: number;
  active_providers: number;
}

const Analytics = () => {
  const [data, setData] = useState<AnalyticsData | null>(null);
  const [aiData, setAIData] = useState<AIProviderData | null>(null);
  const [loading, setLoading] = useState(true);
  const [aiLoading, setAILoading] = useState(true);
  const [days, setDays] = useState("7");

  const fetchAnalytics = async () => {
    try {
      setLoading(true);
      const response = await api.get<AnalyticsData>(`/analytics/page-views?days=${days}`);
      setData(response);
    } catch (error) {
      console.error('Failed to fetch analytics:', error);
      toast.error('Failed to load analytics data');
    } finally {
      setLoading(false);
    }
  };

  const fetchAIAnalytics = async () => {
    try {
      setAILoading(true);
      const response = await api.get<any[]>('/ai-config/');
      const configs = response;
      const totalUsage = configs.reduce((sum: number, config: any) => sum + (config.usage_count || 0), 0);
      const activeProviders = configs.filter((config: any) => config.is_active).length;

      setAIData({
        ai_configs: configs,
        total_usage: totalUsage,
        active_providers: activeProviders
      });
    } catch (error) {
      console.error('Failed to fetch AI analytics:', error);
      // Don't show error toast for AI data as it's secondary
    } finally {
      setAILoading(false);
    }
  };

  useEffect(() => {
    fetchAnalytics();
    fetchAIAnalytics();
  }, [days]);

  if (loading) {
    return (
      <>
        <div className="h-full flex items-center justify-center">
          <div className="flex items-center gap-2">
            <RefreshCw className="h-6 w-6 animate-spin" />
            Loading analytics...
          </div>
        </div>
      </>
    );
  }

  return (
    <>
      <div className="h-full space-y-6 fade-in">
        <PageHeader
          title="Analytics"
          description="Usage analytics and insights"
          actions={
            <div className="flex gap-2">
              <Select value={days} onValueChange={setDays}>
                <SelectTrigger className="w-[150px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="7">Last 7 days</SelectItem>
                  <SelectItem value="14">Last 14 days</SelectItem>
                  <SelectItem value="30">Last 30 days</SelectItem>
                  <SelectItem value="90">Last 90 days</SelectItem>
                </SelectContent>
              </Select>
              <Button onClick={fetchAnalytics} variant="outline">
                <RefreshCw className="h-4 w-4 mr-2" />
                Refresh
              </Button>
            </div>
          }
        />

        {/* Summary Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <MetricCard
            title="Total Views"
            value={data?.total_views || 0}
            icon={BarChart3}
          />

          <MetricCard
            title="Active Users"
            value={data?.user_stats.length || 0}
            icon={Users}
          />

          <MetricCard
            title="AI Usage"
            value={aiData?.total_usage || 0}
            icon={Bot}
            description={`${aiData?.active_providers || 0} active providers`}
          />

          <MetricCard
            title="Avg Response"
            value={`${Math.round(data?.path_stats.reduce((acc, stat) => acc + stat.avg_response_time, 0) / (data?.path_stats.length || 1) || 0)}ms`}
            icon={Clock}
          />
        </div>

        {/* Charts */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Daily Views Chart */}
          {/* Daily Views Chart */}
          <ProfessionalCard>
            <CardHeader>
              <CardTitle>Daily Page Views</CardTitle>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={data?.daily_stats || []}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis
                    dataKey="date"
                    tickFormatter={(value) => new Date(value).toLocaleDateString()}
                  />
                  <YAxis />
                  <Tooltip
                    labelFormatter={(value) => new Date(value).toLocaleDateString()}
                  />
                  <Line type="monotone" dataKey="views" stroke="#8884d8" strokeWidth={2} />
                </LineChart>
              </ResponsiveContainer>
            </CardContent>
          </ProfessionalCard>

          {/* Top Pages Chart */}
          {/* Top Pages Chart */}
          <ProfessionalCard>
            <CardHeader>
              <CardTitle>Most Popular Pages</CardTitle>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={data?.path_stats.slice(0, 8) || []}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis
                    dataKey="path"
                    tickFormatter={(value) => value.split('/').pop() || value}
                    angle={-45}
                    textAnchor="end"
                    height={60}
                  />
                  <YAxis />
                  <Tooltip />
                  <Bar dataKey="views" fill="#8884d8" />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </ProfessionalCard>
        </div>

        {/* AI Provider Usage Chart */}
        {!aiLoading && aiData && aiData.ai_configs.length > 0 && (
          <ProfessionalCard>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Bot className="h-5 w-5" />
                AI Provider Usage
              </CardTitle>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={aiData.ai_configs}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis
                    dataKey="provider_name"
                    tickFormatter={(value) => value || 'Unknown'}
                  />
                  <YAxis />
                  <Tooltip
                    labelFormatter={(value) => `${value || 'Unknown'} Provider`}
                  />
                  <Bar dataKey="usage_count" fill="#8884d8" name="Usage Count" />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </ProfessionalCard>
        )}

        {/* Tables */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Top Users */}
          {/* Top Users */}
          <ProfessionalCard>
            <CardHeader>
              <CardTitle>Most Active Users</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {data?.user_stats.slice(0, 10).map((user, index) => (
                  <div key={user.user} className="flex justify-between items-center p-2 rounded hover:bg-muted/50">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-muted-foreground">#{index + 1}</span>
                      <span className="text-sm">{user.user}</span>
                    </div>
                    <span className="text-sm font-medium">{user.views} views</span>
                  </div>
                ))}
              </div>
            </CardContent>
          </ProfessionalCard>

          {/* Performance */}
          {/* Performance */}
          <ProfessionalCard>
            <CardHeader>
              <CardTitle>Page Performance</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {data?.path_stats.slice(0, 10).map((page, index) => (
                  <div key={page.path} className="flex justify-between items-center p-2 rounded hover:bg-muted/50">
                    <div className="flex-1">
                      <div className="text-sm font-medium">
                        {page.path.split('/').pop() || page.path}
                      </div>
                      <div className="text-xs text-muted-foreground">{page.views} views</div>
                    </div>
                    <div className="text-right">
                      <div className="text-sm font-medium">{Math.round(page.avg_response_time)}ms</div>
                      <div className="text-xs text-muted-foreground">avg response</div>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </ProfessionalCard>
        </div>
      </div>
    </>
  );
};

export default Analytics;