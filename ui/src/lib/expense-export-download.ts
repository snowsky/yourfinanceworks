import { expenseApi } from './api/expenses';
import { toast } from 'sonner';

/** Fetch + trigger browser download for a per-expense PDF or CSV export. */
export async function downloadExpenseExport(
  expenseId: number,
  format: 'pdf' | 'csv'
): Promise<void> {
  try {
    const fetcher = format === 'pdf' ? expenseApi.exportExpensePdf : expenseApi.exportExpenseCsv;
    const { blob, filename } = await fetcher(expenseId);
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
    toast.success(`Exported ${filename}`);
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Failed to export expense';
    toast.error(message);
  }
}
