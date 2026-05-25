import React, { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus, Trash2 } from 'lucide-react';

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
}

const KINDS: LiabilityKind[] = ['credit_card', 'loan', 'mortgage', 'other'];

export const LiabilitiesDialog: React.FC<Props> = ({ open, onClose }) => {
  const qc = useQueryClient();
  const [name, setName] = useState('');
  const [kind, setKind] = useState<LiabilityKind>('credit_card');
  const [balance, setBalance] = useState('');

  const { data: liabilities = [], isLoading } = useQuery({
    queryKey: ['networth', 'liabilities'],
    queryFn: () => networthApi.listLiabilities(),
    enabled: open,
  });

  const createMutation = useMutation({
    mutationFn: () =>
      networthApi.createLiability({
        name: name.trim(),
        kind,
        balance: parseFloat(balance) || 0,
      }),
    onSuccess: () => {
      setName('');
      setBalance('');
      qc.invalidateQueries({ queryKey: ['networth'] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => networthApi.deleteLiability(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['networth'] });
    },
  });

  const canCreate = name.trim().length > 0 && parseFloat(balance) >= 0;

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Manage liabilities</DialogTitle>
          <DialogDescription>
            Liabilities are subtracted from your bank and investment balances
            to compute net worth. Update these whenever a balance changes.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="grid grid-cols-12 gap-2 items-end">
            <div className="col-span-5">
              <Label htmlFor="liability-name">Name</Label>
              <Input
                id="liability-name"
                placeholder="e.g. Chase Sapphire"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </div>
            <div className="col-span-3">
              <Label>Kind</Label>
              <Select
                value={kind}
                onValueChange={(v) => setKind(v as LiabilityKind)}
              >
                <SelectTrigger>
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
            <div className="col-span-3">
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
            <div className="col-span-1">
              <Button
                size="sm"
                disabled={!canCreate || createMutation.isPending}
                onClick={() => createMutation.mutate()}
              >
                <Plus className="h-4 w-4" />
              </Button>
            </div>
          </div>

          <div className="border rounded">
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
                    <th className="text-left p-2">Name</th>
                    <th className="text-left p-2">Kind</th>
                    <th className="text-right p-2">Balance</th>
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
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Done
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
