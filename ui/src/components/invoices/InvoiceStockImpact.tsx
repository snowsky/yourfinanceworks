import React, { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Loader2, Package, TrendingDown, TrendingUp, ExternalLink, Info } from "lucide-react";
import { inventoryApi, StockMovement, invoiceApi, Invoice } from "@/lib/api";
import { getErrorMessage } from "@/lib/api";
import { toast } from "sonner";
import { useTranslation } from "react-i18next";
import { format } from "date-fns";
import { useNavigate } from "react-router-dom";

interface InvoiceStockImpactProps {
  invoiceId: number;
  invoiceNumber: string;
  invoiceStatus: string;
}

export const InvoiceStockImpact: React.FC<InvoiceStockImpactProps> = ({
  invoiceId,
  invoiceNumber,
  invoiceStatus
}) => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [stockMovements, setStockMovements] = useState<StockMovement[]>([]);
  const [invoice, setInvoice] = useState<Invoice | null>(null);
  const [inventoryItems, setInventoryItems] = useState<any[]>([]);

  useEffect(() => {
    fetchData();
  }, [invoiceId]);

  const fetchData = async () => {
    setLoading(true);
    try {
      // Fetch stock movements and invoice data
      const [movements, invoiceData] = await Promise.all([
        inventoryApi.getStockMovementsByReference("invoice", invoiceId),
        invoiceApi.getInvoice(invoiceId)
      ]);
      
      setStockMovements(movements);
      setInvoice(invoiceData);
      
      // Extract inventory items from invoice
      const itemsWithInventory = invoiceData.items?.filter(item => item.inventory_item_id) || [];
      
      // Fetch detailed inventory information for each item
      if (itemsWithInventory.length > 0) {
        const inventoryPromises = itemsWithInventory.map(async (item) => {
          try {
            const inventoryItem = await inventoryApi.getItem(item.inventory_item_id);
            return {
              invoiceItem: item,
              inventoryItem: inventoryItem
            };
          } catch (error) {
            console.warn(`Failed to fetch inventory item ${item.inventory_item_id}:`, error);
            return {
              invoiceItem: item,
              inventoryItem: null
            };
          }
        });
        
        const inventoryResults = await Promise.all(inventoryPromises);
        setInventoryItems(inventoryResults);
      }
      
    } catch (error) {
      console.error("Failed to fetch data:", error);
      toast.error(getErrorMessage(error, t));
    } finally {
      setLoading(false);
    }
  };

  const getMovementTypeIcon = (type: string) => {
    switch (type.toLowerCase()) {
      case 'sale':
        return <TrendingDown className="h-4 w-4 text-red-500" />;
      case 'purchase':
        return <TrendingUp className="h-4 w-4 text-green-500" />;
      case 'adjustment':
        return <Package className="h-4 w-4 text-blue-500" />;
      default:
        return <Package className="h-4 w-4 text-gray-500" />;
    }
  };

  const getMovementTypeColor = (type: string) => {
    switch (type.toLowerCase()) {
      case 'sale':
        return 'bg-red-100 text-red-800';
      case 'purchase':
        return 'bg-green-100 text-green-800';
      case 'adjustment':
        return 'bg-blue-100 text-blue-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Package className="h-5 w-5" />
            {t('inventory.stock_impact', 'Stock Impact')}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex justify-center items-center py-8">
            <Loader2 className="h-8 w-8 animate-spin mr-2" />
            <p>{t('common.loading', 'Loading...')}</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  const totalImpact = stockMovements.reduce((sum, movement) => sum + movement.quantity, 0);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Package className="h-5 w-5" />
          {t('inventory.stock_impact', 'Stock Impact')}
        </CardTitle>
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted-foreground">
            {t('inventory.how_invoice_affected_stock', 'How this invoice affected your inventory')}
          </p>
          <div className="text-right">
            <div className="text-sm text-muted-foreground">
              {t('inventory.total_stock_impact', 'Total Impact')}
            </div>
            <div className={`font-semibold ${totalImpact < 0 ? 'text-red-600' : 'text-green-600'}`}>
              {totalImpact > 0 ? '+' : ''}{totalImpact}
            </div>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {/* Inventory Items Information */}
        {inventoryItems.length > 0 && (
          <div className="mb-6">
            <div className="flex items-center gap-2 mb-4">
              <Info className="h-4 w-4 text-blue-500" />
              <h4 className="font-medium">Inventory Items in this Invoice</h4>
            </div>
            <div className="space-y-3">
              {inventoryItems.map((item, index) => {
                const { invoiceItem, inventoryItem } = item;
                return (
                  <div key={index} className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
                    <div className="flex justify-between items-start mb-2">
                      <div>
                        <div className="font-medium text-gray-900">
                          {inventoryItem?.name || invoiceItem.description}
                        </div>
                        {inventoryItem && (
                          <div className="text-sm text-gray-600">
                            SKU: {inventoryItem.sku || 'N/A'}
                          </div>
                        )}
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => navigate(`/inventory/view/${invoiceItem.inventory_item_id}`)}
                        className="h-8 w-8 p-0"
                        title="View inventory item details"
                      >
                        <ExternalLink className="h-4 w-4" />
                      </Button>
                    </div>
                    
                    {inventoryItem ? (
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                        <div>
                          <span className="text-gray-500">Unit Price:</span>
                          <div className="font-medium">${(inventoryItem.unit_price || 0).toFixed(2)}</div>
                        </div>
                        <div>
                          <span className="text-gray-500">Quantity Sold:</span>
                          <div className="font-medium">{invoiceItem.quantity} {inventoryItem.unit_of_measure || 'units'}</div>
                        </div>
                        <div>
                          <span className="text-gray-500">Current Stock:</span>
                          <div className="font-medium">
                            {inventoryItem.track_stock 
                              ? `${inventoryItem.current_stock || 0} ${inventoryItem.unit_of_measure || 'units'}`
                              : 'Not tracked'
                            }
                          </div>
                        </div>
                        <div>
                          <span className="text-gray-500">Total Value:</span>
                          <div className="font-medium">${((invoiceItem.quantity || 0) * (invoiceItem.price || 0)).toFixed(2)}</div>
                        </div>
                      </div>
                    ) : (
                      <div className="text-sm text-gray-500">
                        Loading inventory information...
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
            <hr className="my-6" />
          </div>
        )}

        {/* Stock Movements Section */}
        {stockMovements.length === 0 ? (
          <div className="text-center py-8">
            <Package className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
            <h3 className="text-lg font-medium mb-2">
              {t('inventory.no_stock_movements', 'No Stock Movements')}
            </h3>
            <p className="text-muted-foreground mb-4">
              {invoiceStatus === 'paid' || invoiceStatus === 'completed'
                ? t('inventory.stock_movements_should_exist', 'Stock movements should have been created for this paid/completed invoice.')
                : t('inventory.stock_movements_will_be_created', 'Stock movements will be created when this invoice is marked as paid or completed.')
              }
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t('inventory.item', 'Item')}</TableHead>
                  <TableHead>{t('inventory.movement_type', 'Movement Type')}</TableHead>
                  <TableHead className="text-right">{t('inventory.quantity', 'Quantity')}</TableHead>
                  <TableHead>{t('inventory.date', 'Date')}</TableHead>
                  <TableHead>{t('inventory.notes', 'Notes')}</TableHead>
                  <TableHead className="text-right">{t('common.actions', 'Actions')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {stockMovements.map((movement) => (
                  <TableRow key={movement.id}>
                    <TableCell className="font-medium">
                      {movement.item?.name || t('inventory.unknown_item', 'Unknown Item')}
                    </TableCell>
                    <TableCell>
                      <Badge className={getMovementTypeColor(movement.movement_type)}>
                        <div className="flex items-center gap-1">
                          {getMovementTypeIcon(movement.movement_type)}
                          <span className="capitalize">{movement.movement_type}</span>
                        </div>
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      <span className={movement.quantity < 0 ? 'text-red-600' : 'text-green-600'}>
                        {movement.quantity > 0 ? '+' : ''}{movement.quantity}
                      </span>
                    </TableCell>
                    <TableCell>
                      {movement.movement_date
                        ? format(new Date(movement.movement_date), 'PPp')
                        : t('common.unknown', 'Unknown')
                      }
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {movement.notes || '-'}
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => navigate(`/inventory/view/${movement.item_id}`)}
                        className="h-8 w-8 p-0"
                        title={t('inventory.view_item_details', 'View item details')}
                      >
                        <ExternalLink className="h-4 w-4" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>

            {/* Summary */}
            <div className="mt-6 p-4 bg-muted/50 rounded-lg">
              <h4 className="font-medium mb-2">
                {t('inventory.stock_impact_summary', 'Stock Impact Summary')}
              </h4>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
                <div>
                  <span className="text-muted-foreground">
                    {t('inventory.items_affected', 'Items Affected')}:
                  </span>
                  <span className="ml-2 font-medium">
                    {new Set(stockMovements.map(m => m.item_id)).size}
                  </span>
                </div>
                <div>
                  <span className="text-muted-foreground">
                    {t('inventory.total_movements', 'Total Movements')}:
                  </span>
                  <span className="ml-2 font-medium">
                    {stockMovements.length}
                  </span>
                </div>
                <div>
                  <span className="text-muted-foreground">
                    {t('inventory.net_stock_change', 'Net Stock Change')}:
                  </span>
                  <span className={`ml-2 font-medium ${totalImpact < 0 ? 'text-red-600' : 'text-green-600'}`}>
                    {totalImpact > 0 ? '+' : ''}{totalImpact}
                  </span>
                </div>
              </div>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
};
