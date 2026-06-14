# Finances Hub + Net Worth Tab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Group Cash Flow and Net Worth into a `/finances` hub with tabs, and build a full Net Worth tab (per-account breakdown, trend chart + timeframe, delta, snapshot, full liabilities management) over existing endpoints.

**Architecture:** Frontend-only. A thin `Finances.tsx` hub owns a `PageHeader` + shadcn `Tabs` (driven by `?tab=`, gated per feature). The Cash Flow body is extracted from the 968-line `CashFlow.tsx` into `CashFlowTabContent`; a new `NetWorthTabContent` renders the Net Worth tab. `LiabilitiesDialog` gains edit mode + `interest_rate`/`notes`. Routing redirects `/cashflow → /finances`.

**Tech Stack:** React + TypeScript + Vite, TanStack Query, shadcn/Radix UI, recharts, react-router v6, Vitest/RTL. Tests: `docker compose exec -T ui npx vitest run <path>`; type-check: `docker compose exec -T ui npx tsc -p tsconfig.app.json --noEmit`. Stack is up.

**No backend changes.** All endpoints already exist: `networthApi.summary()` (returns `accounts: AccountBalanceResponse[]`), `history(months)` (≤60), `snapshot()`, `listLiabilities()/createLiability()/updateLiability(PATCH)/deleteLiability()`.

**Spec:** `docs/superpowers/specs/2026-06-14-finances-hub-networth-tab-design.md`

**Reference facts (verified):**
- `ui/src/test/test-utils.tsx` exports `render` (= renderWithProviders) mocking `FeatureContext` (`isFeatureEnabled → true`), `react-i18next` (`t(key,{defaultValue})→defaultValue`), wrapping `QueryClientProvider` + `BrowserRouter`.
- `networth-helpers.ts` already exports `formatCurrency`, `monthOverMonthDelta` (DeltaInfo{delta,pct,direction}), `KIND_LABELS`.
- `LiabilitiesDialog` Props today: `{ open, onClose }` (create + delete only; ignores interest_rate/notes). Used by `NetWorthWidget` as `<LiabilitiesDialog open onClose />` — adding an optional prop stays compatible.
- `CashFlow.tsx` main component (line 888) = `FeatureGate(cash_flow)` → `div.space-y-6` → `PageHeader("Cash Flow")` → grid; uses `useTranslation`, `useFeatures` (`cashflowEnabled`), `period` state, 3 queries (`getForecast`/`getRunway`/`getAlerts`), and in-file sub-components `AlertsBanner`/`RunwayCard`/`ForecastChart`/`InflowOutflowBreakdown`/`ScenarioBuilder`/`StatementPatternSidebar`.
- `App.tsx`: `Navigate` already imported (line 11); query-param redirect precedent at line 316 (`/projects → /time-tracking?tab=projects`); `CashFlow` lazy at line 98; `/cashflow` route at line 309.
- `AppSidebar.tsx` cashflow entry (~line 390): `...(isFeatureEnabled('cash_flow') ? [{ path:'/cashflow', label:t('navigation.cashflow',{defaultValue:'Cash Flow'}), icon:<TrendingUp .../>, tourId:'nav-cashflow' }] : [])`.
- `CashFlowForecastCard.tsx` line 79: `onClick={() => navigate('/cashflow')}`.
- `NetWorthWidget.tsx`: "View all" link/area → should target `/finances?tab=networth`.

---

## Task 1: Enhance `LiabilitiesDialog` (edit mode + interest_rate/notes)

**Files:**
- Modify: `ui/src/components/networth/LiabilitiesDialog.tsx`
- Test: `ui/src/components/networth/__tests__/LiabilitiesDialog.test.tsx` (create)

- [ ] **Step 1: Write the failing test**

