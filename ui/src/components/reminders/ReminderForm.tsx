import React, { useState, useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { format } from 'date-fns';
import { CalendarIcon, Plus, X, Clock, Flag, User, Repeat } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage, FormDescription } from '@/components/ui/form';
import { Calendar } from '@/components/ui/calendar';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { cn } from '@/lib/utils';
import { useTranslation } from 'react-i18next';

const reminderSchema = z.object({
  title: z.string().min(1, 'Title is required').max(200, 'Title must be less than 200 characters'),
  description: z.string().max(1000, 'Description must be less than 1000 characters').optional(),
  due_date: z.date({
    required_error: 'Due date is required',
  }),
  recurrence_pattern: z.enum(['none', 'daily', 'weekly', 'monthly', 'yearly']),
  recurrence_interval: z.number().min(1).max(365).default(1),
  recurrence_end_date: z.date().optional(),
  priority: z.enum(['low', 'medium', 'high', 'urgent']),
  assigned_to_id: z.number({
    required_error: 'Please select who to assign this reminder to',
  }),
  tags: z.array(z.string()).optional(),
  is_pinned: z.boolean().default(false),
}).refine((data) => {
  if (data.recurrence_end_date && data.recurrence_end_date <= data.due_date) {
    return false;
  }
  return true;
}, {
  message: 'End date must be after due date',
  path: ['recurrence_end_date'],
});

type ReminderFormData = z.infer<typeof reminderSchema>;

interface ReminderFormProps {
  reminder?: any;
  users: Array<{
    id: number;
    email: string;
    first_name?: string;
    last_name?: string;
  }>;
  onSubmit: (data: ReminderFormData) => void;
  onCancel: () => void;
  isLoading?: boolean;
}

