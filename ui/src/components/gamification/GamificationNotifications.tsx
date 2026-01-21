import React, { useEffect, useState } from 'react';
import { ProfessionalCard, ProfessionalCardContent } from '@/components/ui/professional-card';
import { ProfessionalButton } from '@/components/ui/professional-button';
import { Badge } from '@/components/ui/badge';
import {
  AlertTriangle,
  Flame,
  Heart,
  Target,
  TrendingUp,
  Calendar,
  CheckCircle,
  X,
  Clock
} from 'lucide-react';
import { useGamification } from '@/hooks/useGamification';
import type { UserStreak, HabitType } from '@/types/gamification';

interface NotificationItem {
  id: string;
  type: 'streak_risk' | 'welcome_back' | 'daily_tip' | 'achievement_reminder';
  title: string;
  message: string;
  icon: React.ReactNode;
  color: string;
  action?: {
    label: string;
    onClick: () => void;
  };
  dismissible?: boolean;
}

const habitTypeLabels = {
  daily_expense_tracking: 'Daily Expense Tracking',
  weekly_budget_review: 'Weekly Budget Review',
  invoice_follow_up: 'Invoice Follow-up',
  receipt_documentation: 'Receipt Documentation'
};

const habitTypeIcons = {
  daily_expense_tracking: Target,
  weekly_budget_review: TrendingUp,
  invoice_follow_up: Calendar,
  receipt_documentation: CheckCircle
};

