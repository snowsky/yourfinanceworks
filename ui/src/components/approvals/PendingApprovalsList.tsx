import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { approvalApi } from '@/lib/api';
import { ExpenseApproval } from '@/types';
import {
  Search,
  Filter,
  Calendar,
  DollarSign,
  Building,
  SortAsc,
  SortDesc,
  Eye
} from 'lucide-react';
import { toast } from 'sonner';
import { formatDistanceToNow } from 'date-fns';

interface PendingApprovalsListProps {
  onApprovalAction?: () => void;
}

interface Filters {
  category?: string;
  min_amount?: number;
  max_amount?: number;
  sort_by: string;
  sort_order: 'asc' | 'desc';
}

export function PendingApprovalsList({ onApprovalAction }: PendingApprovalsListProps) {
  const navigate = useNavigate();
  const [approvals, setApprovals] = useState<ExpenseApproval[]>([]);
  const [loading, setLoading] = useState(true);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [searchQuery, setSearchQuery] = useState('');
  const [filters, setFilters] = useState<Filters>({
    sort_by: 'submitted_at',
    sort_order: 'desc'
  });
  const [showFilters, setShowFilters] = useState(false);

  const pageSize = 10;

  useEffect(() => {
    fetchApprovals();
  }, [page, filters]);

  const fetchApprovals = async () => {
    try {
      setLoading(true);
      const data = await approvalApi.getPendingApprovals({
        limit: pageSize,
        offset: page * pageSize,
        ...filters
      });
      setApprovals(data.approvals || []);
      setTotal(data.total || 0);
    } catch (error) {
      console.error('Failed to fetch pending approvals:', error);
      toast.error('Failed to load pending approvals');
    } finally {
      setLoading(false);
    }
  };

  const handleApprovalAction = async (approvalId: number, action: 'approve' | 'reject', data?: any) => {
    try {
      if (action === 'approve') {
        await approvalApi.approveExpense(approvalId, data?.notes);
        toast.success('Expense approved successfully');
      } else {
        await approvalApi.rejectExpense(approvalId, data?.reason, data?.notes);
        toast.success('Expense rejected successfully');
      }
      
      // Refresh the list
      await fetchApprovals();
      onApprovalAction?.();
    } catch (error) {
      console.error(`Failed to ${action} expense:`, error);
      toast.error(`Failed to ${action} expense`);
    }
  };

  const handleSortChange = (sortBy: string) => {
    setFilters(prev => ({
      ...prev,
      sort_by: sortBy,
      sort_order: prev.sort_by === sortBy && prev.sort_order === 'asc' ? 'desc' : 'asc'
    }));
  };

  const filteredApprovals = (approvals || []).filter(approval => {
    if (!searchQuery) return true;
    const searchLower = searchQuery.toLowerCase();
    return (
      approval.expense?.vendor?.toLowerCase().includes(searchLower) ||
      approval.expense?.category?.toLowerCase().includes(searchLower) ||
      approval.expense?.notes?.toLowerCase().includes(searchLower)
    );
  });

  if (loading && (approvals || []).length === 0) {
    return (
      <div className="space-y-4">
        {[...Array(3)].map((_, i) => (
          <Card key={i}>
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div className="space-y-2 flex-1">
                  <Skeleton className="h-4 w-32" />
                  <Skeleton className="h-3 w-48" />
                  <Skeleton className="h-3 w-24" />
                </div>
                <div className="flex gap-2">
                  <Skeleton className="h-8 w-20" />
                  <Skeleton className="h-8 w-20" />
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Search and Filters */}
      <div className="flex flex-col sm:flex-row gap-4">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-muted-foreground h-4 w-4" />
          <Input
            placeholder="Search by vendor, category, or notes..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-10"
          />
        </div>
        
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowFilters(!showFilters)}
            className="flex items-center gap-2"
          >
            <Filter className="h-4 w-4" />
            Filters
          </Button>
          
          <Select value={filters.sort_by} onValueChange={handleSortChange}>
            <SelectTrigger className="w-40">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="submitted_at">Date Submitted</SelectItem>
              <SelectItem value="amount">Amount</SelectItem>
              <SelectItem value="category">Category</SelectItem>
              <SelectItem value="vendor">Vendor</SelectItem>
            </SelectContent>
          </Select>
          
          <Button
            variant="outline"
            size="sm"
            onClick={() => handleSortChange(filters.sort_by)}
            className="px-2"
          >
            {filters.sort_order === 'asc' ? <SortAsc className="h-4 w-4" /> : <SortDesc className="h-4 w-4" />}
          </Button>
        </div>
      </div>

      {/* Advanced Filters */}
      {showFilters && (
        <Card>
          <CardContent className="p-4">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="text-sm font-medium mb-2 block">Category</label>
                <Input
                  placeholder="Filter by category"
                  value={filters.category || ''}
                  onChange={(e) => setFilters(prev => ({ ...prev, category: e.target.value || undefined }))}
                />
              </div>
              <div>
                <label className="text-sm font-medium mb-2 block">Min Amount</label>
                <Input
                  type="number"
                  placeholder="0.00"
                  value={filters.min_amount || ''}
                  onChange={(e) => setFilters(prev => ({ ...prev, min_amount: e.target.value ? parseFloat(e.target.value) : undefined }))}
                />
              </div>
              <div>
                <label className="text-sm font-medium mb-2 block">Max Amount</label>
                <Input
                  type="number"
                  placeholder="1000.00"
                  value={filters.max_amount || ''}
                  onChange={(e) => setFilters(prev => ({ ...prev, max_amount: e.target.value ? parseFloat(e.target.value) : undefined }))}
                />
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Approvals List */}
      {filteredApprovals.length === 0 ? (
        <Card>
          <CardContent className="p-8 text-center">
            <div className="text-muted-foreground">
              {searchQuery || Object.values(filters).some(v => v && v !== 'submitted_at' && v !== 'desc') 
                ? 'No approvals match your search criteria' 
                : 'No pending approvals'}
            </div>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {filteredApprovals.map((approval) => (
            <Card key={approval.id} className="hover:shadow-md transition-shadow">
              <CardContent className="p-4">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 space-y-2">
                    <div className="flex items-center gap-2 flex-wrap">
                      <Badge variant="outline" className="flex items-center gap-1">
                        <DollarSign className="h-3 w-3" />
                        {approval.expense?.currency || 'USD'} {approval.expense?.amount?.toFixed(2)}
                      </Badge>
                      
                      <Badge variant="secondary">
                        {approval.expense?.category}
                      </Badge>
                      
                      {approval.expense?.vendor && (
                        <Badge variant="outline" className="flex items-center gap-1">
                          <Building className="h-3 w-3" />
                          {approval.expense?.vendor}
                        </Badge>
                      )}
                      
                      <Badge variant="outline" className="flex items-center gap-1">
                        <Calendar className="h-3 w-3" />
                        {new Date(approval.expense?.expense_date || '').toLocaleDateString()}
                      </Badge>
                    </div>
                    
                    {approval.expense?.notes && (
                      <p className="text-sm text-muted-foreground">
                        {approval.expense.notes}
                      </p>
                    )}
                    
                    <div className="flex items-center gap-4 text-xs text-muted-foreground">
                      <span>
                        Submitted {approval.submitted_at && !isNaN(new Date(approval.submitted_at).getTime()) ? formatDistanceToNow(new Date(approval.submitted_at)) : 'recently'} ago
                      </span>
                      {approval.approval_rule && (
                        <span>Rule: {approval.approval_rule.name}</span>
                      )}
                    </div>
                  </div>
                  
                  <div className="flex-shrink-0 flex flex-col gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => navigate(`/expenses/view/${approval.expense_id}`)}
                      className="w-full"
                    >
                      <Eye className="h-4 w-4 mr-2" />
                      View Details
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Pagination */}
      {total > pageSize && (
        <div className="flex items-center justify-between">
          <div className="text-sm text-muted-foreground">
            Showing {page * pageSize + 1} to {Math.min((page + 1) * pageSize, total)} of {total} approvals
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
              onClick={() => setPage(prev => prev + 1)}
              disabled={(page + 1) * pageSize >= total}
            >
              Next
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}