export function ReminderForm({
  reminder,
  users,
  onSubmit,
  onCancel,
  isLoading = false
}: ReminderFormProps) {
  const { t } = useTranslation();
  const [newTag, setNewTag] = useState('');
  const [tags, setTags] = useState<string[]>(reminder?.tags || []);

  const form = useForm<ReminderFormData>({
    resolver: zodResolver(reminderSchema),
    defaultValues: {
      title: reminder?.title || '',
      description: reminder?.description || '',
      due_date: reminder?.due_date ? new Date(reminder.due_date) : new Date(),
      recurrence_pattern: reminder?.recurrence_pattern || 'none',
      recurrence_interval: reminder?.recurrence_interval || 1,
      recurrence_end_date: reminder?.recurrence_end_date ? new Date(reminder.recurrence_end_date) : undefined,
      priority: reminder?.priority || 'medium',
      assigned_to_id: reminder?.assigned_to_id || users[0]?.id,
      tags: reminder?.tags || [],
      is_pinned: reminder?.is_pinned || false,
    },
  });

  const watchRecurrence = form.watch('recurrence_pattern');

  useEffect(() => {
    form.setValue('tags', tags);
  }, [tags, form]);

  const handleSubmit = (data: ReminderFormData) => {
    onSubmit({ ...data, tags });
  };

  const addTag = () => {
    if (newTag.trim() && !tags.includes(newTag.trim())) {
      setTags([...tags, newTag.trim()]);
      setNewTag('');
    }
  };

  const removeTag = (tagToRemove: string) => {
    setTags(tags.filter(tag => tag !== tagToRemove));
  };

  const getUserDisplayName = (user: any) => {
    if (user?.first_name && user?.last_name) {
      return `${user.first_name} ${user.last_name} (${user.email})`;
    }
    return user?.first_name || user?.last_name || user?.email || 'Unknown';
  };

  const priorityOptions = [
    { value: 'low', label: t('reminders.priority.low'), color: 'text-green-600' },
    { value: 'medium', label: t('reminders.priority.medium'), color: 'text-yellow-600' },
    { value: 'high', label: t('reminders.priority.high'), color: 'text-orange-600' },
    { value: 'urgent', label: t('reminders.priority.urgent'), color: 'text-red-600' },
  ];

  const recurrenceOptions = [
    { value: 'none', label: t('reminders.recurrence.none') },
    { value: 'daily', label: t('reminders.recurrence.daily') },
    { value: 'weekly', label: t('reminders.recurrence.weekly') },
    { value: 'monthly', label: t('reminders.recurrence.monthly') },
    { value: 'yearly', label: t('reminders.recurrence.yearly') },
  ];

  return (
    <Card className="w-full max-w-2xl mx-auto">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Clock className="h-5 w-5" />
          {reminder ? t('reminders.form.edit_reminder') : t('reminders.form.create_reminder')}
        </CardTitle>
      </CardHeader>

      <Form {...form}>
        <form onSubmit={form.handleSubmit(handleSubmit)}>
          <CardContent className="space-y-6">
            {/* Title */}
            <FormField
              control={form.control}
              name="title"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t('reminders.form.title')} *</FormLabel>
                  <FormControl>
                    <Input
                      placeholder={t('reminders.form.title_placeholder')}
                      {...field}
                      disabled={isLoading}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            {/* Description */}
            <FormField
              control={form.control}
              name="description"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t('reminders.form.description')}</FormLabel>
                  <FormControl>
                    <Textarea
                      placeholder={t('reminders.form.description_placeholder')}
                      className="min-h-[80px]"
                      {...field}
                      disabled={isLoading}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            {/* Due Date */}
            <FormField
              control={form.control}
              name="due_date"
              render={({ field }) => (
                <FormItem className="flex flex-col">
                  <FormLabel>{t('reminders.form.due_date')} *</FormLabel>
                  <Popover>
                    <PopoverTrigger asChild>
                      <FormControl>
                        <Button
                          variant="outline"
                          className={cn(
                            "w-full pl-3 text-left font-normal",
                            !field.value && "text-muted-foreground"
                          )}
                          disabled={isLoading}
                        >
                          {field.value ? (
                            format(field.value, "PPP 'at' h:mm a")
                          ) : (
                            <span>Pick a date and time</span>
                          )}
                          <CalendarIcon className="ml-auto h-4 w-4 opacity-50" />
                        </Button>
                      </FormControl>
                    </PopoverTrigger>
                    <PopoverContent className="w-auto p-0" align="start">
                      <Calendar
                        mode="single"
                        selected={field.value}
                        onSelect={(date) => {
                          if (date) {
                            const current = field.value || new Date();
                            date.setHours(current.getHours());
                            date.setMinutes(current.getMinutes());
                            field.onChange(date);
                          }
                        }}
                        disabled={(date) => date < new Date()}
                        initialFocus
                      />
                      <div className="p-3 border-t">
                        <div className="flex items-center gap-2">
                          <Input
                            type="number"
                            min="0"
                            max="23"
                            placeholder="HH"
                            className="w-16"
                            value={field.value ? field.value.getHours() : 0}
                            onChange={(e) => {
                              const date = field.value || new Date();
                              date.setHours(parseInt(e.target.value) || 0);
                              field.onChange(new Date(date));
                            }}
                          />
                          <span>:</span>
                          <Input
                            type="number"
                            min="0"
                            max="59"
                            placeholder="MM"
                            className="w-16"
                            value={field.value ? field.value.getMinutes() : 0}
                            onChange={(e) => {
                              const date = field.value || new Date();
                              date.setMinutes(parseInt(e.target.value) || 0);
                              field.onChange(new Date(date));
                            }}
                          />
                        </div>
                      </div>
                    </PopoverContent>
                  </Popover>
                  <FormMessage />
                </FormItem>
              )}
            />

            {/* Priority */}
            <FormField
              control={form.control}
              name="priority"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t('reminders.form.priority')}</FormLabel>
                  <Select onValueChange={field.onChange} defaultValue={field.value} disabled={isLoading}>
                    <FormControl>
                      <SelectTrigger>
                        <SelectValue placeholder={t('reminders.form.select_priority')}>
                          <div className="flex items-center gap-2">
                            <Flag className="h-4 w-4" />
                            {t(priorityOptions.find(p => p.value === field.value)?.label)}
                          </div>
                        </SelectValue>
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {priorityOptions.map((option) => (
                        <SelectItem key={option.value} value={option.value}>
                          <div className={cn("flex items-center gap-2", option.color)}>
                            <Flag className="h-4 w-4" />
                            {t(option.label)}
                          </div>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />

            {/* Assigned To */}
            <FormField
              control={form.control}
              name="assigned_to_id"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t('reminders.form.assign_to')} *</FormLabel>
                  <Select 
                    onValueChange={(value) => field.onChange(parseInt(value))} 
                    defaultValue={field.value?.toString()}
                    disabled={isLoading}
                  >
                    <FormControl>
                      <SelectTrigger>
                        <SelectValue placeholder={t('reminders.form.select_user')}>
                          <div className="flex items-center gap-2">
                            <User className="h-4 w-4" />
                            {users.find(u => u.id === field.value) && 
                             getUserDisplayName(users.find(u => u.id === field.value))}
                          </div>
                        </SelectValue>
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {users.map((user) => (
                        <SelectItem key={user.id} value={user.id.toString()}>
                          <div className="flex items-center gap-2">
                            <User className="h-4 w-4" />
                            {getUserDisplayName(user)}
                          </div>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />

            {/* Recurrence */}
            <div className="space-y-4">
              <FormField
                control={form.control}
                name="recurrence_pattern"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t('reminders.form.recurrence')}</FormLabel>
                    <Select onValueChange={field.onChange} defaultValue={field.value} disabled={isLoading}>
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue placeholder={t('reminders.form.select_recurrence')}>
                            <div className="flex items-center gap-2">
                              <Repeat className="h-4 w-4" />
                              {recurrenceOptions.find(r => r.value === field.value)?.label}
                            </div>
                          </SelectValue>
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {recurrenceOptions.map((option) => (
                          <SelectItem key={option.value} value={option.value}>
                            <div className="flex items-center gap-2">
                              <Repeat className="h-4 w-4" />
                              {option.label}
                            </div>
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {watchRecurrence !== 'none' && (
                <>
                  <FormField
                    control={form.control}
                    name="recurrence_interval"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>{t('reminders.repeat_every')}</FormLabel>
                        <FormControl>
                          <div className="flex items-center gap-2">
                            <Input
                              type="number"
                              min={1}
                              max={365}
                              className="w-20"
                              {...field}
                              onChange={(e) => field.onChange(parseInt(e.target.value))}
                              disabled={isLoading}
                            />
                            <span className="text-sm text-muted-foreground">
                              {watchRecurrence === 'daily' && t('reminders.recurrence.days')}
                              {watchRecurrence === 'weekly' && t('reminders.recurrence.weeks')}
                              {watchRecurrence === 'monthly' && t('reminders.recurrence.months')}
                              {watchRecurrence === 'yearly' && t('reminders.recurrence.years')}
                            </span>
                          </div>
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="recurrence_end_date"
                    render={({ field }) => (
                      <FormItem className="flex flex-col">
                        <FormLabel>{t('reminders.end_recurrence')} (Optional)</FormLabel>
                        <Popover>
                          <PopoverTrigger asChild>
                            <FormControl>
                              <Button
                                variant="outline"
                                className={cn(
                                  "w-full pl-3 text-left font-normal",
                                  !field.value && "text-muted-foreground"
                                )}
                                disabled={isLoading}
                              >
                                {field.value ? (
                                  format(field.value, "PPP")
                                ) : (
                                  <span>{t('reminders.select_end_date')} (optional)</span>
                                )}
                                <CalendarIcon className="ml-auto h-4 w-4 opacity-50" />
                              </Button>
                            </FormControl>
                          </PopoverTrigger>
                          <PopoverContent className="w-auto p-0" align="start">
                            <Calendar
                              mode="single"
                              selected={field.value}
                              onSelect={field.onChange}
                              disabled={(date) => date < new Date()}
                              initialFocus
                            />
                          </PopoverContent>
                        </Popover>
                        <FormDescription>
                          {t('reminders.leave_empty_indefinite')}
                        </FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </>
              )}
            </div>

            {/* Pinning */}
            <FormField
              control={form.control}
              name="is_pinned"
              render={({ field }) => (
                <FormItem className="flex flex-row items-start space-x-3 space-y-0 rounded-md border p-4">
                  <FormControl>
                    <Checkbox
                      checked={field.value}
                      onCheckedChange={field.onChange}
                      disabled={isLoading}
                    />
                  </FormControl>
                  <div className="space-y-1 leading-none">
                    <FormLabel>
                      {t('reminders.form.pin_reminder')}
                    </FormLabel>
                    <FormDescription>
                      {t('reminders.form.pin_description')}
                    </FormDescription>
                  </div>
                </FormItem>
              )}
            />

            {/* Tags */}
            <div className="space-y-3">
              <label className="text-sm font-medium">{t('reminders.form.tags')}</label>
              <div className="flex gap-2">
                <Input
                  placeholder={t('reminders.form.add_tag')}
                  value={newTag}
                  onChange={(e) => setNewTag(e.target.value)}
                  onKeyPress={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault();
                      addTag();
                    }
                  }}
                  disabled={isLoading}
                />
                <Button
                  type="button"
                  variant="outline"
                  size="icon"
                  onClick={addTag}
                  disabled={!newTag.trim() || isLoading}
                >
                  <Plus className="h-4 w-4" />
                </Button>
              </div>
              {tags.length > 0 && (
                <div className="flex flex-wrap gap-2">
                  {tags.map((tag, index) => (
                    <Badge key={index} variant="secondary" className="flex items-center gap-1">
                      {tag}
                      <button
                        type="button"
                        onClick={() => removeTag(tag)}
                        className="ml-1 hover:text-red-600"
                        disabled={isLoading}
                      >
                        <X className="h-3 w-3" />
                      </button>
                    </Badge>
                  ))}
                </div>
              )}
            </div>
          </CardContent>

          <CardFooter className="flex justify-end gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={onCancel}
              disabled={isLoading}
            >
              {t('reminders.form.cancel')}
            </Button>
            <Button type="submit" disabled={isLoading}>
              {isLoading ? t('reminders.form.saving') : reminder ? t('reminders.form.update_reminder') : t('reminders.form.create_reminder')}
            </Button>
          </CardFooter>
        </form>
      </Form>
    </Card>
  );
}
