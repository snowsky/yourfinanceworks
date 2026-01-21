import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Pagination, PaginationContent, PaginationItem, PaginationNext, PaginationPrevious } from '@/components/ui/pagination';
import { Checkbox } from '@/components/ui/checkbox';
import { CurrencyDisplay } from '@/components/ui/currency-display';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Calendar } from '@/components/ui/calendar';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { CalendarIcon, X } from 'lucide-react';
import { format, parseISO, isValid } from 'date-fns';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog';
import { Loader2, Plus, Search, Trash2, Upload, ChevronDown, MoreHorizontal, Edit, Send } from 'lucide-react';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { Link } from 'react-router-dom';
import { useSearchParams } from 'react-router-dom';
import { toast } from 'sonner';
import { expenseApi, Expense, ExpenseAttachmentMeta, api } from '@/lib/api';
import { Badge } from '@/components/ui/badge';
import { CurrencySelector } from '@/components/ui/currency-selector';
import { EXPENSE_CATEGORY_OPTIONS } from '@/constants/expenses';
import { canPerformActions } from '@/utils/auth';

// Import Tax Integration Components
import {
  SendToTaxServiceButton,
  TaxIntegrationStatus,
  BulkSendToTaxServiceDialog,
} from '@/components/tax-integration';

// Helper function to format date without timezone issues
const formatDateToISO = (date: Date): string => {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
};

// Helper function to safely parse date strings without timezone issues
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

const defaultNewExpense: Partial<Expense> = {
  amount: 0,
  currency: 'USD',
  expense_date: formatDateToISO(new Date()),
  category: 'General',
  status: 'recorded',
};

