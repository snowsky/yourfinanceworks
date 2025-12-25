import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { StatCard } from '@/components/dashboard/StatCard';
import { CurrencyDisplay } from '@/components/ui/currency-display';
import { PendingApprovalsList } from './PendingApprovalsList';
import { ProcessedExpensesList } from './ProcessedExpensesList';
import { ProcessedInvoicesList } from './ProcessedInvoicesList';
import { approvalApi } from '@/lib/api';
import { ApprovalDashboardStats } from '@/types';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Clock,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Timer,
  History,
  FileText,
  Lock,
  Search
} from 'lucide-react';
import { toast } from 'sonner';
import ApprovalHelpTooltips, { HelpTooltip, QuickHelp } from '@/components/help/ApprovalHelpTooltips';
import { useTranslation } from 'react-i18next';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import { Loader2 } from 'lucide-react';
import { Link } from 'react-router-dom';
import { formatDate } from '@/lib/utils';

interface PendingInvoiceApproval {
  id: number;
  invoice_id: number;
  invoice_number: string;
  client_name: string;
  amount: number;
  currency: string;
  status: string;
  submitted_at: string;
  approver_id: number;
  approval_level: number;
}

export function ApprovalDashboard() {
  const { t } = useTranslation();
  const [stats, setStats] = useState<ApprovalDashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshKey, setRefreshKey] = useState(0);
  const [invoiceApprovals, setInvoiceApprovals] = useState<PendingInvoiceApproval[]>([]);
  const [invoiceApprovalsLoading, setInvoiceApprovalsLoading] = useState(false);
  const [approving, setApproving] = useState<number | null>(null);
  const [rejecting, setRejecting] = useState<number | null>(null);
  const [licenseError, setLicenseError] = useState(false);
  const [invoiceSearchQuery, setInvoiceSearchQuery] = useState('');

  useEffect(() => {
    const fetchStats = async () => {
      try {
        setLoading(true);
        setLicenseError(false);
        const data = await approvalApi.getDashboardStats();
        setStats(data);
      } catch (error: any) {
        console.error('Failed to fetch approval stats:', error);
        // Check if it's a license/feature error (403 or specific error message)
        if (error?.response?.status === 403 || error?.message?.includes('license') || error?.message?.includes('feature')) {
          setLicenseError(true);
        } else {
          toast.error(t('approvalDashboard.failed_to_load_approval_statistics'));
        }
      } finally {
        setLoading(false);
      }
    };

    fetchStats();
  }, [refreshKey, t]);

  useEffect(() => {
    const fetchInvoiceApprovals = async () => {
      try {
        setInvoiceApprovalsLoading(true);
        const response = await approvalApi.getPendingInvoiceApprovals({ limit: 100 });
        setInvoiceApprovals(response.approvals || []);
      } catch (error) {
        console.error('Failed to fetch pending invoice approvals:', error);
      } finally {
        setInvoiceApprovalsLoading(false);
      }
    };

    fetchInvoiceApprovals();
  }, [refreshKey]);

  const handleApprovalAction = () => {
    // Refresh stats when an approval action is completed
    setRefreshKey(prev => prev + 1);
  };

  const handleApproveInvoice = async (approvalId: number) => {
    try {
      setApproving(approvalId);
      await approvalApi.approveInvoice(approvalId, '');
      toast.success('Invoice approved successfully');
      setInvoiceApprovals(prev => prev.filter(a => a.id !== approvalId));
      handleApprovalAction();
    } catch (error) {
      console.error('Failed to approve invoice:', error);
      toast.error('Failed to approve invoice');
    } finally {
      setApproving(null);
    }
  };

  const handleRejectInvoice = async (approvalId: number) => {
    try {
      setRejecting(approvalId);
      await approvalApi.rejectInvoice(approvalId, 'Rejected by approver', '');
      toast.success('Invoice rejected successfully');
      setInvoiceApprovals(prev => prev.filter(a => a.id !== approvalId));
      handleApprovalAction();
    } catch (error) {
      console.error('Failed to reject invoice:', error);
      toast.error('Failed to reject invoice');
    } finally {
      setRejecting(null);
    }
  };

  if (licenseError) {
    return (
      <div className="container mx-auto p-6">
        <div className="mb-6">
          <h1 className="text-3xl font-bold">{t('approvalDashboard.title')}</h1>
          <p className="text-gray-600 mt-2">{t('approvalDashboard.description')}</p>
        </div>

        <div className="bg-amber-50 border border-amber-200 rounded-lg p-6">
          <div className="flex items-start gap-4">
            <div className="flex-shrink-0">
              <Lock className="h-8 w-8 text-amber-600" />
            </div>
            <div className="flex-1">
              <h2 className="text-xl font-semibold text-amber-900 mb-2">
                Approval Workflows Require a Business License
              </h2>
              <p className="text-amber-800 mb-4">
                The approval workflows feature is part of our Business Edition. Upgrade your license to access:
              </p>
              <ul className="list-disc list-inside text-amber-800 mb-4 space-y-1">
                <li>Multi-level approval workflows for expenses and invoices</li>
                <li>Customizable approval rules based on amount thresholds</li>
                <li>Approval delegation and escalation</li>
                <li>Comprehensive approval analytics and reporting</li>
              </ul>
              <div>
                <Button asChild variant="default">
                  <Link to="/settings?tab=license">Manage License</Link>
                </Button>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <ApprovalHelpTooltips context="dashboard">
      <div className="space-y-6">
        {/* Dashboard Header with Professional Styling */}
        <div className="bg-gradient-to-r from-primary/10 via-primary/5 to-transparent rounded-2xl border border-primary/20 p-8 backdrop-blur-sm">
          <div className="flex items-center justify-between gap-4">
            <div className="space-y-2 flex-1">
              <h1 className="text-4xl font-bold tracking-tight">{t('approvalDashboard.title')}</h1>
              <p className="text-muted-foreground text-base">{t('approvalDashboard.description')}</p>
            </div>
            <div className="flex-shrink-0">
              <QuickHelp context="dashboard" />
            </div>
          </div>
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
            description={t('approvalDashboard.items_approved_today', { defaultValue: 'Items approved today' })}
            loading={loading}
            variant="success"
          />

          <StatCard
            title={t('approvalDashboard.rejected_today')}
            value={stats?.rejected_today?.toString() || '0'}
            icon={XCircle}
            description={t('approvalDashboard.items_rejected_today', { defaultValue: 'Items rejected today' })}
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

        {/* Pending Approvals List with Tabs */}
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
            <Tabs defaultValue="expenses" className="w-full tabs-professional">
              <TabsList className="grid w-full grid-cols-2 bg-gradient-to-r from-muted/50 to-muted/30 border border-border/50 rounded-lg p-1">
                <TabsTrigger value="expenses" className="data-[state=active]:bg-background data-[state=active]:shadow-sm transition-all duration-200">Expenses</TabsTrigger>
                <TabsTrigger value="invoices" className="data-[state=active]:bg-background data-[state=active]:shadow-sm transition-all duration-200">Invoices</TabsTrigger>
              </TabsList>

              <TabsContent value="expenses" className="mt-4">
                <HelpTooltip id="bulk-actions" context="dashboard">
                  <PendingApprovalsList onApprovalAction={handleApprovalAction} />
                </HelpTooltip>
              </TabsContent>

              <TabsContent value="invoices" className="mt-4 space-y-4">
                {invoiceApprovalsLoading ? (
                  <div className="flex justify-center items-center py-8">
                    <Loader2 className="h-6 w-6 animate-spin" />
                  </div>
                ) : (
                  <>
                    {invoiceApprovals.length > 0 && (
                      <div className="relative">
                        <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-muted-foreground h-4 w-4" />
                        <Input
                          placeholder={t('approvalDashboard.search_invoices_placeholder', { defaultValue: 'Search by invoice number or client...' })}
                          value={invoiceSearchQuery}
                          onChange={(e) => setInvoiceSearchQuery(e.target.value)}
                          className="pl-10"
                        />
                      </div>
                    )}

                    {invoiceApprovals.filter(approval =>
                      approval.invoice_number.toLowerCase().includes(invoiceSearchQuery.toLowerCase()) ||
                      approval.client_name.toLowerCase().includes(invoiceSearchQuery.toLowerCase())
                    ).length === 0 ? (
                      <div className="flex flex-col items-center justify-center py-12 text-center animate-in fade-in zoom-in duration-300">
                        <div className="bg-primary/5 p-6 rounded-full mb-6 ring-8 ring-primary/2">
                          <FileText className="h-12 w-12 text-primary/40" />
                        </div>
                        <h3 className="text-xl font-semibold mb-2">
                          {invoiceSearchQuery
                            ? t('approvalDashboard.no_approvals_match_your_search_criteria', 'No approvals match your search criteria')
                            : t('approvalDashboard.no_pending_invoice_approvals_title', 'No pending invoice approvals')}
                        </h3>
                        <p className="text-muted-foreground max-w-sm mx-auto mb-8">
                          {invoiceSearchQuery
                            ? t('approvalDashboard.try_adjusting_filters', 'Try adjusting your search or filters to find what you are looking for.')
                            : t('approvalDashboard.no_pending_invoice_approvals_description', 'All invoice approvals are up to date.')}
                        </p>
                      </div>
                    ) : (
                      <div className="overflow-x-auto">
                        <Table>
                          <TableHeader>
                            <TableRow>
                              <TableHead>Invoice Number</TableHead>
                              <TableHead>Client</TableHead>
                              <TableHead>Amount</TableHead>
                              <TableHead>Submitted</TableHead>
                              <TableHead>Actions</TableHead>
                            </TableRow>
                          </TableHeader>
                          <TableBody>
                            {invoiceApprovals
                              .filter(approval =>
                                approval.invoice_number.toLowerCase().includes(invoiceSearchQuery.toLowerCase()) ||
                                approval.client_name.toLowerCase().includes(invoiceSearchQuery.toLowerCase())
                              )
                              .map((approval) => (
                                <TableRow key={approval.id}>
                                  <TableCell>
                                    <Link
                                      to={`/invoices/view/${approval.invoice_id}`}
                                      className="text-blue-600 hover:underline font-medium"
                                    >
                                      {approval.invoice_number}
                                    </Link>
                                  </TableCell>
                                  <TableCell>{approval.client_name}</TableCell>
                                  <TableCell>
                                    <CurrencyDisplay
                                      amount={approval.amount}
                                      currency={approval.currency || 'USD'}
                                    />
                                  </TableCell>
                                  <TableCell>{formatDate(approval.submitted_at)}</TableCell>
                                  <TableCell>
                                    <div className="flex gap-2">
                                      <Button
                                        size="sm"
                                        variant="outline"
                                        onClick={() => handleApproveInvoice(approval.id)}
                                        disabled={approving === approval.id || rejecting === approval.id}
                                        className="text-green-600 hover:text-green-700"
                                      >
                                        {approving === approval.id ? (
                                          <Loader2 className="h-4 w-4 animate-spin" />
                                        ) : (
                                          <CheckCircle className="h-4 w-4" />
                                        )}
                                        Approve
                                      </Button>
                                      <Button
                                        size="sm"
                                        variant="outline"
                                        onClick={() => handleRejectInvoice(approval.id)}
                                        disabled={approving === approval.id || rejecting === approval.id}
                                        className="text-red-600 hover:text-red-700"
                                      >
                                        {rejecting === approval.id ? (
                                          <Loader2 className="h-4 w-4 animate-spin" />
                                        ) : (
                                          <XCircle className="h-4 w-4" />
                                        )}
                                        Reject
                                      </Button>
                                    </div>
                                  </TableCell>
                                </TableRow>
                              ))}
                          </TableBody>
                        </Table>
                      </div>
                    )}
                  </>
                )}
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>

        {/* Processed Items List */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <History className="h-5 w-5" />
                {t('approvalDashboard.processed_items', 'Processed Items')}
              </div>
              <HelpTooltip id="processed-items" context="dashboard">
                <div className="text-sm text-gray-500 cursor-help">
                  {t('approvalDashboard.items_approved_rejected', 'Expenses and invoices already approved or rejected')}
                </div>
              </HelpTooltip>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <Tabs defaultValue="expenses" className="w-full tabs-professional">
              <TabsList className="grid w-full grid-cols-2 bg-gradient-to-r from-muted/50 to-muted/30 border border-border/50 rounded-lg p-1">
                <TabsTrigger value="expenses" className="data-[state=active]:bg-background data-[state=active]:shadow-sm transition-all duration-200">Expenses</TabsTrigger>
                <TabsTrigger value="invoices" className="data-[state=active]:bg-background data-[state=active]:shadow-sm transition-all duration-200">Invoices</TabsTrigger>
              </TabsList>

              <TabsContent value="expenses" className="mt-4">
                <ProcessedExpensesList />
              </TabsContent>

              <TabsContent value="invoices" className="mt-4">
                <ProcessedInvoicesList />
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>
      </div>
    </ApprovalHelpTooltips>
  );
}