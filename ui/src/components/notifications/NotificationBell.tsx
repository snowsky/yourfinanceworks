import React, { useState, useEffect } from 'react';
import { Bell, X, CheckCircle, AlertCircle, Clock, UserPlus } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

export interface Notification {
  id: string;
  type: 'success' | 'error' | 'processing' | 'join_request';
  title: string;
  message: string;
  timestamp: Date;
  read: boolean;
  actionUrl?: string;
}

interface NotificationBellProps {
  notifications: Notification[];
  onMarkAsRead: (id: string) => void;
  onClearAll: () => void;
  onHide?: () => void;
}

export function NotificationBell({ notifications, onMarkAsRead, onClearAll, onHide }: NotificationBellProps) {
  const navigate = useNavigate();
  const [isOpen, setIsOpen] = useState(false);
  const [hasNewNotifications, setHasNewNotifications] = useState(false);

  // Auto-hide old notifications (older than 1 hour)
  const recentNotifications = notifications.filter(n => {
    const hourAgo = new Date(Date.now() - 60 * 60 * 1000);
    return n.timestamp > hourAgo;
  });

  const displayNotifications = recentNotifications;
  const unreadCount = displayNotifications.filter(n => !n.read).length;

  // Show animation when new notifications arrive
  useEffect(() => {
    if (unreadCount > 0) {
      setHasNewNotifications(true);
      const timer = setTimeout(() => setHasNewNotifications(false), 2000);
      return () => clearTimeout(timer);
    }
  }, [unreadCount]);

  // Return null after all hooks have been called
  if (recentNotifications.length === 0) return null;

  const getIcon = (type: Notification['type']) => {
    switch (type) {
      case 'success':
        return <CheckCircle className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />;
      case 'error':
        return <AlertCircle className="w-4 h-4 text-red-600 dark:text-red-400" />;
      case 'processing':
        return <Clock className="w-4 h-4 text-blue-600 dark:text-blue-400" />;
      case 'join_request':
        return <UserPlus className="w-4 h-4 text-purple-600 dark:text-purple-400" />;
    }
  };

  const handleNotificationClick = (notification: Notification) => {
    onMarkAsRead(notification.id);
    if (notification.actionUrl) {
      setIsOpen(false);
      navigate(notification.actionUrl);
    }
  };

  const formatTime = (date: Date) => {
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  return (
    <div className="fixed bottom-6 left-1/2 transform -translate-x-1/2 z-50">
      {/* Notification Bell Button */}
      <div className="relative">
        <Button
          onClick={() => setIsOpen(!isOpen)}
          size="lg"
          className={`rounded-full shadow-lg transition-all duration-300 ${
            hasNewNotifications ? 'animate-bounce' : ''
          }`}
        >
          <Bell className={`w-5 h-5 ${hasNewNotifications ? 'animate-pulse' : ''}`} />
          {unreadCount > 0 && (
            <Badge 
              variant="destructive" 
              className="absolute -top-2 -right-2 h-5 w-5 rounded-full p-0 flex items-center justify-center text-xs"
            >
              {unreadCount > 9 ? '9+' : unreadCount}
            </Badge>
          )}
        </Button>
      </div>

      {/* Notification Panel */}
      {isOpen && (
        <Card className="absolute bottom-16 left-1/2 transform -translate-x-1/2 w-80 max-h-96 overflow-hidden shadow-xl animate-in slide-in-from-bottom-2 bg-card border-border">
          <div className="flex items-center justify-between p-4 border-b">
            <h3 className="font-semibold text-sm text-foreground">AI Processing Updates</h3>
            <div className="flex items-center gap-2">
              {displayNotifications.length > 0 && (
                <>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={onClearAll}
                    className="text-xs"
                  >
                    Clear All
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={onHide}
                    className="text-xs"
                  >
                    Hide
                  </Button>
                </>
              )}
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setIsOpen(false)}
              >
                <X className="w-4 h-4" />
              </Button>
            </div>
          </div>
          
          <CardContent className="p-0 max-h-80 overflow-y-auto">
            {displayNotifications.length === 0 ? (
                  <div className="p-4 text-center text-sm text-muted-foreground">
                No recent notifications
              </div>
            ) : (
              <div className="space-y-0">
                {displayNotifications.map((notification) => (
                  <div
                    key={notification.id}
                    className={`p-4 border-b last:border-b-0 cursor-pointer hover:bg-gray-50 transition-colors ${
                      !notification.read ? 'bg-blue-50' : ''
                    }`}
                    onClick={() => handleNotificationClick(notification)}
                  >
                    <div className="flex items-start gap-3">
                      {getIcon(notification.type)}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between">
                          <p className="text-sm font-medium text-foreground truncate">
                            {notification.title}
                          </p>
                          <span className="text-xs text-muted-foreground">
                            {formatTime(notification.timestamp)}
                          </span>
                        </div>
                        <p className="text-xs text-muted-foreground mt-1">
                          {notification.message}
                        </p>
                        {!notification.read && (
                          <div className="w-2 h-2 bg-blue-600 dark:bg-blue-400 rounded-full mt-2"></div>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
