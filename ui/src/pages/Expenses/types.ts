import { parseISO, isValid } from 'date-fns';
import type { ColumnDef } from '@/hooks/useColumnVisibility';

export interface PreviewState {
  open: boolean;
  url: string | null;
  contentType: string | null;
  filename: string | null;
}

export interface AttachmentPreviewState {
  expenseId: number | null;
}

export const EXPENSE_COLUMNS: ColumnDef[] = [
  { key: 'select', label: 'Select', essential: true },
  { key: 'id', label: 'ID' },
  { key: 'date', label: 'Date', essential: true },
  { key: 'category', label: 'Category', essential: true },
  { key: 'vendor', label: 'Vendor' },
  { key: 'labels', label: 'Labels' },
  { key: 'amount', label: 'Amount', essential: true },
  { key: 'total', label: 'Total' },
  { key: 'invoice', label: 'Invoice' },
  { key: 'statement', label: 'Statement' },
  { key: 'approval_status', label: 'Approval Status' },
  { key: 'created_at_by', label: 'Created at / by' },
  { key: 'analyzed', label: 'Analyzed' },
  { key: 'review', label: 'Review' },
  { key: 'receipt', label: 'Receipt' },
  { key: 'actions', label: 'Actions', essential: true },
];

// Helper function to format date without timezone issues
export const formatDateToISO = (date: Date): string => {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
};

// Helper function to safely parse date strings without timezone issues
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
