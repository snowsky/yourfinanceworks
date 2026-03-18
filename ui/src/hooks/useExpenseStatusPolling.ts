import { useEffect, useRef } from 'react';
import { expenseApi } from '@/lib/api';

const BASE_INTERVAL_MS = 5_000;
const MAX_INTERVAL_MS = 60_000;

export function useExpenseStatusPolling() {
  const pollingRef = useRef<any>(null);
  const trackedExpenses = useRef<Set<number>>(new Set());
  // Track per-item attempt count for exponential backoff
  const attemptsRef = useRef<Map<number, number>>(new Map());

  const startPolling = (expenseId: number) => {
    trackedExpenses.current.add(expenseId);
    attemptsRef.current.set(expenseId, 0);

    if (!pollingRef.current) {
      const tick = async () => {
        const addNotification = (window as any).addAINotification;
        if (!addNotification) return;

        for (const id of Array.from(trackedExpenses.current)) {
          try {
            const expense = await expenseApi.getExpense(id);
            const status = expense.analysis_status?.toLowerCase();

            if (status === 'done') {
              addNotification('success', 'Expense Analysis Complete', `Expense #${id} has been analyzed and processed.`);
              trackedExpenses.current.delete(id);
              attemptsRef.current.delete(id);
            } else if (status === 'failed') {
              addNotification('error', 'Expense Analysis Failed', `Expense #${id} analysis failed.`);
              trackedExpenses.current.delete(id);
              attemptsRef.current.delete(id);
            } else {
              // Still in progress — increment attempt count
              attemptsRef.current.set(id, (attemptsRef.current.get(id) ?? 0) + 1);
            }
          } catch (e: any) {
            const errorMessage = e instanceof Error ? e.message : String(e);

            if (
              errorMessage.includes('Failed to fetch') ||
              errorMessage.includes('NetworkError') ||
              errorMessage.includes('404') ||
              errorMessage.includes('AI unavailable') ||
              errorMessage.includes('not found')
            ) {
              addNotification('error', 'AI Analysis Unavailable', `Could not reach the analysis server for expense #${id}. Please check your connection.`);
              trackedExpenses.current.delete(id);
              attemptsRef.current.delete(id);
            } else {
              trackedExpenses.current.delete(id);
              attemptsRef.current.delete(id);
            }
          }
        }

        if (trackedExpenses.current.size === 0) {
          clearTimeout(pollingRef.current);
          pollingRef.current = null;
          return;
        }

        // Next interval: exponential backoff based on the max attempt count across tracked items
        const maxAttempts = Math.max(0, ...Array.from(attemptsRef.current.values()));
        const nextInterval = Math.min(BASE_INTERVAL_MS * Math.pow(2, maxAttempts), MAX_INTERVAL_MS);
        pollingRef.current = setTimeout(tick, nextInterval);
      };

      pollingRef.current = setTimeout(tick, BASE_INTERVAL_MS);
    }
  };

  useEffect(() => {
    return () => {
      if (pollingRef.current) {
        clearTimeout(pollingRef.current);
      }
    };
  }, []);

  return { startPolling };
}
