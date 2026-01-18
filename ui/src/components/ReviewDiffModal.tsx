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
import { Check, X, ArrowRight, AlertTriangle } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { format } from 'date-fns';
import { cn } from '@/lib/utils';

interface ReviewDiffModalProps {
  isOpen: boolean;
  onClose: () => void;
  originalData: any;
  reviewResult: any; // The review_result dictionary from backend
  onAccept: () => void;
  isAccepting: boolean;
  type: 'expense' | 'invoice' | 'statement';
}

interface DiffRowProps {
  label: string;
  originalValue: any;
  newValue: any;
  formatter?: (val: any) => string;
}

const DiffRow: React.FC<DiffRowProps> = ({ label, originalValue, newValue, formatter }) => {
  const isDifferent = JSON.stringify(originalValue) !== JSON.stringify(newValue);
  
  // Format values
  const formatValue = (val: any) => {
    if (val === null || val === undefined) return <span className="text-muted-foreground italic">Empty</span>;
    if (formatter) return formatter(val);
    if (typeof val === 'boolean') return val ? 'Yes' : 'No';
    if (typeof val === 'object') return JSON.stringify(val);
    return String(val);
  };

  return (
    <div className={cn("grid grid-cols-[120px_1fr_24px_1fr] gap-4 py-3 border-b text-sm items-center", 
      isDifferent ? "bg-amber-500/5 -mx-4 px-4 border-amber-500/20" : "border-border/50"
    )}>
      <div className="font-medium text-muted-foreground">{label}</div>
      <div className="break-all">{formatValue(originalValue)}</div>
      <div className="flex justify-center text-muted-foreground">
        {isDifferent ? <ArrowRight className="h-4 w-4 text-amber-500" /> : <div className="w-4" />}
      </div>
      <div className={cn("break-all font-medium", isDifferent ? "text-amber-600 dark:text-amber-400" : "")}>
        {formatValue(newValue)}
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
  isAccepting,
  type
}) => {
  const { t } = useTranslation();

  if (!reviewResult) return null;

  // Extract relevant fields based on type
  // This comparison logic mimics backend but for display
  const fields = [];
  
  if (type === 'expense') {
    fields.push({ key: 'amount', label: 'Amount' });
    fields.push({ key: 'currency', label: 'Currency' });
    fields.push({ key: 'expense_date', label: 'Date', formatter: (v: any) => v ? format(new Date(v), 'yyyy-MM-dd') : '' });
    fields.push({ key: 'category', label: 'Category' });
    fields.push({ key: 'vendor', label: 'Vendor' });
    fields.push({ key: 'tax_amount', label: 'Tax' });
    fields.push({ key: 'total_amount', label: 'Total' });
    fields.push({ key: 'notes', label: 'Notes' });
  } else if (type === 'invoice') {
    fields.push({ key: 'number', label: 'Number' });
    fields.push({ key: 'date', label: 'Date', formatter: (v: any) => v ? format(new Date(v), 'yyyy-MM-dd') : '' });
    fields.push({ key: 'due_date', label: 'Due Date', formatter: (v: any) => v ? format(new Date(v), 'yyyy-MM-dd') : '' });
    fields.push({ key: 'total_amount', label: 'Total' });
    fields.push({ key: 'currency', label: 'Currency' });
    // TODO: Line items diffing is complex, maybe just show count
  } else if (type === 'statement') {
     fields.push({ key: 'period_start', label: 'Start Date', formatter: (v: any) => v ? format(new Date(v), 'yyyy-MM-dd') : '' });
     fields.push({ key: 'period_end', label: 'End Date', formatter: (v: any) => v ? format(new Date(v), 'yyyy-MM-dd') : '' });
     fields.push({ key: 'opening_balance', label: 'Opening Balance' });
     fields.push({ key: 'closing_balance', label: 'Closing Balance' });
     // Transactions diffing is complex
  }

  const hasDifferences = fields.some(f => {
    const v1 = originalData[f.key];
    const v2 = reviewResult[f.key];
    // Simple equality check, can be improved
    return JSON.stringify(v1) !== JSON.stringify(v2);
  });

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-3xl max-h-[85vh] flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-amber-500" />
            Review Differences
          </DialogTitle>
          <DialogDescription>
            Review the differences found by the secondary AI reviewer. Accept to apply these changes.
          </DialogDescription>
        </DialogHeader>

        <div className="grid grid-cols-[120px_1fr_24px_1fr] gap-4 py-2 font-semibold text-sm border-b-2 border-primary/20 bg-muted/20 px-4 -mx-4 mt-4">
          <div>Field</div>
          <div>Current Value</div>
          <div></div>
          <div>Reviewer Value</div>
        </div>

        <ScrollArea className="flex-1 -mx-4 px-4">
          <div className="space-y-0">
            {fields.map(field => (
              <DiffRow
                key={field.key}
                label={field.label}
                originalValue={originalData[field.key]}
                newValue={reviewResult[field.key]}
                formatter={field.formatter}
              />
            ))}
          </div>
        </ScrollArea>

        <DialogFooter className="mt-6 gap-2">
          <Button variant="outline" onClick={onClose}>
            <X className="w-4 h-4 mr-2" />
            Dismiss
          </Button>
          <Button onClick={onAccept} disabled={isAccepting} className="bg-amber-600 hover:bg-amber-700 text-white">
            {isAccepting ? (
              <span className="flex items-center gap-2">Processing...</span>
            ) : (
              <>
                <Check className="w-4 h-4 mr-2" />
                Accept Review
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
