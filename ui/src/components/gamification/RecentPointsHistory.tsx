import React from 'react';
import {
  ProfessionalCard,
  ProfessionalCardContent,
  ProfessionalCardHeader,
  ProfessionalCardTitle
} from '@/components/ui/professional-card';
import { Badge } from '@/components/ui/badge';
import { Zap, Target, TrendingUp, Calendar, CheckCircle, Plus } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import type { PointHistory } from '@/types/gamification';

const actionTypeIcons = {
  expense_added: Target,
  invoice_created: TrendingUp,
  receipt_uploaded: CheckCircle,
  budget_reviewed: Calendar,
  payment_recorded: Plus,
  category_assigned: CheckCircle
};

const actionTypeColors = {
  expense_added: 'text-blue-500',
  invoice_created: 'text-green-500',
  receipt_uploaded: 'text-orange-500',
  budget_reviewed: 'text-purple-500',
  payment_recorded: 'text-teal-500',
  category_assigned: 'text-pink-500'
};

interface RecentPointsHistoryProps {
  points: PointHistory[];
  compact?: boolean;
}

export function RecentPointsHistory({ points, compact = false }: RecentPointsHistoryProps) {
  const { t } = useTranslation();

  const actionTypeLabels = {
    expense_added: t('settings.gamification.recent_points.expense_added'),
    invoice_created: t('settings.gamification.recent_points.invoice_created'),
    receipt_uploaded: t('settings.gamification.recent_points.receipt_uploaded'),
    budget_reviewed: t('settings.gamification.recent_points.budget_reviewed'),
    payment_recorded: t('settings.gamification.recent_points.payment_recorded'),
    category_assigned: t('settings.gamification.recent_points.category_assigned')
  };

  if (!points || points.length === 0) {
    return (
      <ProfessionalCard variant="elevated">
        <ProfessionalCardHeader>
          <ProfessionalCardTitle className="flex items-center space-x-2">
            <Zap className="h-5 w-5 text-blue-500" />
            <span>{t('settings.gamification.recent_points.title')}</span>
          </ProfessionalCardTitle>
        </ProfessionalCardHeader>
        <ProfessionalCardContent>
          <div className="text-center py-8">
            <Zap className="h-12 w-12 mx-auto text-muted-foreground/30 mb-4" />
            <h3 className="text-lg font-semibold mb-2">{t('settings.gamification.recent_points.no_activity')}</h3>
            <p className="text-muted-foreground">
              {t('settings.gamification.recent_points.start_tracking')}
            </p>
          </div>
        </ProfessionalCardContent>
      </ProfessionalCard>
    );
  }

  const totalRecentPoints = points.reduce((sum, point) => sum + point.points_awarded, 0);

  return (
    <ProfessionalCard variant="elevated">
      <ProfessionalCardHeader>
        <ProfessionalCardTitle className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <Zap className="h-5 w-5 text-blue-500" />
            <span>{t('settings.gamification.recent_points.title')}</span>
          </div>
          <Badge variant="outline" className="text-blue-600 bg-blue-50 dark:bg-blue-900/10 border-blue-200 dark:border-blue-900/30">
            +{totalRecentPoints} XP
          </Badge>
        </ProfessionalCardTitle>
      </ProfessionalCardHeader>
      <ProfessionalCardContent>
        <div className="space-y-3">
          {points.slice(0, 8).map((point) => {
            const IconComponent = actionTypeIcons[point.action_type as keyof typeof actionTypeIcons] || Target;
            const actionLabel = actionTypeLabels[point.action_type as keyof typeof actionTypeLabels] || point.action_type;
            const iconColor = actionTypeColors[point.action_type as keyof typeof actionTypeColors] || 'text-gray-500';

            return (
              <div key={point.id} className="flex items-center justify-between p-3 bg-muted/40 rounded-lg border border-border/50 hover:bg-muted/60 transition-colors">
                <div className="flex items-center space-x-3">
                  <div className="p-2 bg-background rounded-lg shadow-sm">
                    <IconComponent className={`h-4 w-4 ${iconColor}`} />
                  </div>
                  <div>
                    <p className="text-sm font-medium">{actionLabel}</p>
                    <p className="text-xs text-muted-foreground">
                      {new Date(point.created_at).toLocaleDateString()} at{' '}
                      {new Date(point.created_at).toLocaleTimeString([], {
                        hour: '2-digit',
                        minute: '2-digit'
                      })}
                    </p>
                  </div>
                </div>

                <div className="text-right">
                  <div className="flex items-center space-x-1">
                    <Zap className="h-3 w-3 text-blue-500" />
                    <span className="text-sm font-bold text-blue-600 dark:text-blue-400">
                      +{point.points_awarded}
                    </span>
                  </div>

                  {/* Show bonus breakdown if applicable */}
                  {(point.streak_multiplier > 1 || point.accuracy_bonus > 0 || point.completeness_bonus > 0) && (
                    <div className="flex items-center space-x-1 text-xs text-muted-foreground mt-1">
                      <span>{point.base_points} base</span>
                      {point.streak_multiplier > 1 && (
                        <span className="text-orange-600 dark:text-orange-400">
                          ×{point.streak_multiplier.toFixed(1)} streak
                        </span>
                      )}
                      {point.accuracy_bonus > 0 && (
                        <span className="text-green-600 dark:text-green-400">
                          +{point.accuracy_bonus} accuracy
                        </span>
                      )}
                      {point.completeness_bonus > 0 && (
                        <span className="text-purple-600 dark:text-purple-400">
                          +{point.completeness_bonus} complete
                        </span>
                      )}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {points.length > 8 && (
          <div className="text-center mt-4">
            <p className="text-sm text-muted-foreground">
              {t('settings.gamification.recent_points.showing_activities', { shown: Math.min(8, points.length), total: points.length })}
            </p>
          </div>
        )}
      </ProfessionalCardContent>
    </ProfessionalCard>
  );
}