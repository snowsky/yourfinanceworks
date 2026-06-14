# Touchless AP — Slice 2 (Web "Scan a bill" modal) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "Scan a bill" modal on the Expenses page: drop a receipt → preview the AI-extracted fields → confirm (creates the expense + attaches the file) or cancel (nothing persisted).

**Architecture:** A self-contained `ScanBillDialog` renders its own trigger button and a dialog. On file select it calls the slice-1 `scanReceipt` endpoint, pre-fills an editable form from `{available, fields}` (empty + notice when `available:false`), and on Save reuses the existing `createExpense` + `uploadReceipt`. No new expense status; nothing persists until Save.

**Tech Stack:** React + TypeScript, ShadCN Dialog, sonner toasts, react-i18next, Vitest.

**Spec:** `docs/superpowers/specs/2026-06-13-touchless-ap-receipt-scan-design.md` (slice 2).

**Conventions (verified):**
- UI test: `docker compose exec -T ui npx vitest run <path>`. tsc: `docker compose exec -T ui npx tsc -p tsconfig.app.json --noEmit`.
- `expenseApi` is in `ui/src/lib/api/expenses.ts`, re-exported via `ui/src/lib/api/index.ts` (`export * from './expenses'`). `uploadReceipt(expenseId, file)` does a manual multipart `fetch` (mirror it for `scanReceipt`). `createExpense(payload)` posts to `/expenses/`; ExpensesNew passes the payload `as any` with `imported_from_attachment` + `analysis_status`.
- `API_BASE_URL`, `getTenantId` come from `./_base`.
- Test mock style mirrors `ui/src/components/invoices/SendInvoiceDialog.test.tsx`: mock `react-i18next`, mock `@/lib/api`, mock `sonner`.
- Dialog primitives: `@/components/ui/dialog` (`Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter`). Button: `@/components/ui/professional-button` (`ProfessionalButton`). Icons: `lucide-react`.

---

## File Structure
- `ui/src/lib/api/expenses.ts` (modify) — `scanReceipt` method + `ExpenseScanFields`/`ScanResult` types.
- `ui/src/components/expenses/ScanBillDialog.tsx` (new) — the modal (trigger + flow).
- `ui/src/components/expenses/ScanBillDialog.test.tsx` (new) — component tests.
- `ui/src/pages/Expenses/index.tsx` (modify) — mount `<ScanBillDialog>` beside "New Expense".
- `ui/src/i18n/locales/en.json` (modify) — `expenses.scan_*` keys.

---

## Task 1: `scanReceipt` API method + types

**Files:** Modify `ui/src/lib/api/expenses.ts`

- [ ] **Step 1: Add the types** (near the top of the file, after the existing `import` line)

```ts
export interface ExpenseScanFields {
  vendor?: string;
  amount?: number;
  currency?: string;
  expense_date?: string;
  category?: string;
  tax_amount?: number;
  total_amount?: number;
  payment_method?: string;
  reference_number?: string;
  notes?: string;
}

export interface ScanResult {
  available: boolean;
  fields?: ExpenseScanFields;
  reason?: string;
}
```

- [ ] **Step 2: Add the `scanReceipt` method** inside the `expenseApi` object, immediately AFTER the `uploadReceipt: async (...) => { ... },` method

```ts
  scanReceipt: async (file: File): Promise<ScanResult> => {
    const tenantId = getTenantId();
    const formData = new FormData();
    formData.append('file', file);
    const headers: Record<string, string> = {};
    if (tenantId) headers['X-Tenant-ID'] = tenantId;
    const response = await fetch(`${API_BASE_URL}/expenses/scan-receipt`, {
      method: 'POST', headers, body: formData, credentials: 'include',
    });
    if (!response.ok) {
      const errorText = await response.text();
      try { throw new Error(JSON.parse(errorText).detail || 'Failed to scan receipt'); }
      catch { throw new Error(errorText || 'Failed to scan receipt'); }
    }
    return response.json();
  },
```

- [ ] **Step 3: Type-check (only this file's errors matter)**

Run: `docker compose exec -T ui npx tsc -p tsconfig.app.json --noEmit 2>&1 | grep "lib/api/expenses.ts" || echo "no errors in expenses.ts"`
Expected: `no errors in expenses.ts`

- [ ] **Step 4: Commit**

```bash
git add ui/src/lib/api/expenses.ts
git commit -m "feat(expenses): scanReceipt API client method + types"
```

---

## Task 2: `ScanBillDialog` component (TDD)

**Files:** Create `ui/src/components/expenses/ScanBillDialog.tsx` + `ui/src/components/expenses/ScanBillDialog.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `ui/src/components/expenses/ScanBillDialog.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, opts?: Record<string, any>) => (opts?.defaultValue as string) ?? key,
  }),
}));

