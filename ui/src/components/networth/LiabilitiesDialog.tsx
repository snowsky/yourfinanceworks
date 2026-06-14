import React, { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Trash2 } from 'lucide-react';

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  networthApi,
  type LiabilityKind,
  type LiabilityResponse,
} from '@/lib/api/networth';
import { formatCurrency, KIND_LABELS } from './networth-helpers';

interface Props {
  open: boolean;
  onClose: () => void;
  /** When provided, the form is in edit mode (PATCH); otherwise create mode (POST). */
  liability?: LiabilityResponse | null;
}

const KINDS: LiabilityKind[] = ['credit_card', 'loan', 'mortgage', 'other'];

export const LiabilitiesDialog: React.FC<Props> = ({ open, onClose, liability }) => {
  const qc = useQueryClient();
  const editing = liability ?? null;

  const [name, setName] = useState('');
  const [kind, setKind] = useState<LiabilityKind>('credit_card');
  const [balance, setBalance] = useState('');
  const [interestRate, setInterestRate] = useState('');
  const [notes, setNotes] = useState('');

  // Sync form to the row being edited (or reset for add) whenever it changes / dialog opens.
  useEffect(() => {
    if (editing) {
      setName(editing.name);
      setKind(editing.kind);
      setBalance(String(editing.balance ?? ''));
      setInterestRate(editing.interest_rate != null ? String(editing.interest_rate) : '');
      setNotes(editing.notes ?? '');
    } else {
      setName('');
      setKind('credit_card');
      setBalance('');
      setInterestRate('');
      setNotes('');
    }
  }, [editing, open]);

  const { data: liabilities = [], isLoading } = useQuery({
    queryKey: ['networth', 'liabilities'],
    queryFn: () => networthApi.listLiabilities(),
    enabled: open && !editing,
  });

  const body = () => ({
    name: name.trim(),
    kind,
    balance: parseFloat(balance) || 0,
    interest_rate: interestRate.trim() === '' ? null : parseFloat(interestRate),
    notes: notes.trim() === '' ? null : notes.trim(),
  });

  const saveMutation = useMutation({
    mutationFn: () =>
      editing
        ? networthApi.updateLiability(editing.id, body())
        : networthApi.createLiability(body()),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['networth'] });
      if (editing) {
        onClose();
      } else {
        setName('');
        setBalance('');
        setInterestRate('');
        setNotes('');
      }
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => networthApi.deleteLiability(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['networth'] }),
  });

  const canSave = name.trim().length > 0 && (parseFloat(balance) || 0) >= 0;

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>{editing ? 'Edit liability' : 'Manage liabilities'}</DialogTitle>
          <DialogDescription>
            Liabilities are subtracted from your bank and investment balances to compute
            net worth. Update these whenever a balance changes.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label htmlFor="liability-name">Name</Label>
              <Input
                id="liability-name"
                placeholder="e.g. Chase Sapphire"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </div>
            <div>
              <Label htmlFor="liability-kind">Kind</Label>
              <Select value={kind} onValueChange={(v) => setKind(v as LiabilityKind)}>
                <SelectTrigger id="liability-kind">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {KINDS.map((k) => (
                    <SelectItem key={k} value={k}>
                      {KIND_LABELS[k]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label htmlFor="liability-balance">Balance</Label>
              <Input
                id="liability-balance"
                type="number"
                min={0}
                step="0.01"
                placeholder="0.00"
                value={balance}
                onChange={(e) => setBalance(e.target.value)}
              />
            </div>
            <div>
              <Label htmlFor="liability-rate">Interest rate (%)</Label>
              <Input
                id="liability-rate"
                type="number"
                min={0}
                max={100}
                step="0.01"
                placeholder="optional"
                value={interestRate}
                onChange={(e) => setInterestRate(e.target.value)}
              />
            </div>
            <div className="col-span-2">
              <Label htmlFor="liability-notes">Notes</Label>
              <Input
                id="liability-notes"
                placeholder="optional"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
              />
            </div>
          </div>

          <div className="flex justify-end">
            <Button disabled={!canSave || saveMutation.isPending} onClick={() => saveMutation.mutate()}>
              {editing ? 'Save' : 'Add liability'}
            </Button>
          </div>

          {!editing ? (
            <div className="rounded border">
              {isLoading ? (
                <div className="p-4 text-sm text-muted-foreground">Loading…</div>
              ) : liabilities.length === 0 ? (
                <div className="p-4 text-sm text-muted-foreground">
                  No liabilities yet. Add one above.
                </div>
              ) : (
                <table className="w-full text-sm">
                  <thead className="bg-muted/50">
                    <tr>
                      <th className="p-2 text-left">Name</th>
                      <th className="p-2 text-left">Kind</th>
                      <th className="p-2 text-right">Balance</th>
                      <th className="p-2"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {liabilities.map((liab: LiabilityResponse) => (
                      <tr key={liab.id} className="border-t">
                        <td className="p-2">{liab.name}</td>
                        <td className="p-2 text-muted-foreground">
                          {KIND_LABELS[liab.kind] ?? liab.kind}
                        </td>
                        <td className="p-2 text-right">
                          {formatCurrency(liab.balance, liab.currency)}
                        </td>
                        <td className="p-2 text-right">
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => deleteMutation.mutate(liab.id)}
                            disabled={deleteMutation.isPending}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          ) : null}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            {editing ? 'Cancel' : 'Done'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
