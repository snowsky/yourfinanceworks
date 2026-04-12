export type ExpenseDraft = {
  amount: number | null;
  currency: string;
  expense_date: string;
  category: string;
  vendor?: string | null;
  notes?: string | null;
  confidence?: number;
  parser_used?: string;
};

export type ExpenseListItem = {
  id: number;
  amount: number;
  currency: string;
  expense_date: string;
  category: string;
  vendor?: string | null;
  analysis_status?: string | null;
  review_status?: string | null;
  attachments_count?: number | null;
};
