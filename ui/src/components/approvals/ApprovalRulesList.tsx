import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { Switch } from '@/components/ui/switch';
import { 
  Table, 
  TableBody, 
  TableCell, 
  TableHead, 
  TableHeader, 
  TableRow 
} from '@/components/ui/table';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { 
  Search, 
  Edit, 
  Trash2, 
  ArrowUp, 
  ArrowDown, 
  Filter,
  MoreHorizontal,
  GripVertical
} from 'lucide-react';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { toast } from 'sonner';
import { approvalApi, userApi } from '@/lib/api';
import { ApprovalRule, User } from '@/types';

interface ApprovalRulesListProps {
  onEdit: (rule: ApprovalRule) => void;
  onRefresh?: () => void;
  refreshKey?: number;
}

export function ApprovalRulesList({ onEdit, onRefresh, refreshKey }: ApprovalRulesListProps) {
  const [rules, setRules] = useState<ApprovalRule[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [approverFilter, setApproverFilter] = useState<string>('all');
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [ruleToDelete, setRuleToDelete] = useState<ApprovalRule | null>(null);
  const [draggedRule, setDraggedRule] = useState<ApprovalRule | null>(null);

  useEffect(() => {
    fetchData();
  }, [refreshKey]);

  const fetchData = async () => {
    try {
      setLoading(true);
      const [rulesData, usersData] = await Promise.all([
        approvalApi.getApprovalRules(),
        userApi.getUsers()
      ]);
      
      // Sort rules by priority (descending) then by name
      const sortedRules = rulesData.sort((a, b) => {
        if (a.priority !== b.priority) {
          return b.priority - a.priority;
        }
        return a.name.localeCompare(b.name);
      });
      
      setRules(sortedRules);
      setUsers(usersData);
    } catch (error) {
      console.error('Failed to fetch approval rules:', error);
      toast.error('Failed to load approval rules');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (rule: ApprovalRule) => {
    setRuleToDelete(rule);
    setDeleteDialogOpen(true);
  };

  const confirmDelete = async () => {
    if (!ruleToDelete) return;

    try {
      await approvalApi.deleteApprovalRule(ruleToDelete.id);
      toast.success('Approval rule deleted successfully');
      fetchData();
      onRefresh?.();
    } catch (error) {
      console.error('Failed to delete approval rule:', error);
      toast.error('Failed to delete approval rule');
    } finally {
      setDeleteDialogOpen(false);
      setRuleToDelete(null);
    }
  };

  const handleToggleActive = async (rule: ApprovalRule) => {
    try {
      await approvalApi.updateApprovalRule(rule.id, { is_active: !rule.is_active });
      toast.success(`Rule ${rule.is_active ? 'deactivated' : 'activated'} successfully`);
      fetchData();
      onRefresh?.();
    } catch (error) {
      console.error('Failed to toggle rule status:', error);
      toast.error('Failed to update rule status');
    }
  };

  const handlePriorityChange = async (rule: ApprovalRule, direction: 'up' | 'down') => {
    const currentIndex = rules.findIndex(r => r.id === rule.id);
    if (currentIndex === -1) return;

    // Find the adjacent rule to swap with
    let adjacentIndex: number;
    if (direction === 'up' && currentIndex > 0) {
      adjacentIndex = currentIndex - 1;
    } else if (direction === 'down' && currentIndex < rules.length - 1) {
      adjacentIndex = currentIndex + 1;
    } else {
      return; // Can't move in that direction
    }

    const adjacentRule = rules[adjacentIndex];
    if (!adjacentRule) return;

    try {
      // Swap priorities between the current rule and the adjacent rule
      const currentRuleNewPriority = adjacentRule.priority;
      const adjacentRuleNewPriority = rule.priority;

      // Update both rules' priorities
      await Promise.all([
        approvalApi.updateApprovalRulePriority(rule.id, currentRuleNewPriority),
        approvalApi.updateApprovalRulePriority(adjacentRule.id, adjacentRuleNewPriority)
      ]);

      toast.success('Rule priority updated');
      fetchData();
      onRefresh?.();
    } catch (error) {
      console.error('Failed to update rule priority:', error);
      toast.error('Failed to update rule priority');
    }
  };

  const filteredRules = rules.filter(rule => {
    const matchesSearch = rule.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         rule.approver?.name?.toLowerCase().includes(searchTerm.toLowerCase());
    
    const matchesStatus = statusFilter === 'all' || 
                         (statusFilter === 'active' && rule.is_active) ||
                         (statusFilter === 'inactive' && !rule.is_active);
    
    const matchesApprover = approverFilter === 'all' || 
                           rule.approver_id.toString() === approverFilter;

    return matchesSearch && matchesStatus && matchesApprover;
  });

  const getUserName = (userId: number) => {
    const user = users.find(u => u.id === userId);
    return user ? user.name : 'Unknown User';
  };

  const formatAmount = (amount?: number | null) => {
    return amount !== undefined && amount !== null ? `$${amount.toFixed(2)}` : 'No limit';
  };

  const formatCategories = (categoryFilter?: string) => {
    if (!categoryFilter) return 'All categories';
    try {
      const categories = JSON.parse(categoryFilter);
      return categories.length > 0 ? categories.join(', ') : 'All categories';
    } catch {
      return 'All categories';
    }
  };

  if (loading) {
    return (
      <Card>
        <CardContent className="p-6">
          <div className="flex items-center justify-center">
            <div className="text-muted-foreground">Loading approval rules...</div>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Filter className="h-5 w-5" />
            Approval Rules
          </CardTitle>
          
          {/* Filters */}
          <div className="flex flex-col sm:flex-row gap-4">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search rules or approvers..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-10"
              />
            </div>
            
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-full sm:w-[150px]">
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Status</SelectItem>
                <SelectItem value="active">Active</SelectItem>
                <SelectItem value="inactive">Inactive</SelectItem>
              </SelectContent>
            </Select>
            
            <Select value={approverFilter} onValueChange={setApproverFilter}>
              <SelectTrigger className="w-full sm:w-[200px]">
                <SelectValue placeholder="Approver" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Approvers</SelectItem>
                {users.map((user) => (
                  <SelectItem key={user.id} value={user.id.toString()}>
                    {user.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </CardHeader>
        
        <CardContent>
          {filteredRules.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              {rules.length === 0 ? 'No approval rules configured' : 'No rules match your filters'}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-[50px]">Order</TableHead>
                    <TableHead>Rule Name</TableHead>
                    <TableHead>Approver</TableHead>
                    <TableHead>Amount Range</TableHead>
                    <TableHead>Categories</TableHead>
                    <TableHead>Level</TableHead>
                    <TableHead>Priority</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="w-[100px]">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredRules.map((rule, index) => (
                    <TableRow key={rule.id}>
                      <TableCell>
                        <div className="flex items-center gap-1">
                          <GripVertical className="h-4 w-4 text-muted-foreground cursor-move" />
                          <div className="flex flex-col gap-1">
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-6 w-6 p-0"
                              onClick={() => handlePriorityChange(rule, 'up')}
                              disabled={index === 0}
                            >
                              <ArrowUp className="h-3 w-3" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-6 w-6 p-0"
                              onClick={() => handlePriorityChange(rule, 'down')}
                              disabled={index === filteredRules.length - 1}
                            >
                              <ArrowDown className="h-3 w-3" />
                            </Button>
                          </div>
                        </div>
                      </TableCell>
                      
                      <TableCell>
                        <div className="font-medium">{rule.name}</div>
                        {rule.auto_approve_below && (
                          <div className="text-sm text-muted-foreground">
                            Auto-approve below ${rule.auto_approve_below}
                          </div>
                        )}
                      </TableCell>
                      
                      <TableCell>
                        <div className="font-medium">{getUserName(rule.approver_id)}</div>
                      </TableCell>
                      
                      <TableCell>
                        <div className="text-sm">
                          {formatAmount(rule.min_amount)} - {formatAmount(rule.max_amount)}
                        </div>
                        <div className="text-xs text-muted-foreground">{rule.currency}</div>
                      </TableCell>
                      
                      <TableCell>
                        <div className="text-sm max-w-[200px] truncate" title={formatCategories(rule.category_filter)}>
                          {formatCategories(rule.category_filter)}
                        </div>
                      </TableCell>
                      
                      <TableCell>
                        <Badge variant="outline">Level {rule.approval_level}</Badge>
                      </TableCell>
                      
                      <TableCell>
                        <Badge variant="secondary">{rule.priority}</Badge>
                      </TableCell>
                      
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <Switch
                            checked={rule.is_active}
                            onCheckedChange={() => handleToggleActive(rule)}
                          />
                          <Badge variant={rule.is_active ? 'default' : 'secondary'}>
                            {rule.is_active ? 'Active' : 'Inactive'}
                          </Badge>
                        </div>
                      </TableCell>
                      
                      <TableCell>
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button variant="ghost" className="h-8 w-8 p-0">
                              <MoreHorizontal className="h-4 w-4" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem onClick={() => onEdit(rule)}>
                              <Edit className="mr-2 h-4 w-4" />
                              Edit
                            </DropdownMenuItem>
                            <DropdownMenuItem 
                              onClick={() => handleDelete(rule)}
                              className="text-destructive"
                            >
                              <Trash2 className="mr-2 h-4 w-4" />
                              Delete
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Approval Rule</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete the approval rule "{ruleToDelete?.name}"? 
              This action cannot be undone and may affect future expense approvals.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={confirmDelete} className="bg-destructive text-destructive-foreground">
              Delete Rule
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}