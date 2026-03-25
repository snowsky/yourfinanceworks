import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Badge } from "@/components/ui/badge";
import { 
  Loader2, 
  FileText, 
  Users, 
  Package, 
  CheckCircle, 
  Bell, 
  Calendar, 
  TrendingUp,
  Filter,
  RefreshCw,
  Clock,
  ArrowLeft
} from "lucide-react";
import { toast } from "sonner";
import { Link, useNavigate } from "react-router-dom";
import { formatDate } from "@/lib/utils";
import { activityApi, ActivityItem } from "@/lib/api";
import { PageHeader, ContentSection } from '@/components/ui/professional-layout';
import { ProfessionalButton } from '@/components/ui/professional-button';
import { ProfessionalCard } from '@/components/ui/professional-card';

export function ActivityPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [allActivities, setAllActivities] = useState<ActivityItem[]>([]);
  const [activities, setActivities] = useState<ActivityItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<ActivityItem['type'] | 'all'>('all');
  const [dateRange, setDateRange] = useState<'today' | 'week' | 'month' | 'all'>('all');

  const getActivityIcon = (type: ActivityItem['type']) => {
    switch (type) {
      case 'invoice':
        return <FileText className="h-5 w-5 text-blue-600" />;
      case 'client':
        return <Users className="h-5 w-5 text-green-600" />;
      case 'inventory':
        return <Package className="h-5 w-5 text-purple-600" />;
      case 'approval':
        return <CheckCircle className="h-5 w-5 text-orange-600" />;
      case 'reminder':
        return <Bell className="h-5 w-5 text-red-600" />;
      case 'expense':
        return <TrendingUp className="h-5 w-5 text-indigo-600" />;
      case 'report':
        return <Calendar className="h-5 w-5 text-teal-600" />;
      default:
        return <FileText className="h-5 w-5 text-gray-600" />;
    }
  };

  const getActivityBadge = (type: ActivityItem['type'], status?: string) => {
    if (status) {
      switch (status) {
        case 'paid':
        case 'approved':
        case 'completed':
          return <Badge className="bg-green-100 text-green-800 border-green-200">{t('dashboard.activity.badges.completed')}</Badge>;
        case 'pending':
        case 'draft':
          return <Badge className="bg-yellow-100 text-yellow-800 border-yellow-200">{t('dashboard.activity.badges.pending')}</Badge>;
        case 'overdue':
        case 'rejected':
          return <Badge className="bg-red-100 text-red-800 border-red-200">{t('dashboard.activity.badges.attention')}</Badge>;
        default:
          return <Badge className="bg-gray-100 text-gray-800 border-gray-200">{status}</Badge>;
      }
    }

    switch (type) {
      case 'invoice':
        return <Badge className="bg-blue-100 text-blue-800 border-blue-200">{t('dashboard.activity.badges.invoice')}</Badge>;
      case 'client':
        return <Badge className="bg-green-100 text-green-800 border-green-200">{t('dashboard.activity.badges.client')}</Badge>;
      case 'inventory':
        return <Badge className="bg-purple-100 text-purple-800 border-purple-200">{t('dashboard.activity.badges.inventory')}</Badge>;
      case 'approval':
        return <Badge className="bg-orange-100 text-orange-800 border-orange-200">{t('dashboard.activity.badges.approval')}</Badge>;
      case 'reminder':
        return <Badge className="bg-red-100 text-red-800 border-red-200">{t('dashboard.activity.badges.reminder')}</Badge>;
      case 'expense':
        return <Badge className="bg-indigo-100 text-indigo-800 border-indigo-200">{t('dashboard.activity.badges.expense')}</Badge>;
      case 'report':
        return <Badge className="bg-teal-100 text-teal-800 border-teal-200">{t('dashboard.activity.badges.report')}</Badge>;
      default:
        return <Badge className="bg-gray-100 text-gray-800 border-gray-200">{t('dashboard.activity.badges.activity')}</Badge>;
    }
  };

  const fetchActivities = async () => {
    setLoading(true);
    try {
      // Fetch all activities without any filters
      const fetchedActivities = await activityApi.getRecentActivities(100);
      setAllActivities(fetchedActivities);
    } catch (error) {
      console.error("Failed to fetch activities:", error);
      toast.error("Failed to load activities");
      setAllActivities([]);
    } finally {
      setLoading(false);
    }
  };

  // Apply filters to the activities
  const applyFilters = () => {
    let filteredActivities = [...allActivities];

    // Apply activity type filter
    if (filter !== 'all') {
      filteredActivities = filteredActivities.filter(activity => activity.type === filter);
    }

    // Apply date range filter
    if (dateRange !== 'all') {
      const now = new Date();
      let startDate: Date;
      
      switch (dateRange) {
        case 'today':
          startDate = new Date(now.getFullYear(), now.getMonth(), now.getDate());
          break;
        case 'week':
          startDate = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
          break;
        case 'month':
          startDate = new Date(now.getFullYear(), now.getMonth(), 1);
          break;
        default:
          startDate = new Date(0);
      }
      
      filteredActivities = filteredActivities.filter(activity => 
        new Date(activity.timestamp) >= startDate
      );
    }

    setActivities(filteredActivities);
  };

  useEffect(() => {
    fetchActivities();
  }, []);

  useEffect(() => {
    applyFilters();
  }, [allActivities, filter, dateRange]);

  const formatAmount = (amount?: number, currency?: string) => {
    if (!amount || !currency) return null;
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currency
    }).format(amount);
  };

  const getRelativeTime = (timestamp: string) => {
    const now = new Date();
    const activityTime = new Date(timestamp);
    const diffInMinutes = Math.floor((now.getTime() - activityTime.getTime()) / (1000 * 60));
    
    if (diffInMinutes < 1) return 'Just now';
    if (diffInMinutes < 60) return `${diffInMinutes}m ago`;
    
    const diffInHours = Math.floor(diffInMinutes / 60);
    if (diffInHours < 24) return `${diffInHours}h ago`;
    
    const diffInDays = Math.floor(diffInHours / 24);
    if (diffInDays < 7) return `${diffInDays}d ago`;
    
    return formatDate(timestamp);
  };

  const activityTypes = [
    { value: 'all', label: t('dashboard.activity.all_activities'), count: allActivities.length },
    { value: 'invoice', label: t('dashboard.activity.badges.invoice'), count: allActivities.filter(a => a.type === 'invoice').length },
    { value: 'client', label: t('dashboard.activity.badges.client'), count: allActivities.filter(a => a.type === 'client').length },
    { value: 'expense', label: t('dashboard.activity.badges.expense'), count: allActivities.filter(a => a.type === 'expense').length },
    { value: 'approval', label: t('dashboard.activity.badges.approval'), count: allActivities.filter(a => a.type === 'approval').length },
    { value: 'reminder', label: t('dashboard.activity.badges.reminder'), count: allActivities.filter(a => a.type === 'reminder').length },
    { value: 'report', label: t('dashboard.activity.badges.report'), count: allActivities.filter(a => a.type === 'report').length },
  ];

  return (
    <div className="space-y-8">
      {/* Page Header */}
      <PageHeader
        title={t('dashboard.activity.timeline_title')}
        description={t('dashboard.activity.timeline_description')}
        breadcrumbs={[
          { label: t('common.dashboard'), href: '/' },
          { label: t('dashboard.activity.timeline_title') }
        ]}
        actions={
          <div className="flex items-center gap-3">
            <ProfessionalButton 
              variant="ghost" 
              size="sm"
              onClick={() => navigate('/')}
            >
              <ArrowLeft className="h-4 w-4" />
              {t('dashboard.activity.back_to_dashboard')}
            </ProfessionalButton>
            <ProfessionalButton 
              variant="outline" 
              size="sm"
              onClick={fetchActivities}
              disabled={loading}
            >
              <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
              {t('dashboard.activity.refresh')}
            </ProfessionalButton>
          </div>
        }
      />

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
          {/* Enhanced Filters Sidebar */}
          <div className="lg:col-span-1">
            <div className="space-y-6">
              {/* Quick Stats Card */}
              <ProfessionalCard className="p-6">
                <h3 className="font-semibold mb-4 flex items-center gap-2">
                  <TrendingUp className="h-4 w-4 text-primary" />
                  {t('dashboard.activity.activity_summary')}
                </h3>
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">{t('dashboard.activity.total_activities')}</span>
                    <span className="font-semibold">{allActivities.length}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">{t('dashboard.activity.this_week')}</span>
                    <span className="font-semibold text-green-600">
                      {allActivities.filter(a => {
                        const activityDate = new Date(a.timestamp);
                        const weekAgo = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000);
                        return activityDate >= weekAgo;
                      }).length}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">{t('dashboard.activity.today')}</span>
                    <span className="font-semibold text-blue-600">
                      {allActivities.filter(a => {
                        const activityDate = new Date(a.timestamp);
                        const today = new Date();
                        return activityDate.toDateString() === today.toDateString();
                      }).length}
                    </span>
                  </div>
                </div>
              </ProfessionalCard>

              {/* Filters Card */}
              <ProfessionalCard className="p-6">
                <div className="space-y-6">
                  <div>
                    <h3 className="font-semibold mb-4 flex items-center gap-2">
                      <Filter className="h-4 w-4" />
                      {t('dashboard.activity.filters')}
                    </h3>
                    
                    {/* Activity Type Filter */}
                    <div className="space-y-3">
                      <label className="text-sm font-medium text-muted-foreground">{t('dashboard.activity.activity_type')}</label>
                      <div className="space-y-1">
                        {activityTypes.map((type) => (
                          <button
                            key={type.value}
                            onClick={() => setFilter(type.value as any)}
                            className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-all duration-200 flex items-center justify-between group ${
                              filter === type.value 
                                ? 'bg-primary text-primary-foreground shadow-sm' 
                                : 'hover:bg-muted/50 hover:shadow-sm'
                            }`}
                          >
                            <span className="flex items-center gap-2">
                              {type.value === 'invoice' && <FileText className="h-3 w-3" />}
                              {type.value === 'client' && <Users className="h-3 w-3" />}
                              {type.value === 'expense' && <TrendingUp className="h-3 w-3" />}
                              {type.value === 'approval' && <CheckCircle className="h-3 w-3" />}
                              {type.value === 'reminder' && <Bell className="h-3 w-3" />}
                              {type.value === 'report' && <Calendar className="h-3 w-3" />}
                              {type.value === 'all' && <Filter className="h-3 w-3" />}
                              {type.label}
                            </span>
                            <Badge className={`text-xs transition-colors ${
                              filter === type.value 
                                ? 'bg-white/20 text-white border-white/20' 
                                : 'bg-muted text-muted-foreground border-muted'
                            }`}>
                              {type.count}
                            </Badge>
                          </button>
                        ))}
                      </div>
                    </div>

                    {/* Date Range Filter */}
                    <div className="space-y-3 mt-6">
                      <label className="text-sm font-medium text-muted-foreground">{t('dashboard.activity.time_period')}</label>
                      <div className="space-y-1">
                        {[
                          { value: 'all', label: t('dashboard.activity.all_activities'), icon: Calendar },
                          { value: 'today', label: t('dashboard.activity.today'), icon: Clock },
                          { value: 'week', label: t('dashboard.activity.this_week'), icon: Calendar },
                          { value: 'month', label: t('dashboard.activity.this_month'), icon: Calendar }
                        ].map((period) => {
                          const Icon = period.icon;
                          return (
                            <button
                              key={period.value}
                              onClick={() => setDateRange(period.value as any)}
                              className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-all duration-200 flex items-center gap-2 ${
                                dateRange === period.value 
                                  ? 'bg-primary text-primary-foreground shadow-sm' 
                                  : 'hover:bg-muted/50 hover:shadow-sm'
                              }`}
                            >
                              <Icon className="h-3 w-3" />
                              {period.label}
                            </button>
                          );
                        })}
                      </div>
                    </div>

                    {/* Clear Filters */}
                    {(filter !== 'all' || dateRange !== 'all') && (
                      <div className="pt-4 border-t border-border/50">
                        <ProfessionalButton 
                          variant="outline" 
                          size="sm" 
                          onClick={() => {
                            setFilter('all');
                            setDateRange('all');
                          }}
                          className="w-full"
                        >
                          {t('dashboard.activity.clear_all_filters')}
                        </ProfessionalButton>
                      </div>
                    )}
                  </div>
                </div>
              </ProfessionalCard>
            </div>
          </div>

          {/* Activity Timeline */}
          <div className="lg:col-span-3">
            <ContentSection 
              title={`${t('dashboard.activity.timeline_title')} (${activities.length})`}
              description={t('dashboard.activity.chronological_view')}
            >
              {loading ? (
                <div className="flex justify-center items-center h-64">
                  <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                </div>
              ) : activities.length > 0 ? (
                <div className="space-y-4">
                  {activities.map((activity, index) => (
                    <ProfessionalCard key={activity.id} className="p-6 hover:shadow-md transition-shadow">
                      <div className="flex items-start gap-4">
                        {/* Timeline indicator */}
                        <div className="relative">
                          <div className="p-3 rounded-full bg-muted/50 border-2 border-background shadow-sm">
                            {getActivityIcon(activity.type)}
                          </div>
                          {index < activities.length - 1 && (
                            <div className="absolute top-12 left-1/2 transform -translate-x-1/2 w-0.5 h-8 bg-border"></div>
                          )}
                        </div>

                        {/* Activity content */}
                        <div className="flex-1 min-w-0">
                          <div className="flex items-start justify-between gap-4">
                            <div className="flex-1">
                              <div className="flex items-center gap-3 mb-2">
                                <h3 className="font-semibold text-lg">
                                  {activity.link ? (
                                    <Link to={activity.link} className="hover:underline text-primary">
                                      {activity.title}
                                    </Link>
                                  ) : (
                                    activity.title
                                  )}
                                </h3>
                                {getActivityBadge(activity.type, activity.status)}
                              </div>
                              
                              <p className="text-muted-foreground mb-3">
                                {activity.description}
                              </p>
                              
                              <div className="flex items-center gap-4 text-sm text-muted-foreground">
                                <div className="flex items-center gap-1">
                                  <Clock className="h-3 w-3" />
                                  <span>{getRelativeTime(activity.timestamp)}</span>
                                </div>
                                {activity.amount && (
                                  <div className="font-medium text-foreground">
                                    {formatAmount(activity.amount, activity.currency)}
                                  </div>
                                )}
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>
                    </ProfessionalCard>
                  ))}
                </div>
              ) : (
                <div className="text-center py-20 bg-muted/5 rounded-xl border-2 border-dashed border-muted-foreground/20">
                  <Calendar className="h-16 w-16 text-muted-foreground mx-auto mb-6" />
                  <h3 className="text-xl font-semibold mb-2">{t('dashboard.activity.no_activities_found')}</h3>
                  <p className="text-muted-foreground mb-6">
                    {filter === 'all' 
                      ? t('dashboard.activity.no_activities_recorded')
                      : t('dashboard.activity.no_filtered_activities', { type: filter })
                    }
                  </p>
                  <div className="flex justify-center gap-3">
                    <ProfessionalButton 
                      variant="outline"
                      onClick={() => {
                        setFilter('all');
                        setDateRange('all');
                      }}
                    >
                      {t('dashboard.activity.clear_filters')}
                    </ProfessionalButton>
                    <ProfessionalButton onClick={() => navigate('/')}>
                      {t('dashboard.activity.back_to_dashboard')}
                    </ProfessionalButton>
                  </div>
                </div>
              )}
            </ContentSection>
          </div>
      </div>
    </div>
  );
}