import { useState } from 'react';
import { AlertTriangle, ChevronDown, ChevronUp, ExternalLink } from 'lucide-react';
import { Link } from 'react-router-dom';

interface DuplicateExpenseEntry {
  id: number;
  amount: number | string;
  expense_date: string;
  vendor?: string | null;
  category?: string | null;
  status?: string | null;
}

interface DuplicateExpensePanelProps {
  groups: DuplicateExpenseEntry[][];
}

export function DuplicateExpensePanel({ groups }: DuplicateExpensePanelProps) {
  const [expanded, setExpanded] = useState(false);
  const [expandedGroups, setExpandedGroups] = useState<Set<number>>(new Set([0]));

  const count = groups.length;

  const toggleGroup = (idx: number) => {
    setExpandedGroups(prev => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return next;
    });
  };

  const formatAmount = (amount: number | string) => {
    const n = typeof amount === 'string' ? parseFloat(amount) : amount;
    if (isNaN(n)) return String(amount);
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(Math.abs(n));
  };

  return (
    <div className="rounded-xl border border-amber-300 bg-amber-50 dark:bg-amber-950/20 dark:border-amber-800 mb-3 overflow-hidden shadow-sm">
      {/* Header row — always visible, click to expand */}
      <button
        className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-amber-100 dark:hover:bg-amber-900/30 transition-colors"
        onClick={() => setExpanded(v => !v)}
        aria-expanded={expanded}
      >
        <AlertTriangle className="h-4 w-4 text-amber-600 dark:text-amber-400 flex-shrink-0" />
        <span className="flex-1 text-sm font-medium text-amber-800 dark:text-amber-300">
          <span className="font-bold">{count}</span>{' '}
          potential duplicate expense {count !== 1 ? 'groups' : 'group'} detected — same amount, vendor, and similar dates.{' '}
          <span className="font-normal opacity-80">Click to {expanded ? 'hide' : 'review'}.</span>
        </span>
        {expanded
          ? <ChevronUp className="h-4 w-4 text-amber-600 dark:text-amber-400 flex-shrink-0" />
          : <ChevronDown className="h-4 w-4 text-amber-600 dark:text-amber-400 flex-shrink-0" />
        }
      </button>

      {/* Expandable body */}
      {expanded && (
        <div className="border-t border-amber-200 dark:border-amber-800 divide-y divide-amber-200 dark:divide-amber-800">
          {groups.map((group, gi) => (
            <div key={gi} className="bg-white dark:bg-background">
              {/* Group header */}
              <button
                className="w-full flex items-center gap-2 px-4 py-2.5 text-left hover:bg-amber-50 dark:hover:bg-amber-950/10 transition-colors"
                onClick={() => toggleGroup(gi)}
              >
                <span className="text-xs font-bold uppercase tracking-wider text-amber-700 dark:text-amber-400 min-w-[60px]">
                  Group {gi + 1}
                </span>
                <span className="flex-1 text-xs text-muted-foreground truncate">
                  {group[0]?.vendor && (
                    <span className="mr-2 font-medium text-foreground">{group[0].vendor}</span>
                  )}
                  {group[0]?.amount !== undefined && (
                    <span className="font-mono mr-2">{formatAmount(group[0].amount)}</span>
                  )}
                  {group[0]?.category && (
                    <span className="mr-2 opacity-70">{group[0].category}</span>
                  )}
                  <span className="text-amber-600 dark:text-amber-500">
                    · {group.length} occurrences
                  </span>
                </span>
                {expandedGroups.has(gi)
                  ? <ChevronUp className="h-3.5 w-3.5 text-muted-foreground flex-shrink-0" />
                  : <ChevronDown className="h-3.5 w-3.5 text-muted-foreground flex-shrink-0" />
                }
              </button>

              {/* Expense rows within group */}
              {expandedGroups.has(gi) && (
                <div className="px-4 pb-3 space-y-1.5">
                  {group.map((exp, ei) => (
                    <div
                      key={ei}
                      className="flex items-center gap-3 rounded-lg border border-amber-100 dark:border-amber-900/40 bg-amber-50/50 dark:bg-amber-950/10 px-3 py-2 text-xs"
                    >
                      <div className="flex-1 min-w-0">
                        <span className="font-medium text-foreground truncate block">
                          {exp.vendor || <span className="italic text-muted-foreground">No vendor</span>}
                        </span>
                        <span className="text-muted-foreground">
                          {exp.expense_date}
                          {' · '}
                          <span className="font-mono font-semibold text-foreground">{formatAmount(exp.amount)}</span>
                          {exp.category && (
                            <>{' · '}<span className="opacity-70">{exp.category}</span></>
                          )}
                          {exp.status && (
                            <>{' · '}<span className="opacity-60 capitalize">{exp.status}</span></>
                          )}
                        </span>
                      </div>
                      <Link
                        to={`/expenses/view/${exp.id}`}
                        className="flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium bg-amber-200 dark:bg-amber-800/40 text-amber-800 dark:text-amber-300 hover:bg-amber-300 dark:hover:bg-amber-700/50 transition-colors flex-shrink-0 whitespace-nowrap"
                        title={`View expense #${exp.id}`}
                      >
                        <ExternalLink className="h-3 w-3" />
                        View
                      </Link>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
