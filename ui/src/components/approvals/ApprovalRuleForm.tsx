import React, { useState, useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form';
import { Badge } from '@/components/ui/badge';
import { X, Plus } from 'lucide-react';
import { toast } from 'sonner';
import { approvalApi, userApi } from '@/lib/api';
import { ApprovalRule, User } from '@/types';
import { EXPENSE_CATEGORY_OPTIONS } from '@/constants/expenses';

const approvalRuleSchema = z.object({
  name: z.string().min(1, 'Rule name is required'),
  min_amount: z.number().min(0, 'Minimum amount must be 0 or greater').optional(),
  max_amount: z.number().min(0, 'Maximum amount must be 0 or greater').optional(),
  category_filter: z.array(z.string()).optional(),
  currency: z.string().min(1, 'Currency is required'),
  approval_level: z.number().min(1, 'Approval level must be 1 or greater'),
  approver_id: z.number().min(1, 'Approver is required'),
  is_active: z.boolean(),
  priority: z.number().min(0, 'Priority must be 0 or greater'),
  auto_approve_below: z.number().min(0, 'Auto-approve amount must be 0 or greater').optional(),
}).refine((data) => {
  if (data.min_amount !== undefined && data.max_amount !== undefined) {
    return data.max_amount > data.min_amount;
  }
  return true;
}, {
  message: "Maximum amount must be greater than minimum amount",
  path: ["max_amount"],
});

type ApprovalRuleFormData = z.infer<typeof approvalRuleSchema>;

interface ApprovalRuleFormProps {
  rule?: ApprovalRule;
  onSubmit: (data: ApprovalRuleFormData) => Promise<void>;
  onCancel: () => void;
  loading?: boolean;
}

export function ApprovalRuleForm({ rule, onSubmit, onCancel, loading = false }: ApprovalRuleFormProps) {
  const [users, setUsers] = useState<User[]>([]);
  const [loadingUsers, setLoadingUsers] = useState(true);
  const [selectedCategories, setSelectedCategories] = useState<string[]>(
    rule?.category_filter ? JSON.parse(rule.category_filter) : []
  );

  const form = useForm<ApprovalRuleFormData>({
    resolver: zodResolver(approvalRuleSchema),
    defaultValues: {
      name: rule?.name || '',
      min_amount: rule?.min_amount || undefined,
      max_amount: rule?.max_amount || undefined,
      category_filter: rule?.category_filter ? JSON.parse(rule.category_filter) : [],
      currency: rule?.currency || 'USD',
      approval_level: rule?.approval_level || 1,
      approver_id: rule?.approver_id || 0,
      is_active: rule?.is_active ?? true,
      priority: rule?.priority || 0,
      auto_approve_below: rule?.auto_approve_below || undefined,
    },
  });

  useEffect(() => {
    const fetchUsers = async () => {
      try {
        setLoadingUsers(true);
        const data = await userApi.getUsers();
        setUsers(data);
      } catch (error) {
        console.error('Failed to fetch users:', error);
        toast.error('Failed to load users');
      } finally {
        setLoadingUsers(false);
      }
    };

    fetchUsers();
  }, []);

  const handleSubmit = async (data: ApprovalRuleFormData) => {
    try {
      const formData = {
        ...data,
        category_filter: selectedCategories.length > 0 ? JSON.stringify(selectedCategories) : undefined,
      };
      await onSubmit(formData as any);
    } catch (error) {
      console.error('Failed to submit approval rule:', error);
      toast.error('Failed to save approval rule');
    }
  };

  const addCategory = (category: string) => {
    if (!selectedCategories.includes(category)) {
      const newCategories = [...selectedCategories, category];
      setSelectedCategories(newCategories);
      form.setValue('category_filter', newCategories);
    }
  };

  const removeCategory = (category: string) => {
    const newCategories = selectedCategories.filter(c => c !== category);
    setSelectedCategories(newCategories);
    form.setValue('category_filter', newCategories);
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          {rule ? 'Edit Approval Rule' : 'Create Approval Rule'}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-6">
            {/* Basic Information */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <FormField
                control={form.control}
                name="name"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Rule Name</FormLabel>
                    <FormControl>
                      <Input placeholder="e.g., Manager Approval for $500+" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="approver_id"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Approver</FormLabel>
                    <Select 
                      onValueChange={(value) => field.onChange(parseInt(value))}
                      value={field.value?.toString()}
                      disabled={loadingUsers}
                    >
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue placeholder="Select approver" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {users.map((user) => (
                          <SelectItem key={user.id} value={user.id.toString()}>
                            {user.name} ({user.email})
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>

            {/* Amount Thresholds */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <FormField
                control={form.control}
                name="min_amount"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Minimum Amount</FormLabel>
                    <FormControl>
                      <Input 
                        type="number" 
                        step="0.01" 
                        placeholder="0.00"
                        {...field}
                        onChange={(e) => field.onChange(e.target.value ? parseFloat(e.target.value) : undefined)}
                        value={field.value || ''}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="max_amount"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Maximum Amount</FormLabel>
                    <FormControl>
                      <Input 
                        type="number" 
                        step="0.01" 
                        placeholder="No limit"
                        {...field}
                        onChange={(e) => field.onChange(e.target.value ? parseFloat(e.target.value) : undefined)}
                        value={field.value || ''}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="currency"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Currency</FormLabel>
                    <Select onValueChange={field.onChange} value={field.value}>
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue placeholder="Select currency" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        <SelectItem value="USD">USD</SelectItem>
                        <SelectItem value="EUR">EUR</SelectItem>
                        <SelectItem value="GBP">GBP</SelectItem>
                        <SelectItem value="CAD">CAD</SelectItem>
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>

            {/* Categories */}
            <div className="space-y-3">
              <Label>Expense Categories (optional)</Label>
              <div className="space-y-2">
                <Select onValueChange={addCategory}>
                  <SelectTrigger>
                    <SelectValue placeholder="Add category filter" />
                  </SelectTrigger>
                  <SelectContent>
                    {EXPENSE_CATEGORY_OPTIONS
                      .filter(category => !selectedCategories.includes(category))
                      .map((category) => (
                        <SelectItem key={category} value={category}>
                          {category}
                        </SelectItem>
                      ))}
                  </SelectContent>
                </Select>
                
                {selectedCategories.length > 0 && (
                  <div className="flex flex-wrap gap-2">
                    {selectedCategories.map((category) => (
                      <Badge key={category} variant="secondary" className="flex items-center gap-1">
                        {category}
                        <X 
                          className="h-3 w-3 cursor-pointer" 
                          onClick={() => removeCategory(category)}
                        />
                      </Badge>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Advanced Settings */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <FormField
                control={form.control}
                name="approval_level"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Approval Level</FormLabel>
                    <FormControl>
                      <Input 
                        type="number" 
                        min="1"
                        {...field}
                        onChange={(e) => field.onChange(parseInt(e.target.value))}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="priority"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Priority</FormLabel>
                    <FormControl>
                      <Input 
                        type="number" 
                        min="0"
                        placeholder="0"
                        {...field}
                        onChange={(e) => field.onChange(parseInt(e.target.value))}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="auto_approve_below"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Auto-approve Below</FormLabel>
                    <FormControl>
                      <Input 
                        type="number" 
                        step="0.01" 
                        placeholder="No auto-approval"
                        {...field}
                        onChange={(e) => field.onChange(e.target.value ? parseFloat(e.target.value) : undefined)}
                        value={field.value || ''}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>

            {/* Active Status */}
            <FormField
              control={form.control}
              name="is_active"
              render={({ field }) => (
                <FormItem className="flex flex-row items-center justify-between rounded-lg border p-4">
                  <div className="space-y-0.5">
                    <FormLabel className="text-base">Active Rule</FormLabel>
                    <div className="text-sm text-muted-foreground">
                      Enable this rule for expense approval workflow
                    </div>
                  </div>
                  <FormControl>
                    <Switch
                      checked={field.value}
                      onCheckedChange={field.onChange}
                    />
                  </FormControl>
                </FormItem>
              )}
            />

            {/* Form Actions */}
            <div className="flex justify-end space-x-2">
              <Button type="button" variant="outline" onClick={onCancel}>
                Cancel
              </Button>
              <Button type="submit" disabled={loading}>
                {loading ? 'Saving...' : rule ? 'Update Rule' : 'Create Rule'}
              </Button>
            </div>
          </form>
        </Form>
      </CardContent>
    </Card>
  );
}