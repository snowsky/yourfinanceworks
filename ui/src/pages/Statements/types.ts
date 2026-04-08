import { parseISO, isValid } from 'date-fns';
import { BankTransactionEntry } from '@/lib/api';
import { TransactionLinkInfo } from '@/lib/api/bank-statements';
import type { ColumnDef } from '@/hooks/useColumnVisibility';

export type BankRow = BankTransactionEntry & {
  id?: number;
  invoice_id?: number | null;
  expense_id?: number | null;
  backend_id?: number | null;
  linked_transfer?: TransactionLinkInfo | null;
};

export const STATEMENT_COLUMNS: ColumnDef[] = [
  { key: 'select', label: 'Select', essential: true },
  { key: 'id', label: 'ID' },
  { key: 'filename', label: 'Filename', essential: true },
  { key: 'labels', label: 'Labels' },
  { key: 'type', label: 'Type' },
  { key: 'status', label: 'Status', essential: true },
  { key: 'review_status', label: 'Review Status' },
  { key: 'transactions', label: 'Transactions' },
  { key: 'created_at_by', label: 'Created at/by' },
  { key: 'actions', label: 'Actions', essential: true },
];

export const CATEGORY_OPTIONS = [
  'Income', 'Food', 'Transportation', 'Shopping', 'Bills', 'Healthcare', 'Entertainment', 'Financial', 'Travel', 'Other'
];

export const STATEMENT_PROVIDERS = [
  { value: 'bank', label: 'Bank', icon: '🏦' },
  { value: 'paypal', label: 'PayPal', icon: '💰' },
  { value: 'wise', label: 'Wise', icon: '🌍' },
  { value: 'stripe', label: 'Stripe', icon: '💳' },
  { value: 'square', label: 'Square', icon: '🔲' },
  { value: 'other', label: 'Other', icon: '📄' }
];

export const STATEMENT_STATUSES = ['uploaded', 'processing', 'processed', 'failed', 'merged'] as const;

export const formatDateToISO = (date: Date): string => {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
};

export const safeParseDateString = (dateString?: string): Date => {
  if (!dateString) return new Date();
  try {
    const parsedDate = parseISO(dateString);
    return isValid(parsedDate) ? parsedDate : new Date();
  } catch (error) {
    console.warn('Failed to parse date:', dateString, error);
    return new Date();
  }
};
