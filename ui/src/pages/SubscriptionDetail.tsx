import React, { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { ArrowLeft, Bell, TrendingDown, TrendingUp } from 'lucide-react';
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import {
  subscriptionsApi,
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

import { SubscriptionStatusBadge } from '@/components/subscriptions/SubscriptionStatusBadge';
import { CancelReminderDialog } from '@/components/subscriptions/CancelReminderDialog';
import {
  annualizedCost,
  cadenceLabel,
  formatCurrency,
  hasUnacknowledgedPriceChange,
  monthlyCost,
  priceChangePercent,
} from '@/components/subscriptions/subscription-helpers';

const SubscriptionDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { t } = useTranslation();
  const subscriptionId = id ? Number(id) : NaN;
  const [reminderOpen, setReminderOpen] = useState(false);

  const subQuery = useQuery({
    queryKey: ['subscription', subscriptionId],
    queryFn: () => subscriptionsApi.get(subscriptionId),
    enabled: Number.isFinite(subscriptionId),
  });

  const chargesQuery = useQuery({
    queryKey: ['subscription-charges', subscriptionId],
    queryFn: () => subscriptionsApi.charges(subscriptionId),
    enabled: Number.isFinite(subscriptionId),
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['subscription', subscriptionId] });
    queryClient.invalidateQueries({ queryKey: ['subscriptions'] });
  };

  const statusMutation = useMutation({
    mutationFn: (status: SubscriptionStatus) =>
      subscriptionsApi.updateStatus(subscriptionId, status),
    onSuccess: invalidate,
    onError: (err) => toast.error(getErrorMessage(err, t)),
  });

  const reminderMutation = useMutation({
    mutationFn: (remindOn: string | null) =>
      subscriptionsApi.setCancelReminder(subscriptionId, remindOn),
    onSuccess: invalidate,
    onError: (err) => toast.error(getErrorMessage(err, t)),
  });

  const ackMutation = useMutation({
    mutationFn: () => subscriptionsApi.acknowledgePriceChange(subscriptionId),
    onSuccess: invalidate,
    onError: (err) => toast.error(getErrorMessage(err, t)),
  });

  const sub = subQuery.data;
  const charges = chargesQuery.data?.entries ?? [];
  const change = sub ? priceChangePercent(sub) : null;
  const showPriceAlert = sub ? hasUnacknowledgedPriceChange(sub) : false;

  if (!Number.isFinite(subscriptionId)) {
    return <div className="p-6">Invalid subscription id.</div>;
  }

  return (
    <FeatureGate feature="subscription_detection" showUpgradePrompt>
      <div className="space-y-6 p-6">
        <PageHeader
          title={sub?.label ?? 'Subscription'}
          description={
            sub
              ? `${cadenceLabel(sub.cadence_days)} • ${formatCurrency(
                  sub.amount,
                  sub.currency,
                )}`
              : 'Loading…'
          }
          actions={
            <ProfessionalButton
              variant="ghost"
              onClick={() => navigate('/subscriptions')}
            >
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back
            </ProfessionalButton>
          }
        />

        {showPriceAlert && sub ? (
          <ProfessionalCard className="border-warning/30 bg-warning/10">
            <ProfessionalCardContent className="flex items-center justify-between gap-3 py-3">
              <div className="flex items-center gap-3">
                {change != null && change > 0 ? (
                  <TrendingUp className="h-4 w-4 text-destructive" />
                ) : (
                  <TrendingDown className="h-4 w-4 text-success" />
                )}
                <div>
                  <div className="text-sm font-medium">
                    Price{' '}
                    {change != null && change > 0 ? 'increased' : 'decreased'}{' '}
                    by {Math.abs(change ?? 0).toFixed(1)}%
                  </div>
                  <div className="text-xs text-muted-foreground">
                    From {formatCurrency(sub.last_amount ?? 0, sub.currency)} to{' '}
                    {formatCurrency(sub.amount, sub.currency)}
                  </div>
                </div>
              </div>
              <ProfessionalButton
                variant="outline"
                onClick={() => ackMutation.mutate()}
                disabled={ackMutation.isPending}
              >
                Acknowledge
              </ProfessionalButton>
            </ProfessionalCardContent>
          </ProfessionalCard>
        ) : null}

        {sub ? (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
            <MetricCard
              title="Monthly cost"
              value={formatCurrency(monthlyCost(sub), sub.currency)}
            />
            <MetricCard
              title="Annual cost"
              value={formatCurrency(annualizedCost(sub), sub.currency)}
            />
            <MetricCard
              title="Charges seen"
              value={String(sub.charge_count)}
            />
            <MetricCard
              title="Confidence"
              value={`${Math.round(sub.confidence * 100)}%`}
            />
          </div>
        ) : null}

        <ProfessionalCard>
          <ProfessionalCardHeader>
            <ProfessionalCardTitle>Charge history</ProfessionalCardTitle>
          </ProfessionalCardHeader>
          <ProfessionalCardContent>
            {chargesQuery.isLoading ? (
              <div className="py-12 text-center text-sm text-muted-foreground">
                Loading…
              </div>
            ) : charges.length === 0 ? (
              <div className="py-12 text-center text-sm text-muted-foreground">
                No matching transactions found.
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={280}>
                <LineChart data={charges}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="date" />
                  <YAxis />
                  <Tooltip
                    formatter={(value: number) =>
                      formatCurrency(value, sub?.currency ?? 'USD')
                    }
                  />
                  <Line
                    type="monotone"
                    dataKey="amount"
                    stroke="#2563eb"
                    strokeWidth={2}
                    dot
                  />
                </LineChart>
              </ResponsiveContainer>
            )}
          </ProfessionalCardContent>
        </ProfessionalCard>

        {sub ? (
          <ProfessionalCard>
            <ProfessionalCardHeader>
              <ProfessionalCardTitle>Manage</ProfessionalCardTitle>
            </ProfessionalCardHeader>
            <ProfessionalCardContent className="space-y-3">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="text-sm font-medium">Status</div>
                  <div className="text-xs text-muted-foreground">
                    Current state of this subscription.
                  </div>
                </div>
                <SubscriptionStatusBadge status={sub.status} />
              </div>

              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="text-sm font-medium">Cancel reminder</div>
                  <div className="text-xs text-muted-foreground">
                    {sub.cancel_reminder_at
                      ? `Reminding you on ${sub.cancel_reminder_at}`
                      : 'No reminder set.'}
                  </div>
                </div>
                <ProfessionalButton
                  variant="outline"
                  onClick={() => setReminderOpen(true)}
                >
                  <Bell className="mr-2 h-4 w-4" />
                  {sub.cancel_reminder_at ? 'Edit' : 'Set reminder'}
                </ProfessionalButton>
              </div>

              <div className="flex flex-wrap gap-2 pt-2">
                {sub.status === 'active' ? (
                  <>
                    <ProfessionalButton
                      variant="outline"
                      onClick={() => statusMutation.mutate('canceled_by_user')}
                    >
                      Mark as canceled
                    </ProfessionalButton>
                    <ProfessionalButton
                      variant="outline"
                      onClick={() => statusMutation.mutate('dismissed')}
                    >
                      Dismiss
                    </ProfessionalButton>
                    <ProfessionalButton
                      variant="ghost"
                      onClick={() => statusMutation.mutate('not_a_subscription')}
                    >
                      Not a subscription
                    </ProfessionalButton>
                  </>
                ) : (
                  <ProfessionalButton
                    variant="outline"
                    onClick={() => statusMutation.mutate('active')}
                  >
                    Restore as active
                  </ProfessionalButton>
                )}
              </div>

              <div className="pt-2 text-xs text-muted-foreground">
                Merchant key: <Badge variant="outline">{sub.merchant_key}</Badge>
              </div>
            </ProfessionalCardContent>
          </ProfessionalCard>
        ) : null}

        <CancelReminderDialog
          open={reminderOpen}
          subscription={sub ?? null}
          onClose={() => setReminderOpen(false)}
          onSubmit={async (remindOn) => {
            await reminderMutation.mutateAsync(remindOn);
            toast.success(remindOn ? 'Reminder saved' : 'Reminder cleared');
          }}
        />
      </div>
    </FeatureGate>
  );
};

export default SubscriptionDetailPage;