Create `ui/src/components/networth/__tests__/LiabilitiesDialog.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, fireEvent, waitFor } from '@testing-library/react';
import { render } from '@/test/test-utils';
import type { LiabilityResponse } from '@/lib/api/networth';

const createLiability = vi.fn();
const updateLiability = vi.fn();
vi.mock('@/lib/api/networth', () => ({
  networthApi: {
    listLiabilities: () => Promise.resolve([]),
    createLiability: (...a: unknown[]) => createLiability(...a),
    updateLiability: (...a: unknown[]) => updateLiability(...a),
    deleteLiability: vi.fn(),
  },
}));

import { LiabilitiesDialog } from '../LiabilitiesDialog';

const sample: LiabilityResponse = {
  id: 7,
  name: 'Car loan',
  kind: 'loan',
  balance: 12000,
  currency: 'USD',
  interest_rate: 4.5,
  notes: 'Toyota',
  created_at: '2025-01-01T00:00:00Z',
  updated_at: '2025-01-01T00:00:00Z',
};

beforeEach(() => {
  createLiability.mockReset().mockResolvedValue(sample);
  updateLiability.mockReset().mockResolvedValue(sample);
});

describe('LiabilitiesDialog', () => {
  it('edit mode prefills and saves via updateLiability with interest_rate + notes', async () => {
    render(<LiabilitiesDialog open liability={sample} onClose={() => {}} />);
    expect((screen.getByLabelText('Name') as HTMLInputElement).value).toBe('Car loan');
    fireEvent.click(screen.getByRole('button', { name: /save/i }));
    await waitFor(() => expect(updateLiability).toHaveBeenCalledTimes(1));
    const [id, body] = updateLiability.mock.calls[0];
    expect(id).toBe(7);
    expect(body).toMatchObject({ name: 'Car loan', interest_rate: 4.5, notes: 'Toyota' });
    expect(createLiability).not.toHaveBeenCalled();
  });

  it('add mode (no liability) creates via createLiability', async () => {
    render(<LiabilitiesDialog open onClose={() => {}} />);
    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'New card' } });
    fireEvent.change(screen.getByLabelText('Balance'), { target: { value: '500' } });
    fireEvent.click(screen.getByRole('button', { name: /add liability/i }));
    await waitFor(() => expect(createLiability).toHaveBeenCalledTimes(1));
    expect(createLiability.mock.calls[0][0]).toMatchObject({ name: 'New card', balance: 500 });
  });
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `docker compose exec -T ui npx vitest run src/components/networth/__tests__/LiabilitiesDialog.test.tsx`
Expected: FAIL — no `Name` label association / no Save button / `liability` prop unknown.

- [ ] **Step 3: Rewrite the dialog with edit mode + fields**

Replace the entire contents of `ui/src/components/networth/LiabilitiesDialog.tsx` with:

```tsx
import React, { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Trash2 } from 'lucide-react';

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  networthApi,
  type LiabilityKind,
  type LiabilityResponse,
} from '@/lib/api/networth';
import { formatCurrency, KIND_LABELS } from './networth-helpers';

interface Props {
  open: boolean;
  onClose: () => void;
  /** When provided, the form is in edit mode (PATCH); otherwise create mode (POST). */
  liability?: LiabilityResponse | null;
}

const KINDS: LiabilityKind[] = ['credit_card', 'loan', 'mortgage', 'other'];

