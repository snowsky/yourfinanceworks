import React from 'react';
import { format, isToday, isPast, isTomorrow } from 'date-fns';
import { Clock, User, Flag, Calendar, Edit, Check, Timer, Trash2, AlertCircle, Play, CheckSquare, Square, Pin, GripVertical } from 'lucide-react';
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
    is_pinned?: boolean;
    position?: number;
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
  onTogglePin?: (id: number) => void;
  dragHandleProps?: any;
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
  showSelection = false,
  onTogglePin,
  dragHandleProps
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
    const time = format(date, 'h:mm a');
    if (isToday(date)) {
      return t('reminders.today_at', { time });
    } else if (isTomorrow(date)) {
      return t('reminders.tomorrow_at', { time });
    } else {
      return format(date, 'MMM d, yyyy h:mm a');
    }
  };

  const getUserDisplayName = (user: any) => {
    if (user?.first_name && user?.last_name) {
      return `${user.first_name} ${user.last_name}`;
    }
    return user?.first_name || user?.last_name || user?.email || t('common.unknown');
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
      "transition-all duration-200 hover:shadow-md h-full flex flex-col",
      isOverdue && "border-red-300 bg-red-50",
      isDueToday && "border-orange-300 bg-orange-50",
      reminder.is_pinned && "border-primary/50 bg-primary/5 shadow-sm",
      reminder.status === 'completed' && "opacity-75",
      className
    )}>
      <CardHeader className="p-3 pb-1">
        <div className="flex flex-col gap-1 w-full">
          {/* Top row: Handle, Checkbox, Title, Pin */}
          <div className="flex items-start justify-between gap-1">
            <div className="flex items-center gap-2 flex-1 min-w-0">
              {dragHandleProps && (
                <div {...dragHandleProps} className="cursor-grab active:cursor-grabbing text-muted-foreground/50 hover:text-muted-foreground">
                  <GripVertical className="h-4 w-4" />
                </div>
              )}
              {showSelection && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => onSelect?.(reminder.id)}
                  className="h-7 w-7 p-0 flex-shrink-0"
                >
                  {isSelected ? (
                    <CheckSquare className="h-4 w-4 text-primary" />
                  ) : (
                    <Square className="h-4 w-4 text-muted-foreground/30" />
                  )}
                </Button>
              )}
              <h3 className="font-semibold text-sm truncate">
                {reminder.title}
              </h3>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onTogglePin?.(reminder.id)}
              className={cn(
                "h-7 w-7 p-0 flex-shrink-0",
                reminder.is_pinned ? "text-primary" : "text-muted-foreground/30"
              )}
              title={reminder.is_pinned ? t('reminders.unpin') : t('reminders.pin')}
            >
              <Pin className={cn("h-3.5 w-3.5", reminder.is_pinned && "fill-current")} />
            </Button>
          </div>

          {/* Second row: Date and Badges */}
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <div className="flex items-center gap-1 text-muted-foreground whitespace-nowrap">
              <Calendar className="h-3 w-3" />
              <span className={cn(
                "font-medium",
                isOverdue && "text-red-500",
                isDueToday && "text-orange-500"
              )}>
                {formatDueDate(dueDate)}
              </span>
              {isOverdue && <AlertCircle className="h-3 w-3 text-red-500" />}
            </div>
            
            <div className="flex items-center gap-1 ml-auto">
              <Badge variant="outline" className={cn("px-1.5 py-0 h-4 text-[10px]", getPriorityColor(reminder.priority))}>
                <Flag className="h-2.5 w-2.5 mr-0.5" />
                {t(`reminders.priority.${reminder.priority}`)}
              </Badge>
              <Badge variant="outline" className={cn("px-1.5 py-0 h-4 text-[10px]", getStatusColor(reminder.status))}>
                {t(`reminders.status.${reminder.status}`)}
              </Badge>
            </div>
          </div>
        </div>
      </CardHeader>

      <CardContent className="p-3 pt-1 flex-1">
        {reminder.description && (
          <p className="text-xs text-muted-foreground mb-2 line-clamp-2">
            {reminder.description}
          </p>
        )}

        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[10px] text-muted-foreground mb-2">
          {reminder.assigned_to && (
            <div className="flex items-center gap-1">
              <User className="h-2.5 w-2.5" />
              <span>
                {isAssignedToCurrentUser ? t('reminders.you') : getUserDisplayName(reminder.assigned_to)}
              </span>
            </div>
          )}

          {reminder.created_by && (
            <div className="flex items-center gap-1">
              <User className="h-2.5 w-2.5" />
              <span>
                {isCreatedByCurrentUser ? t('reminders.you') : getUserDisplayName(reminder.created_by)}
              </span>
            </div>
          )}

          {reminder.recurrence_pattern !== 'none' && (
            <div className="flex items-center gap-1">
              <Clock className="h-2.5 w-2.5" />
              <span className="capitalize">{reminder.recurrence_pattern}</span>
            </div>
          )}

          {typeof reminder.snooze_count === 'number' && reminder.snooze_count > 0 && (
            <div className="flex items-center gap-1 text-blue-600">
              <Timer className="h-2.5 w-2.5" />
              <span>{t('reminders.snoozed')} {reminder.snooze_count}x</span>
            </div>
          )}
        </div>

        {reminder.tags && reminder.tags.length > 0 && (
          <div className="flex flex-wrap gap-1 mb-2">
            {reminder.tags.map((tag, index) => (
              <Badge key={index} variant="secondary" className="text-[10px] py-0 h-4 px-1.5 opacity-70">
                {tag}
              </Badge>
            ))}
          </div>
        )}

        {reminder.snoozed_until && (
          <div className="text-[10px] text-blue-600 mb-1">
            {t('reminders.snoozed_until')} {format(new Date(reminder.snoozed_until), 'MMM d, yyyy h:mm a')}
          </div>
        )}

        {reminder.completed_at && (
          <div className="text-[10px] text-green-600 mb-1">
            {t('reminders.completed_on')} {format(new Date(reminder.completed_at), 'MMM d, yyyy h:mm a')}
          </div>
        )}
      </CardContent>

      <CardFooter className="p-3 pt-0 border-t border-muted/20 bg-muted/5">
        <div className="flex items-center justify-between w-full pt-2">
          <div className="flex items-center gap-1">
            {reminder.status === 'pending' && (isAssignedToCurrentUser || canActOnAdminReminder) && (
              <>
                <Button
                  size="sm"
                  onClick={() => onComplete?.(reminder.id)}
                  className="h-7 px-2 text-[11px] flex items-center gap-1"
                >
                  <Check className="h-3.5 w-3.5" />
                  {t('reminders.complete')}
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={handleSnooze}
                  className="h-7 w-7 p-0"
                  title={t('reminders.snooze')}
                >
                  <Timer className="h-3.5 w-3.5" />
                </Button>
              </>
            )}

            {reminder.status === 'snoozed' && (isAssignedToCurrentUser || canActOnAdminReminder) && (
              <>
                <Button
                  size="sm"
                  onClick={() => onComplete?.(reminder.id)}
                  className="h-7 px-2 text-[11px] flex items-center gap-1"
                >
                  <Check className="h-3.5 w-3.5" />
                  {t('reminders.complete')}
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => onUnsnooze?.(reminder.id)}
                  className="h-7 w-7 p-0 text-blue-600"
                  title={t('reminders.unsnooze')}
                >
                  <Play className="h-3.5 w-3.5" />
                </Button>
              </>
            )}
          </div>

          <div className="flex items-center gap-1">
            {onEdit && canEdit && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => onEdit?.(reminder)}
                className="h-7 w-7 p-0 text-muted-foreground"
                title={t('common.edit')}
              >
                <Edit className="h-3.5 w-3.5" />
              </Button>
            )}
            {onDelete && (isCreatedByCurrentUser || canActOnAdminReminder) && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => onDelete?.(reminder.id)}
                className="h-7 w-7 p-0 text-red-400 hover:text-red-600 hover:bg-red-50"
                title={t('common.delete')}
              >
                <Trash2 className="h-3.5 w-3.5" />
              </Button>
            )}
          </div>
        </div>
      </CardFooter>
    </Card>
  );
}
