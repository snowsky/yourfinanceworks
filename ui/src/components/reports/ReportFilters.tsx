import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Checkbox } from '@/components/ui/checkbox';
import { Calendar } from '@/components/ui/calendar';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { CalendarIcon, X } from 'lucide-react';
import { format } from 'date-fns';
import { cn } from '@/lib/utils';
import { ReportFilters as ReportFiltersType, ReportType, clientApi, currencyApi } from '@/lib/api';
import { useQuery } from '@tanstack/react-query';
import { EXPENSE_CATEGORY_OPTIONS } from '@/constants/expenses';

interface ReportFiltersProps {
  reportType: string;
  reportTypeConfig: ReportType;
  filters: ReportFiltersType;
  onFiltersChange: (filters: ReportFiltersType) => void;
}

export const ReportFilters: React.FC<ReportFiltersProps> = ({
  reportType,
  reportTypeConfig,
  filters,
  onFiltersChange,
}) => {
  const [dateFrom, setDateFrom] = useState<Date | undefined>(
    filters.date_from ? new Date(filters.date_from) : undefined
  );
  const [dateTo, setDateTo] = useState<Date | undefined>(
    filters.date_to ? new Date(filters.date_to) : undefined
  );

  // Fetch clients for client selector
  const { data: clients = [] } = useQuery({
    queryKey: ['clients'],
    queryFn: clientApi.getClients,
  });

  // Fetch currencies
  const { data: currencyData } = useQuery({
    queryKey: ['currencies'],
    queryFn: currencyApi.getSupportedCurrencies,
  });

  const currencies = currencyData?.currencies || [];

  // Update filters when dates change
  useEffect(() => {
    const newFilters = { ...filters };
    if (dateFrom) {
      newFilters.date_from = format(dateFrom, 'yyyy-MM-dd');
    } else {
      delete newFilters.date_from;
    }
    if (dateTo) {
      newFilters.date_to = format(dateTo, 'yyyy-MM-dd');
    } else {
      delete newFilters.date_to;
    }
    onFiltersChange(newFilters);
  }, [dateFrom, dateTo]);

  const updateFilter = (key: keyof ReportFiltersType, value: any) => {
    const newFilters = { ...filters };
    if (value === undefined || value === null || value === '') {
      delete newFilters[key];
    } else {
      newFilters[key] = value;
    }
    onFiltersChange(newFilters);
  };

  const addToArrayFilter = (key: keyof ReportFiltersType, value: string | number) => {
    const currentArray = (filters[key] as any[]) || [];
    if (!currentArray.includes(value)) {
      updateFilter(key, [...currentArray, value]);
    }
  };

  const removeFromArrayFilter = (key: keyof ReportFiltersType, value: string | number) => {
    const currentArray = (filters[key] as any[]) || [];
    updateFilter(key, currentArray.filter(item => item !== value));
  };

  const renderDateRangeFilter = () => (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div className="space-y-2">
        <Label>From Date</Label>
        <Popover>
          <PopoverTrigger asChild>
            <Button
              variant="outline"
              className={cn(
                "w-full justify-start text-left font-normal",
                !dateFrom && "text-muted-foreground"
              )}
            >
              <CalendarIcon className="mr-2 h-4 w-4" />
              {dateFrom ? format(dateFrom, "PPP") : "Pick a date"}
            </Button>
          </PopoverTrigger>
          <PopoverContent className="w-auto p-0">
            <Calendar
              mode="single"
              selected={dateFrom}
              onSelect={setDateFrom}
              initialFocus
            />
          </PopoverContent>
        </Popover>
      </div>
      <div className="space-y-2">
        <Label>To Date</Label>
        <Popover>
          <PopoverTrigger asChild>
            <Button
              variant="outline"
              className={cn(
                "w-full justify-start text-left font-normal",
                !dateTo && "text-muted-foreground"
              )}
            >
              <CalendarIcon className="mr-2 h-4 w-4" />
              {dateTo ? format(dateTo, "PPP") : "Pick a date"}
            </Button>
          </PopoverTrigger>
          <PopoverContent className="w-auto p-0">
            <Calendar
              mode="single"
              selected={dateTo}
              onSelect={setDateTo}
              initialFocus
            />
          </PopoverContent>
        </Popover>
      </div>
    </div>
  );

  const renderClientFilter = () => (
    <div className="space-y-2">
      <Label>Clients</Label>
      <Select onValueChange={(value) => addToArrayFilter('client_ids', parseInt(value))}>
        <SelectTrigger>
          <SelectValue placeholder="Select clients..." />
        </SelectTrigger>
        <SelectContent>
          {clients.map((client) => (
            <SelectItem key={client.id} value={client.id.toString()}>
              {client.name}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      {filters.client_ids && filters.client_ids.length > 0 && (
        <div className="flex flex-wrap gap-2 mt-2">
          {filters.client_ids.map((clientId) => {
            const client = clients.find(c => c.id === clientId);
            return (
              <div key={clientId} className="flex items-center bg-secondary text-secondary-foreground px-2 py-1 rounded-md text-sm">
                {client?.name || `Client ${clientId}`}
                <Button
                  variant="ghost"
                  size="sm"
                  className="ml-1 h-4 w-4 p-0"
                  onClick={() => removeFromArrayFilter('client_ids', clientId)}
                >
                  <X className="h-3 w-3" />
                </Button>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );

  const renderCurrencyFilter = () => (
    <div className="space-y-2">
      <Label>Currency</Label>
      <Select value={filters.currency || 'all'} onValueChange={(value) => updateFilter('currency', value === 'all' ? undefined : value)}>
        <SelectTrigger>
          <SelectValue placeholder="Select currency..." />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All Currencies</SelectItem>
          {currencies.map((currency: any) => (
            <SelectItem key={currency.code} value={currency.code}>
              {currency.code} - {currency.name}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );

  const renderAmountRangeFilter = () => (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div className="space-y-2">
        <Label>Minimum Amount</Label>
        <Input
          type="number"
          placeholder="0.00"
          value={filters.amount_min || ''}
          onChange={(e) => updateFilter('amount_min', e.target.value ? parseFloat(e.target.value) : undefined)}
        />
      </div>
      <div className="space-y-2">
        <Label>Maximum Amount</Label>
        <Input
          type="number"
          placeholder="0.00"
          value={filters.amount_max || ''}
          onChange={(e) => updateFilter('amount_max', e.target.value ? parseFloat(e.target.value) : undefined)}
        />
      </div>
    </div>
  );

  const renderInvoiceFilters = () => (
    <>
      <div className="space-y-2">
        <Label>Invoice Status</Label>
        <Select onValueChange={(value) => addToArrayFilter('status', value)}>
          <SelectTrigger>
            <SelectValue placeholder="Select status..." />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="draft">Draft</SelectItem>
            <SelectItem value="pending">Pending</SelectItem>
            <SelectItem value="paid">Paid</SelectItem>
            <SelectItem value="overdue">Overdue</SelectItem>
            <SelectItem value="partially_paid">Partially Paid</SelectItem>
          </SelectContent>
        </Select>
        {filters.status && filters.status.length > 0 && (
          <div className="flex flex-wrap gap-2 mt-2">
            {filters.status.map((status) => (
              <div key={status} className="flex items-center bg-secondary text-secondary-foreground px-2 py-1 rounded-md text-sm">
                {status.replace('_', ' ').toUpperCase()}
                <Button
                  variant="ghost"
                  size="sm"
                  className="ml-1 h-4 w-4 p-0"
                  onClick={() => removeFromArrayFilter('status', status)}
                >
                  <X className="h-3 w-3" />
                </Button>
              </div>
            ))}
          </div>
        )}
      </div>
      <div className="flex items-center space-x-2">
        <Checkbox
          id="include_items"
          checked={filters.include_items || false}
          onCheckedChange={(checked) => updateFilter('include_items', checked)}
        />
        <Label htmlFor="include_items">Include line items</Label>
      </div>
      <div className="flex items-center space-x-2">
        <Checkbox
          id="is_recurring"
          checked={filters.is_recurring}
          onCheckedChange={(checked) => updateFilter('is_recurring', checked === true ? true : undefined)}
        />
        <Label htmlFor="is_recurring">Recurring invoices only</Label>
      </div>
    </>
  );

  const renderPaymentFilters = () => (
    <>
      <div className="space-y-2">
        <Label>Payment Methods</Label>
        <Select onValueChange={(value) => addToArrayFilter('payment_methods', value)}>
          <SelectTrigger>
            <SelectValue placeholder="Select payment method..." />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="cash">Cash</SelectItem>
            <SelectItem value="check">Check</SelectItem>
            <SelectItem value="credit_card">Credit Card</SelectItem>
            <SelectItem value="bank_transfer">Bank Transfer</SelectItem>
            <SelectItem value="paypal">PayPal</SelectItem>
            <SelectItem value="other">Other</SelectItem>
          </SelectContent>
        </Select>
        {filters.payment_methods && filters.payment_methods.length > 0 && (
          <div className="flex flex-wrap gap-2 mt-2">
            {filters.payment_methods.map((method) => (
              <div key={method} className="flex items-center bg-secondary text-secondary-foreground px-2 py-1 rounded-md text-sm">
                {method.replace('_', ' ').toUpperCase()}
                <Button
                  variant="ghost"
                  size="sm"
                  className="ml-1 h-4 w-4 p-0"
                  onClick={() => removeFromArrayFilter('payment_methods', method)}
                >
                  <X className="h-3 w-3" />
                </Button>
              </div>
            ))}
          </div>
        )}
      </div>
      <div className="flex items-center space-x-2">
        <Checkbox
          id="include_unmatched"
          checked={filters.include_unmatched || false}
          onCheckedChange={(checked) => updateFilter('include_unmatched', checked)}
        />
        <Label htmlFor="include_unmatched">Include unmatched payments</Label>
      </div>
    </>
  );

  const renderExpenseFilters = () => (
    <>
      <div className="space-y-2">
        <Label>Categories</Label>
        <Select onValueChange={(value) => addToArrayFilter('categories', value)}>
          <SelectTrigger>
            <SelectValue placeholder="Select category..." />
          </SelectTrigger>
          <SelectContent>
            {EXPENSE_CATEGORY_OPTIONS.map((category) => (
              <SelectItem key={category.value} value={category.value}>
                {category.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {filters.categories && filters.categories.length > 0 && (
          <div className="flex flex-wrap gap-2 mt-2">
            {filters.categories.map((category) => (
              <div key={category} className="flex items-center bg-secondary text-secondary-foreground px-2 py-1 rounded-md text-sm">
                {EXPENSE_CATEGORY_OPTIONS.find(c => c.value === category)?.label || category}
                <Button
                  variant="ghost"
                  size="sm"
                  className="ml-1 h-4 w-4 p-0"
                  onClick={() => removeFromArrayFilter('categories', category)}
                >
                  <X className="h-3 w-3" />
                </Button>
              </div>
            ))}
          </div>
        )}
      </div>
      <div className="space-y-2">
        <Label>Vendor</Label>
        <Input
          placeholder="Enter vendor name..."
          value={filters.vendor || ''}
          onChange={(e) => updateFilter('vendor', e.target.value)}
        />
      </div>
      <div className="flex items-center space-x-2">
        <Checkbox
          id="include_attachments"
          checked={filters.include_attachments || false}
          onCheckedChange={(checked) => updateFilter('include_attachments', checked)}
        />
        <Label htmlFor="include_attachments">Include attachment information</Label>
      </div>
    </>
  );

  const renderClientSpecificFilters = () => (
    <>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label>Minimum Balance</Label>
          <Input
            type="number"
            placeholder="0.00"
            value={filters.balance_min || ''}
            onChange={(e) => updateFilter('balance_min', e.target.value ? parseFloat(e.target.value) : undefined)}
          />
        </div>
        <div className="space-y-2">
          <Label>Maximum Balance</Label>
          <Input
            type="number"
            placeholder="0.00"
            value={filters.balance_max || ''}
            onChange={(e) => updateFilter('balance_max', e.target.value ? parseFloat(e.target.value) : undefined)}
          />
        </div>
      </div>
      <div className="flex items-center space-x-2">
        <Checkbox
          id="include_inactive"
          checked={filters.include_inactive || false}
          onCheckedChange={(checked) => updateFilter('include_inactive', checked)}
        />
        <Label htmlFor="include_inactive">Include inactive clients</Label>
      </div>
    </>
  );

  const renderStatementFilters = () => (
    <>
      <div className="space-y-2">
        <Label>Transaction Types</Label>
        <Select onValueChange={(value) => addToArrayFilter('transaction_types', value)}>
          <SelectTrigger>
            <SelectValue placeholder="Select transaction type..." />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="debit">Debit</SelectItem>
            <SelectItem value="credit">Credit</SelectItem>
          </SelectContent>
        </Select>
        {filters.transaction_types && filters.transaction_types.length > 0 && (
          <div className="flex flex-wrap gap-2 mt-2">
            {filters.transaction_types.map((type) => (
              <div key={type} className="flex items-center bg-secondary text-secondary-foreground px-2 py-1 rounded-md text-sm">
                {type.toUpperCase()}
                <Button
                  variant="ghost"
                  size="sm"
                  className="ml-1 h-4 w-4 p-0"
                  onClick={() => removeFromArrayFilter('transaction_types', type)}
                >
                  <X className="h-3 w-3" />
                </Button>
              </div>
            ))}
          </div>
        )}
      </div>
      <div className="flex items-center space-x-2">
        <Checkbox
          id="include_reconciliation"
          checked={filters.include_reconciliation || false}
          onCheckedChange={(checked) => updateFilter('include_reconciliation', checked)}
        />
        <Label htmlFor="include_reconciliation">Include reconciliation status</Label>
      </div>
    </>
  );

  return (
    <Card>
      <CardHeader>
        <CardTitle>Report Filters</CardTitle>
        <CardDescription>
          Configure filters for your {reportTypeConfig.name.toLowerCase()} report
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Common filters */}
        {renderDateRangeFilter()}
        {reportType !== 'client' && renderClientFilter()}
        {renderCurrencyFilter()}
        
        {/* Amount range for applicable report types */}
        {['invoice', 'payment', 'expense', 'statement'].includes(reportType) && renderAmountRangeFilter()}
        
        {/* Report-specific filters */}
        {reportType === 'invoice' && renderInvoiceFilters()}
        {reportType === 'payment' && renderPaymentFilters()}
        {reportType === 'expense' && renderExpenseFilters()}
        {reportType === 'client' && renderClientSpecificFilters()}
        {reportType === 'statement' && renderStatementFilters()}
      </CardContent>
    </Card>
  );
};