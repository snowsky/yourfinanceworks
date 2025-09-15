import React, { useState, useEffect } from "react";
import { Package, Plus, X, AlertTriangle, DollarSign } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { inventoryApi, InventoryItem } from "@/lib/api";
import { getErrorMessage } from "@/lib/api";
import { toast } from "sonner";
import { useTranslation } from "react-i18next";

interface InventoryPurchaseItem {
  item_id: number;
  quantity: number;
  unit_cost: number;
  item_name?: string;
  sku?: string;
}

interface InventoryPurchaseFormProps {
  onPurchaseItemsChange: (items: InventoryPurchaseItem[]) => void;
  currency: string;
  totalAmount?: number;
}

export const InventoryPurchaseForm: React.FC<InventoryPurchaseFormProps> = ({
  onPurchaseItemsChange,
  currency,
  totalAmount = 0
}) => {
  const { t } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);
  const [items, setItems] = useState<InventoryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [purchaseItems, setPurchaseItems] = useState<InventoryPurchaseItem[]>([]);

  useEffect(() => {
    if (isOpen) {
      fetchItems();
    }
  }, [isOpen]);

  useEffect(() => {
    onPurchaseItemsChange(purchaseItems);
  }, [purchaseItems, onPurchaseItemsChange]);

  const fetchItems = async () => {
    setLoading(true);
    try {
      const itemsData = await inventoryApi.getItems({ limit: 100 });
      setItems(itemsData.items);
    } catch (error) {
      console.error("Failed to fetch inventory items:", error);
      toast.error(getErrorMessage(error, t));
    } finally {
      setLoading(false);
    }
  };

  const addPurchaseItem = (item: InventoryItem) => {
    const existingItem = purchaseItems.find(p => p.item_id === item.id);
    if (existingItem) {
      // Update existing item
      setPurchaseItems(prev => prev.map(p =>
        p.item_id === item.id
          ? { ...p, quantity: p.quantity + 1 }
          : p
      ));
    } else {
      // Add new item
      const newItem: InventoryPurchaseItem = {
        item_id: item.id,
        quantity: 1,
        unit_cost: item.cost_price || item.unit_price,
        item_name: item.name,
        sku: item.sku
      };
      setPurchaseItems(prev => [...prev, newItem]);
    }
  };

  const updatePurchaseItem = (index: number, field: string, value: any) => {
    setPurchaseItems(prev => prev.map((item, i) =>
      i === index ? { ...item, [field]: value } : item
    ));
  };

  const removePurchaseItem = (index: number) => {
    setPurchaseItems(prev => prev.filter((_, i) => i !== index));
  };

  const calculateTotal = () => {
    return purchaseItems.reduce((total, item) => total + (item.quantity * item.unit_cost), 0);
  };

  const filteredItems = items.filter(item => item.is_active);

  return (
    <div className="space-y-4">
      <Dialog open={isOpen} onOpenChange={setIsOpen}>
        <DialogTrigger asChild>
          <Button variant="outline" className="w-full justify-start gap-2">
            <Package className="h-4 w-4" />
            {purchaseItems.length > 0 ? (
              <>
                <span>Add Inventory Items ({purchaseItems.length} selected)</span>
                <Badge variant="secondary">{purchaseItems.length}</Badge>
              </>
            ) : (
              <span>Add Inventory Items</span>
            )}
          </Button>
        </DialogTrigger>

        <DialogContent className="max-w-4xl max-h-[80vh] overflow-hidden">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Package className="h-5 w-5" />
              Select Inventory Items for Purchase
            </DialogTitle>
          </DialogHeader>

          <div className="space-y-4">
            {/* Items Selection */}
            <div className="max-h-64 overflow-y-auto border rounded-lg p-4">
              {loading ? (
                <div className="text-center py-8">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto"></div>
                  <p className="mt-2 text-muted-foreground">Loading inventory items...</p>
                </div>
              ) : filteredItems.length > 0 ? (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {filteredItems.map((item) => {
                    const isSelected = purchaseItems.some(p => p.item_id === item.id);
                    return (
                      <div
                        key={item.id}
                        className={`p-3 border rounded-lg cursor-pointer transition-colors ${
                          isSelected ? 'border-primary bg-primary/5' : 'border-border hover:bg-muted/50'
                        }`}
                        onClick={() => addPurchaseItem(item)}
                      >
                        <div className="flex items-center justify-between">
                          <div className="flex-1 min-w-0">
                            <h4 className="font-medium truncate">{item.name}</h4>
                            <p className="text-sm text-muted-foreground">
                              SKU: {item.sku || 'N/A'}
                            </p>
                            <p className="text-sm text-muted-foreground">
                              Current Stock: {item.track_stock ? item.current_stock : 'Not tracked'}
                            </p>
                          </div>
                          <div className="text-right">
                            <p className="font-medium">${item.unit_price.toFixed(2)}</p>
                            {isSelected && (
                              <Badge variant="default" className="mt-1">
                                Selected
                              </Badge>
                            )}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className="text-center py-8">
                  <Package className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                  <p className="text-muted-foreground">No inventory items found</p>
                  <p className="text-sm text-muted-foreground mt-2">
                    Add some items to your inventory first
                  </p>
                </div>
              )}
            </div>

            {/* Selected Items Summary */}
            {purchaseItems.length > 0 && (
              <div className="bg-muted/50 p-4 rounded-lg">
                <h4 className="font-medium mb-3">Selected Items ({purchaseItems.length})</h4>
                <div className="space-y-2">
                  {purchaseItems.map((item, index) => (
                    <div key={index} className="flex items-center gap-3 p-2 bg-background rounded border">
                      <div className="flex-1">
                        <p className="font-medium">{item.item_name}</p>
                        <p className="text-sm text-muted-foreground">SKU: {item.sku || 'N/A'}</p>
                      </div>
                      <div className="flex items-center gap-2">
                        <Label className="text-sm">Qty:</Label>
                        <Input
                          type="number"
                          min="0.01"
                          step="0.01"
                          value={item.quantity}
                          onChange={(e) => updatePurchaseItem(index, 'quantity', parseFloat(e.target.value) || 0)}
                          className="w-20 h-8"
                        />
                      </div>
                      <div className="flex items-center gap-2">
                        <Label className="text-sm">Cost:</Label>
                        <Input
                          type="number"
                          min="0"
                          step="0.01"
                          value={item.unit_cost}
                          onChange={(e) => updatePurchaseItem(index, 'unit_cost', parseFloat(e.target.value) || 0)}
                          className="w-24 h-8"
                        />
                      </div>
                      <div className="text-right min-w-[80px]">
                        <p className="font-medium">${(item.quantity * item.unit_cost).toFixed(2)}</p>
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => removePurchaseItem(index)}
                        className="text-muted-foreground hover:text-destructive"
                      >
                        <X className="h-4 w-4" />
                      </Button>
                    </div>
                  ))}
                </div>
                <div className="border-t pt-3 mt-3 flex justify-between items-center">
                  <span className="font-medium">Total Purchase Value:</span>
                  <span className="font-bold text-lg">${calculateTotal().toFixed(2)}</span>
                </div>
              </div>
            )}
          </div>

          <div className="flex justify-end gap-2 pt-4 border-t">
            <Button variant="outline" onClick={() => setIsOpen(false)}>
              {purchaseItems.length > 0 ? 'Continue Editing' : 'Cancel'}
            </Button>
            {purchaseItems.length > 0 && (
              <Button onClick={() => setIsOpen(false)}>
                Done ({purchaseItems.length} items)
              </Button>
            )}
          </div>
        </DialogContent>
      </Dialog>

      {/* Purchase Items Summary (when not in dialog) */}
      {purchaseItems.length > 0 && (
        <Card className="bg-purple-50/50 border-purple-200">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Package className="h-5 w-5 text-purple-600" />
                <span className="font-medium text-purple-900">
                  Inventory Purchase: {purchaseItems.length} items
                </span>
              </div>
              <div className="text-right">
                <div className="font-bold text-purple-900">
                  ${calculateTotal().toFixed(2)} {currency}
                </div>
                <div className="text-sm text-purple-700">
                  {purchaseItems.reduce((total, item) => total + item.quantity, 0)} units total
                </div>
              </div>
            </div>

            {/* Validation Warning */}
            {totalAmount > 0 && Math.abs(calculateTotal() - totalAmount) > 0.01 && (
              <div className="mt-3 p-3 bg-orange-50 border border-orange-200 rounded-lg">
                <div className="flex items-center gap-2 text-orange-800">
                  <AlertTriangle className="h-4 w-4" />
                  <span className="text-sm font-medium">Amount Mismatch</span>
                </div>
                <p className="text-sm text-orange-700 mt-1">
                  Purchase total (${calculateTotal().toFixed(2)}) doesn't match expense amount (${totalAmount.toFixed(2)})
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
};
