import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useCostSetup } from '../profitability-hooks';
import type { BackfillPreview, CostRateWrite } from '../profitability-api';

export function ProjectCostSetup({ projectId, currency, eligibleExpenseIds = [] }: { projectId: number; currency: string; eligibleExpenseIds?: number[] }) {
  const { t } = useTranslation('time_tracking', { keyPrefix: 'profitability' });
  const [contributor, setContributor] = useState(0);
  const [rate, setRate] = useState('');
  const [date, setDate] = useState('');
  const [kind, setKind] = useState<CostRateWrite['contributor_kind']>('employee');
  const [rateCurrency, setRateCurrency] = useState(currency);
  const [selected, setSelected] = useState<number[]>([]);
  const [expenses, setExpenses] = useState<number[]>([]);
  const [preview, setPreview] = useState<BackfillPreview | null>(null);
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const setup = useCostSetup(projectId, rateCurrency, contributor);
  if (!setup.access.allowed) return null;
  const { users = [], entries = [], expenses: allExpenses = [] } = setup.details.data || {};
  const name = (id: number) => { const user = users.find(u => u.id === id); return user ? [user.first_name, user.last_name].filter(Boolean).join(' ') || user.email : `${t('contributor')} #${id}`; };
  const label = (id: number) => { const entry = entries.find(e => e.id === id); return entry ? `${entry.description || t('time_entry')} — ${name(entry.user_id)} · ${entry.started_at.slice(0, 10)} · #${id}` : `#${id}`; };
  const toggle = (values: number[], id: number) => values.includes(id) ? values.filter(v => v !== id) : [...values, id];
  const run = async (action: () => Promise<unknown>) => { setBusy(true); setMessage(''); try { await action(); } catch { setPreview(null); setMessage(t('refresh_preview')); } finally { setBusy(false); } };
  return <section className="rounded-lg border p-4"><fieldset disabled={busy} className="space-y-5">
    <h3 className="font-semibold">{t('setup')}</h3><p>{t('rate_explanation')}</p>
    {setup.details.isError && <p role="alert">{t('load_error')}</p>}
    {message && <p role="alert">{message}</p>}
    <form className="grid gap-3 sm:grid-cols-2" onSubmit={e => { e.preventDefault(); setPreview(null); void run(() => setup.saveRate.mutateAsync({ user_id: contributor, hourly_cost: rate, currency: rateCurrency, effective_from: date, contributor_kind: kind })); }}>
      <label>{t('contributor')}<select className="block w-full rounded border p-2" required value={contributor || ''} onChange={e => { setContributor(Number(e.target.value)); setPreview(null); }}><option value="">{t('select_contributor')}</option>{users.map(user => <option key={user.id} value={user.id}>{name(user.id)} · {user.email}</option>)}</select></label>
      <label>{t('kind')}<select className="block w-full rounded border p-2" value={kind} onChange={e => setKind(e.target.value as CostRateWrite['contributor_kind'])}>{(['owner', 'employee', 'subcontractor'] as const).map(value => <option key={value} value={value}>{t(value)}</option>)}</select></label>
      <label>{t('hourly_rate')}<Input required type="number" min="0" step="0.000001" value={rate} onChange={e => { setRate(e.target.value); setPreview(null); }} /></label>
      <label>{t('effective_date')}<Input required type="date" value={date} onChange={e => { setDate(e.target.value); setPreview(null); }} /></label>
      <label>{t('currency')}<Input required pattern="[A-Z]{3}" maxLength={3} value={rateCurrency} onChange={e => { setRateCurrency(e.target.value.toUpperCase()); setPreview(null); }} /></label>
      <Button disabled={busy || !contributor} type="submit">{t('save_rate')}</Button>
    </form>
    <ul>{setup.rates.data?.map(item => <li key={item.id}>{name(item.user_id)} · {item.effective_from} · {item.hourly_cost} {item.currency} · {t(item.contributor_kind)}</li>)}</ul>
    <h4 className="font-semibold">{t('history')}</h4><p>{t('history_explanation')}</p>
    <div className="max-h-64 overflow-y-auto space-y-2">{entries.filter(entry => ['logged', 'approved', 'invoiced'].includes(entry.status)).map(entry => <label key={entry.id} className="flex gap-2"><input type="checkbox" checked={selected.includes(entry.id)} onChange={() => { setSelected(toggle(selected, entry.id)); setPreview(null); }} />{label(entry.id)}</label>)}</div>
    <div className="flex gap-3"><Button disabled={busy || !selected.length} onClick={() => { setPreview(null); void run(async () => { const result = await setup.preview.mutateAsync(selected); setPreview(result); }); }}>{t('preview')}</Button>
      <Button disabled={busy || !preview} onClick={() => void run(async () => { if (preview) await setup.apply.mutateAsync(preview); setPreview(null); })}>{t('apply')}</Button></div>
    {preview && <div className="space-y-2"><p>{t('before')}: {preview.before_total} {currency} · {t('after')}: {preview.after_total} {currency}</p>{preview.entries.map(entry => <p key={entry.entry_id}>{label(entry.entry_id)} · {entry.work_date} · {t('hourly_rate')}: {entry.hourly_cost ?? t('unavailable')} {entry.currency} · {t('before')}: {entry.before_cost ?? t('unavailable')} · {t('after')}: {entry.after_cost ?? t('unavailable')} {entry.currency}</p>)}</div>}
    <h4 className="font-semibold">{t('supplier_replacement')}</h4><p>{t('supplier_explanation')}</p>
    <p>{t('affected_entries')}: {selected.map(label).join('; ') || t('none_selected')}</p>
    {allExpenses.filter(expense => eligibleExpenseIds.includes(expense.id)).map(expense => <label key={expense.id} className="flex gap-2"><input type="checkbox" checked={expenses.includes(expense.id)} onChange={() => { setExpenses(toggle(expenses, expense.id)); setPreview(null); }} />{expense.vendor || expense.category} · {expense.expense_date} · {expense.amount} {expense.currency} · #{expense.id}</label>)}
    <Button disabled={busy || !selected.length || !expenses.length} onClick={() => { setPreview(null); void run(async () => { for (const entry of selected) await setup.replace.mutateAsync({ entry, data: { method: 'supplier_expense', expense_ids: expenses } }); }); }}>{t('replace')}</Button>
    <Button className="ml-2" variant="outline" disabled={busy || !selected.length} onClick={() => { setPreview(null); void run(async () => { for (const entry of selected) await setup.replace.mutateAsync({ entry, data: { method: 'hourly', expense_ids: [] } }); }); }}>{t('restore_hourly')}</Button>
  </fieldset></section>;
}
