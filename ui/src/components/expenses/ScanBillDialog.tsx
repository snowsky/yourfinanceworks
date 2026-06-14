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
