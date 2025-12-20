import React, { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { format, subDays, addDays } from 'date-fns';
import {
  Plus,
  Filter,
  Search,
  Calendar,
  List,
  Clock,
  AlertCircle,
  CheckCircle,
  Loader2,
  RefreshCw,
  Timer
} from 'lucide-react';

import { Button } from '@/components/ui/button';
import { ProfessionalButton } from '@/components/ui/professional-button';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Calendar as CalendarComponent } from '@/components/ui/calendar';
import { toast } from 'sonner';

import { ReminderCard } from './ReminderCard';
import { ReminderForm } from './ReminderForm';
import { cn } from '@/lib/utils';
import { reminderApi, userApi, authApi } from '@/lib/api';
import { useTranslation } from 'react-i18next';

interface ReminderListProps {
  className?: string;
}

interface Reminder {
  id: number;
  title: string;
  description?: string;
  due_date: string;
  priority: 'low' | 'medium' | 'high' | 'urgent';
  status: 'pending' | 'completed' | 'snoozed' | 'cancelled';
  recurrence_pattern: 'none' | 'daily' | 'weekly' | 'monthly' | 'yearly';
  assigned_to: {
    id: number;
    email: string;
    first_name?: string;
    last_name?: string;
  };
  created_by: {
    id: number;
    email: string;
    first_name?: string;
    last_name?: string;
  };
  completed_at?: string;
  snoozed_until?: string;
  tags?: string[];
  snooze_count?: number;
}

interface User {
  id: number;
  email: string;
  first_name?: string;
  last_name?: string;
}