export function GamificationNotifications() {
  const { dashboard, canShowGamification } = useGamification();
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [dismissedNotifications, setDismissedNotifications] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (!canShowGamification || !dashboard) return;

    const newNotifications: NotificationItem[] = [];

    // Check for streak risks
    dashboard.active_streaks.forEach((streak) => {
      const daysSinceActivity = streak.last_activity_date
        ? Math.floor((new Date().getTime() - new Date(streak.last_activity_date).getTime()) / (1000 * 60 * 60 * 24))
        : 0;

      const isAtRisk = (
        (streak.habit_type === 'daily_expense_tracking' && daysSinceActivity >= 1) ||
        (streak.habit_type === 'weekly_budget_review' && daysSinceActivity >= 7) ||
        (daysSinceActivity >= 3)
      );

      if (isAtRisk && streak.is_active) {
        const IconComponent = habitTypeIcons[streak.habit_type as keyof typeof habitTypeIcons] || Target;
        const habitLabel = habitTypeLabels[streak.habit_type as keyof typeof habitTypeLabels] || streak.habit_type;

        newNotifications.push({
          id: `streak_risk_${streak.id}`,
          type: 'streak_risk',
          title: 'Streak at Risk!',
          message: `Your ${habitLabel.toLowerCase()} streak (${streak.current_length} days) is at risk. Take action today to keep it alive!`,
          icon: <Flame className="h-5 w-5 text-orange-500" />,
          color: 'border-orange-200 bg-orange-50',
          action: {
            label: 'Take Action',
            onClick: () => {
              // Navigate to appropriate action based on habit type
              if (streak.habit_type === 'daily_expense_tracking') {
                window.location.href = '/expenses/new';
              } else if (streak.habit_type === 'invoice_follow_up') {
                window.location.href = '/invoices';
              } else {
                window.location.href = '/';
              }
            }
          },
          dismissible: true
        });
      }
    });

    // Welcome back message (if user hasn't been active recently)
    const lastActivity = dashboard.recent_points[0]?.created_at;
    if (lastActivity) {
      const daysSinceLastActivity = Math.floor(
        (new Date().getTime() - new Date(lastActivity).getTime()) / (1000 * 60 * 60 * 24)
      );

      if (daysSinceLastActivity >= 3 && daysSinceLastActivity <= 30) {
        newNotifications.push({
          id: 'welcome_back',
          type: 'welcome_back',
          title: 'Welcome Back!',
          message: `It's been ${daysSinceLastActivity} days since your last activity. Ready to get back on track with your financial goals?`,
          icon: <Heart className="h-5 w-5 text-pink-500" />,
          color: 'border-pink-200 bg-pink-50',
          action: {
            label: 'Get Started',
            onClick: () => {
              window.location.href = '/expenses/new';
            }
          },
          dismissible: true
        });
      }
    }

    // Daily motivational tip
    const dailyTips = [
      "Track your expenses daily to build a strong financial foundation.",
      "Small consistent actions lead to big financial improvements.",
      "Review your budget weekly to stay on top of your spending.",
      "Upload receipts to get the full picture of your expenses.",
      "Follow up on invoices promptly to maintain healthy cash flow.",
      "Categorize your expenses accurately for better insights.",
      "Set financial goals and track your progress regularly.",
      "Celebrate small wins on your financial journey!"
    ];

    const today = new Date().toDateString();
    const tipIndex = new Date().getDate() % dailyTips.length;

    newNotifications.push({
      id: `daily_tip_${today}`,
      type: 'daily_tip',
      title: 'Daily Financial Tip',
      message: dailyTips[tipIndex],
      icon: <Target className="h-5 w-5 text-blue-500" />,
      color: 'border-blue-200 bg-blue-50',
      dismissible: true
    });

    // Filter out dismissed notifications
    const filteredNotifications = newNotifications.filter(
      notification => !dismissedNotifications.has(notification.id)
    );

    setNotifications(filteredNotifications);
  }, [dashboard, canShowGamification, dismissedNotifications]);

  const dismissNotification = (id: string) => {
    setDismissedNotifications(prev => new Set([...prev, id]));

    // Store dismissed notifications in localStorage
    const dismissed = Array.from(dismissedNotifications);
    dismissed.push(id);
    localStorage.setItem('gamification_dismissed_notifications', JSON.stringify(dismissed));
  };

  // Load dismissed notifications from localStorage on mount
  useEffect(() => {
    const stored = localStorage.getItem('gamification_dismissed_notifications');
    if (stored) {
      try {
        const dismissed = JSON.parse(stored);
        setDismissedNotifications(new Set(dismissed));
      } catch (error) {
        console.error('Error loading dismissed notifications:', error);
      }
    }
  }, []);

  if (!canShowGamification || notifications.length === 0) {
    return null;
  }

  return (
    <div className="space-y-3">
      {notifications.map((notification) => (
        <ProfessionalCard key={notification.id} className={`border-2 ${notification.color}`}>
          <ProfessionalCardContent className="p-4">
            <div className="flex items-start space-x-3">
              <div className="flex-shrink-0 mt-0.5">
                {notification.icon}
              </div>

              <div className="flex-1 min-w-0">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <h4 className="text-sm font-medium text-foreground">
                      {notification.title}
                    </h4>
                    <p className="text-sm text-muted-foreground mt-1">
                      {notification.message}
                    </p>
                  </div>

                  {notification.dismissible && (
                    <ProfessionalButton
                      variant="ghost"
                      size="sm"
                      onClick={() => dismissNotification(notification.id)}
                      className="h-6 w-6 p-0 ml-2"
                    >
                      <X className="h-4 w-4" />
                    </ProfessionalButton>
                  )}
                </div>

                {notification.action && (
                  <div className="mt-3">
                    <ProfessionalButton
                      size="sm"
                      onClick={notification.action.onClick}
                      className="text-xs"
                    >
                      {notification.action.label}
                    </ProfessionalButton>
                  </div>
                )}
              </div>
            </div>
          </ProfessionalCardContent>
        </ProfessionalCard>
      ))}
    </div>
  );
}

// Hook for managing celebration state
export function useCelebrations() {
  const [celebrations, setCelebrations] = useState<{
    isOpen: boolean;
    type: 'achievement' | 'level_up' | 'streak_milestone';
    data: any;
    pointsAwarded?: number;
  } | null>(null);

  const showCelebration = (
    type: 'achievement' | 'level_up' | 'streak_milestone',
    data: any,
    pointsAwarded?: number
  ) => {
    setCelebrations({
      isOpen: true,
      type,
      data,
      pointsAwarded
    });
  };

  const closeCelebration = () => {
    setCelebrations(null);
  };

  return {
    celebration: celebrations,
    showCelebration,
    closeCelebration
  };
}