const ExpensesWithTaxIntegration = () => {
  const { t } = useTranslation();
  const [expenses, setExpenses] = useState<Expense[]>([]);
  const categoryOptions = EXPENSE_CATEGORY_OPTIONS;
  const [loading, setLoading] = useState(true);
  const [categoryFilter, setCategoryFilter] = useState('all');
  const [labelFilter, setLabelFilter] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [unlinkedOnly, setUnlinkedOnly] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [bulkLabel, setBulkLabel] = useState('');
  const [newLabelValueById, setNewLabelValueById] = useState<Record<number, string>>({});
  const [searchParams, setSearchParams] = useSearchParams();
  const [hasNextPage, setHasNextPage] = useState(false);
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [newExpense, setNewExpense] = useState<Partial<Expense>>(defaultNewExpense);
  const [uploadingId, setUploadingId] = useState<number | null>(null);
  const [isEditOpen, setIsEditOpen] = useState(false);
  const [editExpense, setEditExpense] = useState<Partial<Expense> & { id?: number }>({});
  const [newReceiptFile, setNewReceiptFile] = useState<File | null>(null);
  const [editReceiptFile, setEditReceiptFile] = useState<File | null>(null);
  const [attachmentPreviewOpen, setAttachmentPreviewOpen] = useState<{ expenseId: number | null }>({ expenseId: null });
  const [attachments, setAttachments] = useState<Record<number, ExpenseAttachmentMeta[]>>({});
  const [preview, setPreview] = useState<{ open: boolean; url: string | null; contentType: string | null; filename: string | null }>({ open: false, url: null, contentType: null, filename: null });

  // Tax Integration State
  const [bulkSendDialogOpen, setBulkSendDialogOpen] = useState(false);

  useEffect(() => {
    return () => {
      if (preview.url) URL.revokeObjectURL(preview.url);
    };
  }, [preview.url]);

  useEffect(() => {
    fetchExpenses();
  }, [categoryFilter, labelFilter, unlinkedOnly, page, pageSize]);

  // ... existing useEffect hooks and functions from original Expenses.tsx ...

  // Handle bulk send to tax service
  const handleBulkSendToTaxService = () => {
    if (selectedIds.length === 0) {
      toast.error(t('taxIntegration.errors.noItemsSelected'));
      return;
    }
    setBulkSendDialogOpen(true);
  };

  const fetchExpenses = async () => {
    setLoading(true);
    try {
      const skip = (page - 1) * pageSize;
      const data = await expenseApi.getExpensesFiltered({
        category: categoryFilter,
        label: labelFilter || undefined,
        unlinkedOnly,
        skip,
        limit: pageSize,
        excludeStatus: 'pending_approval' // Exclude pending approval expenses from the API
      });
      setExpenses(data);

      // Determine if there's a next page based on the current page and total results
      // If we got exactly pageSize results, there might be more, so probe the next page
      if (data.length === pageSize) {
        // Probe next page existence precisely
        try {
          const probe = await expenseApi.getExpensesFiltered({
            category: categoryFilter,
            label: labelFilter || undefined,
            unlinkedOnly,
            skip: skip + pageSize,
            limit: 1,
            excludeStatus: 'pending_approval'
          });
          setHasNextPage(Array.isArray(probe) && probe.length > 0);
        } catch {
          setHasNextPage(false);
        }
      } else {
        // If we got fewer results than pageSize, there's definitely no next page
        setHasNextPage(false);
      }
    } catch (e) {
      toast.error('Failed to load expenses');
    } finally {
      setLoading(false);
    }
  };

  // Handle successful tax service send
  const handleTaxServiceSuccess = () => {
    // Refresh the expenses list to show updated status
    fetchExpenses();
    // Clear selection
    setSelectedIds([]);
  };

  return (
    <>
      <div className="flex-1 space-y-4 p-8 pt-6">
        <div className="flex items-center justify-between space-y-2">
          <h2 className="text-3xl font-bold tracking-tight">{t('navigation.expenses')}</h2>
          <div className="flex items-center space-x-2">
            <Button onClick={() => setIsCreateOpen(true)}>
              <Plus className="mr-2 h-4 w-4" />
              {t('common.add')} {t('common.expense')}
            </Button>
          </div>
        </div>

        {/* Tax Integration Status */}
        <TaxIntegrationStatus />

        {/* Existing filters and controls */}
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
          <Select value={categoryFilter} onValueChange={setCategoryFilter}>
            <SelectTrigger className="w-[180px]">
              <SelectValue placeholder={t('common.filter')} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{t('common.all')}</SelectItem>
              {categoryOptions.map((category) => (
                <SelectItem key={category} value={category}>
                  {t(`expenses.categories.${category}`)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <div className="flex items-center space-x-2">
            <Checkbox
              id="unlinked-only"
              checked={unlinkedOnly}
              onCheckedChange={(checked) => setUnlinkedOnly(checked as boolean)}
            />
            <label htmlFor="unlinked-only" className="text-sm">
              Unlinked only
            </label>
          </div>
        </div>

        {/* Bulk Actions */}
        {selectedIds.length > 0 && (
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
              {/* Other bulk actions can be added here */}
            </div>
          </div>
        )}

        {/* Expenses Table */}
        <Card>
          <CardHeader>
            <CardTitle>{t('navigation.expenses')}</CardTitle>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-12">
                    <Checkbox
                      checked={expenses.length > 0 && selectedIds.length === expenses.length}
                      onCheckedChange={(checked) => {
                        if (checked) {
                          setSelectedIds(expenses.map(e => e.id));
                        } else {
                          setSelectedIds([]);
                        }
                      }}
                    />
                  </TableHead>
                  <TableHead>{t('common.date')}</TableHead>
                  <TableHead>{t('common.description')}</TableHead>
                  <TableHead>{t('common.category')}</TableHead>
                  <TableHead>{t('common.amount')}</TableHead>
                  <TableHead>{t('common.status')}</TableHead>
                  <TableHead>{t('common.actions')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {expenses.map((expense) => (
                  <TableRow key={expense.id}>
                    <TableCell>
                      <Checkbox
                        checked={selectedIds.includes(expense.id)}
                        onCheckedChange={(checked) => {
                          if (checked) {
                            setSelectedIds(prev => [...prev, expense.id]);
                          } else {
                            setSelectedIds(prev => prev.filter(id => id !== expense.id));
                          }
                        }}
                      />
                    </TableCell>
                    <TableCell>
                      {format(safeParseDateString(expense.expense_date), 'MMM dd, yyyy')}
                    </TableCell>
                    <TableCell>
                      <div>
                        <div className="font-medium">
                          {expense.vendor || t('common.unknownVendor')}
                        </div>
                        {expense.notes && (
                          <div className="text-sm text-muted-foreground">
                            {expense.notes}
                          </div>
                        )}
                      </div>
                    </TableCell>
                    <TableCell>{expense.category}</TableCell>
                    <TableCell>
                      <CurrencyDisplay
                        amount={expense.amount}
                        currency={expense.currency}
                      />
                    </TableCell>
                    <TableCell>
                      <Badge variant={expense.status === 'recorded' ? 'default' : 'secondary'}>
                        {expense.status}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center space-x-2">
                        <SendToTaxServiceButton
                          itemId={expense.id}
                          itemType="expense"
                          onSuccess={handleTaxServiceSuccess}
                          size="sm"
                          variant="ghost"
                        />
                        <Link to={`/expenses/edit/${expense.id}`}>
                          <Button variant="ghost" size="sm">
                            <Edit className="h-4 w-4" />
                          </Button>
                        </Link>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>

        {/* Bulk Send Dialog */}
        <BulkSendToTaxServiceDialog
          open={bulkSendDialogOpen}
          onOpenChange={setBulkSendDialogOpen}
          items={expenses.filter(e => selectedIds.includes(e.id))}
          itemType="expense"
          onSuccess={handleTaxServiceSuccess}
        />

        {/* Existing dialogs and forms */}
        {/* ... (keep all existing dialog components) */}
      </div>
    </>
  );
};

export default ExpensesWithTaxIntegration;
