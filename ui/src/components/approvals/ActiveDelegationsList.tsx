import React, { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from '@/components/ui/alert-dialog';
import { Edit, Trash2, AlertTriangle, Clock, CheckCircle, XCircle, Loader2 } from 'lucide-react';
import { format, isAfter, isBefore, differenceInDays } from 'date-fns';
import { ApprovalDelegate } from '@/types';
import { approvalApi } from '@/lib/api';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';

interface ActiveDelegationsListProps {
  onEdit: (delegation: ApprovalDelegate) => void;
  onDelete: (delegationId: number) => void;
  loading?: boolean;
}

export function ActiveDelegationsList({ onEdit, onDelete, loading }: ActiveDelegationsListProps) {
  const [delegations, setDelegations] = useState<ApprovalDelegate[]>([]);
  const [loadingData, setLoadingData] = useState(true);
  const [filter, setFilter] = useState<'all' | 'active' | 'expired' | 'expiring'>('all');

  useEffect(() => {
    fetchDelegations();
  }, []);

  const fetchDelegations = async () => {
    try {
      setLoadingData(true);
      const response = await approvalApi.getDelegations();
      setDelegations(response);
    } catch (error) {
      console.error('Failed to fetch delegations:', error);
      toast.error('Failed to load delegations');
    } finally {
      setLoadingData(false);
    }
  };

  const getDelegationStatus = (delegation: ApprovalDelegate) => {
    const now = new Date();
    const startDate = new Date(delegation.start_date);
    const endDate = new Date(delegation.end_date);

    if (!delegation.is_active) {
      return { status: 'inactive', label: 'Inactive', variant: 'secondary' as const };
    }

    if (isBefore(endDate, now)) {
      return { status: 'expired', label: 'Expired', variant: 'destructive' as const };
    }

    if (isAfter(startDate, now)) {
      return { status: 'scheduled', label: 'Scheduled', variant: 'outline' as const };
    }

    const daysUntilExpiry = differenceInDays(endDate, now);
    if (daysUntilExpiry <= 3) {
      return { status: 'expiring', label: 'Expiring Soon', variant: 'destructive' as const };
    }

    return { status: 'active', label: 'Active', variant: 'default' as const };
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'active':
        return <CheckCircle className="h-4 w-4 text-green-500" />;
      case 'expired':
        return <XCircle className="h-4 w-4 text-red-500" />;
      case 'expiring':
        return <AlertTriangle className="h-4 w-4 text-orange-500" />;
      case 'scheduled':
        return <Clock className="h-4 w-4 text-blue-500" />;
      case 'inactive':
        return <XCircle className="h-4 w-4 text-gray-500" />;
      default:
        return null;
    }
  };

  const filteredDelegations = delegations.filter(delegation => {
    const { status } = getDelegationStatus(delegation);
    
    switch (filter) {
      case 'active':
        return status === 'active';
      case 'expired':
        return status === 'expired';
      case 'expiring':
        return status === 'expiring';
      default:
        return true;
    }
  });

  const getExpirationWarning = (delegation: ApprovalDelegate) => {
    const { status } = getDelegationStatus(delegation);
    const endDate = new Date(delegation.end_date);
    const daysUntilExpiry = differenceInDays(endDate, new Date());

    if (status === 'expired') {
      return `Expired ${Math.abs(daysUntilExpiry)} day(s) ago`;
    }

    if (status === 'expiring') {
      return `Expires in ${daysUntilExpiry} day(s)`;
    }

    return null;
  };

  if (loadingData) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="h-6 w-6 animate-spin" />
        <span className="ml-2">Loading delegations...</span>
      </div>
    );
  }

  if (delegations.length === 0) {
    return (
      <div className="text-center py-8">
        <p className="text-muted-foreground">No approval delegations found.</p>
        <p className="text-sm text-muted-foreground mt-1">
          Create a delegation to temporarily assign your approval responsibilities to another user.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Filter Buttons */}
      <div className="flex gap-2">
        <Button
          variant={filter === 'all' ? 'default' : 'outline'}
          size="sm"
          onClick={() => setFilter('all')}
        >
          All ({delegations.length})
        </Button>
        <Button
          variant={filter === 'active' ? 'default' : 'outline'}
          size="sm"
          onClick={() => setFilter('active')}
        >
          Active ({delegations.filter(d => getDelegationStatus(d).status === 'active').length})
        </Button>
        <Button
          variant={filter === 'expiring' ? 'default' : 'outline'}
          size="sm"
          onClick={() => setFilter('expiring')}
        >
          Expiring ({delegations.filter(d => getDelegationStatus(d).status === 'expiring').length})
        </Button>
        <Button
          variant={filter === 'expired' ? 'default' : 'outline'}
          size="sm"
          onClick={() => setFilter('expired')}
        >
          Expired ({delegations.filter(d => getDelegationStatus(d).status === 'expired').length})
        </Button>
      </div>

      {/* Delegations Table */}
      <div className="border rounded-lg">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Status</TableHead>
              <TableHead>Approver</TableHead>
              <TableHead>Delegate</TableHead>
              <TableHead>Start Date</TableHead>
              <TableHead>End Date</TableHead>
              <TableHead>Duration</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filteredDelegations.map((delegation) => {
              const { status, label, variant } = getDelegationStatus(delegation);
              const warning = getExpirationWarning(delegation);
              const duration = differenceInDays(new Date(delegation.end_date), new Date(delegation.start_date));

              return (
                <TableRow key={delegation.id} className={cn(
                  status === 'expired' && 'opacity-60',
                  status === 'expiring' && 'bg-orange-50 dark:bg-orange-950/20'
                )}>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      {getStatusIcon(status)}
                      <Badge variant={variant}>{label}</Badge>
                    </div>
                    {warning && (
                      <p className="text-xs text-muted-foreground mt-1">{warning}</p>
                    )}
                  </TableCell>
                  <TableCell>
                    <div>
                      <p className="font-medium">{delegation.approver?.name}</p>
                      <p className="text-sm text-muted-foreground">{delegation.approver?.email}</p>
                    </div>
                  </TableCell>
                  <TableCell>
                    <div>
                      <p className="font-medium">{delegation.delegate?.name}</p>
                      <p className="text-sm text-muted-foreground">{delegation.delegate?.email}</p>
                    </div>
                  </TableCell>
                  <TableCell>
                    {format(new Date(delegation.start_date), 'MMM dd, yyyy')}
                  </TableCell>
                  <TableCell>
                    {format(new Date(delegation.end_date), 'MMM dd, yyyy')}
                  </TableCell>
                  <TableCell>
                    {duration} day{duration !== 1 ? 's' : ''}
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex items-center justify-end gap-2">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => onEdit(delegation)}
                        disabled={loading}
                      >
                        <Edit className="h-4 w-4" />
                      </Button>
                      <AlertDialog>
                        <AlertDialogTrigger asChild>
                          <Button
                            variant="ghost"
                            size="sm"
                            disabled={loading}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </AlertDialogTrigger>
                        <AlertDialogContent>
                          <AlertDialogHeader>
                            <AlertDialogTitle>Delete Delegation</AlertDialogTitle>
                            <AlertDialogDescription>
                              Are you sure you want to delete this delegation? This action cannot be undone.
                              The delegate will no longer be able to approve expenses on behalf of the approver.
                            </AlertDialogDescription>
                          </AlertDialogHeader>
                          <AlertDialogFooter>
                            <AlertDialogCancel>Cancel</AlertDialogCancel>
                            <AlertDialogAction
                              onClick={() => onDelete(delegation.id)}
                              className="bg-red-600 hover:bg-red-700"
                            >
                              Delete
                            </AlertDialogAction>
                          </AlertDialogFooter>
                        </AlertDialogContent>
                      </AlertDialog>
                    </div>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>

      {filteredDelegations.length === 0 && filter !== 'all' && (
        <div className="text-center py-8">
          <p className="text-muted-foreground">No {filter} delegations found.</p>
        </div>
      )}
    </div>
  );
}