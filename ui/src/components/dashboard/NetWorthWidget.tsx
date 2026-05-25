import React, { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { ArrowDownRight, ArrowUpRight, Camera, Scale, Settings2 } from 'lucide-react';

import { networthApi } from '@/lib/api/networth';
import { useFeatures } from '@/contexts/FeatureContext';
import {
  ProfessionalCard,
  ProfessionalCardContent,
  ProfessionalCardHeader,
  ProfessionalCardTitle,
} from '@/components/ui/professional-card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { LiabilitiesDialog } from '@/components/networth/LiabilitiesDialog';
import {
  formatCurrency,
  monthOverMonthDelta,
} from '@/components/networth/networth-helpers';

export const NetWorthWidget: React.FC = () => {
  const { isFeatureEnabled } = useFeatures();
  const enabled = isFeatureEnabled('net_worth');
  const qc = useQueryClient();
  const [liabilitiesOpen, setLiabilitiesOpen] = useState(false);

  const summaryQuery = useQuery({
    queryKey: ['networth', 'summary'],
    queryFn: () => networthApi.summary(),
    enabled,
  });

  const historyQuery = useQuery({
    queryKey: ['networth', 'history'],
    queryFn: () => networthApi.history(12),
    enabled,
  });

  const snapshotMutation = useMutation({
    mutationFn: () => networthApi.snapshot(),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['networth'] });
    },
  });

  if (!enabled) return null;

  const summary = summaryQuery.data;
  const history = historyQuery.data?.points ?? [];
  const delta = monthOverMonthDelta(history);
  const isLoading = summaryQuery.isLoading || historyQuery.isLoading;
  const hasData = summary && summary.snapshot_date;

  return (
    <>
      <ProfessionalCard data-tour="dashboard-net-worth">
        <ProfessionalCardHeader className="flex flex-row items-center justify-between">
          <ProfessionalCardTitle className="text-lg flex items-center gap-2">
            <Scale className="h-4 w-4" />
            Net Worth
          </ProfessionalCardTitle>
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant="outline"
              onClick={() => setLiabilitiesOpen(true)}
            >
              <Settings2 className="h-3 w-3 mr-1" />
              Liabilities
            </Button>
            <Button
              size="sm"
              onClick={() => snapshotMutation.mutate()}
              disabled={snapshotMutation.isPending}
            >
              <Camera className="h-3 w-3 mr-1" />
              {snapshotMutation.isPending ? 'Snapshotting…' : 'Snapshot now'}
            </Button>
          </div>
        </ProfessionalCardHeader>
        <ProfessionalCardContent>
          {isLoading ? (
            <div className="text-sm text-muted-foreground">Loading…</div>
          ) : !hasData ? (
            <div className="text-sm text-muted-foreground">
              No snapshot yet. Click <strong>Snapshot now</strong> to capture
              your current balances.
            </div>
          ) : (
            <div className="space-y-4">
              <div className="flex items-baseline justify-between flex-wrap gap-2">
                <div>
                  <div className="text-3xl font-semibold">
                    {formatCurrency(summary.net_worth)}
                  </div>
                  <div className="text-xs text-muted-foreground">
                    as of {summary.snapshot_date}
                  </div>
                </div>
                {delta.pct !== null && history.length > 1 ? (
                  <Badge
                    className={
                      delta.direction === 'up'
                        ? 'bg-emerald-100 text-emerald-700'
                        : delta.direction === 'down'
                          ? 'bg-red-100 text-red-700'
                          : 'bg-muted text-muted-foreground'
                    }
                  >
                    {delta.direction === 'up' ? (
                      <ArrowUpRight className="h-3 w-3 mr-1" />
                    ) : delta.direction === 'down' ? (
                      <ArrowDownRight className="h-3 w-3 mr-1" />
                    ) : null}
                    {delta.delta >= 0 ? '+' : ''}
                    {formatCurrency(delta.delta)} ({delta.pct.toFixed(1)}%)
                  </Badge>
                ) : null}
              </div>

              {history.length > 1 ? (
                <div className="h-24">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={history}>
                      <XAxis dataKey="snapshot_date" hide />
                      <YAxis hide domain={['dataMin', 'dataMax']} />
                      <Tooltip
                        formatter={(value: number) => formatCurrency(value)}
                        labelFormatter={(label) => `Date: ${label}`}
                      />
                      <Line
                        type="monotone"
                        dataKey="net_worth"
                        stroke="#10b981"
                        strokeWidth={2}
                        dot={false}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              ) : null}

              <div className="grid grid-cols-3 gap-2 text-xs">
                <div>
                  <div className="text-muted-foreground">Bank</div>
                  <div className="font-medium">
                    {formatCurrency(summary.bank_total)}
                  </div>
                </div>
                <div>
                  <div className="text-muted-foreground">Investments</div>
                  <div className="font-medium">
                    {formatCurrency(summary.investment_total)}
                  </div>
                </div>
                <div>
                  <div className="text-muted-foreground">Liabilities</div>
                  <div className="font-medium text-red-600">
                    -{formatCurrency(summary.liability_total)}
                  </div>
                </div>
              </div>
            </div>
          )}
        </ProfessionalCardContent>
      </ProfessionalCard>

      <LiabilitiesDialog
        open={liabilitiesOpen}
        onClose={() => setLiabilitiesOpen(false)}
      />
    </>
  );
};
