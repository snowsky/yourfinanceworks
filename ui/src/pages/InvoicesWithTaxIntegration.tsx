import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Pagination, PaginationContent, PaginationItem, PaginationNext, PaginationPrevious } from '@/components/ui/pagination';
import { Checkbox } from '@/components/ui/checkbox';
import { Badge } from '@/components/ui/badge';
import { Plus, Search, Send, Eye, Download } from 'lucide-react';
import { format, parseISO, isValid } from 'date-fns';
import { Link } from 'react-router-dom';
import { toast } from 'sonner';
import { invoiceApi, Invoice, api } from '@/lib/api';
import { CurrencyDisplay } from '@/components/ui/currency-display';

// Import Tax Integration Components
import {
  SendToTaxServiceButton,
  TaxIntegrationStatus,
  BulkSendToTaxServiceDialog,
} from '@/components/tax-integration';
import { useTaxIntegration } from '@/hooks/useTaxIntegration';

const safeParseDateString = (dateString?: string): Date => {
  if (!dateString) return new Date();
  try {
    const parsedDate = parseISO(dateString);
    return isValid(parsedDate) ? parsedDate : new Date();
  } catch (error) {
    console.warn('Failed to parse date:', dateString, error);
    return new Date();
  }
};

const InvoicesWithTaxIntegration: React.FC = () => {
  const { t } = useTranslation();
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [hasNextPage, setHasNextPage] = useState(false);

  // Tax Integration State
  const [bulkSendDialogOpen, setBulkSendDialogOpen] = useState(false);
  const { isEnabled: taxIntegrationEnabled } = useTaxIntegration();

  useEffect(() => {
    fetchInvoices();
  }, [statusFilter, page, pageSize]);


  const fetchInvoices = async () => {
    try {
      setLoading(true);
      const response = await invoiceApi.getInvoicesWithParams({
        status: statusFilter !== 'all' ? statusFilter : undefined,
        skip: (page - 1) * pageSize,
        limit: pageSize,
      });
      setInvoices(response);
      setHasNextPage(response.length === pageSize);
    } catch (error) {
      console.error('Failed to fetch invoices:', error);
      toast.error('Failed to fetch invoices');
    } finally {
      setLoading(false);
    }
  };

  const handleBulkSendToTaxService = () => {
    if (selectedIds.length === 0) {
      toast.error(t('taxIntegration.errors.noItemsSelected'));
      return;
    }
    setBulkSendDialogOpen(true);
  };

  const handleTaxServiceSuccess = () => {
    fetchInvoices();
    setSelectedIds([]);
  };

  const filteredInvoices = invoices.filter(invoice =>
    invoice.number.toLowerCase().includes(searchQuery.toLowerCase()) ||
    invoice.client_name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <>
      <div className="flex-1 space-y-4 p-8 pt-6">
        <div className="flex items-center justify-between space-y-2">
          <h2 className="text-3xl font-bold tracking-tight">{t('navigation.invoices')}</h2>
          <div className="flex items-center space-x-2">
            <Link to="/invoices/new">
              <Button>
                <Plus className="mr-2 h-4 w-4" />
                {t('common.add')} {t('common.invoice')}
              </Button>
            </Link>
          </div>
        </div>

        {/* Tax Integration Status */}
        <TaxIntegrationStatus />

        {/* Filters */}
        <div className="flex flex-col space-y-4 md:flex-row md:space-y-0 md:space-x-4">
          <div className="flex-1">
            <div className="relative">
              <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder={t('common.search')}
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-8"
              />
            </div>
          </div>
          <Select value={statusFilter} onValueChange={setStatusFilter}>
            <SelectTrigger className="w-[180px]">
              <SelectValue placeholder={t('common.filter')} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{t('common.all')}</SelectItem>
              <SelectItem value="draft">Draft</SelectItem>
              <SelectItem value="pending">Pending</SelectItem>
              <SelectItem value="paid">Paid</SelectItem>
              <SelectItem value="overdue">Overdue</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Bulk Actions */}
        {selectedIds.length > 0 && taxIntegrationEnabled && (
          <div className="flex items-center justify-between p-4 bg-blue-50 border border-blue-200 rounded-md">
            <div className="flex items-center space-x-2">
              <span className="text-sm font-medium">
                {selectedIds.length} {t('common.selected')}
              </span>
            </div>
            <div className="flex items-center space-x-2">
              <Button
                variant="outline"
                size="sm"
                onClick={handleBulkSendToTaxService}
              >
                <Send className="h-4 w-4 mr-2" />
                {t('taxIntegration.sendSelected', { count: selectedIds.length })}
              </Button>
            </div>
          </div>
        )}

        {/* Invoices Table */}
        <Card>
          <CardHeader>
            <CardTitle>{t('navigation.invoices')}</CardTitle>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-12">
                    <Checkbox
                      checked={filteredInvoices.length > 0 && selectedIds.length === filteredInvoices.length}
                      onCheckedChange={(checked) => {
                        if (checked) {
                          setSelectedIds(filteredInvoices.map(i => i.id));
                        } else {
                          setSelectedIds([]);
                        }
                      }}
                    />
                  </TableHead>
                  <TableHead>{t('common.number')}</TableHead>
                  <TableHead>{t('common.client')}</TableHead>
                  <TableHead>{t('common.date')}</TableHead>
                  <TableHead>{t('common.due_date')}</TableHead>
                  <TableHead>{t('common.amount')}</TableHead>
                  <TableHead>{t('common.status')}</TableHead>
                  <TableHead>{t('common.actions')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredInvoices.map((invoice) => (
                  <TableRow key={invoice.id}>
                    <TableCell>
                      <Checkbox
                        checked={selectedIds.includes(invoice.id)}
                        onCheckedChange={(checked) => {
                          if (checked) {
                            setSelectedIds(prev => [...prev, invoice.id]);
                          } else {
                            setSelectedIds(prev => prev.filter(id => id !== invoice.id));
                          }
                        }}
                      />
                    </TableCell>
                    <TableCell>
                      <Link
                        to={`/invoices/${invoice.id}`}
                        className="font-medium text-blue-600 hover:text-blue-800"
                      >
                        {invoice.number}
                      </Link>
                    </TableCell>
                    <TableCell>{invoice.client_name}</TableCell>
                    <TableCell>
                      {format(safeParseDateString(invoice.date), 'MMM dd, yyyy')}
                    </TableCell>
                    <TableCell>
                      {invoice.due_date ?
                        format(safeParseDateString(invoice.due_date), 'MMM dd, yyyy') :
                        '-'
                      }
                    </TableCell>
                    <TableCell>
                      <CurrencyDisplay
                        amount={invoice.amount}
                        currency={invoice.currency}
                      />
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant={
                          invoice.status === 'paid' ? 'default' :
                            invoice.status === 'overdue' ? 'destructive' :
                              invoice.status === 'pending' ? 'secondary' : 'outline'
                        }
                      >
                        {invoice.status}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center space-x-2">
                        <SendToTaxServiceButton
                          itemId={invoice.id}
                          itemType="invoice"
                          onSuccess={handleTaxServiceSuccess}
                          size="sm"
                          variant="ghost"
                        />
                        <Link to={`/invoices/${invoice.id}`}>
                          <Button variant="ghost" size="sm">
                            <Eye className="h-4 w-4" />
                          </Button>
                        </Link>
                        {invoice.has_attachment && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => invoiceApi.downloadAttachment(invoice.id)}
                          >
                            <Download className="h-4 w-4" />
                          </Button>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>

        {/* Pagination */}
        {hasNextPage && (
          <div className="flex justify-center">
            <Pagination>
              <PaginationContent>
                <PaginationItem>
                  <PaginationPrevious
                    onClick={() => setPage(Math.max(1, page - 1))}
                    className={page === 1 ? 'pointer-events-none opacity-50' : 'cursor-pointer'}
                  />
                </PaginationItem>
                <PaginationItem>
                  <span className="px-3 py-2">Page {page}</span>
                </PaginationItem>
                <PaginationItem>
                  <PaginationNext
                    onClick={() => setPage(page + 1)}
                    className={!hasNextPage ? 'pointer-events-none opacity-50' : 'cursor-pointer'}
                  />
                </PaginationItem>
              </PaginationContent>
            </Pagination>
          </div>
        )}

        {/* Bulk Send Dialog */}
        <BulkSendToTaxServiceDialog
          open={bulkSendDialogOpen}
          onOpenChange={setBulkSendDialogOpen}
          items={filteredInvoices.filter(i => selectedIds.includes(i.id))}
          itemType="invoice"
          onSuccess={handleTaxServiceSuccess}
        />
      </div>
    </>
  );
};

export default InvoicesWithTaxIntegration;
