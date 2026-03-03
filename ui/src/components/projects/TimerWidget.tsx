/**
 * TimerWidget — persistent floating timer in the bottom-right corner.
 * Shows when a timer is active, allows quick stop with notes.
 */

import React, { useState } from 'react';
import { Clock, Square, ChevronDown, ChevronUp } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useTimer } from '@/contexts/TimerContext';

function formatElapsed(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  return [h, m, s].map((v) => String(v).padStart(2, '0')).join(':');
}

export function TimerWidget() {
  const { active, entry, elapsedSeconds, stopTimer, isLoading } = useTimer();
  const [expanded, setExpanded] = useState(true);
  const [notes, setNotes] = useState('');
  const [stopping, setStopping] = useState(false);

  if (!active || !entry) return null;

  const handleStop = async () => {
    setStopping(true);
    try {
      await stopTimer(notes || undefined);
      setNotes('');
    } finally {
      setStopping(false);
    }
  };

  return (
    <div className="fixed bottom-6 right-6 z-50 w-72 rounded-2xl shadow-2xl border border-slate-700/50 bg-slate-900/95 backdrop-blur-xl overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 bg-gradient-to-r from-blue-600 to-indigo-600">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
          <span className="text-white font-semibold text-sm">Timer Running</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-white font-mono text-sm font-bold tracking-wider">
            {formatElapsed(elapsedSeconds)}
          </span>
          <button
            onClick={() => setExpanded((e) => !e)}
            className="text-white/70 hover:text-white transition-colors"
          >
            {expanded ? <ChevronDown className="w-4 h-4" /> : <ChevronUp className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {/* Body */}
      {expanded && (
        <div className="px-4 py-3 space-y-3">
          <div className="text-xs text-slate-400 space-y-1">
            <div className="font-medium text-slate-200 truncate">{entry.project_name || `Project #${entry.project_id}`}</div>
            {entry.task_name && <div className="text-slate-400 truncate">Task: {entry.task_name}</div>}
            {entry.description && <div className="text-slate-500 truncate">{entry.description}</div>}
          </div>

          <textarea
            className="w-full rounded-lg bg-slate-800 border border-slate-700 text-slate-200 text-xs px-3 py-2 resize-none focus:outline-none focus:ring-1 focus:ring-blue-500 placeholder-slate-500"
            rows={2}
            placeholder="Notes (optional)…"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
          />

          <Button
            onClick={handleStop}
            disabled={stopping || isLoading}
            className="w-full bg-red-600 hover:bg-red-700 text-white text-sm font-semibold rounded-xl py-2 flex items-center justify-center gap-2 transition-colors"
          >
            <Square className="w-3 h-3 fill-current" />
            {stopping ? 'Stopping…' : 'Stop & Log Time'}
          </Button>
        </div>
      )}
    </div>
  );
}
