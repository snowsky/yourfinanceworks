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
        return <TrendingDown className="h-4 w-4 text-destructive" />;
      case 'purchase':
        return <TrendingUp className="h-4 w-4 text-success" />;
      case 'adjustment':
        return <Package className="h-4 w-4 text-primary" />;
      default:
        return <Package className="h-4 w-4 text-muted-foreground" />;
    }
  };

  const getMovementTypeColor = (type: string) => {
    switch (type.toLowerCase()) {
      case 'sale':
        return 'bg-destructive/10 text-destructive border-destructive/30';
      case 'purchase':
        return 'bg-success/10 text-success border-success/30';
      case 'adjustment':
        return 'bg-primary/10 text-primary border-primary/30';
      default:
        return 'bg-muted text-muted-foreground';
    }
  };

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Package className="h-5 w-5" />
            {t('inventory.stock_impact')}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex justify-center items-center py-8">
            <Loader2 className="h-8 w-8 animate-spin mr-2" />
            <p>{t('common.loading')}</p>
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
          {t('inventory.stock_impact')}
        </CardTitle>
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted-foreground">
            {t('inventory.how_invoice_affected_stock')}
          </p>
          <div className="text-right">
            <div className="text-sm text-muted-foreground">
              {t('inventory.total_stock_impact')}
            </div>
            <div className={`font-semibold ${totalImpact < 0 ? 'text-destructive' : 'text-success'}`}>
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
              <Info className="h-4 w-4 text-primary" />
              <h4 className="font-medium">Inventory Items in this Invoice</h4>
            </div>
            <div className="space-y-3">
              {inventoryItems.map((item, index) => {
                const { invoiceItem, inventoryItem } = item;
                return (
                  <div key={index} className="p-4 bg-primary/10 border border-primary/30 rounded-lg">
                    <div className="flex justify-between items-start mb-2">
                      <div>
                        <div className="font-medium text-foreground">
                          {inventoryItem?.name || invoiceItem.description}
                        </div>
                        {inventoryItem && (
                          <div className="text-sm text-muted-foreground">
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
                          <span className="text-muted-foreground">Unit Price:</span>
                          <div className="font-medium">${(inventoryItem.unit_price || 0).toFixed(2)}</div>
                        </div>
                        <div>
                          <span className="text-muted-foreground">Quantity Sold:</span>
                          <div className="font-medium">{invoiceItem.quantity} {inventoryItem.unit_of_measure || 'units'}</div>
                        </div>
                        <div>
                          <span className="text-muted-foreground">Current Stock:</span>
                          <div className="font-medium">
                            {inventoryItem.track_stock 
                              ? `${inventoryItem.current_stock || 0} ${inventoryItem.unit_of_measure || 'units'}`
                              : 'Not tracked'
                            }
                          </div>
                        </div>
                        <div>
                          <span className="text-muted-foreground">Total Value:</span>
                          <div className="font-medium">${((invoiceItem.quantity || 0) * (invoiceItem.price || 0)).toFixed(2)}</div>
                        </div>
                      </div>
                    ) : (
                      <div className="text-sm text-muted-foreground">
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
              {t('inventory.no_stock_movements')}
            </h3>
            <p className="text-muted-foreground mb-4">
              {invoiceStatus === 'paid' || invoiceStatus === 'completed'
                ? t('inventory.stock_movements_should_exist')
                : t('inventory.stock_movements_will_be_created')
              }
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t('inventory.item')}</TableHead>
                  <TableHead>{t('inventory.movement_type')}</TableHead>
                  <TableHead className="text-right">{t('inventory.quantity')}</TableHead>
                  <TableHead>{t('inventory.date')}</TableHead>
                  <TableHead>{t('inventory.notes')}</TableHead>
                  <TableHead className="text-right">{t('common.actions')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {stockMovements.map((movement) => (
                  <TableRow key={movement.id}>
                    <TableCell className="font-medium">
                      {movement.item?.name || t('inventory.unknown_item')}
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
                      <span className={movement.quantity < 0 ? 'text-destructive' : 'text-success'}>
                        {movement.quantity > 0 ? '+' : ''}{movement.quantity}
                      </span>
                    </TableCell>
                    <TableCell>
                      {movement.movement_date
                        ? format(new Date(movement.movement_date), 'PPp')
                        : t('common.unknown')
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
                        title={t('inventory.view_item_details')}
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
                {t('inventory.stock_impact_summary')}
              </h4>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
                <div>
                  <span className="text-muted-foreground">
                    {t('inventory.items_affected')}:
                  </span>
                  <span className="ml-2 font-medium">
                    {new Set(stockMovements.map(m => m.item_id)).size}
                  </span>
                </div>
                <div>
                  <span className="text-muted-foreground">
                    {t('inventory.total_movements')}:
                  </span>
                  <span className="ml-2 font-medium">
                    {stockMovements.length}
                  </span>
                </div>
                <div>
                  <span className="text-muted-foreground">
                    {t('inventory.net_stock_change')}:
                  </span>
                  <span className={`ml-2 font-medium ${totalImpact < 0 ? 'text-destructive' : 'text-success'}`}>
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
