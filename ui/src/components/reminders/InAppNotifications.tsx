import React, { useState, useEffect } from 'react';
import { format, isToday, isPast } from 'date-fns';
import { Bell, Clock, AlertCircle, Check, X, Loader2 } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import { cn } from '@/lib/utils';
import { toast } from 'sonner';
import { reminderApi } from '@/lib/api';

interface InAppNotification {
  id: number;
  reminder: {
    id: number;
    title: string;
    description?: string;
    due_date: string;
    priority: 'low' | 'medium' | 'high' | 'urgent';
    status: string;
  };
  notification_type: string;
  scheduled_for: string;
  is_read?: boolean;
}

interface InAppNotificationsProps {
  className?: string;
}

export function InAppNotifications({ className }: InAppNotificationsProps) {
  const [notifications, setNotifications] = useState<InAppNotification[]>([]);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);

  useEffect(() => {
    if (open) {
      loadNotifications();
    }
    
    // Poll for new notifications every 30 seconds
    const interval = setInterval(() => {
      loadUnreadCount();
    }, 30000);

    // Load initial unread count
    loadUnreadCount();

    return () => clearInterval(interval);
  }, [open]);

  const loadNotifications = async () => {
    try {
      setLoading(true);

      // Load recent reminder notifications
      const data = await reminderApi.getRecentNotifications();
      setNotifications(data.items || []);
    } catch (error) {
      toast.error('Failed to load notifications');
    } finally {
      setLoading(false);
    }
  };

  const loadUnreadCount = async () => {
    try {
      const data = await reminderApi.getUnreadNotificationCount();
      setUnreadCount(data.count || 0);
    } catch (error) {
      // Error loading unread count - silently fail
    }
  };

  const markAsRead = async (notificationId: number) => {
    try {
      await reminderApi.markNotificationAsRead(notificationId);

      setNotifications(prev =>
        prev.map(n => n.id === notificationId ? { ...n, is_read: true } : n)
      );
      setUnreadCount(prev => Math.max(0, prev - 1));
    } catch (error) {
      // Error marking notification as read - silently fail
    }
  };

  const markAllAsRead = async () => {
    try {
      await reminderApi.markAllNotificationsAsRead();

      setNotifications(prev =>
        prev.map(n => ({ ...n, is_read: true }))
      );
      setUnreadCount(0);
      toast.success('All notifications marked as read');
    } catch (error) {
      toast.error('Failed to mark all as read');
    }
  };

  const dismissNotification = async (notificationId: number) => {
    try {
      await reminderApi.dismissNotification(notificationId);

      setNotifications(prev => prev.filter(n => n.id !== notificationId));
      if (!notifications.find(n => n.id === notificationId)?.is_read) {
        setUnreadCount(prev => Math.max(0, prev - 1));
      }
    } catch (error) {
      toast.error('Failed to dismiss notification');
    }
  };

  const getNotificationIcon = (type: string, priority: string) => {
    if (type === 'overdue') {
      return <AlertCircle className="h-4 w-4 text-red-500" />;
    } else if (type === 'due' || priority === 'urgent') {
      return <Clock className="h-4 w-4 text-orange-500" />;
    }
    return <Bell className="h-4 w-4 text-blue-500" />;
  };

  const getNotificationMessage = (notification: InAppNotification) => {
    const { reminder, notification_type } = notification;
    const dueDate = new Date(reminder.due_date);
    
    switch (notification_type) {
      case 'due':
        return `"${reminder.title}" is due ${isToday(dueDate) ? 'today' : format(dueDate, 'MMM d')}`;
      case 'overdue':
        return `"${reminder.title}" is overdue`;
      case 'upcoming':
        return `"${reminder.title}" is due soon`;
      case 'assigned':
        return `You were assigned reminder "${reminder.title}"`;
      default:
        return `Reminder: ${reminder.title}`;
    }
  };

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'urgent': return 'bg-red-100 border-red-200';
      case 'high': return 'bg-orange-100 border-orange-200';
      case 'medium': return 'bg-yellow-100 border-yellow-200';
      case 'low': return 'bg-green-100 border-green-200';
      default: return 'bg-gray-100 border-gray-200';
    }
  };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button 
          variant="ghost" 
          size="sm" 
          className={cn("relative", className)}
        >
          <Bell className="h-5 w-5" />
          {unreadCount > 0 && (
            <Badge 
              variant="destructive" 
              className="absolute -top-1 -right-1 h-5 w-5 flex items-center justify-center p-0 text-xs"
            >
              {unreadCount > 99 ? '99+' : unreadCount}
            </Badge>
          )}
        </Button>
      </PopoverTrigger>
      
      <PopoverContent className="w-96 p-0" align="end">
        <Card className="border-0 shadow-none">
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-lg">Notifications</CardTitle>
              {notifications.some(n => !n.is_read) && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={markAllAsRead}
                  className="text-xs"
                >
                  Mark all read
                </Button>
              )}
            </div>
          </CardHeader>
          
          <CardContent className="p-0">
            {loading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-6 w-6 animate-spin" />
              </div>
            ) : notifications.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                <Bell className="h-8 w-8 mx-auto mb-2 opacity-50" />
                <p>No notifications</p>
                <p className="text-sm">You're all caught up!</p>
              </div>
            ) : (
              <ScrollArea className="max-h-96">
                <div className="space-y-1 p-2">
                  {notifications.map((notification, index) => (
                    <div key={notification.id}>
                      <div 
                        className={cn(
                          "flex items-start gap-3 p-3 rounded-lg transition-colors hover:bg-muted/50",
                          !notification.is_read && "bg-blue-50 border border-blue-200",
                          getPriorityColor(notification.reminder.priority)
                        )}
                      >
                        <div className="flex-shrink-0 mt-1">
                          {getNotificationIcon(notification.notification_type, notification.reminder.priority)}
                        </div>
                        
                        <div className="flex-1 min-w-0">
                          <p className={cn(
                            "text-sm",
                            !notification.is_read && "font-medium"
                          )}>
                            {getNotificationMessage(notification)}
                          </p>
                          
                          {notification.reminder.description && (
                            <p className="text-xs text-muted-foreground mt-1 line-clamp-2">
                              {notification.reminder.description}
                            </p>
                          )}
                          
                          <div className="flex items-center gap-2 mt-2">
                            <span className="text-xs text-muted-foreground">
                              {format(new Date(notification.scheduled_for), 'MMM d, h:mm a')}
                            </span>
                            
                            <Badge 
                              variant="outline" 
                              className={cn(
                                "text-xs",
                                notification.reminder.priority === 'urgent' && "border-red-500 text-red-700",
                                notification.reminder.priority === 'high' && "border-orange-500 text-orange-700",
                                notification.reminder.priority === 'medium' && "border-yellow-500 text-yellow-700",
                                notification.reminder.priority === 'low' && "border-green-500 text-green-700"
                              )}
                            >
                              {notification.reminder.priority}
                            </Badge>
                          </div>
                        </div>
                        
                        <div className="flex flex-col gap-1">
                          {!notification.is_read && (
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => markAsRead(notification.id)}
                              className="h-6 w-6 p-0"
                            >
                              <Check className="h-3 w-3" />
                            </Button>
                          )}
                          
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => dismissNotification(notification.id)}
                            className="h-6 w-6 p-0 text-muted-foreground hover:text-destructive"
                          >
                            <X className="h-3 w-3" />
                          </Button>
                        </div>
                      </div>
                      
                      {index < notifications.length - 1 && <Separator className="my-1" />}
                    </div>
                  ))}
                </div>
              </ScrollArea>
            )}
            
            {notifications.length > 0 && (
              <div className="p-3 border-t">
                <Button 
                  variant="ghost" 
                  size="sm" 
                  className="w-full text-sm"
                  onClick={() => {
                    setOpen(false);
                    // Navigate to reminders page
                    window.location.href = '/reminders';
                  }}
                >
                  View All Reminders
                </Button>
              </div>
            )}
          </CardContent>
        </Card>
      </PopoverContent>
    </Popover>
  );
}
