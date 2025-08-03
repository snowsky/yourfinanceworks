import { useState, useEffect } from "react";
import { AppLayout } from "@/components/layout/AppLayout";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Trash2, RotateCcw, AlertTriangle } from "lucide-react";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { formatDate } from '@/lib/utils';
import { useTranslation } from 'react-i18next';

interface DeletedInvoice {
  id: number;
  number: string;
  amount: number;
  currency: string;
  due_date: string;
  status: string;
  client_id: number;
  deleted_at: string;
  deleted_by_username: string;
}

const RecycleBin = () => {
  const { t } = useTranslation();
  const [deletedInvoices, setDeletedInvoices] = useState<DeletedInvoice[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchDeletedInvoices();
  }, []);

  const fetchDeletedInvoices = async () => {
    try {
      setLoading(true);
      const data = await api.get<DeletedInvoice[]>('/invoices/recycle-bin');
      setDeletedInvoices(data);
    } catch (error) {
      console.error('Failed to fetch deleted invoices:', error);
      toast.error('Failed to load deleted invoices');
    } finally {
      setLoading(false);
    }
  };

  const handleRestore = async (invoiceId: number) => {
    try {
      await api.post(`/invoices/${invoiceId}/restore`, { new_status: 'draft' });
      toast.success('Invoice restored successfully');
      fetchDeletedInvoices();
    } catch (error) {
      console.error('Failed to restore invoice:', error);
      toast.error('Failed to restore invoice');
    }
  };

  const handlePermanentDelete = async (invoiceId: number) => {
    if (!confirm('Are you sure you want to permanently delete this invoice? This action cannot be undone.')) {
      return;
    }

    try {
      await api.delete(`/invoices/${invoiceId}/permanent`);
      toast.success('Invoice permanently deleted');
      fetchDeletedInvoices();
    } catch (error) {
      console.error('Failed to permanently delete invoice:', error);
      toast.error('Failed to permanently delete invoice');
    }
  };

  const handleEmptyRecycleBin = async () => {
    if (!confirm('Are you sure you want to permanently delete ALL invoices in the recycle bin? This action cannot be undone.')) {
      return;
    }

    try {
      await api.post('/invoices/recycle-bin/empty');
      toast.success('Recycle bin emptied successfully');
      fetchDeletedInvoices();
    } catch (error) {
      console.error('Failed to empty recycle bin:', error);
      toast.error('Failed to empty recycle bin');
    }
  };

  return (
    <AppLayout>
      <div className="h-full space-y-6 fade-in">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold flex items-center gap-2">
              <Trash2 className="h-8 w-8" />
              Recycle Bin
            </h1>
            <p className="text-muted-foreground">Manage deleted invoices</p>
          </div>
          {deletedInvoices.length > 0 && (
            <Button 
              variant="destructive" 
              onClick={handleEmptyRecycleBin}
              className="sm:self-end whitespace-nowrap"
            >
              <Trash2 className="mr-2 h-4 w-4" />
              Empty Recycle Bin
            </Button>
          )}
        </div>
        
        <Card className="slide-in">
          <CardHeader className="pb-3">
            <CardTitle>Deleted Invoices</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Invoice</TableHead>
                    <TableHead>Amount</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Deleted At</TableHead>
                    <TableHead>Deleted By</TableHead>
                    <TableHead className="w-[150px]">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {loading ? (
                    <TableRow>
                      <TableCell colSpan={6} className="h-24 text-center">
                        Loading deleted invoices...
                      </TableCell>
                    </TableRow>
                  ) : deletedInvoices.length > 0 ? (
                    deletedInvoices.map((invoice) => (
                      <TableRow key={invoice.id} className="hover:bg-muted/50">
                        <TableCell className="font-medium">
                          {invoice.number}
                        </TableCell>
                        <TableCell>
                          {invoice.currency} {invoice.amount}
                        </TableCell>
                        <TableCell>
                          <Badge variant="outline">
                            {invoice.status}
                          </Badge>
                        </TableCell>
                        <TableCell>{formatDate(invoice.deleted_at)}</TableCell>
                        <TableCell>{invoice.deleted_by_username || 'Unknown'}</TableCell>
                        <TableCell>
                          <div className="flex gap-1">
                            <Button 
                              variant="ghost" 
                              size="icon"
                              onClick={() => handleRestore(invoice.id)}
                              className="text-green-600 hover:text-green-700 hover:bg-green-50"
                              title="Restore invoice"
                            >
                              <RotateCcw className="h-4 w-4" />
                            </Button>
                            <Button 
                              variant="ghost" 
                              size="icon"
                              onClick={() => handlePermanentDelete(invoice.id)}
                              className="text-red-600 hover:text-red-700 hover:bg-red-50"
                              title="Permanently delete"
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))
                  ) : (
                    <TableRow>
                      <TableCell colSpan={6} className="h-24 text-center">
                        <div className="flex flex-col items-center gap-2">
                          <Trash2 className="h-8 w-8 text-muted-foreground" />
                          <p>Recycle bin is empty</p>
                        </div>
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </div>
          </CardContent>
        </Card>
      </div>
    </AppLayout>
  );
};

export default RecycleBin;