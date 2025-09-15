import React, { useState, useEffect } from "react";
import { X, AlertTriangle, Package, DollarSign } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { InventoryItemSelector } from "./InventoryItemSelector";
import { inventoryApi } from "@/lib/api";
import { getErrorMessage } from "@/lib/api";
import { toast } from "sonner";
import { useTranslation } from "react-i18next";

interface InventoryInvoiceItemProps {
  item: {
    id?: number;
    description: string;
    quantity: number;
    price: number;
    amount: number;
    inventory_item_id?: number;
    unit_of_measure?: string;
  };
  onChange: (item: any) => void;
  onRemove: () => void;
  index: number;
  currency?: string;
}

export const InventoryInvoiceItem: React.FC<InventoryInvoiceItemProps> = ({
  item,
  onChange,
  onRemove,
  index,
  currency = "USD"
}) => {
  const { t } = useTranslation();
  const [stockCheckResult, setStockCheckResult] = useState<{
    is_available: boolean;
    message: string;
    available_stock?: number;
  } | null>(null);

  // Check stock availability when quantity or inventory item changes
  useEffect(() => {
    const checkStockAvailability = async () => {
      if (item.inventory_item_id && item.quantity > 0) {
        try {
          const result = await inventoryApi.checkStockAvailability(item.inventory_item_id, item.quantity);
          setStockCheckResult({
            is_available: result.available >= item.quantity,
            message: result.available >= item.quantity
              ? "Stock available"
              : `Only ${result.available} units available`,
            available_stock: result.available
          });
        } catch (error) {
          console.error("Failed to check stock availability:", error);
          setStockCheckResult(null);
        }
      } else {
        setStockCheckResult(null);
      }
    };

    checkStockAvailability();
  }, [item.inventory_item_id, item.quantity]);

  const handleInventoryItemSelect = (inventoryData: any) => {
    const updatedItem = {
      ...item,
      inventory_item_id: inventoryData.inventory_item_id,
      description: item.description || inventoryData.description,
      price: item.price || inventoryData.price,
      unit_of_measure: inventoryData.unit_of_measure,
      // Recalculate amount
      amount: item.quantity * (item.price || inventoryData.price)
    };
    onChange(updatedItem);
  };

  const handleFieldChange = (field: string, value: any) => {
    let updatedItem = { ...item, [field]: value };

    // Recalculate amount when quantity or price changes
    if (field === 'quantity' || field === 'price') {
      updatedItem.amount = updatedItem.quantity * updatedItem.price;
    }

    onChange(updatedItem);
  };

  const clearInventoryItem = () => {
    const updatedItem = {
      ...item,
      inventory_item_id: undefined,
      unit_of_measure: undefined
    };
    onChange(updatedItem);
    setStockCheckResult(null);
  };

  return (
    <Card className="relative">
      <CardContent className="p-4">
        <div className="space-y-4">
          {/* Header with remove button */}
          <div className="flex items-center justify-between">
            <h4 className="font-medium">Item #{index + 1}</h4>
            <Button
              variant="ghost"
              size="sm"
              onClick={onRemove}
              className="text-muted-foreground hover:text-destructive"
            >
              <X className="h-4 w-4" />
            </Button>
          </div>

          {/* Inventory Item Selector */}
          <div className="space-y-2">
            <Label htmlFor={`inventory-${index}`}>Inventory Item (Optional)</Label>
            <div className="flex gap-2">
              <div className="flex-1">
                <InventoryItemSelector
                  onItemSelect={handleInventoryItemSelect}
                  selectedItemId={item.inventory_item_id}
                />
              </div>
              {item.inventory_item_id && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={clearInventoryItem}
                  className="px-3"
                >
                  Clear
                </Button>
              )}
            </div>

            {/* Inventory Item Info */}
            {item.inventory_item_id && (
              <div className="bg-muted/50 p-3 rounded-lg space-y-2">
                <div className="flex items-center gap-2 text-sm">
                  <Package className="h-4 w-4 text-primary" />
                  <span className="font-medium">Linked to inventory item</span>
                </div>

                {item.unit_of_measure && (
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <span>Unit of Measure:</span>
                    <Badge variant="outline">{item.unit_of_measure}</Badge>
                  </div>
                )}

                {/* Stock Status */}
                {stockCheckResult && (
                  <div className={`flex items-center gap-2 text-sm p-2 rounded ${
                    stockCheckResult.is_available
                      ? 'bg-green-50 text-green-700 border border-green-200'
                      : 'bg-orange-50 text-orange-700 border border-orange-200'
                  }`}>
                    {stockCheckResult.is_available ? (
                      <Package className="h-4 w-4" />
                    ) : (
                      <AlertTriangle className="h-4 w-4" />
                    )}
                    <span>{stockCheckResult.message}</span>
                    {stockCheckResult.available_stock !== undefined && (
                      <Badge variant={stockCheckResult.is_available ? "default" : "destructive"}>
                        Available: {stockCheckResult.available_stock}
                      </Badge>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Item Details */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Description */}
            <div className="md:col-span-2 space-y-2">
              <Label htmlFor={`description-${index}`}>Description *</Label>
              <Input
                id={`description-${index}`}
                value={item.description}
                onChange={(e) => handleFieldChange('description', e.target.value)}
                placeholder="Enter item description"
                required
              />
            </div>

            {/* Unit of Measure */}
            <div className="space-y-2">
              <Label htmlFor={`unit-${index}`}>Unit</Label>
              <Input
                id={`unit-${index}`}
                value={item.unit_of_measure || ''}
                onChange={(e) => handleFieldChange('unit_of_measure', e.target.value)}
                placeholder="each, kg, hours..."
              />
            </div>
          </div>

          {/* Quantity and Price */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Quantity */}
            <div className="space-y-2">
              <Label htmlFor={`quantity-${index}`}>Quantity *</Label>
              <Input
                id={`quantity-${index}`}
                type="number"
                min="0.01"
                step="0.01"
                value={item.quantity}
                onChange={(e) => handleFieldChange('quantity', parseFloat(e.target.value) || 0)}
                placeholder="1.00"
                required
              />
            </div>

            {/* Price */}
            <div className="space-y-2">
              <Label htmlFor={`price-${index}`}>Unit Price *</Label>
              <div className="relative">
                <DollarSign className="absolute left-3 top-1/2 transform -translate-y-1/2 text-muted-foreground h-4 w-4" />
                <Input
                  id={`price-${index}`}
                  type="number"
                  min="0"
                  step="0.01"
                  value={item.price}
                  onChange={(e) => handleFieldChange('price', parseFloat(e.target.value) || 0)}
                  placeholder="0.00"
                  className="pl-10"
                  required
                />
              </div>
            </div>

            {/* Amount (Calculated) */}
            <div className="space-y-2">
              <Label>Total Amount</Label>
              <div className="flex items-center h-10 px-3 border border-input bg-muted rounded-md">
                <span className="text-sm font-medium">
                  {new Intl.NumberFormat('en-US', {
                    style: 'currency',
                    currency: currency,
                    minimumFractionDigits: 2
                  }).format(item.amount)}
                </span>
              </div>
            </div>
          </div>

          {/* Stock Warning */}
          {stockCheckResult && !stockCheckResult.is_available && (
            <div className="bg-orange-50 border border-orange-200 rounded-lg p-3">
              <div className="flex items-center gap-2 text-orange-800">
                <AlertTriangle className="h-4 w-4" />
                <span className="text-sm font-medium">Stock Warning</span>
              </div>
              <p className="text-sm text-orange-700 mt-1">
                {stockCheckResult.message}. Consider reducing the quantity or contact your supplier for restocking.
              </p>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
};
