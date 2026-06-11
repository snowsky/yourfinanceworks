import React, { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Loader2, FileText, Package, TrendingDown, TrendingUp } from "lucide-react";
import { inventoryApi, InvoiceInventoryLink, InventoryStockSummary } from "@/lib/api";
import { getErrorMessage } from "@/lib/api";
import { toast } from "sonner";
import { useTranslation } from "react-i18next";
import { format } from "date-fns";

interface InventoryItemLinkedInvoicesProps {
  itemId: number;
  itemName: string;
}

export const InventoryItemLinkedInvoices: React.FC<InventoryItemLinkedInvoicesProps> = ({
  itemId,
  itemName
}) => {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(true);
  const [linkedInvoices, setLinkedInvoices] = useState<InvoiceInventoryLink[]>([]);
  const [stockSummary, setStockSummary] = useState<InventoryStockSummary | null>(null);

  useEffect(() => {
    fetchData();
  }, [itemId]);

  const fetchData = async () => {
    if (!itemId) return;

    setLoading(true);
    try {
      const [invoicesData, summaryData] = await Promise.all([
        inventoryApi.getInvoicesLinkedToInventoryItem(itemId),
        inventoryApi.getInventoryItemStockSummary(itemId, 30)
      ]);

      setLinkedInvoices(invoicesData);
      setStockSummary(summaryData);
    } catch (error) {
      console.error("Failed to fetch linked invoices data:", error);
      toast.error(getErrorMessage(error, t));
    } finally {
      setLoading(false);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case 'paid':
        return 'bg-success/10 text-success';
      case 'pending':
        return 'bg-warning/10 text-warning';
      case 'overdue':
        return 'bg-destructive/10 text-destructive';
      case 'draft':
        return 'bg-muted text-muted-foreground';
      default:
        return 'bg-primary/10 text-primary';
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

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5" />
            {t('inventory.linked_invoices')}
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

  return (
    <div className="space-y-6">
      {/* Stock Movement Summary */}
      {stockSummary && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Package className="h-5 w-5" />
              {t('inventory.stock_movement_summary')}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              {Object.entries(stockSummary.movement_summary).map(([type, data]) => (
                <div key={type} className="p-4 border rounded-lg">
                  <div className="flex items-center gap-2 mb-2">
                    {getMovementTypeIcon(type)}
                    <span className="font-medium capitalize">{type}</span>
                  </div>
                  <div className="text-2xl font-bold">
                    {data.total_quantity > 0 ? '+' : ''}{data.total_quantity}
                  </div>
                  <div className="text-sm text-muted-foreground">
                    {data.count} {t('inventory.movements')}
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Linked Invoices */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5" />
            {t('inventory.linked_invoices')}
          </CardTitle>
          <p className="text-sm text-muted-foreground">
            {t('inventory.invoices_that_affected_stock')} {itemName}
          </p>
        </CardHeader>
        <CardContent>
          {linkedInvoices.length === 0 ? (
            <div className="text-center py-8">
              <FileText className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
              <h3 className="text-lg font-medium mb-2">
                {t('inventory.no_linked_invoices')}
              </h3>
              <p className="text-muted-foreground mb-4">
                {t('inventory.no_invoices_affected_stock')}
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              {linkedInvoices.map((invoice) => (
                <div key={invoice.id} className="border rounded-lg p-4">
                  <div className="flex justify-between items-start mb-4">
                    <div>
                      <h4 className="font-semibold">#{invoice.number}</h4>
                      <p className="text-sm text-muted-foreground">
                        {format(new Date(invoice.created_at), 'PPp')}
                      </p>
                    </div>
                    <div className="text-right">
                      <div className="font-semibold">
                        {invoice.amount} {invoice.currency}
                      </div>
                      <Badge className={getStatusColor(invoice.status)}>
                        {invoice.status}
                      </Badge>
                    </div>
                  </div>

                  {/* Invoice Items */}
                  {invoice.invoice_items.length > 0 && (
                    <div className="mb-4">
                      <h5 className="text-sm font-medium mb-2">
                        {t('inventory.invoice_items')}
                      </h5>
                      <div className="space-y-2">
                        {invoice.invoice_items.map((item, index) => (
                          <div key={index} className="flex justify-between text-sm bg-muted/50 p-2 rounded">
                            <span>
                              {item.quantity} × {item.price} = {item.amount}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Stock Movements */}
                  {invoice.stock_movements.length > 0 && (
                    <div>
                      <h5 className="text-sm font-medium mb-2">
                        {t('inventory.stock_movements')}
                      </h5>
                      <div className="space-y-2">
                        {invoice.stock_movements.map((movement) => (
                          <div key={movement.id} className="flex items-center justify-between text-sm bg-muted/50 p-2 rounded">
                            <div className="flex items-center gap-2">
                              {getMovementTypeIcon(movement.movement_type)}
                              <span className="capitalize">{movement.movement_type}</span>
                            </div>
                            <div className="flex items-center gap-4">
                              <span className={movement.quantity < 0 ? 'text-destructive' : 'text-success'}>
                                {movement.quantity > 0 ? '+' : ''}{movement.quantity}
                              </span>
                              <span className="text-muted-foreground">
                                {format(new Date(movement.movement_date), 'PP')}
                              </span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};
