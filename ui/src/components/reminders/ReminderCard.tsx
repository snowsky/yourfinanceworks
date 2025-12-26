import React from 'react';
import { format, isToday, isPast, isTomorrow } from 'date-fns';
import { Clock, User, Flag, Calendar, Edit, Check, Timer, Trash2, AlertCircle, Play, CheckSquare, Square } from 'lucide-react';
import { Card, CardContent, CardFooter, CardHeader } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import { useTranslation } from 'react-i18next';

interface ReminderCardProps {
  reminder: {
    id: number;
    title: string;
    description?: string;
    due_date: string;
    priority: 'low' | 'medium' | 'high' | 'urgent';
    status: 'pending' | 'completed' | 'snoozed' | 'cancelled';
    recurrence_pattern: 'none' | 'daily' | 'weekly' | 'monthly' | 'yearly';
    assigned_to?: {
      id: number;
      email: string;
      first_name?: string;
      last_name?: string;
    };
    created_by?: {
      id: number;
      email: string;
      first_name?: string;
      last_name?: string;
    };
    completed_at?: string;
    snoozed_until?: string;
    tags?: string[];
    snooze_count?: number;
  };
  currentUserId: number;
  onEdit?: (reminder: any) => void;
  onComplete?: (id: number, notes?: string) => void;
  onSnooze?: (id: number, until: Date) => void;
  onUnsnooze?: (id: number) => void;
  onDelete?: (id: number) => void;
  className?: string;
  isSelected?: boolean;
  onSelect?: (id: number) => void;
  showSelection?: boolean;
}

