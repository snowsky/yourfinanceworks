import React, { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import {
  Calendar,
  DollarSign,
  RefreshCw,
  TrendingDown,
  TrendingUp,
} from 'lucide-react';

import {
  subscriptionsApi,
  type SubscriptionResponse,
  type SubscriptionStatus,
} from '@/lib/api/subscriptions';
import { getErrorMessage } from '@/lib/api';
import { FeatureGate } from '@/components/FeatureGate';
import { PageHeader } from '@/components/ui/professional-layout';
import {
  MetricCard,
  ProfessionalCard,
  ProfessionalCardContent,
  ProfessionalCardHeader,
  ProfessionalCardTitle,
} from '@/components/ui/professional-card';
import { ProfessionalButton } from '@/components/ui/professional-button';
import { Badge } from '@/components/ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { MoreHorizontal } from 'lucide-react';

import { SubscriptionStatusBadge } from '@/components/subscriptions/SubscriptionStatusBadge';
import { CancelReminderDialog } from '@/components/subscriptions/CancelReminderDialog';
import {
  annualizedCost,
  cadenceLabel,
  formatCurrency,
  hasUnacknowledgedPriceChange,
  priceChangePercent,
} from '@/components/subscriptions/subscription-helpers';

type SortKey = 'next' | 'amount' | 'annual' | 'label';

const SubscriptionsPage: React.FC = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { t } = useTranslation();
  const [statusFilter, setStatusFilter] = useState<SubscriptionStatus | 'all'>(
    'active',
  );
  const [sort, setSort] = useState<SortKey>('next');
  const [reminderTarget, setReminderTarget] =
    useState<SubscriptionResponse | null>(null);

  const summaryQuery = useQuery({
    queryKey: ['subscriptions', statusFilter],
    queryFn: () =>
      subscriptionsApi.list({
        status: statusFilter === 'all' ? undefined : statusFilter,
      }),
  });

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ['subscriptions'] });

  const scanMutation = useMutation({
    mutationFn: () => subscriptionsApi.scan({}),
    onSuccess: (result) => {
      toast.success(
        `Scan complete: ${result.new_subscriptions} new, ${result.price_changed_subscriptions} price changes, ${result.updated_subscriptions} updated`,
      );
      invalidate();
    },
    onError: (err) => toast.error(getErrorMessage(err, t)),
  });

  const statusMutation = useMutation({
    mutationFn: ({
      id,
      status,
    }: {
      id: number;
      status: SubscriptionStatus;
    }) => subscriptionsApi.updateStatus(id, status),
    onSuccess: invalidate,
    onError: (err) => toast.error(getErrorMessage(err, t)),
  });

  const reminderMutation = useMutation({
    mutationFn: ({ id, remindOn }: { id: number; remindOn: string | null }) =>
      subscriptionsApi.setCancelReminder(id, remindOn),
    onSuccess: invalidate,
    onError: (err) => toast.error(getErrorMessage(err, t)),
  });

  const acknowledgeMutation = useMutation({
    mutationFn: (id: number) => subscriptionsApi.acknowledgePriceChange(id),
    onSuccess: invalidate,
    onError: (err) => toast.error(getErrorMessage(err, t)),
  });

  const sortedItems = useMemo(() => {
    const items = summaryQuery.data?.items ?? [];
    const copy = [...items];
    copy.sort((a, b) => {
      if (sort === 'amount') return b.amount - a.amount;
      if (sort === 'annual')
        return annualizedCost(b) - annualizedCost(a);
      if (sort === 'label') return a.label.localeCompare(b.label);
      // 'next' (default): nearest upcoming first, nulls last
      const ad = a.next_expected_date ?? '9999-12-31';
      const bd = b.next_expected_date ?? '9999-12-31';
      return ad.localeCompare(bd);
    });
    return copy;
  }, [summaryQuery.data, sort]);

  return (
    <FeatureGate feature="subscription_detection" showUpgradePrompt>
      <div className="space-y-6 p-6">
        <PageHeader
          title="Subscriptions"
          description="Recurring charges we've found on your bank statements."
          actions={
            <ProfessionalButton
              onClick={() => scanMutation.mutate()}
              disabled={scanMutation.isPending}
              variant="outline"
            >
              <RefreshCw
                className={`mr-2 h-4 w-4 ${scanMutation.isPending ? 'animate-spin' : ''}`}
              />
              {scanMutation.isPending ? 'Scanning…' : 'Scan now'}
            </ProfessionalButton>
          }
        />

        <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
          <MetricCard
            title="Active"
            value={String(summaryQuery.data?.active_count ?? 0)}
            icon={Calendar}
          />
          <MetricCard
            title="Monthly cost"
            value={formatCurrency(summaryQuery.data?.monthly_cost ?? 0)}
            icon={DollarSign}
          />
          <MetricCard
            title="Annual cost"
            value={formatCurrency(summaryQuery.data?.annual_cost ?? 0)}
            icon={DollarSign}
          />
          <MetricCard
            title="Next charge"
            value={summaryQuery.data?.next_charge_date ?? '—'}
            icon={TrendingUp}
          />
        </div>

        <ProfessionalCard>
          <ProfessionalCardHeader className="flex flex-row items-center justify-between gap-3">
            <ProfessionalCardTitle>Detected subscriptions</ProfessionalCardTitle>
            <div className="flex gap-2">
              <Select
                value={statusFilter}
                onValueChange={(v) =>
                  setStatusFilter(v as SubscriptionStatus | 'all')
                }
              >
                <SelectTrigger className="w-44">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="active">Active</SelectItem>
                  <SelectItem value="dismissed">Dismissed</SelectItem>
                  <SelectItem value="canceled_by_user">Canceled</SelectItem>
                  <SelectItem value="all">All (incl. archive)</SelectItem>
                </SelectContent>
              </Select>
              <Select value={sort} onValueChange={(v) => setSort(v as SortKey)}>
                <SelectTrigger className="w-44">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="next">Sort: next charge</SelectItem>
                  <SelectItem value="amount">Sort: amount</SelectItem>
                  <SelectItem value="annual">Sort: annual cost</SelectItem>
                  <SelectItem value="label">Sort: name</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </ProfessionalCardHeader>
          <ProfessionalCardContent>
            {summaryQuery.isLoading ? (
              <div className="py-12 text-center text-sm text-muted-foreground">
                Loading…
              </div>
            ) : sortedItems.length === 0 ? (
              <div className="space-y-2 py-12 text-center">
                <p className="text-sm text-muted-foreground">
                  No subscriptions detected yet.
                </p>
                <p className="text-xs text-muted-foreground">
                  Import a bank statement or run a scan to find recurring charges.
                </p>
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Merchant</TableHead>
                    <TableHead>Amount</TableHead>
                    <TableHead>Cadence</TableHead>
                    <TableHead>Annual cost</TableHead>
                    <TableHead>Next charge</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="w-12"></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {sortedItems.map((sub) => {
                    const change = priceChangePercent(sub);
                    const flagPriceChange = hasUnacknowledgedPriceChange(sub);
                    return (
                      <TableRow
                        key={sub.id}
                        className="cursor-pointer"
                        onClick={() => navigate(`/subscriptions/${sub.id}`)}
                      >
                        <TableCell>
                          <div className="font-medium">{sub.label}</div>
                          {sub.category ? (
                            <div className="text-xs text-muted-foreground">
                              {sub.category}
                            </div>
                          ) : null}
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            <span className="font-medium">
                              {formatCurrency(sub.amount, sub.currency)}
                            </span>
                            {flagPriceChange && change != null ? (
                              <Badge
                                className={
                                  change > 0
                                    ? 'bg-destructive/10 text-destructive'
                                    : 'bg-success/10 text-success'
                                }
                              >
                                {change > 0 ? (
                                  <TrendingUp className="mr-1 h-3 w-3" />
                                ) : (
                                  <TrendingDown className="mr-1 h-3 w-3" />
                                )}
                                {change > 0 ? '+' : ''}
                                {change.toFixed(1)}%
                              </Badge>
                            ) : null}
                          </div>
                        </TableCell>
                        <TableCell>{cadenceLabel(sub.cadence_days)}</TableCell>
                        <TableCell>
                          {formatCurrency(annualizedCost(sub), sub.currency)}
                        </TableCell>
                        <TableCell>{sub.next_expected_date ?? '—'}</TableCell>
                        <TableCell>
                          <SubscriptionStatusBadge status={sub.status} />
                        </TableCell>
                        <TableCell onClick={(e) => e.stopPropagation()}>
                          <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                              <button
                                type="button"
                                className="rounded p-1 hover:bg-muted"
                                aria-label="Subscription actions"
                              >
                                <MoreHorizontal className="h-4 w-4" />
                              </button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end">
                              <DropdownMenuItem
                                onClick={() => setReminderTarget(sub)}
                              >
                                Set cancel reminder
                              </DropdownMenuItem>
                              {flagPriceChange ? (
                                <DropdownMenuItem
                                  onClick={() =>
                                    acknowledgeMutation.mutate(sub.id)
                                  }
                                >
                                  Acknowledge price change
                                </DropdownMenuItem>
                              ) : null}
                              {sub.status === 'active' ? (
                                <>
                                  <DropdownMenuItem
                                    onClick={() =>
                                      statusMutation.mutate({
                                        id: sub.id,
                                        status: 'canceled_by_user',
                                      })
                                    }
                                  >
                                    Mark as canceled
                                  </DropdownMenuItem>
                                  <DropdownMenuItem
                                    onClick={() =>
                                      statusMutation.mutate({
                                        id: sub.id,
                                        status: 'dismissed',
                                      })
                                    }
                                  >
                                    Dismiss
                                  </DropdownMenuItem>
                                  <DropdownMenuItem
                                    onClick={() =>
                                      statusMutation.mutate({
                                        id: sub.id,
                                        status: 'not_a_subscription',
                                      })
                                    }
                                  >
                                    Not a subscription
                                  </DropdownMenuItem>
                                </>
                              ) : (
                                <DropdownMenuItem
                                  onClick={() =>
                                    statusMutation.mutate({
                                      id: sub.id,
                                      status: 'active',
                                    })
                                  }
                                >
                                  Restore as active
                                </DropdownMenuItem>
                              )}
                            </DropdownMenuContent>
                          </DropdownMenu>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            )}
          </ProfessionalCardContent>
        </ProfessionalCard>

        <CancelReminderDialog
          open={!!reminderTarget}
          subscription={reminderTarget}
          onClose={() => setReminderTarget(null)}
          onSubmit={async (remindOn) => {
            if (!reminderTarget) return;
            await reminderMutation.mutateAsync({
              id: reminderTarget.id,
              remindOn,
            });
            toast.success(
              remindOn ? 'Reminder saved' : 'Reminder cleared',
            );
          }}
        />
      </div>
    </FeatureGate>
  );
};

export default SubscriptionsPage;
