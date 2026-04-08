import { useState } from 'react';
import { AlertTriangle, ChevronDown, ChevronUp, ExternalLink } from 'lucide-react';

interface DuplicateTxnEntry {
  id: number;
  statement_id: number;
  statement_filename: string;
  date: string;
  description: string;
  amount: number | string;
  transaction_type?: string;
}

interface DuplicateTransactionPanelProps {
  groups: DuplicateTxnEntry[][];
  onViewTransaction: (statementId: number, backendTxnId: number) => void;
}

export function DuplicateTransactionPanel({ groups, onViewTransaction }: DuplicateTransactionPanelProps) {
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
    <div className="rounded-xl border border-yellow-300 bg-yellow-50 dark:bg-yellow-950/20 dark:border-yellow-800 mb-3 overflow-hidden shadow-sm">
      {/* Header row — always visible, click to expand */}
      <button
        className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-yellow-100 dark:hover:bg-yellow-900/30 transition-colors"
        onClick={() => setExpanded(v => !v)}
        aria-expanded={expanded}
      >
        <AlertTriangle className="h-4 w-4 text-yellow-600 dark:text-yellow-400 flex-shrink-0" />
        <span className="flex-1 text-sm font-medium text-yellow-800 dark:text-yellow-300">
          <span className="font-bold">{count}</span>{' '}
          potential duplicate transaction {count !== 1 ? 'groups' : 'group'} detected across statements.{' '}
          <span className="font-normal opacity-80">Click to {expanded ? 'hide' : 'review'}.</span>
        </span>
        {expanded
          ? <ChevronUp className="h-4 w-4 text-yellow-600 dark:text-yellow-400 flex-shrink-0" />
          : <ChevronDown className="h-4 w-4 text-yellow-600 dark:text-yellow-400 flex-shrink-0" />
        }
      </button>

      {/* Expandable body */}
      {expanded && (
        <div className="border-t border-yellow-200 dark:border-yellow-800 divide-y divide-yellow-200 dark:divide-yellow-800">
          {groups.map((group, gi) => (
            <div key={gi} className="bg-white dark:bg-background">
              {/* Group header */}
              <button
                className="w-full flex items-center gap-2 px-4 py-2.5 text-left hover:bg-yellow-50 dark:hover:bg-yellow-950/10 transition-colors"
                onClick={() => toggleGroup(gi)}
              >
                <span className="text-xs font-bold uppercase tracking-wider text-yellow-700 dark:text-yellow-400 min-w-[60px]">
                  Group {gi + 1}
                </span>
                <span className="flex-1 text-xs text-muted-foreground truncate">
                  {group[0]?.description && (
                    <span className="mr-2 font-medium text-foreground">{group[0].description}</span>
                  )}
                  {group[0]?.date && (
                    <span className="mr-2">{group[0].date}</span>
                  )}
                  {group[0]?.amount !== undefined && (
                    <span className="font-mono">{formatAmount(group[0].amount)}</span>
                  )}
                  <span className="ml-2 text-yellow-600 dark:text-yellow-500">
                    · {group.length} occurrences across {new Set(group.map(t => t.statement_id)).size} statements
                  </span>
                </span>
                {expandedGroups.has(gi)
                  ? <ChevronUp className="h-3.5 w-3.5 text-muted-foreground flex-shrink-0" />
                  : <ChevronDown className="h-3.5 w-3.5 text-muted-foreground flex-shrink-0" />
                }
              </button>

              {/* Transaction rows within group */}
              {expandedGroups.has(gi) && (
                <div className="px-4 pb-3 space-y-1.5">
                  {group.map((txn, ti) => (
                    <div
                      key={ti}
                      className="flex items-center gap-3 rounded-lg border border-yellow-100 dark:border-yellow-900/40 bg-yellow-50/50 dark:bg-yellow-950/10 px-3 py-2 text-xs"
                    >
                      <div className="flex-1 min-w-0">
                        <span className="font-medium text-foreground truncate block">{txn.description}</span>
                        <span className="text-muted-foreground">
                          {txn.date}
                          {' · '}
                          <span className="font-mono font-semibold text-foreground">{formatAmount(txn.amount)}</span>
                          {' · '}
                          <span className="opacity-70">{txn.statement_filename}</span>
                        </span>
                      </div>
                      <button
                        onClick={() => onViewTransaction(txn.statement_id, txn.id)}
                        className="flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium bg-yellow-200 dark:bg-yellow-800/40 text-yellow-800 dark:text-yellow-300 hover:bg-yellow-300 dark:hover:bg-yellow-700/50 transition-colors flex-shrink-0 whitespace-nowrap"
                        title={`Open statement: ${txn.statement_filename}`}
                      >
                        <ExternalLink className="h-3 w-3" />
                        View
                      </button>
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
