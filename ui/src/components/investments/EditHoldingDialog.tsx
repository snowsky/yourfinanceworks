import React, { useState, useEffect } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { api } from '@/lib/api';
import { toast } from 'sonner';

interface Holding {
  id: number;
  portfolio_id: number;
  security_symbol: string;
  security_name?: string;
  security_type: string;
  asset_class: string;
  quantity: number;
  cost_basis: number;
  purchase_date: string;
  current_price?: number;
  price_updated_at?: string;
  is_closed: boolean;
  average_cost_per_share: number;
  current_value: number;
  unrealized_gain_loss: number;
  created_at: string;
  updated_at: string;
}

interface EditHoldingDialogProps {
  holding: Holding;
  portfolioId: number;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const SECURITY_TYPES = [
  { value: 'stock', label: 'Stock' },
  { value: 'bond', label: 'Bond' },
  { value: 'mutual_fund', label: 'Mutual Fund' },
  { value: 'etf', label: 'ETF' },
  { value: 'cash', label: 'Cash' },
];

const ASSET_CLASSES = [
  { value: 'stocks', label: 'Stocks' },
  { value: 'bonds', label: 'Bonds' },
  { value: 'cash', label: 'Cash' },
  { value: 'real_estate', label: 'Real Estate' },
  { value: 'commodities', label: 'Commodities' },
];

const EditHoldingDialog: React.FC<EditHoldingDialogProps> = ({
  holding,
  portfolioId,
  open,
  onOpenChange,
}) => {
  const queryClient = useQueryClient();
  const [formData, setFormData] = useState({
    security_name: holding.security_name || '',
    security_type: holding.security_type,
    asset_class: holding.asset_class,
    quantity: holding.quantity.toString(),
    cost_basis: holding.cost_basis.toString(),
  });

  const [priceData, setPriceData] = useState({
    current_price: holding.current_price?.toString() || '',
  });

  useEffect(() => {
    setFormData({
      security_name: holding.security_name || '',
      security_type: holding.security_type,
      asset_class: holding.asset_class,
      quantity: holding.quantity.toString(),
      cost_basis: holding.cost_basis.toString(),
    });
    setPriceData({
      current_price: holding.current_price?.toString() || '',
    });
  }, [holding, open]);

  const updateHoldingMutation = useMutation({
    mutationFn: async (data: typeof formData) => {
      const payload = {
        ...data,
        quantity: parseFloat(data.quantity),
        cost_basis: parseFloat(data.cost_basis),
      };
      await api.put(`/investments/holdings/${holding.id}`, payload);
    },
    onSuccess: () => {
      toast.success('Holding updated successfully');
      queryClient.invalidateQueries({ queryKey: ['holdings', portfolioId] });
      onOpenChange(false);
    },
    onError: (error: any) => {
      const errorMessage = error?.response?.data?.detail || 'Failed to update holding';
      toast.error(errorMessage);
    },
  });

  const updatePriceMutation = useMutation({
    mutationFn: async (data: typeof priceData) => {
      const payload = {
        current_price: parseFloat(data.current_price),
      };
      // Use PUT instead of PATCH since the API client doesn't have patch method
      await api.put(`/investments/holdings/${holding.id}/price`, payload);
    },
    onSuccess: () => {
      toast.success('Price updated successfully');
      queryClient.invalidateQueries({ queryKey: ['holdings', portfolioId] });
    },
    onError: (error: any) => {
      const errorMessage = error?.response?.data?.detail || 'Failed to update price';
      toast.error(errorMessage);
    },
  });

  const handleUpdateHolding = (e: React.FormEvent) => {
    e.preventDefault();

    if (!formData.quantity || parseFloat(formData.quantity) <= 0) {
      toast.error('Quantity must be greater than 0');
      return;
    }
    if (!formData.cost_basis || parseFloat(formData.cost_basis) <= 0) {
      toast.error('Cost basis must be greater than 0');
      return;
    }

    updateHoldingMutation.mutate(formData);
  };

  const handleUpdatePrice = (e: React.FormEvent) => {
    e.preventDefault();

    if (!priceData.current_price || parseFloat(priceData.current_price) <= 0) {
      toast.error('Price must be greater than 0');
      return;
    }

    updatePriceMutation.mutate(priceData);
  };

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD'
    }).format(amount);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>Edit Holding</DialogTitle>
          <DialogDescription>
            {holding.security_symbol} - {holding.security_name || 'No name'}
          </DialogDescription>
        </DialogHeader>

        <Tabs defaultValue="details" className="w-full">
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="details">Details</TabsTrigger>
            <TabsTrigger value="price">Price</TabsTrigger>
          </TabsList>

          {/* Details Tab */}
          <TabsContent value="details" className="space-y-4">
            <form onSubmit={handleUpdateHolding} className="space-y-4">
              {/* Security Name */}
              <div className="space-y-2">
                <Label htmlFor="name">Security Name</Label>
                <Input
                  id="name"
                  placeholder="e.g., Apple Inc."
                  value={formData.security_name}
                  onChange={(e) => setFormData({ ...formData, security_name: e.target.value })}
                />
              </div>

              {/* Security Type */}
              <div className="space-y-2">
                <Label htmlFor="type">Security Type</Label>
                <Select
                  value={formData.security_type}
                  onValueChange={(value) =>
                    setFormData({ ...formData, security_type: value })
                  }
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {SECURITY_TYPES.map((type) => (
                      <SelectItem key={type.value} value={type.value}>
                        {type.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Asset Class */}
              <div className="space-y-2">
                <Label htmlFor="asset-class">Asset Class</Label>
                <Select
                  value={formData.asset_class}
                  onValueChange={(value) =>
                    setFormData({ ...formData, asset_class: value })
                  }
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {ASSET_CLASSES.map((assetClass) => (
                      <SelectItem key={assetClass.value} value={assetClass.value}>
                        {assetClass.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Quantity */}
              <div className="space-y-2">
                <Label htmlFor="quantity">Quantity</Label>
                <Input
                  id="quantity"
                  type="number"
                  step="0.0001"
                  value={formData.quantity}
                  onChange={(e) => setFormData({ ...formData, quantity: e.target.value })}
                  required
                />
              </div>

              {/* Cost Basis */}
              <div className="space-y-2">
                <Label htmlFor="cost-basis">Total Cost Basis</Label>
                <Input
                  id="cost-basis"
                  type="number"
                  step="0.01"
                  value={formData.cost_basis}
                  onChange={(e) => setFormData({ ...formData, cost_basis: e.target.value })}
                  required
                />
              </div>

              {/* Info */}
              <div className="bg-primary/10 p-3 rounded text-sm text-primary">
                <p>Average cost per share: {formatCurrency(holding.average_cost_per_share)}</p>
              </div>

              {/* Actions */}
              <div className="flex gap-4 pt-4">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => onOpenChange(false)}
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  disabled={updateHoldingMutation.isPending}
                >
                  {updateHoldingMutation.isPending ? 'Updating...' : 'Update Holding'}
                </Button>
              </div>
            </form>
          </TabsContent>

          {/* Price Tab */}
          <TabsContent value="price" className="space-y-4">
            <form onSubmit={handleUpdatePrice} className="space-y-4">
              {/* Current Price */}
              <div className="space-y-2">
                <Label htmlFor="current-price">Current Price per Share</Label>
                <Input
                  id="current-price"
                  type="number"
                  step="0.01"
                  placeholder="e.g., 150.50"
                  value={priceData.current_price}
                  onChange={(e) => setPriceData({ current_price: e.target.value })}
                  required
                />
              </div>

              {/* Info */}
              <div className="space-y-2 bg-muted p-3 rounded text-sm">
                <p>
                  <span className="font-medium">Current Value:</span> {formatCurrency(holding.current_value)}
                </p>
                <p>
                  <span className="font-medium">Unrealized Gain/Loss:</span>{' '}
                  <span className={holding.unrealized_gain_loss >= 0 ? 'text-success' : 'text-destructive'}>
                    {formatCurrency(holding.unrealized_gain_loss)}
                  </span>
                </p>
                {holding.price_updated_at && (
                  <p>
                    <span className="font-medium">Last Updated:</span>{' '}
                    {new Date(holding.price_updated_at).toLocaleString()}
                  </p>
                )}
              </div>

              {/* Actions */}
              <div className="flex gap-4 pt-4">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => onOpenChange(false)}
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  disabled={updatePriceMutation.isPending}
                >
                  {updatePriceMutation.isPending ? 'Updating...' : 'Update Price'}
                </Button>
              </div>
            </form>
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
  );
};

export default EditHoldingDialog;
