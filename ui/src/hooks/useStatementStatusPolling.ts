import { useEffect, useRef } from 'react';
import { bankStatementApi } from '@/lib/api';

const BASE_INTERVAL_MS = 5_000;
const MAX_INTERVAL_MS = 60_000;

export function useStatementStatusPolling() {
  const pollingRef = useRef<any>(null);
  const trackedStatements = useRef<Set<number>>(new Set());
  const attemptsRef = useRef<Map<number, number>>(new Map());

  const startPolling = (statementIds: number[]) => {
    statementIds.forEach(id => {
      trackedStatements.current.add(id);
      attemptsRef.current.set(id, 0);
    });

    if (!pollingRef.current) {
      const tick = async () => {
        const addNotification = (window as any).addAINotification;

        for (const id of Array.from(trackedStatements.current)) {
          try {
            const statement = await bankStatementApi.get(id);
            const status = statement.status?.toLowerCase();

            if (status === 'processed' || status === 'done' || status === 'merged') {
              if (addNotification) addNotification('success', 'Statement Processing Complete', `Statement #${id} has been processed.`);
              trackedStatements.current.delete(id);
              attemptsRef.current.delete(id);
              window.dispatchEvent(new CustomEvent('statement-processed', { detail: { id } }));
            } else if (status === 'failed') {
              if (addNotification) addNotification('error', 'Statement Processing Failed', `Statement #${id} processing failed.`);
              trackedStatements.current.delete(id);
              attemptsRef.current.delete(id);
              window.dispatchEvent(new CustomEvent('statement-failed', { detail: { id } }));
            } else {
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
              if (addNotification) addNotification('error', 'AI Processing Unavailable', `Could not reach the server for statement #${id}. Please check your connection.`);
              trackedStatements.current.delete(id);
              attemptsRef.current.delete(id);
            } else {
              trackedStatements.current.delete(id);
              attemptsRef.current.delete(id);
            }
          }
        }

        if (trackedStatements.current.size === 0) {
          clearTimeout(pollingRef.current);
          pollingRef.current = null;
          return;
        }

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
