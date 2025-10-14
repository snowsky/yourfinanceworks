import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { StatCard } from '@/components/dashboard/StatCard';
import { PendingApprovalsList } from './PendingApprovalsList';
import { ProcessedExpensesList } from './ProcessedExpensesList';
import { approvalApi } from '@/lib/api';
import { ApprovalDashboardStats } from '@/types';
import {
  Clock,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Timer,
  History
} from 'lucide-react';
import { toast } from 'sonner';
import ApprovalHelpTooltips, { HelpTooltip, QuickHelp } from '@/components/help/ApprovalHelpTooltips';
import { useTranslation } from 'react-i18next';

export function ApprovalDashboard() {
  const { t } = useTranslation();
  const [stats, setStats] = useState<ApprovalDashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        setLoading(true);
        const data = await approvalApi.getDashboardStats();
        setStats(data);
      } catch (error) {
        console.error('Failed to fetch approval stats:', error);
        toast.error(t('approvalDashboard.failed_to_load_approval_statistics'));
      } finally {
        setLoading(false);
      }
    };

    fetchStats();
  }, [refreshKey]);

  const handleApprovalAction = () => {
    // Refresh stats when an approval action is completed
    setRefreshKey(prev => prev + 1);
  };

  return (
    <ApprovalHelpTooltips context="dashboard">
      <div className="space-y-6">
        {/* Dashboard Header with Help */}
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold text-gray-900">{t('approvalDashboard.title')}</h1>
          <QuickHelp context="dashboard" />
        </div>

        {/* Dashboard Stats */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
          <HelpTooltip id="pending-count" context="dashboard">
            <StatCard
              title={t('approvalDashboard.pending_approvals')}
              value={stats?.pending_count?.toString() || '0'}
              icon={Clock}
              description={t('approvalDashboard.awaiting_review')}
              loading={loading}
              variant={stats && stats.pending_count > 0 ? 'warning' : 'default'}
            />
          </HelpTooltip>
          
          <StatCard
            title={t('approvalDashboard.approved_today')}
            value={stats?.approved_today?.toString() || '0'}
            icon={CheckCircle}
            description={t('approvalDashboard.expenses_approved_today')}
            loading={loading}
            variant="success"
          />
          
          <StatCard
            title={t('approvalDashboard.rejected_today')}
            value={stats?.rejected_today?.toString() || '0'}
            icon={XCircle}
            description={t('approvalDashboard.expenses_rejected_today')}
            loading={loading}
            variant="destructive"
          />
          
          <StatCard
            title={t('approvalDashboard.overdue')}
            value={stats?.overdue_count?.toString() || '0'}
            icon={AlertTriangle}
            description={t('approvalDashboard.pending_days')}
            loading={loading}
            variant={stats && stats.overdue_count > 0 ? 'destructive' : 'default'}
          />
          
          <StatCard
            title={t('approvalDashboard.avg_approval_time')}
            value={stats ? `${Math.round(stats.average_approval_time_hours)}h` : '0h'}
            icon={Timer}
            description={t('approvalDashboard.avg_time_to_approve')}
            loading={loading}
          />
        </div>

        {/* Pending Approvals List */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Clock className="h-5 w-5" />
                {t('approvalDashboard.pending_approvals')}
              </div>
              <HelpTooltip id="filter-options" context="dashboard">
                <div className="text-sm text-gray-500 cursor-help">
                  {t('approvalDashboard.filter_sort_options')}
                </div>
              </HelpTooltip>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <HelpTooltip id="bulk-actions" context="dashboard">
              <PendingApprovalsList onApprovalAction={handleApprovalAction} />
            </HelpTooltip>
          </CardContent>
        </Card>

        {/* Processed Expenses List */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <History className="h-5 w-5" />
                {t('approvalDashboard.processed_expenses')}
              </div>
              <HelpTooltip id="processed-expenses" context="dashboard">
                <div className="text-sm text-gray-500 cursor-help">
                  {t('approvalDashboard.expenses_approved_rejected')}
                </div>
              </HelpTooltip>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ProcessedExpensesList />
          </CardContent>
        </Card>
      </div>
    </ApprovalHelpTooltips>
  );
}