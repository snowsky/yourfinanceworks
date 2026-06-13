import type { InvoiceSettings } from '@/lib/api/settings';

const UNAPPROVED = new Set(['draft', 'pending_approval', 'rejected']);

/**
 * UX mirror of the backend send-guard (invoice_approval_policy.py). The backend
 * is the real enforcement; this drives client-side messaging / pre-checks.
 */
export function isSendBlockedByApproval(
  invoice: { status: string; amount: number },
  settings?: Pick<InvoiceSettings, 'require_approval_before_send' | 'approval_threshold_amount'>,
): boolean {
  if (!settings?.require_approval_before_send) return false;
  const threshold = settings.approval_threshold_amount ?? 0;
  const applies = threshold <= 0 || (invoice.amount ?? 0) >= threshold;
  return applies && UNAPPROVED.has(invoice.status);
}
