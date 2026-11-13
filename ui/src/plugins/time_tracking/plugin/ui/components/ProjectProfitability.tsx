import { useTranslation } from 'react-i18next';
import { useProjectProfitability, useCostSetup } from '../profitability-hooks';
import type { Breakdown, CostRecord, Decimal } from '../profitability-api';
import { ProjectCostSetup } from './ProjectCostSetup';

/** Format decimal text without binary floating-point conversion or client aggregation. */
function formatDecimal(value: Decimal | null | undefined, language = 'en', money = false, currency = 'USD'): string {
  if (value == null) return '—';
  const match = /^(-?)(\d+)(?:\.(\d+))?$/.exec(value);
  if (!match) return '—';
  const parts = new Intl.NumberFormat(language).formatToParts(1000.1);
  const group = parts.find(p => p.type === 'group')?.value || ',';
  const decimal = parts.find(p => p.type === 'decimal')?.value || '.';
  const precision = new Intl.NumberFormat(language, { style: 'currency', currency }).resolvedOptions().minimumFractionDigits ?? 2;
  const fraction = money ? (match[3] || '').padEnd(precision, '0') : (match[3] || '').replace(/0+$/, '');
  return match[1] + match[2].replace(/\B(?=(\d{3})+(?!\d))/g, group) + (fraction ? decimal + fraction : '');
}
export function ProjectProfitability({ projectId }: { projectId: number }) {
  const { t, i18n } = useTranslation('time_tracking', { keyPrefix: 'profitability' });
  const result = useProjectProfitability(projectId);
  const labels = useCostSetup(projectId, result.data?.currency || '', 0).details.data;
  if (!result.access.allowed) return null;
  if (result.error) return <p role="alert">{t('load_error')}</p>;
  const data = result.data;
  if (!data) return <p role="status">{t('loading')}</p>;
  if (data.status === 'unsupported_billing_method') return <p>{t(data.status)}</p>;
  const number = (value: Decimal | null) => formatDecimal(value, i18n.language);
  const money = (value: Decimal | null) => `${formatDecimal(value, i18n.language, true, data.currency)} ${data.currency}`;
  const recordLink = (type: string, id: number) => type === 'expense' ? `/expenses/view/${id}` : `/projects/${projectId}?time_entry_id=${id}#time-entry-${id}`;
  const records = (items: CostRecord[], title: string) => items.length > 0 && (
    <section>
      <h3 className="font-semibold">{t(title)}</h3>
      <ul>
        {items.map(item => (
          <li key={`${item.record_type}:${item.record_id}:${item.reason}`}>
            <a className="underline" href={recordLink(item.record_type, item.record_id)}>
              {t(item.record_type)} #{item.record_id}
            </a>: {t(`reasons.${item.reason}`, { defaultValue: t('unresolved_reason') })}
          </li>
        ))}
      </ul>
    </section>
  );
  const breakdownName = (item: Breakdown, title: string) => {
    if (item.id == null) return t('unassigned');
    if (title !== 'contributors') {
      return labels?.tasks.find(task => task.id === item.id)?.name || `${t('task')} #${item.id}`;
    }
    const user = labels?.users.find(user => user.id === item.id);
    return user ? [user.first_name, user.last_name].filter(Boolean).join(' ') || user.email : `${t('contributor')} #${item.id}`;
  };
  const breakdown = (items: Breakdown[], title: string) => (
    <details>
      <summary>{t(title)}</summary>
      {items.map(item => (
        <div className="border-b py-2" key={item.id ?? 'none'}>
          <p>{breakdownName(item, title)} · {number(item.completed_hours)} {t('hours')} · {money(item.hourly_cost)}</p>
          <p>
            {item.entry_ids.map(id => (
              <a key={id} className="mr-3 underline" href={recordLink('time_entry', id)}>{t('time_entry')} #{id}</a>
            ))}
          </p>
          {item.supplier_expense_ids.map(id => (
            <a key={id} className="mr-3 underline" href="#project-expenses">{t('expense_bucket')} #{id}</a>
          ))}
        </div>
      ))}
    </details>
  );
  return <div className="space-y-6">
    <p>{t('basis')}</p>
    {data.status === 'incomplete' && <p role="status">{t('incomplete')} · {t('missing_hours')}: {number(data.missing_hours)}</p>}
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">{[['work_value', money(data.work_value)], ['known_cost', money(data.known_cost)], ['contribution', money(data.status === 'complete' ? data.contribution : null)], ['margin', data.status === 'complete' && data.margin_percent != null ? `${number(data.margin_percent)}%` : t('unavailable')]].map(([title, value]) => <div className="rounded-lg border p-4" key={title}><h3>{t(title)}</h3><p className="text-2xl font-semibold">{value}</p></div>)}</div>
    <p>{t('billable_hours')}: {number(data.billable_hours)} · {t('nonbillable_hours')}: {number(data.nonbillable_hours)} · {t('completed_hours')}: {number(data.completed_hours)}</p>
    <p>{t('hours_budget')}: {data.hours_budget_percent == null ? t('unavailable') : `${number(data.hours_budget_percent)}%`} · {t('value_budget')}: {data.amount_budget_percent == null ? t('unavailable') : `${number(data.amount_budget_percent)}%`}</p>
    {data.budget_warnings.map(warning => <p role="status" key={warning}>{t(`reasons.${warning}`, { defaultValue: t('budget_warning') })}</p>)}
    {records(data.unresolved_records, 'unresolved')}{records(data.excluded_records, 'excluded')}
    {breakdown(data.contributors, 'contributors')}{breakdown(data.tasks, 'tasks')}
    <section id="project-expenses"><h3 className="font-semibold">{t('expense_bucket')}</h3><p>{money(data.expense_bucket.amount)} · {t('expense_basis')}</p>{data.expense_bucket.expense_ids.map(id => <a className="mr-3 underline" key={id} href={recordLink('expense', id)}>{t('expense')} #{id}</a>)}</section>
    <section>
      <h3 className="font-semibold">{t('billing')}</h3>
      <p>{t('billing_explanation')}</p>
      {data.billing ? (
        <>
          <p>{t('unbilled')}: {money(data.billing.unbilled_work_value)}</p>
          <p>{t('invoiced')}: {money(data.billing.invoiced_pre_tax)} · {t(data.billing.invoicing_complete ? 'complete' : 'incomplete')}</p>
          <p>{t('expense_reimbursements')}: {money(data.billing.expense_reimbursements_pre_tax)} · {t(data.billing.invoicing_complete ? 'complete' : 'incomplete')}</p>
          <p>{t('reimbursement_basis')}</p>
          <p>{t('cash')}: {money(data.billing.collected_cash)} · {t(data.billing.cash_complete ? 'complete' : 'incomplete')}</p>
          {data.billing.collections_include_tax && <p>{t('cash_tax')}</p>}
          {data.billing.attributed_invoice_ids.map(id => (
            <a key={id} className="mr-3 underline" href={`/invoices/view/${id}`}>{t('invoice')} #{id}</a>
          ))}
          {data.billing.unresolved_invoices.map(invoice => (
            <p key={invoice.invoice_id}>
              <a className="underline" href={`/invoices/view/${invoice.invoice_id}`}>{t('invoice')} #{invoice.invoice_id}</a>
              {': '}{invoice.reasons.map(reason => t(`reasons.${reason}`, { defaultValue: t('unresolved_reason') })).join(', ')}
            </p>
          ))}
        </>
      ) : <p>{t('unavailable')}</p>}
    </section>
    <ProjectCostSetup key={`${result.access.scope}:${projectId}`} projectId={projectId} currency={data.currency} eligibleExpenseIds={data.expense_bucket.expense_ids} />
  </div>;
}
