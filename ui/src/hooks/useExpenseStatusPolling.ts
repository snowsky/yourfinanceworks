import { useEffect, useRef } from 'react';
import { expenseApi } from '@/lib/api';

export function useExpenseStatusPolling() {
  const pollingRef = useRef<any>(null);
  const trackedExpenses = useRef<Set<number>>(new Set());

  const startPolling = (expenseId: number) => {
    trackedExpenses.current.add(expenseId);

    if (!pollingRef.current) {
      pollingRef.current = setInterval(async () => {
        const addNotification = (window as any).addAINotification;
        if (!addNotification) return;

        for (const id of Array.from(trackedExpenses.current)) {
          try {
            const expense = await expenseApi.getExpense(id);
            console.log(`Expense ${id} status:`, expense.analysis_status);

            // Normalize status for comparisons
            const status = expense.analysis_status?.toLowerCase();

            if (status === 'done') {
              addNotification('success', 'Expense Analysis Complete', `Expense #${id} has been analyzed and processed.`);
              trackedExpenses.current.delete(id);
            } else if (status === 'failed') {
              addNotification('error', 'Expense Analysis Failed', `Expense #${id} analysis failed.`);
              trackedExpenses.current.delete(id);
            }
          } catch (e: any) {
            console.error(`Error polling expense ${id}:`, e);

            const errorMessage = e instanceof Error ? e.message : String(e);

            // Check for network errors, server being down, or AI failures
            if (errorMessage.includes('Failed to fetch') ||
              errorMessage.includes('NetworkError') ||
              errorMessage.includes('404') ||
              errorMessage.includes('AI unavailable') ||
              errorMessage.includes('not found')) {

              addNotification('error', 'AI Analysis Unavailable', `Could not reach the analysis server for expense #${id}. Please check your connection.`);
              trackedExpenses.current.delete(id);
            } else {
              // For other errors, we also delete to avoid infinite error loops
              trackedExpenses.current.delete(id);
            }
          }
        }

        if (trackedExpenses.current.size === 0 && pollingRef.current) {
          clearInterval(pollingRef.current);
          pollingRef.current = null;
        }
      }, 5000);
    }
  };

  useEffect(() => {
    return () => {
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
      }
    };
  }, []);

  return { startPolling };
}