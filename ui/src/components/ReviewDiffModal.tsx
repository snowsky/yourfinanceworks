import React from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Check, X, ArrowRight, AlertTriangle, FileText, Calendar, DollarSign, Tag, Hash, Building, Landmark, Percent } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { format, isValid, parseISO } from 'date-fns';
import { cn } from '@/lib/utils';

/**
 * Safely format a date string, handling "null", "None", and other invalid inputs.
 */
const safeFormatDate = (v: any) => {
  if (!v || v === 'null' || v === 'None') return '';
  try {
    const d = typeof v === 'string' ? parseISO(v) : new Date(v);
    return isValid(d) ? format(d, 'yyyy-MM-dd') : '';
  } catch {
    return '';
  }
};

interface ReviewDiffModalProps {
  isOpen: boolean;
  onClose: () => void;
  originalData: any;
  reviewResult: any; // The review_result dictionary from backend
  onAccept: () => void;
  onReject: () => void;
  onRetrigger: () => void;
  isAccepting: boolean;
  isRejecting: boolean;
  isRetriggering: boolean;
  type: 'expense' | 'invoice' | 'statement';
}

interface DiffRowProps {
  label: string;
  originalValue: any;
  newValue: any;
  formatter?: (val: any) => string;
  icon?: React.ReactNode;
}

const DiffRow: React.FC<DiffRowProps> = ({ label, originalValue, newValue, formatter, icon }) => {
  // Enhanced "effectively empty" check
  const isEffectivelyEmpty = (val: any) => {
    if (val === null || val === undefined || val === '') return true;
    if (typeof val === 'string' && (val.toLowerCase() === 'null' || val.toLowerCase() === 'none')) return true;
    return false;
  };

  const isDifferent = (() => {
    const empty1 = isEffectivelyEmpty(originalValue);
    const empty2 = isEffectivelyEmpty(newValue);

    // If both are empty, they are not different
    if (empty1 && empty2) return false;

    // special case for number 0 vs empty
    if ((originalValue === 0 || originalValue === 0.0) && empty2) return false;
    if (empty1 && (newValue === 0 || newValue === 0.0)) return false;

    return JSON.stringify(originalValue) !== JSON.stringify(newValue);
  })();

  // Format values
  const formatValue = (val: any, isNew: boolean = false) => {
    if (isEffectivelyEmpty(val)) return <span className="text-muted-foreground/40 italic text-xs">Empty</span>;

    let content;
    if (formatter) {
      content = formatter(val);
    } else if (typeof val === 'boolean') {
      content = val ? 'Yes' : 'No';
    } else if (typeof val === 'object') {
      content = JSON.stringify(val);
    } else {
      content = String(val);
    }

    return <span className={cn(isNew && isDifferent ? "font-medium text-amber-700 dark:text-amber-400" : "")}>{content}</span>;
  };

  return (
    <div className={cn(
      "group flex flex-col p-4 rounded-lg transition-all duration-200 border",
      isDifferent
        ? "bg-amber-50/50 dark:bg-amber-900/10 border-amber-200 dark:border-amber-800/30 shadow-sm"
        : "bg-card border-transparent hover:bg-muted/30 hover:border-border/50"
    )}>
      <div className="flex items-center gap-2 mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        {icon && <span className={cn("text-muted-foreground/70", isDifferent && "text-amber-500")}>{icon}</span>}
        {label}
        {isDifferent && (
          <Badge variant="outline" className="ml-auto bg-amber-100/50 text-amber-700 border-amber-200 dark:bg-amber-900/20 dark:text-amber-400 dark:border-amber-700/30 text-[10px] h-5 px-1.5 shadow-none">
            Changed
          </Badge>
        )}
      </div>

      <div className="grid grid-cols-[1fr_24px_1fr] gap-4 items-center text-sm">
        <div className={cn(
          "p-2.5 rounded-md text-muted-foreground bg-muted/20 border border-transparent transition-colors",
          isDifferent && "opacity-70"
        )}>
          {formatValue(originalValue)}
        </div>

        <div className="flex justify-center">
          <ArrowRight className={cn(
            "h-4 w-4 transition-colors", 
            isDifferent ? "text-amber-500" : "text-muted-foreground/20"
          )} />
        </div>

        <div className={cn(
          "p-2.5 rounded-md border min-h-[42px] flex items-center transition-all", 
          isDifferent 
            ? "bg-amber-100/40 dark:bg-amber-900/20 border-amber-200/50 dark:border-amber-700/30 shadow-sm" 
            : "bg-muted/10 border-transparent text-muted-foreground"
        )}>
          {formatValue(newValue, true)}
        </div>
      </div>
    </div>
  );
};

