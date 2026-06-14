import React, { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import {
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { ArrowDownRight, ArrowUpRight, Camera, Pencil, Plus, Trash2 } from 'lucide-react';

import {
  networthApi,
  type AccountBalanceResponse,
  type LiabilityResponse,
} from '@/lib/api/networth';
import { getErrorMessage } from '@/lib/api';
import {
  ProfessionalCard,
  ProfessionalCardContent,
  ProfessionalCardHeader,
  ProfessionalCardTitle,
} from '@/components/ui/professional-card';
import { ProfessionalButton } from '@/components/ui/professional-button';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { LiabilitiesDialog } from './LiabilitiesDialog';
import { formatCurrency, monthOverMonthDelta, KIND_LABELS } from './networth-helpers';

const TIMEFRAMES = [
  { value: '6', label: '6 months' },
  { value: '12', label: '12 months' },
  { value: '24', label: '24 months' },
  { value: '60', label: '60 months' },
];

const AccountGroup: React.FC<{
  title: string;
  rows: AccountBalanceResponse[];
  negative?: boolean;
}> = ({ title, rows, negative }) => {
  if (rows.length === 0) return null;
  const subtotal = rows.reduce((s, r) => s + r.balance, 0);
  const sign = negative ? '−' : '';
  return (
    <div>
      <div className="mb-1 flex items-center justify-between font-medium">
        <span>{title}</span>
        <span className={negative ? 'text-destructive' : undefined}>
          {sign}
          {formatCurrency(subtotal, rows[0].currency)}
        </span>
      </div>
      {rows.map((r, i) => (
        <div
          key={`${r.label}-${i}`}
          className="flex items-center justify-between pl-3 text-muted-foreground"
        >
          <span>{r.label}</span>
          <span>
            {sign}
            {formatCurrency(r.balance, r.currency)}
          </span>
        </div>
      ))}
    </div>
  );
};

export const NetWorthTabContent: React.FC = () => {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [months, setMonths] = useState('12');
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<LiabilityResponse | null>(null);

  const summaryQuery = useQuery({
    queryKey: ['networth', 'summary'],
    queryFn: () => networthApi.summary(),
  });
  const historyQuery = useQuery({
    queryKey: ['networth', 'history', months],
    queryFn: () => networthApi.history(Number(months)),
  });
  const liabilitiesQuery = useQuery({
    queryKey: ['networth', 'liabilities'],
    queryFn: () => networthApi.listLiabilities(),
  });

  const snapshotMutation = useMutation({
    mutationFn: () => networthApi.snapshot(),
    onSuccess: () => {
      toast.success('Snapshot captured');
      qc.invalidateQueries({ queryKey: ['networth'] });
    },
    onError: (err) => toast.error(getErrorMessage(err, t)),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => networthApi.deleteLiability(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['networth'] }),
    onError: (err) => toast.error(getErrorMessage(err, t)),
  });

  const summary = summaryQuery.data;
  const points = historyQuery.data?.points ?? [];
  const delta = monthOverMonthDelta(points);
  const liabilities = liabilitiesQuery.data ?? [];
  const accounts = summary?.accounts ?? [];

  const openAdd = () => {
    setEditing(null);
    setDialogOpen(true);
  };
  const openEdit = (l: LiabilityResponse) => {
    setEditing(l);
    setDialogOpen(true);
  };

  return (
    <div className="space-y-6">
      <ProfessionalCard>
        <ProfessionalCardContent className="flex flex-wrap items-center justify-between gap-4 py-4">
          <div>
            <div className="text-sm text-muted-foreground">Net worth</div>
            <div className="text-3xl font-semibold">
              {summary ? formatCurrency(summary.net_worth) : '—'}
            </div>
            <div className="text-xs text-muted-foreground">
              {summary?.snapshot_date ? `as of ${summary.snapshot_date}` : 'No snapshot yet'}
            </div>
          </div>
          <div className="flex items-center gap-3">
            {delta.pct !== null && points.length > 1 ? (
              <Badge
                className={
                  delta.direction === 'up'
                    ? 'bg-success/10 text-success'
                    : delta.direction === 'down'
                      ? 'bg-destructive/10 text-destructive'
                      : 'bg-muted text-muted-foreground'
                }
              >
                {delta.direction === 'up' ? (
                  <ArrowUpRight className="mr-1 h-3 w-3" />
                ) : delta.direction === 'down' ? (
                  <ArrowDownRight className="mr-1 h-3 w-3" />
                ) : null}
                {delta.delta >= 0 ? '+' : ''}
                {formatCurrency(delta.delta)} ({delta.pct.toFixed(1)}%)
              </Badge>
            ) : null}
            <ProfessionalButton
              variant="outline"
              onClick={() => snapshotMutation.mutate()}
              disabled={snapshotMutation.isPending}
            >
              <Camera className="mr-2 h-4 w-4" />
              {snapshotMutation.isPending ? 'Capturing…' : 'Snapshot now'}
            </ProfessionalButton>
          </div>
        </ProfessionalCardContent>
      </ProfessionalCard>

      <ProfessionalCard>
        <ProfessionalCardHeader className="flex flex-row items-center justify-between gap-3">
          <ProfessionalCardTitle>Net worth over time</ProfessionalCardTitle>
          <Select value={months} onValueChange={setMonths}>
            <SelectTrigger className="w-36">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {TIMEFRAMES.map((tf) => (
                <SelectItem key={tf.value} value={tf.value}>
                  {tf.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </ProfessionalCardHeader>
        <ProfessionalCardContent>
          {points.length > 1 ? (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={points}>
                  <XAxis dataKey="snapshot_date" />
                  <YAxis domain={['dataMin', 'dataMax']} />
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
          ) : (
            <div className="py-12 text-center text-sm text-muted-foreground">
              Not enough history yet. Use “Snapshot now” to start tracking your net worth over time.
            </div>
          )}
        </ProfessionalCardContent>
      </ProfessionalCard>

      <ProfessionalCard>
        <ProfessionalCardHeader>
          <ProfessionalCardTitle>Accounts</ProfessionalCardTitle>
        </ProfessionalCardHeader>
        <ProfessionalCardContent>
          {accounts.length === 0 ? (
            <div className="py-8 text-center text-sm text-muted-foreground">
              No accounts yet. Import a bank statement or add investments/liabilities, then snapshot.
            </div>
          ) : (
            <div className="space-y-4 text-sm">
              <AccountGroup
                title="Investments"
                rows={accounts.filter((a) => a.account_kind === 'investment')}
              />
              <AccountGroup
                title="Bank"
                rows={accounts.filter((a) => a.account_kind === 'bank')}
              />
              <AccountGroup
                title="Liabilities"
                rows={accounts.filter((a) => a.account_kind === 'liability')}
                negative
              />
              <div className="flex items-center justify-between border-t pt-3 font-semibold">
                <span>Net worth</span>
                <span>{summary ? formatCurrency(summary.net_worth) : '—'}</span>
              </div>
            </div>
          )}
        </ProfessionalCardContent>
      </ProfessionalCard>

      <ProfessionalCard>
        <ProfessionalCardHeader className="flex flex-row items-center justify-between gap-3">
          <ProfessionalCardTitle>Liabilities</ProfessionalCardTitle>
          <ProfessionalButton variant="outline" onClick={openAdd}>
            <Plus className="mr-2 h-4 w-4" />
            Add liability
          </ProfessionalButton>
        </ProfessionalCardHeader>
        <ProfessionalCardContent>
          {liabilities.length === 0 ? (
            <div className="py-6 text-center text-sm text-muted-foreground">
              No liabilities yet.
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead className="text-left text-muted-foreground">
                <tr>
                  <th className="p-2">Name</th>
                  <th className="p-2">Kind</th>
                  <th className="p-2 text-right">Balance</th>
                  <th className="p-2 text-right">Rate</th>
                  <th className="p-2"></th>
                </tr>
              </thead>
              <tbody>
                {liabilities.map((l) => (
                  <tr key={l.id} className="border-t">
                    <td className="p-2">{l.name}</td>
                    <td className="p-2 text-muted-foreground">{KIND_LABELS[l.kind] ?? l.kind}</td>
                    <td className="p-2 text-right">{formatCurrency(l.balance, l.currency)}</td>
                    <td className="p-2 text-right">
                      {l.interest_rate != null ? `${l.interest_rate}%` : '—'}
                    </td>
                    <td className="whitespace-nowrap p-2 text-right">
                      <Button size="sm" variant="ghost" onClick={() => openEdit(l)}>
                        <Pencil className="h-4 w-4" />
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => deleteMutation.mutate(l.id)}
                        disabled={deleteMutation.isPending}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </ProfessionalCardContent>
      </ProfessionalCard>

      <LiabilitiesDialog
        open={dialogOpen}
        liability={editing}
        onClose={() => setDialogOpen(false)}
      />
    </div>
  );
};
