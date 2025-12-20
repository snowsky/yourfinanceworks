import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { approvalApi } from '@/lib/api';
import {
  Search,
  Filter,
  Calendar,
  DollarSign,
  Building,
  SortAsc,
  SortDesc,
  Eye,
  CheckCircle,
  XCircle
} from 'lucide-react';
import { toast } from 'sonner';
import { formatDistanceToNow } from 'date-fns';
import { useTranslation } from 'react-i18next';

interface ProcessedExpensesListProps {
  onViewDetails?: (expenseId: number) => void;
}

interface Filters {
  category?: string;
  min_amount?: number;
  max_amount?: number;
  sort_by: string;
  sort_order: 'asc' | 'desc';
}

export function ProcessedExpensesList({ onViewDetails }: ProcessedExpensesListProps) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [expenses, setExpenses] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [searchQuery, setSearchQuery] = useState('');
  const [filters, setFilters] = useState<Filters>({
    sort_by: 'date',
    sort_order: 'desc'
  });
  const [showFilters, setShowFilters] = useState(false);

  const pageSize = 10;

  const fetchExpenses = async () => {
    try {
      setLoading(true);
      const skip = page * pageSize;
      const response = await approvalApi.getProcessedExpenses({
        skip,
        limit: pageSize
      });

      const data = response.expenses || [];
      setExpenses(data);
      setTotal(response.total || 0);
    } catch (error: any) {
      console.error('Failed to fetch processed expenses:', error);
      const errorMessage = error?.message || 'Failed to load processed expenses';
      toast.error(errorMessage);
      setExpenses([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchExpenses();
  }, [page, filters]);

  const handleViewDetails = (expenseId: number) => {
    if (onViewDetails) {
      onViewDetails(expenseId);
    } else {
      navigate(`/expenses/view/${expenseId}`);
    }
  };

  const formatCurrency = (amount: number, currency: string = 'USD') => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currency,
    }).format(amount);
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'approved':
        return (
          <Badge variant="default" className="bg-green-100 text-green-800 hover:bg-green-100">
            <CheckCircle className="w-3 h-3 mr-1" />
            {t('approvalDashboard.approved')}
          </Badge>
        );
      case 'rejected':
        return (
          <Badge variant="destructive">
            <XCircle className="w-3 h-3 mr-1" />
            {t('approvalDashboard.rejected')}
          </Badge>
        );
      default:
        return (
          <Badge variant="secondary">
            {status}
          </Badge>
        );
    }
  };

  const totalPages = Math.ceil(total / pageSize);

  return (
    <div className="space-y-4">
      {/* Search and Filters */}
      <div className="flex flex-col sm:flex-row gap-4">
        <div className="flex-1">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 h-4 w-4" />
            <Input
              placeholder={t('expenses.search_placeholder', { defaultValue: 'Search by vendor, category, or notes...' })}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-10"
            />
          </div>
        </div>

        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowFilters(!showFilters)}
          >
            <Filter className="h-4 w-4 mr-2" />
            Filters
          </Button>
        </div>
      </div>

      {/* Filter Options */}
      {showFilters && (
        <Card>
          <CardContent className="pt-4">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="text-sm font-medium mb-2 block">Category</label>
                <Select
                  value={filters.category || ''}
                  onValueChange={(value) => setFilters(prev => ({ ...prev, category: value || undefined }))}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="All categories" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="">{t('approvalDashboard.all_categories')}</SelectItem>
                    <SelectItem value="Travel">{t('approvalDashboard.travel')}</SelectItem>
                    <SelectItem value="Meals">{t('approvalDashboard.meals')}</SelectItem>
                    <SelectItem value="Software">{t('approvalDashboard.software')}</SelectItem>
                    <SelectItem value="Office Supplies">{t('approvalDashboard.office_supplies')}</SelectItem>
                    <SelectItem value="Marketing">{t('approvalDashboard.marketing')}</SelectItem>
                    <SelectItem value="Other">{t('approvalDashboard.other')}</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div>
                <label className="text-sm font-medium mb-2 block">{t('approvalDashboard.sort_by')}</label>
                <Select
                  value={filters.sort_by}
                  onValueChange={(value) => setFilters(prev => ({ ...prev, sort_by: value }))}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="date">{t('approvalDashboard.date')}</SelectItem>
                    <SelectItem value="amount">{t('approvalDashboard.amount')}</SelectItem>
                    <SelectItem value="category">{t('approvalDashboard.category')}</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div>
                <label className="text-sm font-medium mb-2 block">{t('approvalDashboard.order')}</label>
                <Select
                  value={filters.sort_order}
                  onValueChange={(value) => setFilters(prev => ({ ...prev, sort_order: value as 'asc' | 'desc' }))}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="desc">
                      <div className="flex items-center">
                        <SortDesc className="h-4 w-4 mr-2" />
                        {t('approvalDashboard.newest_first')}
                      </div>
                    </SelectItem>
                    <SelectItem value="asc">
                      <div className="flex items-center">
                        <SortAsc className="h-4 w-4 mr-2" />
                        {t('approvalDashboard.oldest_first')}
                      </div>
                    </SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Expenses List */}
      <div className="space-y-2">
        {loading ? (
          // Loading skeletons
          Array.from({ length: 5 }).map((_, index) => (
            <Card key={index}>
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div className="flex-1">
                    <Skeleton className="h-4 w-48 mb-2" />
                    <Skeleton className="h-3 w-32" />
                  </div>
                  <div className="flex items-center gap-4">
                    <Skeleton className="h-6 w-16" />
                    <Skeleton className="h-8 w-20" />
                  </div>
                </div>
              </CardContent>
            </Card>
          ))
        ) : expenses.length === 0 ? (
          <Card className="border-dashed">
            <CardContent className="flex flex-col items-center justify-center py-12 text-center">
              <div className="bg-primary/5 p-6 rounded-full mb-6 ring-8 ring-primary/2">
                <CheckCircle className="h-12 w-12 text-primary/40" />
              </div>
              <h3 className="text-xl font-semibold mb-2">
                {t('approvalDashboard.no_processed_expenses_title', 'No processed expenses')}
              </h3>
              <p className="text-muted-foreground max-w-sm mx-auto mb-8">
                {t('approvalDashboard.no_processed_expenses_description', "You haven't approved or rejected any expenses yet. Your approval history will appear here.")}
              </p>
            </CardContent>
          </Card>
        ) : (
          expenses.map((expense) => (
            <Card key={expense.id} className="hover:shadow-md transition-shadow">
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <h3 className="font-medium text-gray-900 truncate">
                        {expense.description || `${expense.category} - ${expense.vendor || 'Unknown vendor'}`}
                      </h3>
                      {getStatusBadge(expense.status)}
                    </div>

                    <div className="flex items-center gap-4 text-sm text-gray-600">
                      <div className="flex items-center gap-1">
                        <DollarSign className="h-3 w-3" />
                        {formatCurrency(expense.amount, expense.currency)}
                      </div>

                      <div className="flex items-center gap-1">
                        <Building className="h-3 w-3" />
                        {expense.category}
                      </div>

                      <div className="flex items-center gap-1">
                        <Calendar className="h-3 w-3" />
                        {expense.date && !isNaN(new Date(expense.date).getTime())
                          ? formatDistanceToNow(new Date(expense.date), { addSuffix: true })
                          : 'Unknown date'
                        }
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleViewDetails(expense.id)}
                    >
                      <Eye className="h-4 w-4 mr-2" />
                      {t('approvalDashboard.view_details')}
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <div className="text-sm text-gray-600">
            {t('approvalDashboard.showing')} {page * pageSize + 1}-{Math.min((page + 1) * pageSize, total)} {t('approvalDashboard.of')} {total} {t('approvalDashboard.expenses')}
          </div>

          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage(prev => Math.max(0, prev - 1))}
              disabled={page === 0}
            >
              {t('approvalHelp.previous')}
            </Button>

            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage(prev => Math.min(totalPages - 1, prev + 1))}
              disabled={page >= totalPages - 1}
            >
              {t('approvalHelp.next')}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