export const ReviewDiffModal: React.FC<ReviewDiffModalProps> = ({
  isOpen,
  onClose,
  originalData,
  reviewResult,
  onAccept,
  onReject,
  onRetrigger,
  isAccepting,
  isRejecting,
  isRetriggering,
  type
}) => {
  const { t } = useTranslation();

  if (!reviewResult) return null;

  // Extract relevant fields based on type
  interface FieldConfig {
    key: string;
    label: string;
    altKey?: string;
    formatter?: (val: any) => string;
    icon?: React.ReactNode;
  }

  const fields: FieldConfig[] = [];
  const iconClass = "h-3.5 w-3.5";

  if (type === 'expense') {
    fields.push({ key: 'amount', label: 'Amount', icon: <DollarSign className={iconClass} /> });
    fields.push({ key: 'currency', label: 'Currency', icon: <DollarSign className={iconClass} /> });
    fields.push({ key: 'expense_date', label: 'Date', altKey: 'date', formatter: safeFormatDate, icon: <Calendar className={iconClass} /> });
    fields.push({ key: 'category', label: 'Category', icon: <Tag className={iconClass} /> });
    fields.push({ key: 'vendor', label: 'Vendor', altKey: 'vendor_name', icon: <Building className={iconClass} /> });
    fields.push({ key: 'tax_amount', label: 'Tax', icon: <Percent className={iconClass} /> });
    fields.push({ key: 'total_amount', label: 'Total', icon: <DollarSign className={iconClass} /> });
    fields.push({ key: 'notes', label: 'Notes', icon: <FileText className={iconClass} /> });
  } else if (type === 'invoice') {
    fields.push({ key: 'number', label: 'Invoice Number', altKey: 'invoice_number', icon: <Hash className={iconClass} /> });
    fields.push({ key: 'date', label: 'Invoice Date', altKey: 'invoice_date', formatter: safeFormatDate, icon: <Calendar className={iconClass} /> });
    fields.push({ key: 'due_date', label: 'Due Date', formatter: safeFormatDate, icon: <Calendar className={iconClass} /> });
    fields.push({ key: 'total_amount', label: 'Total Amount', icon: <DollarSign className={iconClass} /> });
    fields.push({ key: 'currency', label: 'Currency', icon: <DollarSign className={iconClass} /> });
    fields.push({ key: 'client_name', label: 'Client', icon: <Building className={iconClass} /> });
    fields.push({ key: 'vendor_name', label: 'Vendor', icon: <Building className={iconClass} /> });
  } else if (type === 'statement') {
    fields.push({ key: 'transaction_count', label: 'Transaction Count', icon: <Hash className={iconClass} /> });
    fields.push({ key: 'start_date', label: 'Start Date', formatter: safeFormatDate, icon: <Calendar className={iconClass} /> });
    fields.push({ key: 'end_date', label: 'End Date', formatter: safeFormatDate, icon: <Calendar className={iconClass} /> });
    fields.push({ key: 'account_number', label: 'Account', icon: <Landmark className={iconClass} /> });
  }

  // Handle detailed transaction differences for statements
  const transactionDiffs = [];
  if (type === 'statement' && reviewResult.transactions) {
    const origTxs = originalData.transactions || [];
    const revTxs = reviewResult.transactions || [];
    const maxIdx = Math.max(origTxs.length, revTxs.length);

    for (let i = 0; i < maxIdx; i++) {
        const t1 = origTxs[i];
        const t2 = revTxs[i];

        // Simple heuristic for diff
        if (!t1 || !t2 || safeFormatDate(t1.date) !== safeFormatDate(t2.date) || t1.amount !== t2.amount || t1.description !== t2.description) {
            transactionDiffs.push({
                index: i + 1,
                original: t1,
                reviewed: t2
            });
        }
    }
  }

  const differencesCount = fields.filter(f => {
    const v1 = originalData[f.key];
    const v2 = reviewResult[f.key] !== undefined ? reviewResult[f.key] : reviewResult[f.altKey];
    // Re-use logic from DiffRow ideally, but simplistic check here
    if ((!v1 && !v2) || (v1 === v2)) return false;
    // Don't count null vs empty string false positives etc, but simplistic
    return JSON.stringify(v1) !== JSON.stringify(v2);
  }).length + transactionDiffs.length;

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-4xl max-h-[90vh] flex flex-col p-0 gap-0 overflow-hidden border-none shadow-2xl bg-background/95 backdrop-blur-xl">
        {/* Professional Header */}
        <DialogHeader className="p-6 pb-4 border-b bg-muted/10">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-full bg-amber-100 dark:bg-amber-900/30 flex items-center justify-center border border-amber-200 dark:border-amber-700/50">
              <AlertTriangle className="h-5 w-5 text-amber-600 dark:text-amber-500" />
            </div>
            <div>
              <DialogTitle className="text-xl font-bold tracking-tight">Review AI Analysis Differences</DialogTitle>
              <DialogDescription className="text-muted-foreground mt-1">
                A secondary AI review found {differencesCount > 0 ? <span className="text-amber-600 font-medium">{differencesCount} differences</span> : 'no significant differences'} compared to the original analysis.
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

        {/* Comparison Header Labels */}
        <div className="grid grid-cols-[1fr_24px_1fr] gap-4 px-10 py-3 bg-muted/30 border-b text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          <div className="pl-4">Original Analysis</div>
          <div></div>
          <div className="pl-4">Reviewer Suggestion</div>
        </div>

        <ScrollArea className="flex-1">
          <div className="p-6 space-y-4">
            <div className="grid grid-cols-1 gap-3">
              {fields.map(field => (
                <DiffRow
                  key={field.key}
                  label={field.label}
                  originalValue={originalData[field.key]}
                  newValue={reviewResult[field.key] !== undefined ? reviewResult[field.key] : reviewResult[field.altKey]}
                  formatter={field.formatter}
                  icon={field.icon}
                />
              ))}
            </div>

            {transactionDiffs.length > 0 && (
              <div className="mt-8 animate-fade-in-up">
                <div className="flex items-center gap-2 mb-4 pb-2 border-b border-amber-200/50 dark:border-amber-800/50">
                   <AlertTriangle className="h-4 w-4 text-amber-500" />
                   <h3 className="font-bold text-sm text-amber-700 dark:text-amber-400">
                     Transaction Differences ({transactionDiffs.length})
                   </h3>
                </div>

                <div className="space-y-4">
                  {transactionDiffs.map((diff) => (
                    <div key={diff.index} className="border rounded-lg p-0 overflow-hidden bg-card shadow-sm border-amber-200/50 dark:border-amber-800/30">
                      <div className="px-4 py-2 bg-amber-50/50 dark:bg-amber-900/10 border-b border-amber-100 dark:border-amber-800/20 text-xs font-medium flex justify-between items-center text-muted-foreground">
                        <span>Transaction #{diff.index}</span>
                        {!diff.original && <Badge variant="outline" className="bg-green-500/10 text-green-600 border-green-500/20">New Transaction</Badge>}
                        {!diff.reviewed && <Badge variant="outline" className="bg-red-500/10 text-red-600 border-red-500/20">Removed Transaction</Badge>}
                      </div>

                      <div className="p-4 grid gap-3">
                         <div className="grid grid-cols-[1fr_24px_1fr] gap-4 text-sm">
                            <div className="text-right text-muted-foreground text-xs uppercase tracking-wider self-center col-span-3 mb-1 justify-self-start">Date</div>

                            <div className={cn("p-2 rounded bg-muted/20 text-sm", safeFormatDate(diff.original?.date) !== safeFormatDate(diff.reviewed?.date) && "line-through text-muted-foreground/60")}>
                                {safeFormatDate(diff.original?.date) || '—'}
                            </div>
                            <ArrowRight className="h-4 w-4 text-muted-foreground/30 self-center justify-self-center" />
                            <div className={cn("p-2 rounded border bg-card text-sm font-medium", safeFormatDate(diff.original?.date) !== safeFormatDate(diff.reviewed?.date) ? "border-amber-200 text-amber-700 bg-amber-50/30" : "border-transparent bg-transparent")}>
                                {safeFormatDate(diff.reviewed?.date) || '—'}
                            </div>
                         </div>

                         <div className="grid grid-cols-[1fr_24px_1fr] gap-4 text-sm border-t border-border/40 pt-3">
                            <div className="text-right text-muted-foreground text-xs uppercase tracking-wider self-center col-span-3 mb-1 justify-self-start">Description</div>

                            <div className={cn("p-2 rounded bg-muted/20 text-sm", diff.original?.description !== diff.reviewed?.description && "line-through text-muted-foreground/60")}>
                                {diff.original?.description || '—'}
                            </div>
                            <ArrowRight className="h-4 w-4 text-muted-foreground/30 self-center justify-self-center" />
                            <div className={cn("p-2 rounded border bg-card text-sm font-medium", diff.original?.description !== diff.reviewed?.description ? "border-amber-200 text-amber-700 bg-amber-50/30" : "border-transparent bg-transparent")}>
                                {diff.reviewed?.description || '—'}
                            </div>
                         </div>

                         <div className="grid grid-cols-[1fr_24px_1fr] gap-4 text-sm border-t border-border/40 pt-3">
                            <div className="text-right text-muted-foreground text-xs uppercase tracking-wider self-center col-span-3 mb-1 justify-self-start">Amount</div>

                            <div className={cn("p-2 rounded bg-muted/20 text-sm", diff.original?.amount !== diff.reviewed?.amount && "line-through text-muted-foreground/60")}>
                                {diff.original?.amount ?? '—'}
                            </div>
                            <ArrowRight className="h-4 w-4 text-muted-foreground/30 self-center justify-self-center" />
                            <div className={cn("p-2 rounded border bg-card text-sm font-medium", diff.original?.amount !== diff.reviewed?.amount ? "border-amber-200 text-amber-700 bg-amber-50/30" : "border-transparent bg-transparent")}>
                                {diff.reviewed?.amount ?? '—'}
                            </div>
                         </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </ScrollArea>

        <div className="p-6 pt-4 border-t bg-muted/5">
          <DialogFooter className="flex-col sm:flex-row gap-3 sm:justify-between items-center w-full">
            <Button 
                variant="ghost" 
                onClick={onRetrigger} 
                disabled={isRetriggering}
                className="text-muted-foreground hover:text-foreground"
            >
              {isRetriggering ? 'Starting...' : 'Retrigger Analysis'}
            </Button>

            <div className="flex gap-3 w-full sm:w-auto">
              <Button 
                variant="outline" 
                onClick={onReject} 
                disabled={isRejecting}
                className="flex-1 sm:flex-none border-destructive/20 hover:bg-destructive/5 hover:text-destructive hover:border-destructive/30"
              >
                {isRejecting ? 'Dismissing...' : (
                  <>
                    <X className="w-4 h-4 mr-2" />
                    Dismiss Changes
                  </>
                )}
              </Button>
              <Button 
                onClick={onAccept} 
                disabled={isAccepting} 
                className="flex-1 sm:flex-none bg-amber-600 hover:bg-amber-700 text-white shadow-lg shadow-amber-900/10 hover:shadow-amber-900/20 transition-all"
              >
                {isAccepting ? (
                  <span className="flex items-center gap-2">Applying...</span>
                ) : (
                  <>
                    <Check className="w-4 h-4 mr-2" />
                    Accept New Values
                  </>
                )}
              </Button>
            </div>
          </DialogFooter>
        </div>
      </DialogContent>
    </Dialog>
  );
};
