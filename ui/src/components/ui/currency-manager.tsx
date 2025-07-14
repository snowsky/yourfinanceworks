import React, { useState, useEffect } from 'react';
import { Button } from './button';
import { Card, CardContent, CardHeader, CardTitle } from './card';
import { Input } from './input';
import { Label } from './label';
import { Switch } from './switch';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from './dialog';
import { Badge } from './badge';
import { Trash2, Edit, Plus, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { currencyApi } from '@/lib/api';
import { apiRequest } from '@/lib/api';

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
  const [currencies, setCurrencies] = useState<Currency[]>([]);
  const [loading, setLoading] = useState(true);
  const [showDialog, setShowDialog] = useState(false);
  const [editingCurrency, setEditingCurrency] = useState<Currency | null>(null);
  const [newCurrency, setNewCurrency] = useState<CurrencyCreate>({
    code: '',
    name: '',
    symbol: '',
    decimal_places: 2,
    is_active: true,
  });

  useEffect(() => {
    fetchCurrencies();
  }, []);

  const fetchCurrencies = async () => {
    try {
      setLoading(true);
      const response = await currencyApi.getSupportedCurrencies();
      setCurrencies(response.currencies || []);
    } catch (error) {
      console.error('Failed to fetch currencies:', error);
      toast.error('Failed to load currencies');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateCurrency = async () => {
    try {
      if (!newCurrency.code || !newCurrency.name || !newCurrency.symbol) {
        toast.error('Please fill in all required fields');
        return;
      }

      await currencyApi.createCustomCurrency(newCurrency);
      toast.success('Currency created successfully');
      setShowDialog(false);
      setNewCurrency({
        code: '',
        name: '',
        symbol: '',
        decimal_places: 2,
        is_active: true,
      });
      fetchCurrencies();
    } catch (error: any) {
      console.error('Failed to create currency:', error);
      toast.error(error.message || 'Failed to create currency');
    }
  };

  const checkCurrencyUsage = async (currencyCode: string): Promise<{ used: boolean; count: number }> => {
    try {
      // Check if currency is used in invoices
      const invoices = await apiRequest<any[]>('/invoices/');
      const invoiceCount = (invoices || []).filter(invoice => invoice.currency === currencyCode).length;
      
      // Check if currency is used in payments
      const payments = await apiRequest<any[]>('/payments/');
      const paymentCount = (payments || []).filter(payment => payment.currency === currencyCode).length;
      
      const totalCount = invoiceCount + paymentCount;
      return { used: totalCount > 0, count: totalCount };
    } catch (error) {
      console.error('Failed to check currency usage:', error);
      return { used: false, count: 0 };
    }
  };

  const handleUpdateCurrency = async (currency: Currency, updates: CurrencyUpdate) => {
    try {
      // If trying to disable a currency, check if it's used
      if (updates.is_active === false) {
        const usage = await checkCurrencyUsage(currency.code);
        if (usage.used) {
          toast.error(`Cannot disable ${currency.name} (${currency.code}) as it is used in ${usage.count} invoice(s) or payment(s). Please update or delete those records first.`);
          return;
        }
      }

      await currencyApi.updateCustomCurrency(currency.id, updates);
      toast.success('Currency updated successfully');
      fetchCurrencies();
    } catch (error: any) {
      console.error('Failed to update currency:', error);
      toast.error(error.message || 'Failed to update currency');
    }
  };

  const handleDeleteCurrency = async (currency: Currency) => {
    if (!confirm(`Are you sure you want to delete ${currency.name} (${currency.code})?`)) {
      return;
    }

    try {
      await currencyApi.deleteCustomCurrency(currency.id);
      toast.success('Currency deleted successfully');
      fetchCurrencies();
    } catch (error: any) {
      console.error('Failed to delete currency:', error);
      toast.error(error.message || 'Failed to delete currency');
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

  const handleSave = async () => {
    if (editingCurrency) {
      await handleUpdateCurrency(editingCurrency, {
        name: newCurrency.name,
        symbol: newCurrency.symbol,
        decimal_places: newCurrency.decimal_places,
        is_active: newCurrency.is_active,
      });
    } else {
      await handleCreateCurrency();
    }
  };

  if (loading) {
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
          <h3 className="text-lg font-medium">Custom Currencies</h3>
          <p className="text-sm text-muted-foreground">
            Add your own currencies like Bitcoin, Ethereum, or other cryptocurrencies
          </p>
        </div>
        <Button onClick={openCreateDialog} size="sm">
          <Plus className="h-4 w-4 mr-2" />
          Add Currency
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
                    onCheckedChange={(checked) =>
                      handleUpdateCurrency(currency, { is_active: checked })
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
                    onClick={() => handleDeleteCurrency(currency)}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
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
            <div className="flex justify-end space-x-2">
              <Button variant="outline" onClick={() => setShowDialog(false)}>
                Cancel
              </Button>
              <Button onClick={handleSave}>
                {editingCurrency ? 'Update' : 'Create'}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
} 