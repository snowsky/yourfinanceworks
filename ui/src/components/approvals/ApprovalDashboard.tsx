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

export function ApprovalDashboard() {
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
        toast.error('Failed to load approval statistics');
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
          <h1 className="text-2xl font-bold text-gray-900">Approval Dashboard</h1>
          <QuickHelp context="dashboard" />
        </div>

        {/* Dashboard Stats */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
          <HelpTooltip id="pending-count" context="dashboard">
            <StatCard
              title="Pending Approvals"
              value={stats?.pending_count?.toString() || '0'}
              icon={Clock}
              description="Awaiting your review"
              loading={loading}
              variant={stats && stats.pending_count > 0 ? 'warning' : 'default'}
            />
          </HelpTooltip>
          
          <StatCard
            title="Approved Today"
            value={stats?.approved_today?.toString() || '0'}
            icon={CheckCircle}
            description="Expenses approved today"
            loading={loading}
            variant="success"
          />
          
          <StatCard
            title="Rejected Today"
            value={stats?.rejected_today?.toString() || '0'}
            icon={XCircle}
            description="Expenses rejected today"
            loading={loading}
            variant="destructive"
          />
          
          <StatCard
            title="Overdue"
            value={stats?.overdue_count?.toString() || '0'}
            icon={AlertTriangle}
            description="Pending > 3 days"
            loading={loading}
            variant={stats && stats.overdue_count > 0 ? 'destructive' : 'default'}
          />
          
          <StatCard
            title="Avg. Approval Time"
            value={stats ? `${Math.round(stats.average_approval_time_hours)}h` : '0h'}
            icon={Timer}
            description="Average time to approve"
            loading={loading}
          />
        </div>

        {/* Pending Approvals List */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Clock className="h-5 w-5" />
                Pending Approvals
              </div>
              <HelpTooltip id="filter-options" context="dashboard">
                <div className="text-sm text-gray-500 cursor-help">
                  Filter & Sort Options
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
                Processed Expenses
              </div>
              <HelpTooltip id="processed-expenses" context="dashboard">
                <div className="text-sm text-gray-500 cursor-help">
                  Expenses you've approved or rejected
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