export function ReminderCard({
  reminder,
  currentUserId,
  onEdit,
  onComplete,
  onSnooze,
  onUnsnooze,
  onDelete,
  className,
  isSelected = false,
  onSelect,
  showSelection = false
}: ReminderCardProps) {
  const { t } = useTranslation();
  const dueDate = new Date(reminder.due_date);
  const isOverdue = isPast(dueDate) && reminder.status === 'pending';
  const isDueToday = isToday(dueDate);
  const isDueTomorrow = isTomorrow(dueDate);
  const isAssignedToCurrentUser = reminder.assigned_to?.id === currentUserId;
  const isCreatedByCurrentUser = reminder.created_by?.id === currentUserId;
  const canEdit = isCreatedByCurrentUser;
  
  // Special case: Any admin can act on join request reminders
  const isAdminReminder = reminder.tags?.includes('admin') && reminder.tags?.includes('join_request');
  const canActOnAdminReminder = isAdminReminder;

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'urgent': return 'bg-red-500 text-white';
      case 'high': return 'bg-orange-500 text-white';
      case 'medium': return 'bg-yellow-500 text-white';
      case 'low': return 'bg-green-500 text-white';
      default: return 'bg-gray-500 text-white';
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed': return 'bg-green-100 text-green-800 border-green-200';
      case 'snoozed': return 'bg-blue-100 text-blue-800 border-blue-200';
      case 'cancelled': return 'bg-gray-100 text-gray-800 border-gray-200';
      default: return 'bg-yellow-100 text-yellow-800 border-yellow-200';
    }
  };

  const formatDueDate = (date: Date) => {
    if (isToday(date)) {
      return `Today at ${format(date, 'h:mm a')}`;
    } else if (isTomorrow(date)) {
      return `Tomorrow at ${format(date, 'h:mm a')}`;
    } else {
      return format(date, 'MMM d, yyyy h:mm a');
    }
  };

  const getUserDisplayName = (user: any) => {
    if (user?.first_name && user?.last_name) {
      return `${user.first_name} ${user.last_name}`;
    }
    return user?.first_name || user?.last_name || user?.email || 'Unknown';
  };

  const handleSnooze = () => {
    if (onSnooze) {
      // Default to snooze for 1 hour
      const snoozeUntil = new Date();
      snoozeUntil.setHours(snoozeUntil.getHours() + 1);
      onSnooze(reminder.id, snoozeUntil);
    }
  };

  return (
    <Card className={cn(
      "transition-all duration-200 hover:shadow-md",
      isOverdue && "border-red-300 bg-red-50",
      isDueToday && "border-orange-300 bg-orange-50",
      reminder.status === 'completed' && "opacity-75",
      className
    )}>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3 flex-1 min-w-0">
            {showSelection && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => onSelect?.(reminder.id)}
                className="h-8 w-8 p-0 flex-shrink-0"
              >
                {isSelected ? (
                  <CheckSquare className="h-4 w-4 text-primary" />
                ) : (
                  <Square className="h-4 w-4" />
                )}
              </Button>
            )}
            <div className="flex-1 min-w-0">
              <h3 className="font-semibold text-lg truncate mb-1">
                {reminder.title}
              </h3>
              <div className="flex items-center gap-2 text-sm text-muted-foreground mb-2">
                <Calendar className="h-4 w-4" />
                <span className={cn(
                  isOverdue && "text-red-600 font-medium",
                  isDueToday && "text-orange-600 font-medium"
                )}>
                  {formatDueDate(dueDate)}
                </span>
                {isOverdue && <AlertCircle className="h-4 w-4 text-red-500" />}
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2 ml-2">
            <Badge variant="outline" className={getPriorityColor(reminder.priority)}>
              <Flag className="h-3 w-3 mr-1" />
              {t(`reminders.priority.${reminder.priority}`)}
            </Badge>
            <Badge variant="outline" className={getStatusColor(reminder.status)}>
              {t(`reminders.status.${reminder.status}`)}
            </Badge>
          </div>
        </div>
      </CardHeader>

      <CardContent className="pt-0">
        {reminder.description && (
          <p className="text-sm text-muted-foreground mb-3 line-clamp-3">
            {reminder.description}
          </p>
        )}

        <div className="flex items-center gap-4 text-sm text-muted-foreground mb-3">
          {reminder.assigned_to && (
            <div className="flex items-center gap-1">
              <User className="h-4 w-4" />
              <span>
                {isAssignedToCurrentUser ? t('reminders.you') : getUserDisplayName(reminder.assigned_to)}
              </span>
            </div>
          )}

          {reminder.created_by && (
            <div className="flex items-center gap-1">
              <User className="h-4 w-4" />
              <span className="text-xs">
                {t('common.created_by')}: {isCreatedByCurrentUser ? t('reminders.you') : getUserDisplayName(reminder.created_by)}
              </span>
            </div>
          )}

          {reminder.recurrence_pattern !== 'none' && (
            <div className="flex items-center gap-1">
              <Clock className="h-4 w-4" />
              <span className="capitalize">{reminder.recurrence_pattern}</span>
            </div>
          )}

          {reminder.snooze_count && reminder.snooze_count > 0 && (
            <div className="flex items-center gap-1 text-blue-600">
              <Timer className="h-4 w-4" />
              <span>{t('reminders.snoozed')} {reminder.snooze_count}x</span>
            </div>
          )}
        </div>

        {reminder.tags && reminder.tags.length > 0 && (
          <div className="flex flex-wrap gap-1 mb-3">
            {reminder.tags.map((tag, index) => (
              <Badge key={index} variant="secondary" className="text-xs">
                {tag}
              </Badge>
            ))}
          </div>
        )}

        {reminder.snoozed_until && (
          <div className="text-sm text-blue-600 mb-3">
            {t('reminders.snoozed_until')} {format(new Date(reminder.snoozed_until), 'MMM d, yyyy h:mm a')}
          </div>
        )}

        {reminder.completed_at && (
          <div className="text-sm text-green-600 mb-3">
            {t('reminders.completed_on')} {format(new Date(reminder.completed_at), 'MMM d, yyyy h:mm a')}
          </div>
        )}
      </CardContent>

      <CardFooter className="pt-0">
        <div className="flex items-center gap-2 w-full">
          {reminder.status === 'pending' && (isAssignedToCurrentUser || canActOnAdminReminder) && (
            <>
              <Button
                size="sm"
                onClick={() => onComplete?.(reminder.id)}
                className="flex items-center gap-1"
              >
                <Check className="h-4 w-4" />
                {t('reminders.complete')}
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={handleSnooze}
                className="flex items-center gap-1"
              >
                <Timer className="h-4 w-4" />
                {t('reminders.snooze')}
              </Button>
            </>
          )}

          {reminder.status === 'snoozed' && (isAssignedToCurrentUser || canActOnAdminReminder) && (
            <>
              <Button
                size="sm"
                onClick={() => onComplete?.(reminder.id)}
                className="flex items-center gap-1"
              >
                <Check className="h-4 w-4" />
                {t('reminders.complete')}
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => onUnsnooze?.(reminder.id)}
                className="flex items-center gap-1 text-blue-600 hover:text-blue-700"
              >
                <Play className="h-4 w-4" />
                {t('reminders.unsnooze')}
              </Button>
            </>
          )}

          {isCreatedByCurrentUser && (
            <Button
              size="sm"
              variant="outline"
              onClick={() => onEdit?.(reminder)}
              className="flex items-center gap-1"
            >
              <Edit className="h-4 w-4" />
              {t('reminders.edit')}
            </Button>
          )}

          {isCreatedByCurrentUser && (
            <Button
              size="sm"
              variant="outline"
              onClick={() => onDelete?.(reminder.id)}
              className="flex items-center gap-1 text-red-600 hover:text-red-700 ml-auto"
            >
              <Trash2 className="h-4 w-4" />
              {t('reminders.delete')}
            </Button>
          )}
        </div>
      </CardFooter>
    </Card>
  );
}
