import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { AppLayout } from "@/components/layout/AppLayout";
import { InvoiceForm } from "@/components/invoices/InvoiceForm";
import { invoiceApi, Invoice, getErrorMessage, expenseApi, Expense } from "@/lib/api";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Table, TableHeader, TableRow, TableHead, TableBody, TableCell } from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";
import { Loader2, Package } from "lucide-react";
import { useTranslation } from 'react-i18next';
import { CurrencyDisplay } from '@/components/ui/currency-display';

const EditInvoice = () => {
  const { t } = useTranslation();
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [invoice, setInvoice] = useState<Invoice | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [linkedExpenses, setLinkedExpenses] = useState<Expense[]>([]);
  const [availableExpenses, setAvailableExpenses] = useState<Expense[]>([]);
  const [linkSelect, setLinkSelect] = useState<string | undefined>(undefined);
  const [stockMovements, setStockMovements] = useState<any[]>([]);

  useEffect(() => {
    const fetchInvoice = async () => {
      if (!id) {
        navigate("/invoices");
        return;
      }

      setLoading(true);
      try {
        console.log("🔍 EDIT INVOICE - About to fetch invoice", parseInt(id));
        const data = await invoiceApi.getInvoice(parseInt(id));
        console.log("🔍 EDIT INVOICE - Raw API response:", JSON.stringify(data, null, 2));
        console.log("🔍 EDIT INVOICE - Loaded invoice data:", data);
        console.log("🔍 EDIT INVOICE - Attachment data:", {
          has_attachment: data.has_attachment,
          attachment_filename: data.attachment_filename,
          // attachment_path is not part of Invoice; use filename/has_attachment
        });
        
        // Check if items exists and has content
        if (!data.items || !Array.isArray(data.items) || data.items.length === 0) {
          console.warn("Invoice items are missing or empty:", data.items);
          toast.warning(t('invoices.invoiceItemsMissing'));
        }
        
        setInvoice(data);
        try {
          const expenses = await expenseApi.getExpensesFiltered({ invoiceId: data.id });
          setLinkedExpenses(expenses);
          const unlinked = await expenseApi.getExpensesFiltered({ unlinkedOnly: true });
          setAvailableExpenses(unlinked);

          // Fetch stock movements related to this invoice
          try {
            // Get stock movements by reference (this would need to be implemented in the API)
            // For now, we'll show a placeholder
            setStockMovements([]);
          } catch (stockError) {
            console.warn("Failed to fetch stock movements:", stockError);
          }
        } catch {}
      } catch (error) {
        console.error("Failed to fetch invoice:", error);
        toast.error(getErrorMessage(error, t));
        setError(true);
      } finally {
        setLoading(false);
      }
    };

    fetchInvoice();
  }, [id, navigate, t]);

  if (loading) {
    return (
      <AppLayout>
        <div className="h-full flex justify-center items-center">
          <Loader2 className="h-8 w-8 animate-spin mr-2" />
          <p>{t('editInvoice.loadingInvoiceData')}</p>
        </div>
      </AppLayout>
    );
  }

  if (error || !invoice) {
    return (
      <AppLayout>
        <div className="h-full space-y-6 fade-in">
          <div>
            <h1 className="text-3xl font-bold">{t('editInvoice.invoiceNotFound')}</h1>
            <p className="text-muted-foreground">{t('editInvoice.invoiceNotFoundDescription')}</p>
          </div>
        </div>
      </AppLayout>
    );
  }

  // Make sure invoice has an items array even if API didn't return one
  if (!invoice.items) {
    invoice.items = [];
  }

  return (
    <AppLayout>
      <div className="h-full space-y-6 fade-in">
        <div>
          <h1 className="text-3xl font-bold">{t('editInvoice.editInvoice')}</h1>
          <p className="text-muted-foreground">{t('editInvoice.updateInvoiceDetails')}</p>
        </div>
        
        <InvoiceForm 
          invoice={invoice} 
          isEdit={true} 
          key={`${invoice.id}-${invoice.has_attachment}-${invoice.attachment_filename}`} 
          onInvoiceUpdate={(updatedInvoice) => {
            console.log("🔍 EDIT INVOICE - Invoice updated via callback:", updatedInvoice);
            console.log("🔍 EDIT INVOICE - Updated attachment info:", {
              has_attachment: updatedInvoice.has_attachment,
              attachment_filename: updatedInvoice.attachment_filename
            });
            setInvoice(updatedInvoice);
          }}
        />

        <div className="px-6">
          <Card className="slide-in">
            <CardHeader>
              <CardTitle>Linked Expenses</CardTitle>
            </CardHeader>
            <CardContent>
            <div className="flex flex-col sm:flex-row sm:items-center gap-3 mb-4">
              <Select value={linkSelect} onValueChange={setLinkSelect}>
                <SelectTrigger className="w-full sm:w-[360px]">
                  <SelectValue placeholder="Select an unlinked expense to attach" />
                </SelectTrigger>
                <SelectContent>
                  {availableExpenses.map(e => (
                    <SelectItem key={e.id} value={String(e.id)}>
                      #{e.id} · {e.category} · {e.amount} {e.currency}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Button
                disabled={!linkSelect}
                onClick={async () => {
                  try {
                    if (!linkSelect) return;
                    const expId = Number(linkSelect);
                    const updated = await expenseApi.updateExpense(expId, { invoice_id: invoice!.id } as any);
                    // Optimistic local update
                    setLinkedExpenses(prev => [updated, ...prev.filter(e => e.id !== updated.id)]);
                    setAvailableExpenses(prev => prev.filter(e => e.id !== updated.id));
                    // Then refresh from server
                    try {
                      const [linked, unlinked] = await Promise.all([
                        expenseApi.getExpensesFiltered({ invoiceId: invoice!.id }),
                        expenseApi.getExpensesFiltered({ unlinkedOnly: true })
                      ]);
                      setLinkedExpenses(linked);
                      setAvailableExpenses(unlinked);
                    } catch {}
                    setLinkSelect(undefined);
                    toast.success('Expense linked');
                  } catch (e: any) {
                    toast.error(e?.message || 'Failed to link expense');
                  }
                }}
              >
               {t('invoices.link_expense')}
              </Button>
            </div>
            <div className="rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>ID</TableHead>
                    <TableHead>Category</TableHead>
                    <TableHead>Vendor</TableHead>
                    <TableHead className="text-right">Amount</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {linkedExpenses.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={5} className="text-center text-sm text-muted-foreground">No expenses linked</TableCell>
                    </TableRow>
                  ) : linkedExpenses.map(e => (
                    <TableRow key={e.id}>
                      <TableCell>#{e.id}</TableCell>
                      <TableCell>{e.category}</TableCell>
                      <TableCell>{e.vendor || '—'}</TableCell>
                      <TableCell className="text-right">
                        <CurrencyDisplay amount={e.amount || 0} currency={e.currency || 'USD'} />
                      </TableCell>
                      <TableCell className="text-right">
                        <Button variant="outline" size="sm" onClick={async () => {
                          try {
                            // Use null to explicitly clear the link on the backend
                            const updated = await expenseApi.updateExpense(e.id, { invoice_id: null } as any);
                            // Optimistic local update
                            setLinkedExpenses(prev => prev.filter(x => x.id !== updated.id));
                            setAvailableExpenses(prev => [updated, ...prev.filter(x => x.id !== updated.id)]);
                            // Then refresh from server
                            try {
                              const [linked, unlinked] = await Promise.all([
                                expenseApi.getExpensesFiltered({ invoiceId: invoice!.id }),
                                expenseApi.getExpensesFiltered({ unlinkedOnly: true })
                              ]);
                              setLinkedExpenses(linked);
                              setAvailableExpenses(unlinked);
                            } catch {}
                            toast.success('Expense unlinked');
                          } catch (err: any) {
                            toast.error(err?.message || 'Failed to unlink');
                          }
                        }}>Unlink</Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
            </CardContent>
          </Card>

          {/* Stock Movements Section */}
          <Card className="mt-6">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Package className="h-5 w-5" />
                Inventory Stock Movements
              </CardTitle>
              <p className="text-sm text-muted-foreground">
                Track how this invoice affected your inventory levels
              </p>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {stockMovements.length > 0 ? (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Item</TableHead>
                        <TableHead>Movement Type</TableHead>
                        <TableHead>Quantity</TableHead>
                        <TableHead>Date</TableHead>
                        <TableHead>Notes</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {stockMovements.map((movement: any) => (
                        <TableRow key={movement.id}>
                          <TableCell className="font-medium">
                            {movement.item?.name || 'Unknown Item'}
                          </TableCell>
                          <TableCell>
                            <span className={`px-2 py-1 rounded-full text-xs ${
                              movement.movement_type === 'sale' ? 'bg-red-100 text-red-800' :
                              movement.movement_type === 'adjustment' ? 'bg-blue-100 text-blue-800' :
                              'bg-gray-100 text-gray-800'
                            }`}>
                              {movement.movement_type}
                            </span>
                          </TableCell>
                          <TableCell>
                            <span className={movement.quantity < 0 ? 'text-red-600' : 'text-green-600'}>
                              {movement.quantity > 0 ? '+' : ''}{movement.quantity}
                            </span>
                          </TableCell>
                          <TableCell>
                            {movement.movement_date ? format(new Date(movement.movement_date), 'PPp') : 'N/A'}
                          </TableCell>
                          <TableCell className="text-sm text-muted-foreground">
                            {movement.notes || '-'}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                ) : (
                  <div className="text-center py-8">
                    <Package className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                    <h3 className="text-lg font-medium mb-2">No Stock Movements Yet</h3>
                    <p className="text-muted-foreground mb-4">
                      Stock movements will appear here when this invoice affects your inventory levels.
                    </p>
                    <div className="text-sm text-muted-foreground">
                      {invoice?.status === 'paid' || invoice?.status === 'completed' ? (
                        <p>Stock movements should have been processed automatically.</p>
                      ) : (
                        <p>Stock movements will be processed when the invoice is marked as paid or completed.</p>
                      )}
                    </div>
                  </div>
                )}

                {/* Stock Summary */}
                {invoice && (
                  <div className="mt-6 p-4 bg-muted/50 rounded-lg">
                    <h4 className="font-medium mb-2">Stock Movement Summary</h4>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
                      <div>
                        <span className="text-muted-foreground">Invoice Status:</span>
                        <span className={`ml-2 px-2 py-1 rounded-full text-xs ${
                          invoice.status === 'paid' ? 'bg-green-100 text-green-800' :
                          invoice.status === 'completed' ? 'bg-blue-100 text-blue-800' :
                          'bg-gray-100 text-gray-800'
                        }`}>
                          {invoice.status}
                        </span>
                      </div>
                      <div>
                        <span className="text-muted-foreground">Items with Inventory:</span>
                        <span className="ml-2 font-medium">
                          {invoice.items?.filter(item => item.inventory_item_id).length || 0}
                        </span>
                      </div>
                      <div>
                        <span className="text-muted-foreground">Auto Stock Updates:</span>
                        <span className="ml-2">
                          {(invoice.status === 'paid' || invoice.status === 'completed') ? '✅ Processed' : '⏳ Pending'}
                        </span>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </AppLayout>
  );
};

export default EditInvoice; 