/**
 * TimerContext — global state for the live timer widget.
 *
 * Polls GET /time-entries/timer/active on mount to restore any in-progress timer
 * from a previous session. Child components use `useTimer()`.
 */

import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import type { TimeEntry, TimerActiveResponse } from '@/plugins/time_tracking/plugin/ui/api';

/**
 * Helper to get the time tracking API lazily.
 * This ensures that if the plugin is missing, we don't crash the whole app.
 */
async function getTimeTrackingApi() {
  try {
    const mod = await import('../plugins/time_tracking/plugin/ui/api');
    return mod.timeEntryApi;
  } catch (err) {
    console.warn('[TimerContext] Time tracking plugin not available:', err);
    return null;
  }
}

interface TimerState {
  active: boolean;
  entry: TimeEntry | null;
  elapsedSeconds: number;
  startTimer: (data: { project_id: number; task_id?: number; description?: string; hourly_rate: number; billable?: boolean }) => Promise<void>;
  stopTimer: (notes?: string) => Promise<void>;
  isLoading: boolean;
}

const TimerContext = createContext<TimerState>({
  active: false,
  entry: null,
  elapsedSeconds: 0,
  startTimer: async () => {},
  stopTimer: async () => {},
  isLoading: false,
});

export function TimerProvider({ children }: { children: React.ReactNode }) {
  const qc = useQueryClient();
  const [active, setActive] = useState(false);
  const [entry, setEntry] = useState<TimeEntry | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [isLoading, setIsLoading] = useState(false);

  // Poll active timer on mount
  useEffect(() => {
    const fetchActive = async () => {
      const api = await getTimeTrackingApi();
      if (!api) return;
      try {
        const res: TimerActiveResponse = await api.getActiveTimer();
        if (res.active && res.entry) {
          setActive(true);
          setEntry(res.entry);
          setElapsedSeconds(res.elapsed_seconds || 0);
        }
      } catch {
        // Not running or not logged in, ignore
      }
    };
    fetchActive();
  }, []);

  // Tick elapsed seconds locally while active
  useEffect(() => {
    if (!active) return;
    const interval = setInterval(() => setElapsedSeconds((s) => s + 1), 1000);
    return () => clearInterval(interval);
  }, [active]);

  const startTimer = useCallback(async (data: { project_id: number; task_id?: number; description?: string; hourly_rate: number; billable?: boolean }) => {
    const api = await getTimeTrackingApi();
    if (!api) return;
    setIsLoading(true);
    try {
      const newEntry = await api.startTimer(data);
      setActive(true);
      setEntry(newEntry);
      setElapsedSeconds(0);
      qc.invalidateQueries({ queryKey: ['active-timer'] });
    } finally {
      setIsLoading(false);
    }
  }, [qc]);

  const stopTimer = useCallback(async (notes?: string) => {
    const api = await getTimeTrackingApi();
    if (!api) return;
    setIsLoading(true);
    // Capture project before clearing — needed for cache invalidation
    const projectId = entry?.project_id;
    try {
      await api.stopTimer({ notes });
      setActive(false);
      setEntry(null);
      setElapsedSeconds(0);
      qc.invalidateQueries({ queryKey: ['active-timer'] });
      qc.invalidateQueries({ queryKey: ['time-entries'] });
      qc.invalidateQueries({ queryKey: ['project-summary'] });
      // Refresh unbilled tab immediately so the stopped entry appears
      if (projectId) {
        qc.invalidateQueries({ queryKey: ['project-unbilled', projectId] });
      } else {
        qc.invalidateQueries({ queryKey: ['project-unbilled'] });
      }
    } finally {
      setIsLoading(false);
    }
  }, [qc, entry]);

  return (
    <TimerContext.Provider value={{ active, entry, elapsedSeconds, startTimer, stopTimer, isLoading }}>
      {children}
    </TimerContext.Provider>
  );
}

export function useTimer() {
  return useContext(TimerContext);
}
