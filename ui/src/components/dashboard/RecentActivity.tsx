import { useState, useEffect, useRef } from "react";
import { Badge } from "@/components/ui/badge";
import { Loader2, FileText, Users, Package, CheckCircle, Bell, Calendar, TrendingUp } from "lucide-react";
import { toast } from "sonner";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { formatDate } from "@/lib/utils";
import { activityApi, ActivityItem } from "@/lib/api";
import { formatCurrencySync } from "@/utils/dashboard";

interface RecentActivityProps {
  refreshKey?: number;
}

export function RecentActivity({ refreshKey }: RecentActivityProps) {
  const { t } = useTranslation();
  const [activities, setActivities] = useState<ActivityItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const isFirstLoad = useRef(true);

  const getActivityIcon = (type: ActivityItem['type']) => {
    switch (type) {
      case 'invoice':   return <FileText className="h-3.5 w-3.5 text-blue-500" />;
      case 'client':    return <Users className="h-3.5 w-3.5 text-emerald-500" />;
      case 'inventory': return <Package className="h-3.5 w-3.5 text-purple-500" />;
      case 'approval':  return <CheckCircle className="h-3.5 w-3.5 text-orange-500" />;
      case 'reminder':  return <Bell className="h-3.5 w-3.5 text-red-500" />;
      case 'expense':   return <TrendingUp className="h-3.5 w-3.5 text-indigo-500" />;
      case 'report':    return <Calendar className="h-3.5 w-3.5 text-teal-500" />;
      default:          return <FileText className="h-3.5 w-3.5 text-muted-foreground" />;
    }
  };

  const getActivityBadge = (type: ActivityItem['type'], status?: string) => {
    if (status) {
      switch (status) {
        case 'paid': case 'approved': case 'completed':
          return <Badge className="text-[10px] px-1.5 py-0 bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-400 border-0">{t('dashboard.activity.badges.completed')}</Badge>;
        case 'pending': case 'draft':
          return <Badge className="text-[10px] px-1.5 py-0 bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-400 border-0">{t('dashboard.activity.badges.pending')}</Badge>;
        case 'overdue': case 'rejected':
          return <Badge className="text-[10px] px-1.5 py-0 bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-400 border-0">{t('dashboard.activity.badges.attention')}</Badge>;
        default:
          return <Badge className="text-[10px] px-1.5 py-0 bg-muted text-muted-foreground border-0">{status}</Badge>;
      }
    }

    switch (type) {
      case 'invoice':   return <Badge className="text-[10px] px-1.5 py-0 bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-400 border-0">{t('dashboard.activity.badges.invoice')}</Badge>;
      case 'client':    return <Badge className="text-[10px] px-1.5 py-0 bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-400 border-0">{t('dashboard.activity.badges.client')}</Badge>;
      case 'inventory': return <Badge className="text-[10px] px-1.5 py-0 bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-400 border-0">{t('dashboard.activity.badges.inventory')}</Badge>;
      case 'approval':  return <Badge className="text-[10px] px-1.5 py-0 bg-orange-100 text-orange-700 dark:bg-orange-900/40 dark:text-orange-400 border-0">{t('dashboard.activity.badges.approval')}</Badge>;
      case 'reminder':  return <Badge className="text-[10px] px-1.5 py-0 bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-400 border-0">{t('dashboard.activity.badges.reminder')}</Badge>;
      case 'expense':   return <Badge className="text-[10px] px-1.5 py-0 bg-indigo-100 text-indigo-700 dark:bg-indigo-900/40 dark:text-indigo-400 border-0">{t('dashboard.activity.badges.expense')}</Badge>;
      case 'report':    return <Badge className="text-[10px] px-1.5 py-0 bg-teal-100 text-teal-700 dark:bg-teal-900/40 dark:text-teal-400 border-0">{t('dashboard.activity.badges.report')}</Badge>;
      default:          return <Badge className="text-[10px] px-1.5 py-0 bg-muted text-muted-foreground border-0">{t('dashboard.activity.badges.activity')}</Badge>;
    }
  };

  const fetchActivities = async (firstLoad: boolean) => {
    if (firstLoad) setLoading(true);
    else setIsRefreshing(true);

    try {
      const recentActivities = await activityApi.getRecentActivities(8);
      setActivities(recentActivities);
    } catch (error) {
      console.error("Failed to fetch recent activities:", error);
      toast.error(t('activity.failed_to_load'));
      setActivities([]);
    } finally {
      setLoading(false);
      setIsRefreshing(false);
    }
  };

  useEffect(() => {
    const first = isFirstLoad.current;
    isFirstLoad.current = false;
    fetchActivities(first);
  }, [refreshKey]);

  return (
    <div className="relative h-full flex flex-col">
      {/* Subtle refresh indicator */}
      {isRefreshing && (
        <div className="absolute top-0 left-0 right-0 h-0.5 bg-primary/20 rounded-full overflow-hidden z-10">
          <div className="h-full bg-primary/60 animate-[shimmer_1.2s_ease-in-out_infinite] w-1/3 rounded-full" />
        </div>
      )}

      <div className="flex-1 min-h-0">
        {loading ? (
          <div className="flex justify-center items-center h-full">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : activities.length > 0 ? (
          <div className="h-full overflow-y-auto pr-1 -mr-1">
            {activities.map((activity, i) => (
              <div
                key={activity.id}
                className={`flex items-start gap-3 py-3 px-1 transition-colors hover:bg-muted/40 rounded-lg ${i < activities.length - 1 ? 'border-b border-border/50' : ''}`}
              >
                <div className="mt-0.5 p-1.5 rounded-md bg-muted/60 flex-shrink-0">
                  {getActivityIcon(activity.type)}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0">
                      <div className="font-medium text-sm leading-snug truncate">
                        {activity.link ? (
                          <Link to={activity.link} className="hover:text-primary transition-colors">
                            {activity.title}
                          </Link>
                        ) : (
                          activity.title
                        )}
                      </div>
                      {activity.description && (
                        <div className="text-xs text-muted-foreground mt-0.5 truncate">
                          {activity.description}
                        </div>
                      )}
                      <div className="flex items-center gap-2 mt-1">
                        <span className="text-[11px] text-muted-foreground/70">
                          {formatDate(activity.timestamp)}
                        </span>
                        {activity.amount && (
                          <span className="text-[11px] font-medium text-foreground/80">
                            {formatCurrencySync(activity.amount, activity.currency)}
                          </span>
                        )}
                      </div>
                    </div>
                    <div className="flex-shrink-0 mt-0.5">
                      {getActivityBadge(activity.type, activity.status)}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center h-full text-center gap-2">
            <Calendar className="h-10 w-10 text-muted-foreground/40" />
            <p className="text-sm font-medium text-muted-foreground">{t('dashboard.activity.no_recent_activity')}</p>
            <p className="text-xs text-muted-foreground/60">
              {t('dashboard.activity.activity_will_appear')}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
