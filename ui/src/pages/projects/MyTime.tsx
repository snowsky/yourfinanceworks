import React, { useState } from 'react';
import { Clock, Download, Filter } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useTimeEntries } from '@/plugins/time_tracking/hooks';
import { timeEntryApi } from '@/plugins/time_tracking/api';
import { toast } from 'sonner';

export default function MyTime() {
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [isExporting, setIsExporting] = useState(false);
  const [showExport, setShowExport] = useState(false);

  const { data: entries = [], isLoading } = useTimeEntries({ limit: 200 });

  // Filter entries to current month
  const monthEntries = entries.filter((e) => {
    const d = new Date(e.started_at);
    return d.getFullYear() === now.getFullYear() && d.getMonth() === now.getMonth();
  });

  const totalHours = monthEntries.reduce((s, e) => s + e.hours, 0);
  const totalAmount = monthEntries.reduce((s, e) => s + (e.amount || 0), 0);
  const billableHours = monthEntries.filter((e) => e.billable).reduce((s, e) => s + e.hours, 0);

  const handleExport = async () => {
    setIsExporting(true);
    try {
      await timeEntryApi.downloadMonthlyExport({ year, month });
      toast.success('Export downloaded');
      setShowExport(false);
    } catch (e: any) {
      toast.error(e?.message || 'Export failed');
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-white flex items-center gap-2">
            <Clock className="w-8 h-8 text-blue-400" /> My Time
          </h1>
          <p className="text-slate-400 mt-1">Your personal time log</p>
        </div>
        <Button
          onClick={() => setShowExport((v) => !v)}
          className="bg-slate-700 hover:bg-slate-600 text-white rounded-xl border border-slate-600"
        >
          <Download className="w-4 h-4 mr-2" /> Export Excel
        </Button>
      </div>

      {/* Export panel */}
      {showExport && (
        <div className="mb-6 p-5 rounded-2xl border border-slate-700/50 bg-slate-800/40">
          <h3 className="text-white font-semibold mb-4">Monthly Time Report</h3>
          <div className="flex flex-wrap gap-3 items-center">
            <select
              className="bg-slate-700/50 border border-slate-600 rounded-xl px-3 py-2 text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              value={year}
              onChange={(e) => setYear(parseInt(e.target.value))}
            >
              {[now.getFullYear(), now.getFullYear() - 1, now.getFullYear() - 2].map((y) => (
                <option key={y} value={y}>{y}</option>
              ))}
            </select>
            <select
              className="bg-slate-700/50 border border-slate-600 rounded-xl px-3 py-2 text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              value={month}
              onChange={(e) => setMonth(parseInt(e.target.value))}
            >
              {Array.from({ length: 12 }, (_, i) => (
                <option key={i + 1} value={i + 1}>
                  {new Date(2000, i).toLocaleString('default', { month: 'long' })}
                </option>
              ))}
            </select>
            <Button
              onClick={handleExport}
              disabled={isExporting}
              className="bg-blue-600 hover:bg-blue-700 text-white rounded-xl"
            >
              {isExporting ? 'Exporting…' : 'Download .xlsx'}
            </Button>
          </div>
        </div>
      )}

      {/* This-month summary */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        {[
          { label: 'Hours this month', value: `${totalHours.toFixed(1)}h` },
          { label: 'Billable hours', value: `${billableHours.toFixed(1)}h` },
          { label: 'Amount logged', value: `$${totalAmount.toFixed(2)}` },
        ].map((s) => (
          <div key={s.label} className="bg-slate-800/40 border border-slate-700/50 rounded-2xl p-4">
            <div className="text-slate-400 text-xs mb-1">{s.label}</div>
            <div className="text-2xl font-bold text-white">{s.value}</div>
          </div>
        ))}
      </div>

      {/* Time entries */}
      {isLoading ? (
        <div className="text-slate-400 text-center py-12">Loading entries…</div>
      ) : entries.length === 0 ? (
        <div className="text-center py-24">
          <Clock className="w-16 h-16 text-slate-700 mx-auto mb-4" />
          <p className="text-slate-400">No time logged yet</p>
        </div>
      ) : (
        <div className="space-y-2">
          {entries.map((entry) => (
            <div key={entry.id} className="flex items-center justify-between bg-slate-800/40 border border-slate-700/50 rounded-xl px-4 py-3">
              <div className="flex-1 min-w-0">
                <div className="text-white text-sm font-medium truncate">
                  {entry.project_name || `Project #${entry.project_id}`}
                </div>
                <div className="text-slate-400 text-xs mt-0.5 flex items-center gap-2">
                  <span>{new Date(entry.started_at).toLocaleDateString()}</span>
                  <span>•</span>
                  <span>{entry.task_name || 'General'}</span>
                  <span>•</span>
                  <span>{entry.hours.toFixed(2)}h</span>
                  {entry.description && <><span>•</span><span className="truncate max-w-48">{entry.description}</span></>}
                </div>
              </div>
              <div className="flex items-center gap-3 ml-4">
                <span className={`text-xs px-2 py-0.5 rounded-full ${entry.billable ? 'bg-blue-900/30 text-blue-400' : 'bg-slate-700 text-slate-400'}`}>
                  {entry.billable ? 'Billable' : 'Non-billable'}
                </span>
                <span className="text-white font-semibold text-sm">${(entry.amount || 0).toFixed(2)}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
