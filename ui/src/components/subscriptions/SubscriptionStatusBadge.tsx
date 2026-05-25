import React from 'react';
import { Badge } from '@/components/ui/badge';
import type { SubscriptionStatus } from '@/lib/api/subscriptions';

const STATUS_CONFIG: Record<
  SubscriptionStatus,
  { label: string; className: string }
> = {
  active: { label: 'Active', className: 'bg-green-100 text-green-800' },
  dismissed: { label: 'Dismissed', className: 'bg-gray-100 text-gray-700' },
  canceled_by_user: {
    label: 'Canceled',
    className: 'bg-amber-100 text-amber-800',
  },
  not_a_subscription: {
    label: 'Not a subscription',
    className: 'bg-slate-100 text-slate-600',
  },
};

export const SubscriptionStatusBadge: React.FC<{ status: SubscriptionStatus }> = ({
  status,
}) => {
  const config = STATUS_CONFIG[status] ?? STATUS_CONFIG.active;
  return <Badge className={config.className}>{config.label}</Badge>;
};
