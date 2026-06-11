import React from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { ArrowRight, Repeat, TrendingUp } from 'lucide-react';

import { subscriptionsApi } from '@/lib/api/subscriptions';
import { useFeatures } from '@/contexts/FeatureContext';
import {
  ProfessionalCard,
  ProfessionalCardContent,
  ProfessionalCardHeader,
  ProfessionalCardTitle,
} from '@/components/ui/professional-card';
import { Badge } from '@/components/ui/badge';
import {
  formatCurrency,
  hasUnacknowledgedPriceChange,
} from '@/components/subscriptions/subscription-helpers';

export const SubscriptionsWidget: React.FC = () => {
  const { isFeatureEnabled } = useFeatures();
  const enabled = isFeatureEnabled('subscription_detection');

  const { data, isLoading } = useQuery({
    queryKey: ['subscriptions', 'active'],
    queryFn: () => subscriptionsApi.list({ status: 'active' }),
    enabled,
  });

  if (!enabled) return null;

  const priceChanges =
    data?.items.filter(hasUnacknowledgedPriceChange).length ?? 0;
  const next = data?.next_charge_date;

  return (
    <ProfessionalCard data-tour="dashboard-subscriptions">
      <ProfessionalCardHeader className="flex flex-row items-center justify-between">
        <ProfessionalCardTitle className="text-lg flex items-center gap-2">
          <Repeat className="h-4 w-4" />
          Subscriptions
        </ProfessionalCardTitle>
        <Link
          to="/subscriptions"
          className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
        >
          View all
          <ArrowRight className="h-3 w-3" />
        </Link>
      </ProfessionalCardHeader>
      <ProfessionalCardContent>
        {isLoading ? (
          <div className="text-sm text-muted-foreground">Loading…</div>
        ) : !data || data.active_count === 0 ? (
          <div className="text-sm text-muted-foreground">
            No active subscriptions detected yet.
          </div>
        ) : (
          <div className="space-y-2">
            <div className="flex items-baseline justify-between">
              <div className="text-2xl font-semibold">
                {formatCurrency(data.monthly_cost)}
              </div>
              <div className="text-xs text-muted-foreground">per month</div>
            </div>
            <div className="text-xs text-muted-foreground">
              {data.active_count} active •{' '}
              {formatCurrency(data.annual_cost)} annually
            </div>
            <div className="flex items-center gap-2 pt-1">
              {priceChanges > 0 ? (
                <Badge className="bg-destructive/10 text-destructive">
                  <TrendingUp className="mr-1 h-3 w-3" />
                  {priceChanges} price change{priceChanges === 1 ? '' : 's'}
                </Badge>
              ) : null}
              {next ? (
                <span className="text-xs text-muted-foreground">
                  Next: {next}
                </span>
              ) : null}
            </div>
          </div>
        )}
      </ProfessionalCardContent>
    </ProfessionalCard>
  );
};
