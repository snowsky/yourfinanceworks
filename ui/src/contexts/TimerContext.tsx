/**
 * TimerContext — global state for the live timer widget.
 *
 * Polls GET /time-entries/timer/active on mount to restore any in-progress timer
 * from a previous session. Child components use `useTimer()`.
 */

import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { timeEntryApi, TimeEntry, TimerActiveResponse } from '@/plugins/time_tracking/api';

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
      try {
        const res: TimerActiveResponse = await timeEntryApi.getActiveTimer();
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

  const startTimer = useCallback(async (data: Parameters<typeof timeEntryApi.startTimer>[0]) => {
    setIsLoading(true);
    try {
      const newEntry = await timeEntryApi.startTimer(data);
      setActive(true);
      setEntry(newEntry);
      setElapsedSeconds(0);
      qc.invalidateQueries({ queryKey: ['active-timer'] });
    } finally {
      setIsLoading(false);
    }
  }, [qc]);

  const stopTimer = useCallback(async (notes?: string) => {
    setIsLoading(true);
    // Capture project before clearing — needed for cache invalidation
    const projectId = entry?.project_id;
    try {
      await timeEntryApi.stopTimer({ notes });
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
