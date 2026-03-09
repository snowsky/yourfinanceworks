import { useEffect, useRef } from 'react';
import { bankStatementApi } from '@/lib/api';

export function useStatementStatusPolling() {
  const pollingRef = useRef<any>(null);
  const trackedStatements = useRef<Set<number>>(new Set());

  const startPolling = (statementIds: number[]) => {
    statementIds.forEach(id => trackedStatements.current.add(id));

    if (!pollingRef.current) {
      pollingRef.current = setInterval(async () => {
        const addNotification = (window as any).addAINotification;

        for (const id of Array.from(trackedStatements.current)) {
          try {
            const statement = await bankStatementApi.get(id);
            console.log(`Statement ${id} status:`, statement.status);

            const status = statement.status?.toLowerCase();

            if (status === 'processed' || status === 'done' || status === 'merged') {
              if (addNotification) addNotification('success', 'Statement Processing Complete', `Statement #${id} has been processed.`);
              trackedStatements.current.delete(id);
              // Trigger a refresh event if possible, or we could just rely on the component polling
              window.dispatchEvent(new CustomEvent('statement-processed', { detail: { id } }));
            } else if (status === 'failed') {
              if (addNotification) addNotification('error', 'Statement Processing Failed', `Statement #${id} processing failed.`);
              trackedStatements.current.delete(id);
              window.dispatchEvent(new CustomEvent('statement-failed', { detail: { id } }));
            }
          } catch (e: any) {
            console.error(`Error polling statement ${id}:`, e);

            const errorMessage = e instanceof Error ? e.message : String(e);

            if (errorMessage.includes('Failed to fetch') ||
              errorMessage.includes('NetworkError') ||
              errorMessage.includes('404') ||
              errorMessage.includes('AI unavailable') ||
              errorMessage.includes('not found')) {

              if (addNotification) addNotification('error', 'AI Processing Unavailable', `Could not reach the server for statement #${id}. Please check your connection.`);
              trackedStatements.current.delete(id);
            } else {
              trackedStatements.current.delete(id);
            }
          }
        }

        if (trackedStatements.current.size === 0 && pollingRef.current) {
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