const api = vi.hoisted(() => ({
  scanReceipt: vi.fn(),
  createExpense: vi.fn(),
  uploadReceipt: vi.fn(),
}));
vi.mock('@/lib/api', () => ({ expenseApi: api }));
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

import { toast } from 'sonner';
import { ScanBillDialog } from './ScanBillDialog';

function pickFile() {
  const input = screen.getByLabelText(/receipt file/i) as HTMLInputElement;
  const file = new File(['x'], 'receipt.png', { type: 'image/png' });
  fireEvent.change(input, { target: { files: [file] } });
  return file;
}

describe('ScanBillDialog', () => {
  beforeEach(() => {
    api.scanReceipt.mockReset();
    api.createExpense.mockReset();
    api.uploadReceipt.mockReset();
    (toast.success as any).mockClear();
    (toast.error as any).mockClear();
    api.createExpense.mockResolvedValue({ id: 42 });
    api.uploadReceipt.mockResolvedValue({});
  });

  function open() {
    render(<ScanBillDialog onCreated={vi.fn()} />);
    fireEvent.click(screen.getByRole('button', { name: /scan a bill/i }));
  }

  it('pre-fills the form from extracted fields', async () => {
    api.scanReceipt.mockResolvedValue({ available: true, fields: { vendor: 'Acme', amount: 12.5 } });
    open();
    pickFile();
    await waitFor(() => expect(api.scanReceipt).toHaveBeenCalled());
    const vendor = await screen.findByLabelText(/vendor/i) as HTMLInputElement;
    expect(vendor.value).toBe('Acme');
    const amount = screen.getByLabelText(/amount/i) as HTMLInputElement;
    expect(amount.value).toBe('12.5');
  });

  it('shows the fallback notice when extraction is unavailable', async () => {
    api.scanReceipt.mockResolvedValue({ available: false, reason: 'no AI' });
    open();
    pickFile();
    expect(await screen.findByText(/couldn't read it automatically/i)).toBeInTheDocument();
    const amount = screen.getByLabelText(/amount/i) as HTMLInputElement;
    expect(amount.value).toBe('');
  });

  it('Save creates the expense then attaches the file', async () => {
    api.scanReceipt.mockResolvedValue({ available: true, fields: { vendor: 'Acme', amount: 12.5 } });
    open();
    const file = pickFile();
    await screen.findByLabelText(/vendor/i);
    fireEvent.click(screen.getByRole('button', { name: /^save expense$/i }));
    await waitFor(() => expect(api.createExpense).toHaveBeenCalled());
    const payload = api.createExpense.mock.calls[0][0];
    expect(payload.vendor).toBe('Acme');
    expect(payload.amount).toBe(12.5);
    await waitFor(() => expect(api.uploadReceipt).toHaveBeenCalledWith(42, file));
    await waitFor(() => expect(toast.success).toHaveBeenCalled());
  });

  it('Cancel persists nothing', async () => {
    api.scanReceipt.mockResolvedValue({ available: true, fields: { vendor: 'Acme', amount: 1 } });
    open();
    pickFile();
    await screen.findByLabelText(/vendor/i);
    fireEvent.click(screen.getByRole('button', { name: /^cancel$/i }));
    expect(api.createExpense).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `docker compose exec -T ui npx vitest run src/components/expenses/ScanBillDialog.test.tsx`
Expected: FAIL — cannot resolve `./ScanBillDialog`.

- [ ] **Step 3: Write the component**

Create `ui/src/components/expenses/ScanBillDialog.tsx`:

```tsx
import { useState } from 'react';
import { ScanLine } from 'lucide-react';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
import { expenseApi, type ExpenseScanFields } from '@/lib/api';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import { ProfessionalButton } from '@/components/ui/professional-button';

interface ScanBillDialogProps {
  onCreated?: () => void;
}

type Phase = 'select' | 'reading' | 'review';

const FIELD_DEFS: { key: keyof ExpenseScanFields; label: string }[] = [
  { key: 'vendor', label: 'Vendor' },
  { key: 'amount', label: 'Amount' },
  { key: 'currency', label: 'Currency' },
  { key: 'expense_date', label: 'Date' },
  { key: 'category', label: 'Category' },
  { key: 'tax_amount', label: 'Tax' },
];

export function ScanBillDialog({ onCreated }: ScanBillDialogProps) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [phase, setPhase] = useState<Phase>('select');
  const [file, setFile] = useState<File | null>(null);
  const [available, setAvailable] = useState(true);
  const [fields, setFields] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);

  const reset = () => {
    setPhase('select');
    setFile(null);
    setAvailable(true);
    setFields({});
    setBusy(false);
  };

  const close = () => {
    setOpen(false);
    reset();
  };

  const onFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (!f) return;
    setFile(f);
    setPhase('reading');
    try {
      const res = await expenseApi.scanReceipt(f);
      if (res.available && res.fields) {
        setAvailable(true);
        const next: Record<string, string> = {};
        for (const { key } of FIELD_DEFS) {
          const v = res.fields[key];
          if (v !== undefined && v !== null) next[key] = String(v);
        }
        setFields(next);
      } else {
        setAvailable(false);
        setFields({});
      }
    } catch (err: any) {
      setAvailable(false);
      setFields({});
      toast.error(err?.message || t('expenses.scan_failed', { defaultValue: 'Could not scan the receipt.' }));
    } finally {
      setPhase('review');
    }
  };

  const setField = (key: string, value: string) =>
    setFields((prev) => ({ ...prev, [key]: value }));

  const save = async () => {
    if (!file) return;
    setBusy(true);
    try {
      const today = new Date().toISOString().slice(0, 10);
      const payload = {
        amount: Number(fields.amount) || 0,
        currency: fields.currency || 'USD',
        expense_date: fields.expense_date || today,
        category: fields.category || 'General',
        vendor: fields.vendor || '',
        tax_amount: fields.tax_amount ? Number(fields.tax_amount) : undefined,
        status: 'recorded',
        imported_from_attachment: true,
        analysis_status: 'queued',
      };
      const created = await expenseApi.createExpense(payload as any);
      await expenseApi.uploadReceipt(created.id, file);
      toast.success(t('expenses.scan_saved', { defaultValue: 'Expense created from the scanned bill.' }));
      onCreated?.();
      close();
    } catch (err: any) {
      toast.error(err?.message || t('expenses.scan_save_failed', { defaultValue: 'Could not create the expense.' }));
      setBusy(false);
    }
  };

  return (
    <>
      <ProfessionalButton
        variant="default"
        size="default"
        className="shadow-lg"
        onClick={() => setOpen(true)}
      >
        <ScanLine className="w-4 h-4 mr-2" /> {t('expenses.scan_bill', { defaultValue: 'Scan a bill' })}
      </ProfessionalButton>

      <Dialog open={open} onOpenChange={(o) => (o ? setOpen(true) : close())}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('expenses.scan_bill', { defaultValue: 'Scan a bill' })}</DialogTitle>
          </DialogHeader>

          {phase === 'select' && (
            <div className="space-y-2">
              <label htmlFor="scan-file" className="text-sm text-muted-foreground">
                {t('expenses.scan_pick', { defaultValue: 'Choose a receipt to read automatically.' })}
              </label>
              <input
                id="scan-file"
                aria-label="Receipt file"
                type="file"
                accept=".pdf,.jpg,.jpeg,.png,.heic"
                onChange={onFile}
              />
            </div>
          )}

          {phase === 'reading' && (
            <p className="text-sm text-muted-foreground">
              {t('expenses.scan_reading', { defaultValue: 'Reading your bill…' })}
            </p>
          )}

          {phase === 'review' && (
            <div className="space-y-3">
              {!available && (
                <p className="text-sm text-amber-600">
                  {t('expenses.scan_unavailable', {
                    defaultValue: "Couldn't read it automatically — enter the details.",
                  })}
                </p>
              )}
              <div className="grid grid-cols-2 gap-3">
                {FIELD_DEFS.map(({ key, label }) => (
                  <div key={key} className="space-y-1">
                    <label htmlFor={`scan-${key}`} className="text-xs text-muted-foreground">{label}</label>
                    <input
                      id={`scan-${key}`}
                      aria-label={label}
                      className="w-full rounded-md border border-input bg-background px-2 py-1 text-sm"
                      value={fields[key] ?? ''}
                      onChange={(e) => setField(key, e.target.value)}
                    />
                  </div>
                ))}
              </div>
            </div>
          )}

          <DialogFooter>
            <ProfessionalButton variant="outline" size="default" onClick={close} disabled={busy}>
              {t('common.cancel', { defaultValue: 'Cancel' })}
            </ProfessionalButton>
            {phase === 'review' && (
              <ProfessionalButton variant="default" size="default" onClick={save} disabled={busy}>
                {t('expenses.scan_save', { defaultValue: 'Save expense' })}
              </ProfessionalButton>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `docker compose exec -T ui npx vitest run src/components/expenses/ScanBillDialog.test.tsx`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add ui/src/components/expenses/ScanBillDialog.tsx ui/src/components/expenses/ScanBillDialog.test.tsx
git commit -m "feat(expenses): ScanBillDialog — scan, preview, confirm-create"
```

---

## Task 3: Mount the button + i18n

**Files:** Modify `ui/src/pages/Expenses/index.tsx`, `ui/src/i18n/locales/en.json`

- [ ] **Step 1: Import the dialog** — add near the other component imports at the top of `ui/src/pages/Expenses/index.tsx`

```ts
import { ScanBillDialog } from '@/components/expenses/ScanBillDialog';
```

- [ ] **Step 2: Mount it beside "New Expense"**

Find this block (around line 710):
```tsx
                <div className="flex gap-1">
                  <Link to="/expenses/new">
                    <ProfessionalButton variant="default" size="default" className="shadow-lg">
                      <Plus className="w-4 h-4 mr-2" /> {t('expenses.new')}
                    </ProfessionalButton>
                  </Link>
```
Insert `<ScanBillDialog>` immediately AFTER the opening `<div className="flex gap-1">` line, so it reads:
```tsx
                <div className="flex gap-1">
                  <ScanBillDialog onCreated={fetchExpenses} />
                  <Link to="/expenses/new">
                    <ProfessionalButton variant="default" size="default" className="shadow-lg">
                      <Plus className="w-4 h-4 mr-2" /> {t('expenses.new')}
                    </ProfessionalButton>
                  </Link>
```

NOTE: confirm the list-refetch function is named `fetchExpenses` in this file (Step 3 verifies). If it is named differently, use that name.

- [ ] **Step 3: Verify the refetch function name**

Run: `grep -nE "const fetchExpenses|fetchExpenses *=|refetch" ui/src/pages/Expenses/index.tsx | head`
Expected: a `fetchExpenses` definition exists (it is called by the existing refresh button `onClick={fetchExpenses}`). If the grep shows the refresh button uses a different name, change the `onCreated={...}` prop to match.

- [ ] **Step 4: Add i18n keys** — in `ui/src/i18n/locales/en.json`, inside the existing `"expenses"` object, add (mind comma placement — append after an existing key, keep JSON valid):

```json
    "scan_bill": "Scan a bill",
    "scan_pick": "Choose a receipt to read automatically.",
    "scan_reading": "Reading your bill…",
    "scan_unavailable": "Couldn't read it automatically — enter the details.",
    "scan_save": "Save expense",
    "scan_saved": "Expense created from the scanned bill.",
    "scan_save_failed": "Could not create the expense.",
    "scan_failed": "Could not scan the receipt."
```

- [ ] **Step 5: Validate JSON + type-check the page**

Run: `docker compose exec -T ui node -e "JSON.parse(require('fs').readFileSync('src/i18n/locales/en.json','utf8')); console.log('valid')"`
Expected: `valid`

Run: `docker compose exec -T ui npx tsc -p tsconfig.app.json --noEmit 2>&1 | grep -E "Expenses/index.tsx|ScanBillDialog" || echo "no new errors"`
Expected: `no new errors` (a pre-existing unrelated error line in Expenses/index.tsx, if any, is not from this change — only flag errors mentioning `ScanBillDialog` or the lines you touched).

- [ ] **Step 6: Commit**

```bash
git add ui/src/pages/Expenses/index.tsx ui/src/i18n/locales/en.json
git commit -m "feat(expenses): mount Scan-a-bill button on the Expenses page + i18n"
```

---

## Task 4: Full verification

**Files:** none (verification only).

- [ ] **Step 1: Run the component test**

Run: `docker compose exec -T ui npx vitest run src/components/expenses/ScanBillDialog.test.tsx`
Expected: 4 passed.

- [ ] **Step 2: tsc clean on the new files**

Run: `docker compose exec -T ui npx tsc -p tsconfig.app.json --noEmit 2>&1 | grep -E "ScanBillDialog|lib/api/expenses.ts" || echo "no errors in new files"`
Expected: `no errors in new files`

- [ ] **Step 3: No commit** — verification only. Fix in the relevant task's file and re-run if anything fails.

---

## Self-Review (completed by plan author)

**Spec coverage (slice 2):**
- `scanReceipt(file)` client + types → Task 1.
- "Scan a bill" modal: file drop → "Reading…" → prefilled editable form → Save (createExpense + uploadReceipt) / Cancel → Task 2.
- `available:false` → inline notice + empty form, never blocks → Task 2 (test 2).
- Button on Expenses page → Task 3. i18n under `expenses.scan_*` → Task 3.
- Reuses create + upload, no new status, no reports touched → Task 2 (save()).

**Placeholder scan:** none — full code in every step.

**Type consistency:** `ScanResult`/`ExpenseScanFields` (Task 1) are consumed in Task 2 (`expenseApi.scanReceipt` returns `ScanResult`, `res.fields[key]` typed by `ExpenseScanFields`). `createExpense(payload as any)` mirrors the established ExpensesNew pattern (avoids Omit<Expense> field-completeness errors). `onCreated` prop name consistent across Task 2 + Task 3 mount. The `fetchExpenses` refetch name is verified in Task 3 Step 3 rather than assumed.