export const LiabilitiesDialog: React.FC<Props> = ({ open, onClose, liability }) => {
  const qc = useQueryClient();
  const editing = liability ?? null;

  const [name, setName] = useState('');
  const [kind, setKind] = useState<LiabilityKind>('credit_card');
  const [balance, setBalance] = useState('');
  const [interestRate, setInterestRate] = useState('');
  const [notes, setNotes] = useState('');

  // Sync form to the row being edited (or reset for add) whenever it changes / dialog opens.
  useEffect(() => {
    if (editing) {
      setName(editing.name);
      setKind(editing.kind);
      setBalance(String(editing.balance ?? ''));
      setInterestRate(editing.interest_rate != null ? String(editing.interest_rate) : '');
      setNotes(editing.notes ?? '');
    } else {
      setName('');
      setKind('credit_card');
      setBalance('');
      setInterestRate('');
      setNotes('');
    }
  }, [editing, open]);

  const { data: liabilities = [], isLoading } = useQuery({
    queryKey: ['networth', 'liabilities'],
    queryFn: () => networthApi.listLiabilities(),
    enabled: open && !editing,
  });

  const body = () => ({
    name: name.trim(),
    kind,
    balance: parseFloat(balance) || 0,
    interest_rate: interestRate.trim() === '' ? null : parseFloat(interestRate),
    notes: notes.trim() === '' ? null : notes.trim(),
  });

  const saveMutation = useMutation({
    mutationFn: () =>
      editing
        ? networthApi.updateLiability(editing.id, body())
        : networthApi.createLiability(body()),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['networth'] });
      if (editing) {
        onClose();
      } else {
        setName('');
        setBalance('');
        setInterestRate('');
        setNotes('');
      }
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => networthApi.deleteLiability(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['networth'] }),
  });

  const canSave = name.trim().length > 0 && (parseFloat(balance) || 0) >= 0;

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>{editing ? 'Edit liability' : 'Manage liabilities'}</DialogTitle>
          <DialogDescription>
            Liabilities are subtracted from your bank and investment balances to compute
            net worth. Update these whenever a balance changes.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label htmlFor="liability-name">Name</Label>
              <Input
                id="liability-name"
                placeholder="e.g. Chase Sapphire"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </div>
            <div>
              <Label htmlFor="liability-kind">Kind</Label>
              <Select value={kind} onValueChange={(v) => setKind(v as LiabilityKind)}>
                <SelectTrigger id="liability-kind">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {KINDS.map((k) => (
                    <SelectItem key={k} value={k}>
                      {KIND_LABELS[k]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label htmlFor="liability-balance">Balance</Label>
              <Input
                id="liability-balance"
                type="number"
                min={0}
                step="0.01"
                placeholder="0.00"
                value={balance}
                onChange={(e) => setBalance(e.target.value)}
              />
            </div>
            <div>
              <Label htmlFor="liability-rate">Interest rate (%)</Label>
              <Input
                id="liability-rate"
                type="number"
                min={0}
                max={100}
                step="0.01"
                placeholder="optional"
                value={interestRate}
                onChange={(e) => setInterestRate(e.target.value)}
              />
            </div>
            <div className="col-span-2">
              <Label htmlFor="liability-notes">Notes</Label>
              <Input
                id="liability-notes"
                placeholder="optional"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
              />
            </div>
          </div>

          <div className="flex justify-end">
            <Button disabled={!canSave || saveMutation.isPending} onClick={() => saveMutation.mutate()}>
              {editing ? 'Save' : 'Add liability'}
            </Button>
          </div>

          {!editing ? (
            <div className="rounded border">
              {isLoading ? (
                <div className="p-4 text-sm text-muted-foreground">Loading…</div>
              ) : liabilities.length === 0 ? (
                <div className="p-4 text-sm text-muted-foreground">
                  No liabilities yet. Add one above.
                </div>
              ) : (
                <table className="w-full text-sm">
                  <thead className="bg-muted/50">
                    <tr>
                      <th className="p-2 text-left">Name</th>
                      <th className="p-2 text-left">Kind</th>
                      <th className="p-2 text-right">Balance</th>
                      <th className="p-2"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {liabilities.map((liab: LiabilityResponse) => (
                      <tr key={liab.id} className="border-t">
                        <td className="p-2">{liab.name}</td>
                        <td className="p-2 text-muted-foreground">
                          {KIND_LABELS[liab.kind] ?? liab.kind}
                        </td>
                        <td className="p-2 text-right">
                          {formatCurrency(liab.balance, liab.currency)}
                        </td>
                        <td className="p-2 text-right">
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => deleteMutation.mutate(liab.id)}
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
            </div>
          ) : null}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            {editing ? 'Cancel' : 'Done'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
```

- [ ] **Step 4: Run to verify it passes**

Run: `docker compose exec -T ui npx vitest run src/components/networth/__tests__/LiabilitiesDialog.test.tsx`
Expected: PASS (2 tests). Then `docker compose exec -T ui npx tsc -p tsconfig.app.json --noEmit 2>&1 | grep -E "LiabilitiesDialog|NetWorthWidget" || echo CLEAN` — expect CLEAN (NetWorthWidget still uses `<LiabilitiesDialog open onClose />` which remains valid).

- [ ] **Step 5: Commit**

```bash
git add ui/src/components/networth/LiabilitiesDialog.tsx \
        ui/src/components/networth/__tests__/LiabilitiesDialog.test.tsx
git commit -m "feat(networth): LiabilitiesDialog edit mode + interest_rate/notes"
```

---

## Task 2: `NetWorthTabContent` component

**Files:**
- Create: `ui/src/components/networth/NetWorthTabContent.tsx`
- Test: `ui/src/components/networth/__tests__/NetWorthTabContent.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `ui/src/components/networth/__tests__/NetWorthTabContent.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen } from '@testing-library/react';
import { render } from '@/test/test-utils';
import type { NetWorthSummaryResponse, HistoryResponse } from '@/lib/api/networth';

const summary: NetWorthSummaryResponse = {
  snapshot_date: '2026-06-01',
  total_assets: 130000,
  total_liabilities: 12000,
  net_worth: 118000,
  bank_total: 42000,
  investment_total: 88000,
  liability_total: 12000,
  accounts: [
    { account_kind: 'investment', label: 'Brokerage', balance: 88000, currency: 'USD' },
    { account_kind: 'bank', label: 'Chase Checking', balance: 42000, currency: 'USD' },
    { account_kind: 'liability', label: 'Visa', balance: 12000, currency: 'USD' },
  ],
};
const history: HistoryResponse = {
  points: [
    { snapshot_date: '2026-05-01', total_assets: 120000, total_liabilities: 12000, net_worth: 108000 },
    { snapshot_date: '2026-06-01', total_assets: 130000, total_liabilities: 12000, net_worth: 118000 },
  ],
};

vi.mock('@/lib/api/networth', () => ({
  networthApi: {
    summary: () => Promise.resolve(summary),
    history: () => Promise.resolve(history),
    listLiabilities: () => Promise.resolve([
      { id: 1, name: 'Visa', kind: 'credit_card', balance: 12000, currency: 'USD',
        interest_rate: 19.9, notes: null, created_at: '', updated_at: '' },
    ]),
    snapshot: vi.fn(),
    deleteLiability: vi.fn(),
  },
}));

import { NetWorthTabContent } from '../NetWorthTabContent';

beforeEach(() => {});

describe('NetWorthTabContent', () => {
  it('renders the per-account breakdown, delta, and liabilities section', async () => {
    render(<NetWorthTabContent />);
    // per-account breakdown shows each account by label
    expect(await screen.findByText('Brokerage')).toBeInTheDocument();
    expect(await screen.findByText('Chase Checking')).toBeInTheDocument();
    // group headings present
    expect(screen.getByText('Investments')).toBeInTheDocument();
    expect(screen.getByText('Accounts')).toBeInTheDocument();
    // snapshot action present
    expect(screen.getByRole('button', { name: /snapshot now/i })).toBeInTheDocument();
    // liabilities management section
    expect(screen.getByRole('button', { name: /add liability/i })).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `docker compose exec -T ui npx vitest run src/components/networth/__tests__/NetWorthTabContent.test.tsx`
Expected: FAIL — module `../NetWorthTabContent` not found.

- [ ] **Step 3: Create the component**

Create `ui/src/components/networth/NetWorthTabContent.tsx`:

```tsx
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
```

- [ ] **Step 4: Run to verify it passes**

Run: `docker compose exec -T ui npx vitest run src/components/networth/__tests__/NetWorthTabContent.test.tsx`
Expected: PASS. Then `docker compose exec -T ui npx tsc -p tsconfig.app.json --noEmit 2>&1 | grep NetWorthTabContent || echo CLEAN` → CLEAN.

- [ ] **Step 5: Commit**

```bash
git add ui/src/components/networth/NetWorthTabContent.tsx \
        ui/src/components/networth/__tests__/NetWorthTabContent.test.tsx
git commit -m "feat(networth): NetWorthTabContent (breakdown, chart, delta, snapshot, liabilities)"
```

---

## Task 3: Extract `CashFlowTabContent` from `CashFlow.tsx`

**Files:**
- Modify: `ui/src/pages/CashFlow.tsx`

This is a pure cut-move: turn the existing `CashFlow` main component body into an exported `CashFlowTabContent` (no `FeatureGate`, no `PageHeader`), and keep a thin `CashFlow` default wrapper so the existing `/cashflow` route keeps working until Task 5. No logic changes, no sub-component changes.

- [ ] **Step 1: Read the current main component**

Run: `docker compose exec -T ui sed -n '888,968p' src/pages/CashFlow.tsx` (or Read the file). Confirm it matches the shape: `const CashFlow = () => { hooks; return (<FeatureGate feature="cash_flow" ...><div className="space-y-6"><PageHeader .../>{grid}</div></FeatureGate>); }; export default CashFlow;`.

- [ ] **Step 2: Replace the main component block**

Replace the `const CashFlow: React.FC = () => { ... }; export default CashFlow;` block (lines ~888–968) with the following. The hooks (`t`, `cashflowEnabled`, `period`, the three queries) move into `CashFlowTabContent`; the grid markup is identical to today minus the `<PageHeader .../>`. The thin `CashFlow` default keeps `FeatureGate` + `PageHeader` and renders the new content component.

```tsx
export const CashFlowTabContent: React.FC = () => {
  const { isFeatureEnabled } = useFeatures();
  const cashflowEnabled = isFeatureEnabled('cash_flow');
  const [period, setPeriod] = useState<ForecastPeriod>('30d');

  const { data: forecast, isLoading: forecastLoading } = useQuery({
    queryKey: ['cashflow-forecast', period],
    queryFn: () => cashflowApi.getForecast(period),
    enabled: cashflowEnabled,
  });

  const { data: runway, isLoading: runwayLoading } = useQuery({
    queryKey: ['cashflow-runway'],
    queryFn: () => cashflowApi.getRunway(),
    enabled: cashflowEnabled,
  });

  const { data: alerts } = useQuery({
    queryKey: ['cashflow-alerts'],
    queryFn: () => cashflowApi.getAlerts(),
    enabled: cashflowEnabled,
  });

  return (
    <div className="space-y-6">
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <div className="space-y-6">
          {/* Period selector */}
          <div className="flex items-center gap-3">
            <span className="text-sm font-medium text-muted-foreground">Forecast Period:</span>
            <Select value={period} onValueChange={(v) => setPeriod(v as ForecastPeriod)}>
              <SelectTrigger className="w-32">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="7d">7 Days</SelectItem>
                <SelectItem value="30d">30 Days</SelectItem>
                <SelectItem value="90d">90 Days</SelectItem>
                <SelectItem value="365d">365 Days</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Alerts */}
          <AlertsBanner alerts={alerts} />

          {/* Runway */}
          <RunwayCard runway={runway} isLoading={runwayLoading} />

          {/* Forecast chart */}
          <ForecastChart forecast={forecast} isLoading={forecastLoading} />

          {/* Inflow & Outflow breakdown */}
          <InflowOutflowBreakdown forecast={forecast} isLoading={forecastLoading} />

          {/* Scenario builder */}
          <ScenarioBuilder />
        </div>

        <aside className="space-y-4 lg:sticky lg:top-6 lg:self-start">
          <StatementPatternSidebar period={period} />
        </aside>
      </div>
    </div>
  );
};

const CashFlow: React.FC = () => {
  const { t } = useTranslation();
  return (
    <FeatureGate
      feature="cash_flow"
      showUpgradePrompt={true}
      upgradeMessage="Cash Flow forecasting requires a commercial license."
      showExpiredContent={false}
    >
      <div className="space-y-6">
        <PageHeader
          title={t('cashflow.title', { defaultValue: 'Cash Flow' })}
          subtitle={t('cashflow.subtitle', {
            defaultValue: 'Forecast, runway analysis, and scenario planning',
          })}
        />
        <CashFlowTabContent />
      </div>
    </FeatureGate>
  );
};

export default CashFlow;
```

> Note: `useTranslation`, `useFeatures`, `useState`, `useQuery`, `cashflowApi`, `FeatureGate`, `PageHeader`, the `Select*` primitives, and all sub-components are already imported at the top of the file — no import changes needed. If `tsc` reports an unused import after the move (e.g. a hook now only used in one place), it will still be used by one of the two components; do not remove imports.

- [ ] **Step 3: Verify type-check + existing cashflow behavior**

Run: `docker compose exec -T ui npx tsc -p tsconfig.app.json --noEmit 2>&1 | grep "CashFlow.tsx" || echo CLEAN`
Expected: CLEAN. The `/cashflow` route still renders `<CashFlow/>` (unchanged) — confirm the dev build compiles.

- [ ] **Step 4: Commit**

```bash
git add ui/src/pages/CashFlow.tsx
git commit -m "refactor(cashflow): extract CashFlowTabContent (no behavior change)"
```

---

## Task 4: `Finances` hub page

**Files:**
- Create: `ui/src/pages/Finances.tsx`
- Test: `ui/src/pages/__tests__/Finances.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `ui/src/pages/__tests__/Finances.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';

// Stub the two heavy tab bodies so we test hub behavior in isolation.
vi.mock('@/pages/CashFlow', () => ({
  CashFlowTabContent: () => <div>CASHFLOW_BODY</div>,
}));
vi.mock('@/components/networth/NetWorthTabContent', () => ({
  NetWorthTabContent: () => <div>NETWORTH_BODY</div>,
}));

// Configurable feature flags.
const flags: Record<string, boolean> = { cash_flow: true, net_worth: true };
vi.mock('@/contexts/FeatureContext', () => ({
  useFeatures: () => ({ isFeatureEnabled: (f: string) => !!flags[f] }),
}));
vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (_k: string, o?: { defaultValue?: string }) => o?.defaultValue ?? _k }),
}));

import Finances from '../Finances';

const renderAt = (path: string) => {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[path]}>
        <Finances />
      </MemoryRouter>
    </QueryClientProvider>,
  );
};

beforeEach(() => {
  flags.cash_flow = true;
  flags.net_worth = true;
});

describe('Finances hub', () => {
  it('shows both tabs, defaulting to Cash Flow', () => {
    renderAt('/finances');
    expect(screen.getByRole('tab', { name: 'Cash Flow' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'Net Worth' })).toBeInTheDocument();
    expect(screen.getByText('CASHFLOW_BODY')).toBeInTheDocument();
  });

  it('deep-links to the Net Worth tab via ?tab=networth', () => {
    renderAt('/finances?tab=networth');
    expect(screen.getByText('NETWORTH_BODY')).toBeInTheDocument();
  });

  it('hides the Cash Flow tab when only net_worth is enabled', () => {
    flags.cash_flow = false;
    renderAt('/finances');
    expect(screen.queryByRole('tab', { name: 'Cash Flow' })).not.toBeInTheDocument();
    expect(screen.getByText('NETWORTH_BODY')).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `docker compose exec -T ui npx vitest run src/pages/__tests__/Finances.test.tsx`
Expected: FAIL — `../Finances` not found.

- [ ] **Step 3: Create the hub**

Create `ui/src/pages/Finances.tsx`:

```tsx
import React from 'react';
import { useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import { useFeatures } from '@/contexts/FeatureContext';
import { FeatureGate } from '@/components/FeatureGate';
import { PageHeader } from '@/components/ui/professional-layout';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { CashFlowTabContent } from '@/pages/CashFlow';
import { NetWorthTabContent } from '@/components/networth/NetWorthTabContent';

type TabKey = 'cashflow' | 'networth';

const Finances: React.FC = () => {
  const { t } = useTranslation();
  const { isFeatureEnabled } = useFeatures();
  const [searchParams, setSearchParams] = useSearchParams();

  const cashflowEnabled = isFeatureEnabled('cash_flow');
  const networthEnabled = isFeatureEnabled('net_worth');

  const available: TabKey[] = [
    ...(cashflowEnabled ? (['cashflow'] as TabKey[]) : []),
    ...(networthEnabled ? (['networth'] as TabKey[]) : []),
  ];

  // Neither feature licensed: show the upgrade prompt (gate on cash_flow).
  if (available.length === 0) {
    return (
      <FeatureGate feature="cash_flow" showUpgradePrompt>
        <div />
      </FeatureGate>
    );
  }

  const requested = searchParams.get('tab') as TabKey | null;
  const active: TabKey =
    requested && available.includes(requested) ? requested : available[0];

  const onTabChange = (value: string) => {
    const next = new URLSearchParams(searchParams);
    next.set('tab', value);
    setSearchParams(next, { replace: true });
  };

  return (
    <div className="space-y-6 p-6">
      <PageHeader
        title={t('navigation.finances', { defaultValue: 'Finances' })}
        subtitle={t('finances.subtitle', {
          defaultValue: 'Cash flow forecasting and your net worth in one place',
        })}
      />
      <Tabs value={active} onValueChange={onTabChange}>
        <TabsList>
          {cashflowEnabled ? <TabsTrigger value="cashflow">Cash Flow</TabsTrigger> : null}
          {networthEnabled ? <TabsTrigger value="networth">Net Worth</TabsTrigger> : null}
        </TabsList>
        {cashflowEnabled ? (
          <TabsContent value="cashflow" className="mt-6">
            <CashFlowTabContent />
          </TabsContent>
        ) : null}
        {networthEnabled ? (
          <TabsContent value="networth" className="mt-6">
            <NetWorthTabContent />
          </TabsContent>
        ) : null}
      </Tabs>
    </div>
  );
};

export default Finances;
```

- [ ] **Step 4: Run to verify it passes**

Run: `docker compose exec -T ui npx vitest run src/pages/__tests__/Finances.test.tsx`
Expected: PASS (3 tests). Then `docker compose exec -T ui npx tsc -p tsconfig.app.json --noEmit 2>&1 | grep "Finances.tsx" || echo CLEAN` → CLEAN.

- [ ] **Step 5: Commit**

```bash
git add ui/src/pages/Finances.tsx ui/src/pages/__tests__/Finances.test.tsx
git commit -m "feat(finances): Finances hub page with Cash Flow + Net Worth tabs"
```

---

## Task 5: Routing, sidebar, and dashboard links

**Files:**
- Modify: `ui/src/App.tsx`
- Modify: `ui/src/pages/CashFlow.tsx` (drop now-unused default wrapper)
- Modify: `ui/src/components/layout/AppSidebar.tsx`
- Modify: `ui/src/components/dashboard/CashFlowForecastCard.tsx`
- Modify: `ui/src/components/dashboard/NetWorthWidget.tsx`

- [ ] **Step 1: App.tsx — add `/finances`, redirect `/cashflow`, swap lazy import**

In `ui/src/App.tsx`:
(a) Replace the CashFlow lazy import (line ~98) `const CashFlow = React.lazy(() => import("./pages/CashFlow"));` with:
```tsx
const Finances = React.lazy(() => import("./pages/Finances"));
```
(b) Replace the `/cashflow` route (line ~309) with the hub route + a redirect:
```tsx
                    <Route path="/finances" element={<RoleProtectedRoute allowedRoles={['admin', 'user']}><Finances /></RoleProtectedRoute>} />
                    <Route path="/cashflow" element={<Navigate to="/finances" replace />} />
```
(`Navigate` is already imported.)

- [ ] **Step 2: CashFlow.tsx — drop the now-unused default wrapper**

Now that nothing imports the `CashFlow` default export (App uses `Finances`, which imports `CashFlowTabContent`), remove the thin `CashFlow` wrapper component and `export default CashFlow;` added in Task 3. Keep `export const CashFlowTabContent`. If `tsc` then flags `FeatureGate`, `PageHeader`, or `useTranslation` as unused imports, remove only those now-unused imports from the top of the file (verify each is truly unused elsewhere in the file first).

- [ ] **Step 3: AppSidebar.tsx — Finances entry gated on either feature**

Replace the cashflow entry (~line 390):
```tsx
    ...(isFeatureEnabled('cash_flow') ? [{
      path: '/cashflow',
      label: t('navigation.cashflow', { defaultValue: 'Cash Flow' }),
      icon: <TrendingUp className="w-5 h-5" />,
      tourId: 'nav-cashflow'
    }] : []),
```
with:
```tsx
    ...((isFeatureEnabled('cash_flow') || isFeatureEnabled('net_worth')) ? [{
      path: '/finances',
      label: t('navigation.finances', { defaultValue: 'Finances' }),
      icon: <TrendingUp className="w-5 h-5" />,
      tourId: 'nav-finances'
    }] : []),
```

- [ ] **Step 4: Dashboard links → /finances**

In `ui/src/components/dashboard/CashFlowForecastCard.tsx` (line ~79) change `navigate('/cashflow')` → `navigate('/finances')`.

In `ui/src/components/dashboard/NetWorthWidget.tsx`, find the "View all" navigation/link target and point it at `/finances?tab=networth`. (Search the file for the existing navigate/Link that opens the net-worth area; if there is no existing "view all" link, add a small `Link` to `/finances?tab=networth` in the widget header reading "View all".)

- [ ] **Step 5: Verify**

Run: `docker compose exec -T ui npx tsc -p tsconfig.app.json --noEmit 2>&1 | grep -E "App.tsx|CashFlow.tsx|AppSidebar|CashFlowForecastCard|NetWorthWidget" || echo CLEAN`
Expected: CLEAN.
Run the touched tests still pass: `docker compose exec -T ui npx vitest run src/pages/__tests__/Finances.test.tsx src/components/networth`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add ui/src/App.tsx ui/src/pages/CashFlow.tsx \
        ui/src/components/layout/AppSidebar.tsx \
        ui/src/components/dashboard/CashFlowForecastCard.tsx \
        ui/src/components/dashboard/NetWorthWidget.tsx
git commit -m "feat(finances): route /finances + redirect /cashflow; Finances nav + dashboard links"
```

---

## Task 6: Full verification

**Files:** none (verification only)

- [ ] **Step 1: Type-check the whole app for the touched files**

Run: `docker compose exec -T ui npx tsc -p tsconfig.app.json --noEmit 2>&1 | grep -E "Finances|NetWorthTabContent|LiabilitiesDialog|CashFlow.tsx|AppSidebar|CashFlowForecastCard|NetWorthWidget|App.tsx" || echo "CLEAN: no tsc errors in touched files"`
Expected: CLEAN.

- [ ] **Step 2: Run all new/affected tests**

Run: `docker compose exec -T ui npx vitest run src/pages/__tests__/Finances.test.tsx src/components/networth`
Expected: all pass.

- [ ] **Step 3: Manual sanity (optional)**

With the stack up and a tenant licensed for `net_worth` (and/or `cash_flow`): visit `/finances`, confirm the tabs reflect enabled features, the Net Worth tab shows per-account breakdown / chart with timeframe / delta / snapshot / liabilities add+edit+delete, and that `/cashflow` redirects to `/finances`.

- [ ] **Step 4: No commit** (verification only). If anything failed, return to the relevant task.

---

## Self-Review notes (reconciled)

- **Spec coverage:** hub + tabs + ?tab + gating → Task 4; CashFlow extraction → Task 3; Net Worth tab (breakdown/chart+timeframe/delta/snapshot/liabilities) → Task 2; liabilities edit + interest_rate/notes → Task 1; routing/redirect/sidebar/dashboard links → Task 5; tests → Tasks 1,2,4 + Task 6. No backend changes (matches spec). Out-of-scope items (auto-snapshots, full i18n, Decimal, Budgets/Goals) absent.
- **Build stays green between tasks:** Task 3 keeps a working `/cashflow` route (thin wrapper); Task 5 swaps routing and only then removes the wrapper.
- **Type/name consistency:** `CashFlowTabContent` (named export from `@/pages/CashFlow`), `NetWorthTabContent` (named export), `Finances` (default export), `LiabilitiesDialog` gains optional `liability` prop. `?tab` values `cashflow`/`networth` consistent across hub + tests + links.
- **No placeholders:** full code for new files; precise diffs for edits; exact commands with expected output.
