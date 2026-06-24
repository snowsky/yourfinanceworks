import type { Anomaly } from '@/lib/api';

/** Tailwind classes for an outline Badge, keyed by risk level. */
export const RISK_BADGE: Record<string, string> = {
  critical: 'bg-red-500/15 text-red-600 dark:text-red-400 border-red-500/30',
  high: 'bg-red-500/10 text-red-600 dark:text-red-400 border-red-500/25',
  medium: 'bg-amber-500/15 text-amber-600 dark:text-amber-400 border-amber-500/30',
  low: 'bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/25',
};

/** Deep-link to the record an anomaly was raised against, or null if none. */
export function entityHref(a: Anomaly): string | null {
  switch (a.entity_type) {
    case 'invoice':
      return `/invoices/view/${a.entity_id}`;
    case 'expense':
      return `/expenses/view/${a.entity_id}`;
    // The audit pipeline stores bank items as "bank_statement_transaction";
    // "bank_transaction" is an older alias. When the parent statement is known
    // we deep-link to it and highlight the transaction; otherwise fall back to
    // the statements list.
    case 'bank_transaction':
    case 'bank_statement_transaction':
      return a.statement_id
        ? `/statements?id=${a.statement_id}&txn=${a.entity_id}`
        : '/statements';
    default:
      return null;
  }
}

/** Human label for an entity reference, e.g. "Bank statement transaction #42". */
export function entityLabel(a: Anomaly): string {
  const type = a.entity_type.replace(/_/g, ' ');
  return `${type.charAt(0).toUpperCase()}${type.slice(1)} #${a.entity_id}`;
}

/** Tailwind classes for an outline Badge, keyed by resolution status. */
export const STATUS_BADGE: Record<string, string> = {
  open: 'bg-amber-500/15 text-amber-600 dark:text-amber-400 border-amber-500/30',
  confirmed: 'bg-red-500/15 text-red-600 dark:text-red-400 border-red-500/30',
  dismissed: 'bg-muted text-muted-foreground border-border',
};

/** Flatten an anomaly `details` blob into label/value rows for generic display. */
export function renderDetailEntries(details: unknown): Array<{ label: string; value: string }> {
  if (!details || typeof details !== 'object') return [];
  return Object.entries(details as Record<string, unknown>).map(([k, v]) => ({
    label: k.replace(/_/g, ' '),
    value:
      v != null && typeof v === 'object' ? JSON.stringify(v, null, 2) : String(v),
  }));
}
