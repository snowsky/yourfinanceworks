import React from 'react';
import { Badge } from '@/components/ui/badge';
import type { SubscriptionStatus } from '@/lib/api/subscriptions';

const STATUS_CONFIG: Record<
  SubscriptionStatus,
  { label: string; className: string }
> = {
  active: { label: 'Active', className: 'bg-success/10 text-success border-success/30' },
  dismissed: { label: 'Dismissed', className: 'bg-muted text-muted-foreground' },
  canceled_by_user: {
    label: 'Canceled',
    className: 'bg-warning/10 text-warning border-warning/30',
  },
  not_a_subscription: {
    label: 'Not a subscription',
    className: 'bg-muted text-muted-foreground',
  },
};

export const SubscriptionStatusBadge: React.FC<{ status: SubscriptionStatus }> = ({
  status,
}) => {
  const config = STATUS_CONFIG[status] ?? STATUS_CONFIG.active;
  return <Badge className={config.className}>{config.label}</Badge>;
};
