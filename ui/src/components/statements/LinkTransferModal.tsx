import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { ScrollArea } from '@/components/ui/scroll-area';
import { ArrowLeftRight, ArrowRight, FileText, Loader2 } from 'lucide-react';
import { format, parseISO, isValid } from 'date-fns';
import { bankStatementApi, BankTransactionEntry, TransactionLinkInfo, BankStatementDetail, BankStatementSummary } from '@/lib/api/bank-statements';
import { toast } from 'sonner';

type Step = 'pick-statement' | 'pick-transaction' | 'confirm';

interface LinkTransferModalProps {
  isOpen: boolean;
  onClose: () => void;
  sourceTransaction: BankTransactionEntry;
  sourceStatementId: number;
  onLinked: (link: TransactionLinkInfo) => void;
}

const safeDate = (d: string) => {
  try {
    const parsed = parseISO(d);
    return isValid(parsed) ? format(parsed, 'MMM d, yyyy') : d;
  } catch {
    return d;
  }
};

const formatAmount = (amount: number, type: string) => {
  const sign = type === 'debit' ? '-' : '+';
  return `${sign}$${Math.abs(amount).toFixed(2)}`;
};

export function LinkTransferModal({
  isOpen,
  onClose,
  sourceTransaction,
  sourceStatementId,
  onLinked,
}: LinkTransferModalProps) {
  const [step, setStep] = useState<Step>('pick-statement');
  const [search, setSearch] = useState('');
  const [statements, setStatements] = useState<BankStatementSummary[]>([]);
  const [loadingStatements, setLoadingStatements] = useState(false);
  const [selectedStatement, setSelectedStatement] = useState<BankStatementSummary | null>(null);
  const [statementDetail, setStatementDetail] = useState<BankStatementDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [selectedTransaction, setSelectedTransaction] = useState<BankTransactionEntry | null>(null);
  const [linkType, setLinkType] = useState<'transfer' | 'fx_conversion'>('transfer');
  const [notes, setNotes] = useState('');
  const [submitting, setSubmitting] = useState(false);

  // Load statements when modal opens
  React.useEffect(() => {
    if (!isOpen) return;
    setStep('pick-statement');
    setSearch('');
    setSelectedStatement(null);
    setStatementDetail(null);
    setSelectedTransaction(null);
    setLinkType('transfer');
    setNotes('');

    setLoadingStatements(true);
    bankStatementApi
      .list(0, 200)
      .then(({ statements: all }) => {
        setStatements(all.filter((s) => s.id !== sourceStatementId && s.status !== 'failed'));
      })
      .catch(() => toast.error('Failed to load statements'))
      .finally(() => setLoadingStatements(false));
  }, [isOpen, sourceStatementId]);

  const handleSelectStatement = async (stmt: BankStatementSummary) => {
    setSelectedStatement(stmt);
    setStep('pick-transaction');
    setLoadingDetail(true);
    try {
      const detail = await bankStatementApi.get(stmt.id);
      setStatementDetail(detail);
    } catch {
      toast.error('Failed to load transactions');
      setStep('pick-statement');
    } finally {
      setLoadingDetail(false);
    }
  };

  const handleSelectTransaction = (txn: BankTransactionEntry) => {
    setSelectedTransaction(txn);
    setStep('confirm');
  };

  const handleLink = async () => {
    if (!sourceTransaction.id || !selectedTransaction?.id) return;
    setSubmitting(true);
    try {
      const result = await bankStatementApi.createTransactionLink(
        sourceTransaction.id,
        selectedTransaction.id,
        linkType,
        notes || undefined
      );
      // Build the TransactionLinkInfo from the perspective of the source transaction
      const linkForSource =
        result.link.linked_for_a?.linked_transaction_id === selectedTransaction.id
          ? result.link.linked_for_a
          : result.link.linked_for_b;

      if (linkForSource) {
        onLinked(linkForSource);
        toast.success('Transfer linked successfully');
      } else {
        // Fallback: construct from response
        onLinked({
          id: result.link.id,
          link_type: linkType,
          notes: notes || null,
          linked_transaction_id: selectedTransaction.id,
          linked_statement_id: selectedStatement!.id,
          linked_statement_filename: selectedStatement!.original_filename,
          created_at: result.link.created_at,
        });
        toast.success('Transfer linked successfully');
      }
    } catch (e: any) {
      toast.error(e?.message || 'Failed to link transfer');
    } finally {
      setSubmitting(false);
    }
  };

  // For transfers, show the complementary type; for fx_conversion show all
  const filteredTransactions = React.useMemo(() => {
    if (!statementDetail) return [];
    return statementDetail.transactions.filter((t) => {
      if (t.id === sourceTransaction.id) return false;
      if (t.linked_transfer) return false; // already linked
      if (linkType === 'transfer') {
        return t.transaction_type !== sourceTransaction.transaction_type;
      }
      return true;
    });
  }, [statementDetail, sourceTransaction, linkType]);

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-2xl max-h-[85vh] flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <ArrowLeftRight className="w-5 h-5 text-blue-500" />
            Link Transfer
          </DialogTitle>
        </DialogHeader>

        {/* Step indicator */}
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <span className={step === 'pick-statement' ? 'text-primary font-medium' : ''}>1. Select statement</span>
          <ArrowRight className="w-3 h-3" />
          <span className={step === 'pick-transaction' ? 'text-primary font-medium' : ''}>2. Select transaction</span>
          <ArrowRight className="w-3 h-3" />
          <span className={step === 'confirm' ? 'text-primary font-medium' : ''}>3. Confirm</span>
        </div>

        <div className="flex-1 overflow-hidden">
          {/* Step 1: Pick statement */}
          {step === 'pick-statement' && (
            <div className="space-y-3">
              <p className="text-sm text-muted-foreground">
                Source: <span className="font-medium text-foreground">{sourceTransaction.description}</span>{' '}
                <span className={sourceTransaction.transaction_type === 'debit' ? 'text-red-500' : 'text-green-500'}>
                  {formatAmount(sourceTransaction.amount, sourceTransaction.transaction_type)}
                </span>{' '}
                on {safeDate(sourceTransaction.date)}
              </p>
              <Input
                placeholder="Search statements..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="h-8"
              />
              {loadingStatements ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
                </div>
              ) : (
                <ScrollArea className="h-72">
                  <div className="space-y-1 pr-2">
                    {statements
                      .filter((s) =>
                        !search || s.original_filename.toLowerCase().includes(search.toLowerCase())
                      )
                      .map((stmt) => (
                        <button
                          key={stmt.id}
                          onClick={() => handleSelectStatement(stmt)}
                          className="w-full text-left flex items-center gap-3 px-3 py-2 rounded-md hover:bg-accent transition-colors"
                        >
                          <FileText className="w-4 h-4 text-muted-foreground shrink-0" />
                          <div className="min-w-0 flex-1">
                            <p className="text-sm font-medium truncate">{stmt.original_filename}</p>
                            {stmt.created_at && (
                              <p className="text-xs text-muted-foreground">{safeDate(stmt.created_at)}</p>
                            )}
                          </div>
                          <Badge variant="outline" className="shrink-0 text-xs capitalize">
                            {stmt.card_type || 'debit'}
                          </Badge>
                        </button>
                      ))}
                    {!loadingStatements && statements.filter((s) =>
                      !search || s.original_filename.toLowerCase().includes(search.toLowerCase())
                    ).length === 0 && (
                      <p className="text-center text-sm text-muted-foreground py-8">No other statements found</p>
                    )}
                  </div>
                </ScrollArea>
              )}
            </div>
          )}

          {/* Step 2: Pick transaction */}
          {step === 'pick-transaction' && (
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <button onClick={() => setStep('pick-statement')} className="text-xs text-muted-foreground hover:text-foreground underline">
                  ← {selectedStatement?.original_filename}
                </button>
              </div>
              <div className="flex items-center gap-3">
                <Label className="text-xs text-muted-foreground shrink-0">Link type</Label>
                <Select value={linkType} onValueChange={(v) => setLinkType(v as typeof linkType)}>
                  <SelectTrigger className="h-7 w-44 text-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="transfer">Transfer</SelectItem>
                    <SelectItem value="fx_conversion">FX Conversion</SelectItem>
                  </SelectContent>
                </Select>
                <span className="text-xs text-muted-foreground">
                  {linkType === 'transfer' ? 'Showing opposite type only' : 'Showing all transactions'}
                </span>
              </div>
              {loadingDetail ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
                </div>
              ) : (
                <ScrollArea className="h-64">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b text-muted-foreground">
                        <th className="text-left py-1 pr-2">Date</th>
                        <th className="text-left py-1 pr-2">Description</th>
                        <th className="text-right py-1 pr-2">Amount</th>
                        <th className="text-left py-1">Type</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredTransactions.map((txn, i) => (
                        <tr
                          key={txn.id ?? i}
                          onClick={() => handleSelectTransaction(txn)}
                          className="border-b hover:bg-accent cursor-pointer transition-colors"
                        >
                          <td className="py-1.5 pr-2 whitespace-nowrap">{safeDate(txn.date)}</td>
                          <td className="py-1.5 pr-2 max-w-[200px] truncate">{txn.description}</td>
                          <td className={`py-1.5 pr-2 text-right tabular-nums ${txn.transaction_type === 'debit' ? 'text-red-500' : 'text-green-500'}`}>
                            {formatAmount(txn.amount, txn.transaction_type)}
                          </td>
                          <td className="py-1.5">
                            <Badge variant="outline" className="text-[10px] h-4">
                              {txn.transaction_type}
                            </Badge>
                          </td>
                        </tr>
                      ))}
                      {filteredTransactions.length === 0 && (
                        <tr>
                          <td colSpan={4} className="text-center text-muted-foreground py-8">
                            No matching transactions
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </ScrollArea>
              )}
            </div>
          )}

          {/* Step 3: Confirm */}
          {step === 'confirm' && selectedTransaction && (
            <div className="space-y-4">
              <button onClick={() => setStep('pick-transaction')} className="text-xs text-muted-foreground hover:text-foreground underline">
                ← Back
              </button>
              <div className="grid grid-cols-2 gap-4">
                <div className="rounded-lg border p-3 space-y-1">
                  <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide">Source</p>
                  <p className="text-sm font-medium">{sourceTransaction.description}</p>
                  <p className={`text-sm font-semibold ${sourceTransaction.transaction_type === 'debit' ? 'text-red-500' : 'text-green-500'}`}>
                    {formatAmount(sourceTransaction.amount, sourceTransaction.transaction_type)}
                  </p>
                  <p className="text-xs text-muted-foreground">{safeDate(sourceTransaction.date)}</p>
                </div>
                <div className="rounded-lg border p-3 space-y-1 border-blue-200 bg-blue-50/50 dark:border-blue-800 dark:bg-blue-950/20">
                  <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide">Target</p>
                  <p className="text-sm font-medium">{selectedTransaction.description}</p>
                  <p className={`text-sm font-semibold ${selectedTransaction.transaction_type === 'debit' ? 'text-red-500' : 'text-green-500'}`}>
                    {formatAmount(selectedTransaction.amount, selectedTransaction.transaction_type)}
                  </p>
                  <p className="text-xs text-muted-foreground">{safeDate(selectedTransaction.date)}</p>
                  <p className="text-xs text-muted-foreground truncate">{selectedStatement?.original_filename}</p>
                </div>
              </div>
              <div className="space-y-3">
                <div className="flex items-center gap-3">
                  <Label className="text-sm shrink-0">Link type</Label>
                  <Select value={linkType} onValueChange={(v) => setLinkType(v as typeof linkType)}>
                    <SelectTrigger className="h-8 w-44">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="transfer">Transfer</SelectItem>
                      <SelectItem value="fx_conversion">FX Conversion</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-1">
                  <Label className="text-sm">Notes (optional)</Label>
                  <Textarea
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                    placeholder="e.g. Monthly savings transfer, CAD conversion at 1.38"
                    className="resize-none h-16 text-sm"
                  />
                </div>
              </div>
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          {step === 'confirm' && (
            <Button onClick={handleLink} disabled={submitting} className="gap-2">
              {submitting && <Loader2 className="w-4 h-4 animate-spin" />}
              <ArrowLeftRight className="w-4 h-4" />
              Link Transfer
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
