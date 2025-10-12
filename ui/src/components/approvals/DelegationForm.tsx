import React, { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Calendar } from '@/components/ui/calendar';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { CalendarIcon, Loader2, AlertTriangle } from 'lucide-react';
import { format, addDays, isAfter, isBefore } from 'date-fns';
import { cn } from '@/lib/utils';
import { ApprovalDelegate, User } from '@/types';
import { userApi } from '@/lib/api';
import { Alert, AlertDescription } from '@/components/ui/alert';

interface DelegationFormProps {
  delegation?: ApprovalDelegate | null;
  onSubmit: (data: any) => void;
  onCancel: () => void;
  loading?: boolean;
}

export function DelegationForm({ delegation, onSubmit, onCancel, loading }: DelegationFormProps) {
  const [formData, setFormData] = useState({
    approver_id: delegation?.approver_id || 0,
    delegate_id: delegation?.delegate_id || 0,
    start_date: delegation?.start_date ? new Date(delegation.start_date) : new Date(),
    end_date: delegation?.end_date ? new Date(delegation.end_date) : addDays(new Date(), 7),
    is_active: delegation?.is_active ?? true,
  });

  const [users, setUsers] = useState<User[]>([]);
  const [loadingUsers, setLoadingUsers] = useState(true);
  const [errors, setErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    const fetchUsers = async () => {
      try {
        setLoadingUsers(true);
        const response = await userApi.getUsers();
        setUsers(response);
      } catch (error) {
        console.error('Failed to fetch users:', error);
      } finally {
        setLoadingUsers(false);
      }
    };

    fetchUsers();
  }, []);

  const validateForm = () => {
    const newErrors: Record<string, string> = {};

    if (!formData.approver_id) {
      newErrors.approver_id = 'Approver is required';
    }

    if (!formData.delegate_id) {
      newErrors.delegate_id = 'Delegate is required';
    }

    if (formData.approver_id === formData.delegate_id) {
      newErrors.delegate_id = 'Delegate cannot be the same as approver';
    }

    if (!formData.start_date) {
      newErrors.start_date = 'Start date is required';
    }

    if (!formData.end_date) {
      newErrors.end_date = 'End date is required';
    }

    if (formData.start_date && formData.end_date) {
      if (isAfter(formData.start_date, formData.end_date)) {
        newErrors.end_date = 'End date must be after start date';
      }

      if (isBefore(formData.end_date, new Date())) {
        newErrors.end_date = 'End date cannot be in the past';
      }
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!validateForm()) {
      return;
    }

    const submitData = {
      approver_id: formData.approver_id,
      delegate_id: formData.delegate_id,
      start_date: formData.start_date.toISOString(),
      end_date: formData.end_date.toISOString(),
      is_active: formData.is_active,
    };

    onSubmit(submitData);
  };

  const handleDateSelect = (field: 'start_date' | 'end_date', date: Date | undefined) => {
    if (date) {
      setFormData(prev => ({ ...prev, [field]: date }));
      // Clear related errors
      if (errors[field]) {
        setErrors(prev => ({ ...prev, [field]: '' }));
      }
    }
  };

  const isExpiringSoon = (endDate: Date) => {
    const daysUntilExpiry = Math.ceil((endDate.getTime() - new Date().getTime()) / (1000 * 60 * 60 * 24));
    return daysUntilExpiry <= 3 && daysUntilExpiry > 0;
  };

  const isExpired = (endDate: Date) => {
    return isBefore(endDate, new Date());
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {/* Expiration Warning */}
      {delegation && (isExpiringSoon(new Date(delegation.end_date)) || isExpired(new Date(delegation.end_date))) && (
        <Alert variant={isExpired(new Date(delegation.end_date)) ? "destructive" : "default"}>
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription>
            {isExpired(new Date(delegation.end_date)) 
              ? 'This delegation has expired and is no longer active.'
              : `This delegation expires in ${Math.ceil((new Date(delegation.end_date).getTime() - new Date().getTime()) / (1000 * 60 * 60 * 24))} day(s).`
            }
          </AlertDescription>
        </Alert>
      )}

      <div className="grid grid-cols-2 gap-4">
        {/* Approver Selection */}
        <div className="space-y-2">
          <Label htmlFor="approver_id">Approver *</Label>
          <Select
            value={formData.approver_id.toString()}
            onValueChange={(value) => {
              setFormData(prev => ({ ...prev, approver_id: parseInt(value) }));
              if (errors.approver_id) {
                setErrors(prev => ({ ...prev, approver_id: '' }));
              }
            }}
            disabled={loadingUsers}
          >
            <SelectTrigger className={cn(errors.approver_id && "border-red-500")}>
              <SelectValue placeholder="Select approver" />
            </SelectTrigger>
            <SelectContent>
              {users.map((user) => (
                <SelectItem key={user.id} value={user.id.toString()}>
                  {user.name} ({user.email})
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {errors.approver_id && (
            <p className="text-sm text-red-500">{errors.approver_id}</p>
          )}
        </div>

        {/* Delegate Selection */}
        <div className="space-y-2">
          <Label htmlFor="delegate_id">Delegate *</Label>
          <Select
            value={formData.delegate_id.toString()}
            onValueChange={(value) => {
              setFormData(prev => ({ ...prev, delegate_id: parseInt(value) }));
              if (errors.delegate_id) {
                setErrors(prev => ({ ...prev, delegate_id: '' }));
              }
            }}
            disabled={loadingUsers}
          >
            <SelectTrigger className={cn(errors.delegate_id && "border-red-500")}>
              <SelectValue placeholder="Select delegate" />
            </SelectTrigger>
            <SelectContent>
              {users
                .filter(user => user.id !== formData.approver_id)
                .map((user) => (
                  <SelectItem key={user.id} value={user.id.toString()}>
                    {user.name} ({user.email})
                  </SelectItem>
                ))}
            </SelectContent>
          </Select>
          {errors.delegate_id && (
            <p className="text-sm text-red-500">{errors.delegate_id}</p>
          )}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        {/* Start Date */}
        <div className="space-y-2">
          <Label>Start Date *</Label>
          <Popover>
            <PopoverTrigger asChild>
              <Button
                variant="outline"
                className={cn(
                  "w-full justify-start text-left font-normal",
                  !formData.start_date && "text-muted-foreground",
                  errors.start_date && "border-red-500"
                )}
              >
                <CalendarIcon className="mr-2 h-4 w-4" />
                {formData.start_date ? format(formData.start_date, "PPP") : "Pick a date"}
              </Button>
            </PopoverTrigger>
            <PopoverContent className="w-auto p-0" align="start">
              <Calendar
                mode="single"
                selected={formData.start_date}
                onSelect={(date) => handleDateSelect('start_date', date)}
                disabled={(date) => isBefore(date, new Date())}
                initialFocus
              />
            </PopoverContent>
          </Popover>
          {errors.start_date && (
            <p className="text-sm text-red-500">{errors.start_date}</p>
          )}
        </div>

        {/* End Date */}
        <div className="space-y-2">
          <Label>End Date *</Label>
          <Popover>
            <PopoverTrigger asChild>
              <Button
                variant="outline"
                className={cn(
                  "w-full justify-start text-left font-normal",
                  !formData.end_date && "text-muted-foreground",
                  errors.end_date && "border-red-500"
                )}
              >
                <CalendarIcon className="mr-2 h-4 w-4" />
                {formData.end_date ? format(formData.end_date, "PPP") : "Pick a date"}
              </Button>
            </PopoverTrigger>
            <PopoverContent className="w-auto p-0" align="start">
              <Calendar
                mode="single"
                selected={formData.end_date}
                onSelect={(date) => handleDateSelect('end_date', date)}
                disabled={(date) => isBefore(date, formData.start_date || new Date())}
                initialFocus
              />
            </PopoverContent>
          </Popover>
          {errors.end_date && (
            <p className="text-sm text-red-500">{errors.end_date}</p>
          )}
        </div>
      </div>

      {/* Active Status */}
      <div className="flex items-center space-x-2">
        <Switch
          id="is_active"
          checked={formData.is_active}
          onCheckedChange={(checked) => 
            setFormData(prev => ({ ...prev, is_active: checked }))
          }
        />
        <Label htmlFor="is_active">Active delegation</Label>
      </div>

      {/* Form Actions */}
      <div className="flex justify-end space-x-2 pt-4">
        <Button type="button" variant="outline" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" disabled={loading}>
          {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
          {delegation ? 'Update Delegation' : 'Create Delegation'}
        </Button>
      </div>
    </form>
  );
}