export function ReminderList({ className }: ReminderListProps) {
  const { t } = useTranslation();
  const [searchParams, setSearchParams] = useSearchParams();
  const [reminders, setReminders] = useState<Reminder[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [editingReminder, setEditingReminder] = useState<Reminder | null>(null);
  const [formLoading, setFormLoading] = useState(false);

  // Filter states
  const [searchQuery, setSearchQuery] = useState(searchParams.get('search') || '');
  const [statusFilter, setStatusFilter] = useState(searchParams.get('status') || 'all');
  const [priorityFilter, setPriorityFilter] = useState(searchParams.get('priority') || 'all');
  const [assignedToFilter, setAssignedToFilter] = useState(searchParams.get('assigned_to') || 'all');
  const [dueDateFrom, setDueDateFrom] = useState<Date | undefined>(
    searchParams.get('due_from') ? new Date(searchParams.get('due_from')!) : undefined
  );
  const [dueDateTo, setDueDateTo] = useState<Date | undefined>(
    searchParams.get('due_to') ? new Date(searchParams.get('due_to')!) : undefined
  );

  // Pagination
  const [page, setPage] = useState(parseInt(searchParams.get('page') || '1'));
  const [totalPages, setTotalPages] = useState(1);
  const [totalCount, setTotalCount] = useState(0);

  // Tab counts
  const [tabCounts, setTabCounts] = useState({
    all: 0,
    my: 0,
    due_today: 0,
    overdue: 0,
    snoozed: 0,
    completed: 0,
  });

  const activeTab = searchParams.get('tab') || 'all';

  useEffect(() => {
    loadReminders();
    loadUsers();
    loadCurrentUser();
  }, [page, searchQuery, statusFilter, priorityFilter, assignedToFilter, dueDateFrom, dueDateTo, activeTab]);

  // Fetch tab counts when currentUser is loaded or when reminders change
  useEffect(() => {
    if (currentUser) {
      fetchTabCounts();
    }
  }, [currentUser, page, searchQuery, statusFilter, priorityFilter, assignedToFilter, dueDateFrom, dueDateTo, activeTab]);

  useEffect(() => {
    // Update URL params
    const params = new URLSearchParams();
    if (searchQuery) params.set('search', searchQuery);
    if (statusFilter !== 'all') params.set('status', statusFilter);
    if (priorityFilter !== 'all') params.set('priority', priorityFilter);
    if (assignedToFilter !== 'all') params.set('assigned_to', assignedToFilter);
    if (dueDateFrom) params.set('due_from', format(dueDateFrom, 'yyyy-MM-dd'));
    if (dueDateTo) params.set('due_to', format(dueDateTo, 'yyyy-MM-dd'));
    if (page > 1) params.set('page', page.toString());
    if (activeTab !== 'all') params.set('tab', activeTab);
    setSearchParams(params);
  }, [searchQuery, statusFilter, priorityFilter, assignedToFilter, dueDateFrom, dueDateTo, page, activeTab, setSearchParams]);

  const fetchTabCounts = async () => {
    try {
      const today = new Date();
      today.setHours(0, 0, 0, 0);
      const tomorrow = new Date(today);
      tomorrow.setDate(tomorrow.getDate() + 1);

      // Fetch counts for each tab in parallel
      const [allData, myData, dueTodayData, overdueData, snoozedData, completedData] = await Promise.all([
        reminderApi.getReminders({ page: 1, per_page: 1 }), // all
        currentUser ? reminderApi.getReminders({ page: 1, per_page: 1, assigned_to_id: currentUser.id }) : Promise.resolve({ total: 0 }), // my
        reminderApi.getReminders({ page: 1, per_page: 1, due_date_from: today.toISOString(), due_date_to: tomorrow.toISOString(), status: ['pending', 'snoozed'] }), // due_today
        reminderApi.getReminders({ page: 1, per_page: 1, due_date_to: new Date().toISOString(), status: ['pending'] }), // overdue
        reminderApi.getReminders({ page: 1, per_page: 1, status: ['snoozed'] }), // snoozed
        reminderApi.getReminders({ page: 1, per_page: 1, status: ['completed'] }), // completed
      ]);

      setTabCounts({
        all: allData.total || 0,
        my: myData.total || 0,
        due_today: dueTodayData.total || 0,
        overdue: overdueData.total || 0,
        snoozed: snoozedData.total || 0,
        completed: completedData.total || 0,
      });
    } catch (error) {
      console.error('Failed to fetch tab counts:', error);
    }
  };

  const loadReminders = async () => {
    try {
      setLoading(true);

      const params: any = {
        page,
        per_page: 20,
        sort_by: 'created_at',
        sort_order: 'desc',
      };

      if (searchQuery) params.search = searchQuery;
      if (dueDateFrom) params.due_date_from = dueDateFrom.toISOString();
      if (dueDateTo) params.due_date_to = dueDateTo.toISOString();

      // Apply tab-specific filters
      switch (activeTab) {
        case 'my':
          if (currentUser) params.assigned_to_id = currentUser.id;
          break;
        case 'due_today':
          const today = new Date();
          today.setHours(0, 0, 0, 0);
          const tomorrow = new Date(today);
          tomorrow.setDate(tomorrow.getDate() + 1);
          params.due_date_from = today.toISOString();
          params.due_date_to = tomorrow.toISOString();
          params.status = ['pending', 'snoozed'];
          break;
        case 'overdue':
          params.due_date_to = new Date().toISOString();
          params.status = ['pending'];
          break;
        case 'snoozed':
          params.status = ['snoozed'];
          break;
        case 'completed':
          params.status = ['completed'];
          break;
      }

      // Apply manual filters
      if (statusFilter !== 'all' && activeTab === 'all') {
        params.status = [statusFilter];
      }
      if (priorityFilter !== 'all') {
        params.priority = [priorityFilter];
      }
      if (assignedToFilter !== 'all') {
        params.assigned_to_id = parseInt(assignedToFilter);
      }

      const data = await reminderApi.getReminders(params);
      setReminders(data.items);
      setTotalPages(data.pages);
      setTotalCount(data.total);
    } catch (error) {
      toast.error('Failed to load reminders');
    } finally {
      setLoading(false);
    }
  };

  const loadUsers = async () => {
    try {
      const data = await userApi.getUsers();
      setUsers(data);
    } catch (error) {
      // Error loading users - silently fail
    }
  };

  const loadCurrentUser = async () => {
    try {
      const data = await authApi.getCurrentUser();
      setCurrentUser(data);
    } catch (error) {
      // Error loading current user - silently fail
    }
  };

  const handleCreateReminder = async (data: any) => {
    try {
      setFormLoading(true);
      const reminderData = {
        ...data,
        due_date: data.due_date.toISOString(),
        recurrence_end_date: data.recurrence_end_date?.toISOString(),
      };

      await reminderApi.createReminder(reminderData);

      toast.success('Reminder created successfully');
      setShowForm(false);
      loadReminders();
      fetchTabCounts();
    } catch (error) {
      toast.error('Failed to create reminder');
    } finally {
      setFormLoading(false);
    }
  };

  const handleUpdateReminder = async (data: any) => {
    if (!editingReminder) return;

    try {
      setFormLoading(true);
      const reminderData = {
        ...data,
        due_date: data.due_date.toISOString(),
        recurrence_end_date: data.recurrence_end_date?.toISOString(),
      };

      await reminderApi.updateReminder(editingReminder.id, reminderData);

      toast.success('Reminder updated successfully');
      setEditingReminder(null);
      loadReminders();
      fetchTabCounts();
    } catch (error) {
      toast.error('Failed to update reminder');
    } finally {
      setFormLoading(false);
    }
  };

  const handleCompleteReminder = async (id: number, notes?: string) => {
    try {
      await reminderApi.updateReminderStatus(id, {
        status: 'completed',
        completion_notes: notes,
      });

      toast.success('Reminder marked as completed');
      loadReminders();
      fetchTabCounts();
    } catch (error) {
      toast.error('Failed to complete reminder');
    }
  };

  const handleSnoozeReminder = async (id: number, until: Date) => {
    try {
      await reminderApi.updateReminderStatus(id, {
        status: 'snoozed',
        snoozed_until: until.toISOString(),
      });

      toast.success('Reminder snoozed');
      loadReminders();
      fetchTabCounts();
    } catch (error) {
      toast.error('Failed to snooze reminder');
    }
  };

  const handleUnsnoozeReminder = async (id: number) => {
    try {
      await reminderApi.unsnoozeReminder(id);

      toast.success('Reminder unsnoozed');
      loadReminders();
      fetchTabCounts();
    } catch (error) {
      toast.error('Failed to unsnooze reminder');
    }
  };

  const handleDeleteReminder = async (id: number) => {
    try {
      await reminderApi.deleteReminder(id);

      toast.success('Reminder deleted');
      loadReminders();
      fetchTabCounts();
    } catch (error) {
      toast.error('Failed to delete reminder');
    }
  };

  // Use the fetched tab counts from state
  const counts = tabCounts;

  if (showForm || editingReminder) {
    return (
      <div className={cn("p-6", className)}>
        <ReminderForm
          reminder={editingReminder}
          users={users}
          onSubmit={editingReminder ? handleUpdateReminder : handleCreateReminder}
          onCancel={() => {
            setShowForm(false);
            setEditingReminder(null);
          }}
          isLoading={formLoading}
        />
      </div>
    );
  }

  return (
    <div className={cn("p-6 space-y-6", className)}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">{t('reminders.title', { count: totalCount })}</h1>
          <p className="text-muted-foreground">
            {t('reminders.description')}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={loadReminders}
            disabled={loading}
          >
            <RefreshCw className={cn("h-4 w-4 mr-2", loading && "animate-spin")} />
            {t('reminders.refresh')}
          </Button>
          <ProfessionalButton onClick={() => setShowForm(true)}>
            <Plus className="h-4 w-4 mr-2" />
            {t('reminders.create_reminder')}
          </ProfessionalButton>
        </div>
      </div>

      {/* Tabs */}
      <Tabs
        value={activeTab}
        onValueChange={(value) => {
          const params = new URLSearchParams(searchParams);
          if (value === 'all') {
            params.delete('tab');
          } else {
            params.set('tab', value);
          }
          setSearchParams(params);
          setPage(1);
        }}
      >
        <TabsList className="grid w-full grid-cols-6">
          <TabsTrigger value="all" className="flex items-center gap-2">
            <List className="h-4 w-4" />
            {t('reminders.all')} ({counts.all})
          </TabsTrigger>
          <TabsTrigger value="my" className="flex items-center gap-2">
            <Clock className="h-4 w-4" />
            {t('reminders.my_tasks')} ({counts.my})
          </TabsTrigger>
          <TabsTrigger value="due_today" className="flex items-center gap-2">
            <Calendar className="h-4 w-4" />
            {t('reminders.due_today')} ({counts.due_today})
          </TabsTrigger>
          <TabsTrigger value="overdue" className="flex items-center gap-2">
            <AlertCircle className="h-4 w-4" />
            {t('reminders.overdue')} ({counts.overdue})
          </TabsTrigger>
          <TabsTrigger value="snoozed" className="flex items-center gap-2">
            <Timer className="h-4 w-4" />
            {t('reminders.snoozed')} ({counts.snoozed})
          </TabsTrigger>
          <TabsTrigger value="completed" className="flex items-center gap-2">
            <CheckCircle className="h-4 w-4" />
            {t('reminders.completed')} ({counts.completed})
          </TabsTrigger>
        </TabsList>

        {/* Filters */}
        <div className="flex items-center gap-4 py-4">
          <div className="flex-1">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder={t('reminders.search_placeholder')}
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-10"
              />
            </div>
          </div>

          {activeTab === 'all' && (
            <>
              <Select value={statusFilter} onValueChange={setStatusFilter}>
                <SelectTrigger className="w-40">
                  <SelectValue placeholder="Status" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">{t('reminders.all_status')}</SelectItem>
                  <SelectItem value="pending">{t('reminders.status.pending')}</SelectItem>
                  <SelectItem value="completed">{t('reminders.status.completed')}</SelectItem>
                  <SelectItem value="snoozed">{t('reminders.status.snoozed')}</SelectItem>
                  <SelectItem value="cancelled">{t('reminders.status.cancelled')}</SelectItem>
                </SelectContent>
              </Select>

              <Select value={priorityFilter} onValueChange={setPriorityFilter}>
                <SelectTrigger className="w-40">
                  <SelectValue placeholder="Priority" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">{t('reminders.all_priority')}</SelectItem>
                  <SelectItem value="urgent">{t('reminders.priority.urgent')}</SelectItem>
                  <SelectItem value="high">{t('reminders.priority.high')}</SelectItem>
                  <SelectItem value="medium">{t('reminders.priority.medium')}</SelectItem>
                  <SelectItem value="low">{t('reminders.priority.low')}</SelectItem>
                </SelectContent>
              </Select>

              <Select value={assignedToFilter} onValueChange={setAssignedToFilter}>
                <SelectTrigger className="w-48">
                  <SelectValue placeholder="Assigned To" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">{t('reminders.all_users')}</SelectItem>
                  {users.map((user) => (
                    <SelectItem key={user.id} value={user.id.toString()}>
                      {user.first_name && user.last_name
                        ? `${user.first_name} ${user.last_name}`
                        : user.email}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </>
          )}

          <Popover>
            <PopoverTrigger asChild>
              <Button variant="outline" className="flex items-center gap-2">
                <Filter className="h-4 w-4" />
                {t('reminders.date_range')}
                {(dueDateFrom || dueDateTo) && (
                  <Badge variant="secondary" className="ml-1">
                    {dueDateFrom && dueDateTo
                      ? `${format(dueDateFrom, 'MMM d')} - ${format(dueDateTo, 'MMM d')}`
                      : dueDateFrom
                        ? `From ${format(dueDateFrom, 'MMM d')}`
                        : `Until ${format(dueDateTo!, 'MMM d')}`}
                  </Badge>
                )}
              </Button>
            </PopoverTrigger>
            <PopoverContent className="w-auto p-0" align="end">
              <div className="p-4 space-y-4">
                <div>
                  <label className="text-sm font-medium mb-2 block">{t('reminders.from_date')}</label>
                  <CalendarComponent
                    mode="single"
                    selected={dueDateFrom}
                    onSelect={setDueDateFrom}
                  />
                </div>
                <div>
                  <label className="text-sm font-medium mb-2 block">{t('reminders.to_date')}</label>
                  <CalendarComponent
                    mode="single"
                    selected={dueDateTo}
                    onSelect={setDueDateTo}
                  />
                </div>
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => {
                      setDueDateFrom(undefined);
                      setDueDateTo(undefined);
                    }}
                  >
                    {t('reminders.clear')}
                  </Button>
                </div>
              </div>
            </PopoverContent>
          </Popover>
        </div>

        {/* Content */}
        <TabsContent value={activeTab} className="space-y-4">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-8 w-8 animate-spin" />
            </div>
          ) : reminders.length === 0 ? (
            <Card className="border-none shadow-none bg-transparent">
              <CardContent className="flex flex-col items-center justify-center py-20 bg-muted/5 rounded-xl border-2 border-dashed border-muted-foreground/20 m-4">
                <div className="bg-primary/10 w-16 h-16 rounded-full flex items-center justify-center mb-4">
                  <Timer className="h-8 w-8 text-primary" />
                </div>
                <h3 className="text-xl font-bold mb-2">{t('reminders.no_reminders_found', 'No reminders found')}</h3>
                <p className="text-muted-foreground max-w-sm mx-auto text-center">
                  {activeTab === 'all'
                    ? t('reminders.no_reminders_description', 'You don\'t have any reminders yet. Create one to stay on top of your tasks and deadlines.')
                    : activeTab === 'snoozed'
                      ? t('reminders.no_snoozed_reminders', 'All your reminders are currently active.')
                      : t('reminders.no_reminders_tab', { tab: activeTab.replace('_', ' '), defaultValue: `No ${activeTab.replace('_', ' ')} reminders found.` })}
                </p>
              </CardContent>
            </Card>
          ) : (
            <div className="grid gap-4">
              {reminders.map((reminder) => (
                <ReminderCard
                  key={reminder.id}
                  reminder={reminder}
                  currentUserId={currentUser?.id || 0}
                  onEdit={setEditingReminder}
                  onComplete={handleCompleteReminder}
                  onSnooze={handleSnoozeReminder}
                  onUnsnooze={handleUnsnoozeReminder}
                  onDelete={handleDeleteReminder}
                />
              ))}
            </div>
          )}

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-2 pt-4">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage(Math.max(1, page - 1))}
                disabled={page === 1}
              >
                {t('reminders.previous')}
              </Button>
              <span className="text-sm text-muted-foreground">
                {t('reminders.page')} {page} {t('reminders.of')} {totalPages}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage(Math.min(totalPages, page + 1))}
                disabled={page === totalPages}
              >
                {t('reminders.next')}
              </Button>
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
