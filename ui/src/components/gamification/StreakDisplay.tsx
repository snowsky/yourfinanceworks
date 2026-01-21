import React from 'react';
import {
  ProfessionalCard,
  ProfessionalCardContent,
  ProfessionalCardHeader,
  ProfessionalCardTitle
} from '@/components/ui/professional-card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { ProfessionalButton } from '@/components/ui/professional-button';
import { Flame, Calendar, Target, TrendingUp, AlertTriangle, CheckCircle } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import type { UserStreak, HabitType } from '@/types/gamification';

interface StreakDisplayProps {
  streak: UserStreak;
  compact?: boolean;
}

const habitTypeIcons = {
  daily_expense_tracking: Target,
  weekly_budget_review: TrendingUp,
  invoice_follow_up: Calendar,
  receipt_documentation: CheckCircle
};

const habitTypeColors = {
  daily_expense_tracking: 'text-blue-500',
  weekly_budget_review: 'text-green-500',
  invoice_follow_up: 'text-purple-500',
  receipt_documentation: 'text-orange-500'
};

export function StreakDisplay({ streak, compact = false }: StreakDisplayProps) {
  const { t } = useTranslation();

  const habitTypeLabels = {
    daily_expense_tracking: t('settings.gamification.streaks.habit_types.daily_expense_tracking'),
    weekly_budget_review: t('settings.gamification.streaks.habit_types.weekly_budget_review'),
    invoice_follow_up: t('settings.gamification.streaks.habit_types.invoice_follow_up'),
    receipt_documentation: t('settings.gamification.streaks.habit_types.receipt_documentation')
  };

  const habitLabel = habitTypeLabels[streak.habit_type as keyof typeof habitTypeLabels] || streak.habit_type;
  const IconComponent = habitTypeIcons[streak.habit_type as keyof typeof habitTypeIcons] || Target;
  const iconColor = habitTypeColors[streak.habit_type as keyof typeof habitTypeColors] || 'text-gray-500';

  const isActive = streak.is_active;
  const daysSinceActivity = streak.last_activity_date
    ? Math.floor((new Date().getTime() - new Date(streak.last_activity_date).getTime()) / (1000 * 60 * 60 * 24))
    : 0;

  // Determine risk level based on habit type and days since activity
  const getRiskLevel = () => {
    if (!isActive) return 'broken';
    if (daysSinceActivity === 0) return 'safe';
    if (streak.habit_type === 'daily_expense_tracking' && daysSinceActivity >= 1) return 'high_risk';
    if (streak.habit_type === 'weekly_budget_review' && daysSinceActivity >= 7) return 'high_risk';
    if (daysSinceActivity >= 3) return 'medium_risk';
    return 'low_risk';
  };

  const riskLevel = getRiskLevel();

  const riskColors = {
    safe: 'text-green-600 bg-green-50/50 border-green-200 dark:bg-green-900/10 dark:border-green-800 dark:text-green-400',
    low_risk: 'text-yellow-600 bg-yellow-50/50 border-yellow-200 dark:bg-yellow-900/10 dark:border-yellow-800 dark:text-yellow-400',
    medium_risk: 'text-orange-600 bg-orange-50/50 border-orange-200 dark:bg-orange-900/10 dark:border-orange-800 dark:text-orange-400',
    high_risk: 'text-red-600 bg-red-50/50 border-red-200 dark:bg-red-900/10 dark:border-red-800 dark:text-red-400',
    broken: 'text-muted-foreground bg-muted/50 border-border'
  };

  const riskLabels = {
    safe: t('settings.gamification.streaks.risk_labels.safe'),
    low_risk: t('settings.gamification.streaks.risk_labels.low_risk'),
    medium_risk: t('settings.gamification.streaks.risk_labels.medium_risk'),
    high_risk: t('settings.gamification.streaks.risk_labels.high_risk'),
    broken: t('settings.gamification.streaks.risk_labels.broken')
  };

  if (compact) {
    return (
      <div className="flex items-center justify-between p-3 bg-muted/30 rounded-lg border border-border/50">
        <div className="flex items-center space-x-3">
          <div className={`p-2 rounded-lg ${isActive ? 'bg-orange-100 dark:bg-orange-900/30' : 'bg-muted'}`}>
            {isActive ? (
              <Flame className="h-4 w-4 text-orange-500" />
            ) : (
              <IconComponent className={`h-4 w-4 ${iconColor}`} />
            )}
          </div>
          <div>
            <p className="text-sm font-medium">{habitLabel}</p>
            <p className="text-xs text-muted-foreground">
              {isActive ? `${streak.current_length} ${t('settings.gamification.streaks.days')}` : t('settings.gamification.streaks.broken')}
            </p>
          </div>
        </div>
        <div className="text-right">
          <Badge variant="outline" className={`text-xs ${riskColors[riskLevel]}`}>
            {riskLabels[riskLevel]}
          </Badge>
          {streak.longest_length > 0 && (
            <p className="text-xs text-muted-foreground mt-1">
              {t('settings.gamification.streaks.best')}: {streak.longest_length} {t('settings.gamification.streaks.days')}
            </p>
          )}
        </div>
      </div>
    );
  }

  return (
    <ProfessionalCard className={`${riskColors[riskLevel]} border-2`}>
      <ProfessionalCardHeader>
        <ProfessionalCardTitle className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <IconComponent className={`h-5 w-5 ${iconColor}`} />
            <span>{habitLabel}</span>
          </div>
          <Badge variant="outline" className={riskColors[riskLevel]}>
            {riskLabels[riskLevel]}
          </Badge>
        </ProfessionalCardTitle>
      </ProfessionalCardHeader>
      <ProfessionalCardContent className="space-y-4">
        {/* Current Streak */}
        <div className="text-center">
          <div className="flex items-center justify-center space-x-2 mb-2">
            <Flame className={`h-8 w-8 ${isActive ? 'text-orange-500' : 'text-muted-foreground/30'}`} />
            <span className="text-3xl font-bold">
              {isActive ? streak.current_length : 0}
            </span>
          </div>
          <p className="text-sm text-muted-foreground">
            {isActive ? t('settings.gamification.streaks.current_streak') : t('settings.gamification.streaks.broken')}
          </p>
        </div>

        {/* Progress to next milestone */}
        {isActive && (
          <div className="space-y-2">
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">{t('settings.gamification.streaks.next_milestone')}</span>
              <span className="font-medium">
                {streak.current_length < 7 ? `7 ${t('settings.gamification.streaks.days')}` :
                  streak.current_length < 30 ? `30 ${t('settings.gamification.streaks.days')}` :
                    streak.current_length < 90 ? `90 ${t('settings.gamification.streaks.days')}` : `365 ${t('settings.gamification.streaks.days')}`}
              </span>
            </div>
            <Progress
              value={
                streak.current_length < 7 ? (streak.current_length / 7) * 100 :
                  streak.current_length < 30 ? ((streak.current_length - 7) / 23) * 100 :
                    streak.current_length < 90 ? ((streak.current_length - 30) / 60) * 100 :
                      ((streak.current_length - 90) / 275) * 100
              }
              className="h-2"
            />
          </div>
        )}

        {/* Stats */}
        <div className="grid grid-cols-3 gap-4 pt-4 border-t border-border/50">
          <div className="text-center">
            <p className="text-lg font-bold text-blue-600 dark:text-blue-400">{streak.longest_length}</p>
            <p className="text-xs text-muted-foreground">{t('settings.gamification.streaks.longest_streak')}</p>
          </div>
          <div className="text-center">
            <p className="text-lg font-bold text-purple-600 dark:text-purple-400">{streak.times_broken || 0}</p>
            <p className="text-xs text-muted-foreground">{t('settings.gamification.streaks.times_broken')}</p>
          </div>
          <div className="text-center">
            <p className="text-lg font-bold text-green-600 dark:text-green-400">{daysSinceActivity}</p>
            <p className="text-xs text-muted-foreground">{t('settings.gamification.streaks.days_since')}</p>
          </div>
        </div>

        {/* Last Activity */}
        {streak.last_activity_date && (
          <div className="text-center text-sm text-muted-foreground">
            {t('settings.gamification.streaks.last_activity')}: {new Date(streak.last_activity_date).toLocaleDateString()}
          </div>
        )}

        {/* Risk Warning */}
        {riskLevel === 'high_risk' && (
          <div className="flex items-center space-x-2 p-3 bg-red-50 dark:bg-red-900/10 border border-red-200 dark:border-red-900/30 rounded-lg">
            <AlertTriangle className="h-4 w-4 text-red-500" />
            <div className="text-sm">
              <p className="font-medium text-red-800 dark:text-red-300">{t('settings.gamification.streaks.risk_warning')}</p>
              <p className="text-red-600 dark:text-red-400">
                {streak.habit_type === 'daily_expense_tracking'
                  ? t('settings.gamification.streaks.expense_tracking_warning')
                  : t('settings.gamification.streaks.habit_completion_warning')
                }
              </p>
            </div>
          </div>
        )}

        {/* Encouragement for broken streaks */}
        {!isActive && (
          <div className="text-center">
            <p className="text-sm text-muted-foreground mb-3">
              {t('settings.gamification.streaks.encouragement')}
            </p>
            <ProfessionalButton size="sm" variant="outline">
              {t('settings.gamification.streaks.start_new_streak')}
            </ProfessionalButton>
          </div>
        )}
      </ProfessionalCardContent>
    </ProfessionalCard>
  );
}