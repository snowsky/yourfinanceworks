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

interface InventoryConsumptionItem {
  item_id: number;
  quantity: number;
  unit_cost?: number;
  item_name?: string;
  sku?: string;
}

interface InventoryConsumptionFormProps {
  onConsumptionItemsChange: (items: InventoryConsumptionItem[]) => void;
  currency: string;
  initialConsumptionItems?: InventoryConsumptionItem[];
}

export const InventoryConsumptionForm: React.FC<InventoryConsumptionFormProps> = ({
  onConsumptionItemsChange,
  currency,
  initialConsumptionItems = []
}) => {
  const { t } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);
  const [items, setItems] = useState<InventoryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [consumptionItems, setConsumptionItems] = useState<InventoryConsumptionItem[]>(initialConsumptionItems);

  useEffect(() => {
    if (isOpen) {
      fetchItems();
    }
  }, [isOpen]);

  useEffect(() => {
    // Update internal state when initialConsumptionItems changes
    setConsumptionItems(initialConsumptionItems);
  }, [initialConsumptionItems]);

  useEffect(() => {
    onConsumptionItemsChange(consumptionItems);
  }, [consumptionItems, onConsumptionItemsChange]);

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

  const addConsumptionItem = (item: InventoryItem) => {
    const existingItem = consumptionItems.find(c => c.item_id === item.id);
    if (existingItem) {
      // Update existing item
      setConsumptionItems(prev => prev.map(c =>
        c.item_id === item.id
          ? { ...c, quantity: c.quantity + 1 }
          : c
      ));
    } else {
      // Add new item
      const newItem: InventoryConsumptionItem = {
        item_id: item.id,
        quantity: 1,
        unit_cost: item.cost_price || item.unit_price,
        item_name: item.name,
        sku: item.sku
      };
      setConsumptionItems(prev => [...prev, newItem]);
    }
  };

  const updateConsumptionItem = (index: number, field: string, value: any) => {
    if (field === 'quantity') {
      // Validate quantity is positive
      const quantity = parseFloat(value);
      if (isNaN(quantity) || quantity <= 0) {
        toast.error('Quantity must be greater than 0');
        return;
      }
    }

    setConsumptionItems(prev => prev.map((item, i) =>
      i === index ? { ...item, [field]: value } : item
    ));
  };

  const removeConsumptionItem = (index: number) => {
    setConsumptionItems(prev => prev.filter((_, i) => i !== index));
  };

  const calculateTotal = () => {
    return consumptionItems.reduce((total, item) => total + (item.quantity * (item.unit_cost || 0)), 0);
  };

  const filteredItems = items.filter(item => item.is_active && item.track_stock && item.current_stock > 0);

  // Validation helpers
  const hasInvalidQuantities = consumptionItems.some(item => item.quantity <= 0);
  const totalValidItems = consumptionItems.filter(item => item.quantity > 0).length;

  return (
    <div className="space-y-4">
      <Dialog open={isOpen} onOpenChange={setIsOpen}>
        <DialogTrigger asChild>
          <Button variant="outline" className="w-full justify-start gap-2">
            <Package className="h-4 w-4" />
            {consumptionItems.length > 0 ? (
              <>
                <span>Select Inventory Items ({consumptionItems.length} selected)</span>
                <Badge variant="secondary">{consumptionItems.length.toString()}</Badge>
              </>
            ) : (
              <span>Select Inventory Items</span>
            )}
          </Button>
        </DialogTrigger>

        <DialogContent className="max-w-4xl max-h-[80vh] overflow-hidden">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Package className="h-5 w-5" />
              Select Inventory Items for Consumption
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
                    const isSelected = consumptionItems.some(c => c.item_id === item.id);
                    return (
                      <div
                        key={item.id}
                        className={`p-3 border rounded-lg cursor-pointer transition-colors ${
                          isSelected ? 'border-primary bg-primary/5' : 'border-border hover:bg-muted/50'
                        }`}
                        onClick={() => addConsumptionItem(item)}
                      >
                        <div className="flex items-center justify-between">
                          <div className="flex-1 min-w-0">
                            <h4 className="font-medium truncate">{item.name}</h4>
                            <p className="text-sm text-muted-foreground">
                              SKU: {item.sku || 'N/A'}
                            </p>
                            <p className="text-sm text-muted-foreground">
                              Available: {item.current_stock} {item.unit_of_measure}
                            </p>
                            <p className="text-sm font-medium">
                              Cost: ${item.cost_price?.toFixed(2) || item.unit_price.toFixed(2)}
                            </p>
                          </div>
                          <div className="text-right">
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
                  <p className="text-muted-foreground">No inventory items available for consumption</p>
                  <p className="text-sm text-muted-foreground mt-2">
                    Items must be active, track stock, and have available quantity
                  </p>
                </div>
              )}
            </div>

            {/* Selected Items Summary */}
            {consumptionItems.length > 0 && (
              <div className="bg-muted/50 p-4 rounded-lg">
                <h4 className="font-medium mb-3">Selected Items ({consumptionItems.length})</h4>
                <div className="space-y-2">
                  {consumptionItems.map((item, index) => (
                    <div key={index} className="flex items-center gap-3 p-2 bg-background rounded border">
                      <div className="flex-1">
                        <p className="font-medium">{item.item_name}</p>
                        <p className="text-sm text-muted-foreground">SKU: {item.sku || 'N/A'}</p>
                      </div>
                      <div className="flex items-center gap-2">
                        <Label className="text-sm">Qty:</Label>
                        <Input
                          type="number"
                          min="0"
                          step="0.01"
                          value={item.quantity}
                          onChange={(e) => updateConsumptionItem(index, 'quantity', parseFloat(e.target.value) || 0)}
                          className={`w-20 h-8 ${item.quantity <= 0 ? 'border-red-500 focus:border-red-500' : ''}`}
                        />
                        {item.quantity <= 0 && (
                          <span className="text-xs text-red-500">Must be greater than 0</span>
                        )}
                      </div>
                      <div className="flex items-center gap-2">
                        <Label className="text-sm">Cost:</Label>
                        <Input
                          type="number"
                          min="0"
                          step="0.01"
                          value={item.unit_cost || 0}
                          onChange={(e) => updateConsumptionItem(index, 'unit_cost', parseFloat(e.target.value) || 0)}
                          className="w-24 h-8"
                        />
                      </div>
                      <div className="text-right min-w-[80px]">
                        <p className="font-medium">${((item.quantity * (item.unit_cost || 0))).toFixed(2)}</p>
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => removeConsumptionItem(index)}
                        className="text-muted-foreground hover:text-destructive"
                      >
                        <X className="h-4 w-4" />
                      </Button>
                    </div>
                  ))}
                </div>
                <div className="border-t pt-3 mt-3 flex justify-between items-center">
                  <span className="font-medium">Total Consumption Value:</span>
                  <span className="font-bold text-lg">${calculateTotal().toFixed(2)}</span>
                </div>
              </div>
            )}
          </div>

          <div className="flex justify-end gap-2 pt-4 border-t">
            <Button variant="outline" onClick={() => setIsOpen(false)}>
              {consumptionItems.length > 0 ? 'Continue Editing' : 'Cancel'}
            </Button>
            {consumptionItems.length > 0 && (
              <Button
                onClick={() => {
                  if (hasInvalidQuantities) {
                    toast.error('Please fix invalid quantities (must be greater than 0) before continuing');
                    return;
                  }
                  setIsOpen(false);
                }}
                disabled={hasInvalidQuantities}
              >
                Done ({totalValidItems} valid items)
              </Button>
            )}
          </div>
        </DialogContent>
      </Dialog>

      {/* Consumption Items Summary (when not in dialog) */}
      {consumptionItems.length > 0 && (
        <Card className="bg-orange-50/50 border-orange-200">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Package className="h-5 w-5 text-orange-600" />
                <span className="font-medium text-orange-900">
                  Inventory Consumption: {consumptionItems.length} items
                </span>
              </div>
              <div className="text-right">
                <div className="font-bold text-orange-900">
                  ${calculateTotal().toFixed(2)} {currency}
                </div>
                <div className="text-sm text-orange-700">
                  {consumptionItems.reduce((total, item) => total + item.quantity, 0)} units total
                </div>
              </div>
            </div>

            {/* Warning about stock reduction */}
            <div className="mt-3 p-3 bg-orange-50 border border-orange-200 rounded-lg">
              <div className="flex items-center gap-2 text-orange-800">
                <AlertTriangle className="h-4 w-4" />
                <span className="text-sm font-medium">Stock Impact Warning</span>
              </div>
              <p className="text-sm text-orange-700 mt-1">
                These items will be marked as consumed and stock levels will be reduced when you save the expense.
              </p>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
};
