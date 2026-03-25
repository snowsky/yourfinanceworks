import React, { useState } from 'react';
import { Button } from './button';
import { Card, CardContent } from './card';
import { Input } from './input';
import { Label } from './label';
import { Switch } from './switch';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from './dialog';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from './alert-dialog';
import { Badge } from './badge';
import { Trash2, Edit, Plus, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { currencyApi, apiRequest, getErrorMessage } from '@/lib/api';
import { useTranslation } from 'react-i18next';
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";

interface Currency {
  id: number;
  code: string;
  name: string;
  symbol: string;
  decimal_places: number;
  is_active: boolean;
  created_at: string;
}

interface CurrencyCreate {
  code: string;
  name: string;
  symbol: string;
  decimal_places: number;
  is_active: boolean;
}

interface CurrencyUpdate {
  name?: string;
  symbol?: string;
  decimal_places?: number;
  is_active?: boolean;
}

export function CurrencyManager() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();

  const [showDialog, setShowDialog] = useState(false);
  const [editingCurrency, setEditingCurrency] = useState<Currency | null>(null);
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [currencyToDelete, setCurrencyToDelete] = useState<Currency | null>(null);
  const [newCurrency, setNewCurrency] = useState<CurrencyCreate>({
    code: '',
    name: '',
    symbol: '',
    decimal_places: 2,
    is_active: true,
  });

  const { data: currencies = [], isLoading } = useQuery({
    queryKey: ['currencies'],
    queryFn: () => currencyApi.getSupportedCurrencies(),
  });

  const createMutation = useMutation({
    mutationFn: (data: CurrencyCreate) => currencyApi.createCustomCurrency(data),
    onSuccess: () => {
      toast.success('Currency created successfully');
      queryClient.invalidateQueries({ queryKey: ['currencies'] });
      setShowDialog(false);
    },
    onError: (error) => {
      toast.error(getErrorMessage(error, t));
    }
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, updates }: { id: number; updates: CurrencyUpdate }) => currencyApi.updateCustomCurrency(id, updates),
    onSuccess: () => {
      toast.success('Currency updated successfully');
      queryClient.invalidateQueries({ queryKey: ['currencies'] });
    },
    onError: (error) => {
      toast.error(getErrorMessage(error, t));
    }
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => currencyApi.deleteCustomCurrency(id),
    onSuccess: () => {
      toast.success('Currency deleted successfully');
      queryClient.invalidateQueries({ queryKey: ['currencies'] });
    },
    onError: (error) => {
      toast.error(getErrorMessage(error, t));
    }
  });

  const checkCurrencyUsage = async (currencyCode: string): Promise<{ used: boolean; count: number }> => {
    try {
      const invoices = await apiRequest<any[]>('/invoices/');
      const invoiceCount = Array.isArray(invoices) ? invoices.filter(invoice => invoice.currency === currencyCode).length : 0;

      const payments = await apiRequest<any[]>('/payments/');
      const paymentCount = Array.isArray(payments) ? payments.filter(payment => payment.currency === currencyCode).length : 0;

      const totalCount = invoiceCount + paymentCount;
      return { used: totalCount > 0, count: totalCount };
    } catch (error) {
      console.error('Failed to check currency usage:', error);
      return { used: false, count: 0 };
    }
  };

  const handleUpdateActive = async (currency: Currency, checked: boolean) => {
    if (checked === false) {
      const usage = await checkCurrencyUsage(currency.code);
      if (usage.used) {
        toast.error(`Cannot disable ${currency.name} (${currency.code}) as it is used in ${usage.count} invoice(s) or payment(s).`);
        return;
      }
    }
    updateMutation.mutate({ id: currency.id, updates: { is_active: checked } });
  };

  const handleSave = async () => {
    if (!newCurrency.code || !newCurrency.name || !newCurrency.symbol) {
      toast.error('Please fill in all required fields');
      return;
    }

    if (editingCurrency) {
      updateMutation.mutate({
        id: editingCurrency.id,
        updates: {
          name: newCurrency.name,
          symbol: newCurrency.symbol,
          decimal_places: newCurrency.decimal_places,
          is_active: newCurrency.is_active,
        }
      }, {
        onSuccess: () => setShowDialog(false)
      });
    } else {
      createMutation.mutate(newCurrency);
    }
  };

  const openEditDialog = (currency: Currency) => {
    setEditingCurrency(currency);
    setNewCurrency({
      code: currency.code,
      name: currency.name,
      symbol: currency.symbol,
      decimal_places: currency.decimal_places,
      is_active: currency.is_active,
    });
    setShowDialog(true);
  };

  const openCreateDialog = () => {
    setEditingCurrency(null);
    setNewCurrency({
      code: '',
      name: '',
      symbol: '',
      decimal_places: 2,
      is_active: true,
    });
    setShowDialog(true);
  };

  const handleDeleteClick = (currency: Currency) => {
    setCurrencyToDelete(currency);
    setDeleteModalOpen(true);
  };

  const confirmDelete = () => {
    if (currencyToDelete) {
      deleteMutation.mutate(currencyToDelete.id, {
        onSettled: () => {
          setDeleteModalOpen(false);
          setCurrencyToDelete(null);
        }
      });
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center p-8">
        <Loader2 className="h-8 w-8 animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold">{t('currency_manager.custom_currencies')}</h3>
          <p className="text-sm text-muted-foreground">
            {t('currency_manager.custom_currencies_description')}
          </p>
        </div>
        <Button onClick={openCreateDialog} size="sm">
          <Plus className="h-4 w-4 mr-2" />
          {t('currency_manager.add_currency')}
        </Button>
      </div>

      <div className="grid gap-4">
        {currencies.map((currency) => (
          <Card key={currency.id}>
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-4">
                  <div>
                    <div className="flex items-center space-x-2">
                      <span className="font-medium">{currency.name}</span>
                      <Badge variant="outline">{currency.code}</Badge>
                      {!currency.is_active && (
                        <Badge variant="secondary">Inactive</Badge>
                      )}
                    </div>
                    <div className="text-sm text-muted-foreground">
                      Symbol: {currency.symbol} • Decimals: {currency.decimal_places}
                    </div>
                  </div>
                </div>
                <div className="flex items-center space-x-2">
                  <Switch
                    checked={currency.is_active}
                    disabled={updateMutation.isPending}
                    onCheckedChange={(checked) =>
                      handleUpdateActive(currency, checked)
                    }
                  />
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => openEditDialog(currency)}
                  >
                    <Edit className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-destructive hover:bg-destructive/10"
                    onClick={() => handleDeleteClick(currency)}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
        {currencies.length === 0 && (
          <div className="text-center py-12 bg-muted/10 rounded-xl border-2 border-dashed border-border">
            <p className="text-muted-foreground font-medium">No custom currencies found</p>
          </div>
        )}
      </div>

      <Dialog open={showDialog} onOpenChange={setShowDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {editingCurrency ? 'Edit Currency' : 'Add Custom Currency'}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="code">Currency Code</Label>
                <Input
                  id="code"
                  value={newCurrency.code}
                  onChange={(e) =>
                    setNewCurrency({ ...newCurrency, code: e.target.value.toUpperCase() })
                  }
                  placeholder="BTC"
                  disabled={!!editingCurrency}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="symbol">Symbol</Label>
                <Input
                  id="symbol"
                  value={newCurrency.symbol}
                  onChange={(e) =>
                    setNewCurrency({ ...newCurrency, symbol: e.target.value })
                  }
                  placeholder="₿"
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="name">Currency Name</Label>
              <Input
                id="name"
                value={newCurrency.name}
                onChange={(e) =>
                  setNewCurrency({ ...newCurrency, name: e.target.value })
                }
                placeholder="Bitcoin"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="decimal_places">Decimal Places</Label>
              <Input
                id="decimal_places"
                type="number"
                min="0"
                max="8"
                value={newCurrency.decimal_places}
                onChange={(e) =>
                  setNewCurrency({
                    ...newCurrency,
                    decimal_places: parseInt(e.target.value) || 2,
                  })
                }
              />
            </div>
            <div className="flex items-center space-x-2">
              <Switch
                id="is_active"
                checked={newCurrency.is_active}
                onCheckedChange={(checked) =>
                  setNewCurrency({ ...newCurrency, is_active: checked })
                }
              />
              <Label htmlFor="is_active">Active</Label>
            </div>
            <div className="flex justify-end space-x-2 pt-4">
              <Button variant="outline" onClick={() => setShowDialog(false)}>
                Cancel
              </Button>
              <Button
                onClick={handleSave}
                disabled={createMutation.isPending || updateMutation.isPending}
              >
                {createMutation.isPending || updateMutation.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  editingCurrency ? 'Update' : 'Create'
                )}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      <AlertDialog open={deleteModalOpen} onOpenChange={setDeleteModalOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Currency</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete {currencyToDelete?.name} ({currencyToDelete?.code})? This action cannot be undone and the currency will be completely removed from the system.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={confirmDelete}
              disabled={deleteMutation.isPending}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {deleteMutation.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Trash2 className="mr-2 h-4 w-4" />
              )}
              Delete Currency
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}