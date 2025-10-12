import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { approvalApi } from '@/lib/api';
import { Expense } from '@/types';
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
  const navigate = useNavigate();
  const [expenses, setExpenses] = useState<Expense[]>([]);
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
    } catch (error) {
      console.error('Failed to fetch processed expenses:', error);
      toast.error('Failed to load processed expenses');
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
            Approved
          </Badge>
        );
      case 'rejected':
        return (
          <Badge variant="destructive">
            <XCircle className="w-3 h-3 mr-1" />
            Rejected
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
              placeholder="Search expenses..."
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
                    <SelectItem value="">All categories</SelectItem>
                    <SelectItem value="Travel">Travel</SelectItem>
                    <SelectItem value="Meals">Meals</SelectItem>
                    <SelectItem value="Software">Software</SelectItem>
                    <SelectItem value="Office Supplies">Office Supplies</SelectItem>
                    <SelectItem value="Marketing">Marketing</SelectItem>
                    <SelectItem value="Other">Other</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div>
                <label className="text-sm font-medium mb-2 block">Sort By</label>
                <Select
                  value={filters.sort_by}
                  onValueChange={(value) => setFilters(prev => ({ ...prev, sort_by: value }))}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="date">Date</SelectItem>
                    <SelectItem value="amount">Amount</SelectItem>
                    <SelectItem value="category">Category</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div>
                <label className="text-sm font-medium mb-2 block">Order</label>
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
                        Newest First
                      </div>
                    </SelectItem>
                    <SelectItem value="asc">
                      <div className="flex items-center">
                        <SortAsc className="h-4 w-4 mr-2" />
                        Oldest First
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
          <Card>
            <CardContent className="p-8 text-center">
              <div className="text-gray-500">
                <CheckCircle className="h-12 w-12 mx-auto mb-4 text-gray-300" />
                <h3 className="text-lg font-medium mb-2">No processed expenses</h3>
                <p>You haven't approved or rejected any expenses yet.</p>
              </div>
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
                      View Details
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
            Showing {page * pageSize + 1}-{Math.min((page + 1) * pageSize, total)} of {total} expenses
          </div>

          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage(prev => Math.max(0, prev - 1))}
              disabled={page === 0}
            >
              Previous
            </Button>

            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage(prev => Math.min(totalPages - 1, prev + 1))}
              disabled={page >= totalPages - 1}
            >
              Next
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
