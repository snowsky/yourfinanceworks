import React, { useState } from 'react';
import { ProfessionalCard, ProfessionalCardContent, ProfessionalCardHeader, ProfessionalCardTitle } from '@/components/ui/professional-card';
import { ProfessionalButton } from '@/components/ui/professional-button';
import { Badge } from '@/components/ui/badge';
import {
  Trophy,
  Flame,
  Star,
  Zap,
  ChevronDown,
  ChevronUp,
  Target,
  TrendingUp
} from 'lucide-react';
import { useGamification } from '@/hooks/useGamification';
import { useTranslation } from 'react-i18next';
import { GamificationNotifications } from './GamificationNotifications';

export function GamificationWidget() {
  const { t } = useTranslation();
  const { profile, dashboard, canShowGamification, isEnabled } = useGamification();
  const [isExpanded, setIsExpanded] = useState(false);

  if (!isEnabled || !canShowGamification || !profile || !dashboard) {
    return null;
  }

  const activeStreaks = dashboard.active_streaks.filter(s => s.is_active);
  const recentAchievements = dashboard.recent_achievements.slice(0, 3);
  const activeChallenges = dashboard.active_challenges.filter(c => c.opted_in && !c.is_completed);

  return (
    <ProfessionalCard className="w-full max-w-sm">
      <ProfessionalCardHeader className="pb-3">
        <ProfessionalCardTitle className="flex items-center justify-between text-sm">
          <div className="flex items-center space-x-2">
            <Trophy className="h-4 w-4 text-yellow-500" />
            <span>Progress</span>
          </div>
          <ProfessionalButton
            variant="ghost"
            size="sm"
            onClick={() => setIsExpanded(!isExpanded)}
            className="h-6 w-6 p-0"
          >
            {isExpanded ? (
              <ChevronUp className="h-4 w-4" />
            ) : (
              <ChevronDown className="h-4 w-4" />
            )}
          </ProfessionalButton>
        </ProfessionalCardTitle>
      </ProfessionalCardHeader>

      <ProfessionalCardContent className="space-y-3">
        {/* Quick Stats */}
        <div className="grid grid-cols-3 gap-2 text-center">
          <div>
            <div className="flex items-center justify-center space-x-1">
              <Star className="h-3 w-3 text-yellow-500" />
              <span className="text-sm font-bold">{profile.level}</span>
            </div>
            <p className="text-xs text-muted-foreground">{t('settings.gamification.dashboard.level')}</p>
          </div>
          <div>
            <div className="flex items-center justify-center space-x-1">
              <Zap className="h-3 w-3 text-blue-500" />
              <span className="text-sm font-bold">{profile.total_experience_points.toLocaleString()}</span>
            </div>
            <p className="text-xs text-muted-foreground">{t('settings.gamification.dashboard.total_xp')}</p>
          </div>
          <div>
            <div className="flex items-center justify-center space-x-1">
              <TrendingUp className="h-3 w-3 text-green-500" />
              <span className="text-sm font-bold">{Math.round(profile.financial_health_score)}</span>
            </div>
            <p className="text-xs text-muted-foreground">{t('settings.gamification.dashboard.wellness_score')}</p>
          </div>
        </div>

        {/* Active Streaks */}
        {activeStreaks.length > 0 && (
          <div>
            <h4 className="text-xs font-medium text-muted-foreground mb-2">{t('settings.gamification.streaks.title')}</h4>
            <div className="space-y-1">
              {activeStreaks.slice(0, 2).map((streak) => (
                <div key={streak.id} className="flex items-center justify-between text-xs">
                  <div className="flex items-center space-x-1">
                    <Flame className="h-3 w-3 text-orange-500" />
                    <span className="text-muted-foreground truncate">
                      {streak.habit_type.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())}
                    </span>
                  </div>
                  <Badge variant="outline" className="text-xs px-1 py-0">
                    {streak.current_length}d
                  </Badge>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Recent Achievements */}
        {recentAchievements.length > 0 && (
          <div>
            <h4 className="text-xs font-medium text-muted-foreground mb-2">{t('settings.gamification.achievements.title')}</h4>
            <div className="space-y-1">
              {recentAchievements.map((achievement) => (
                <div key={achievement.id} className="flex items-center space-x-2 text-xs">
                  <Trophy className="h-3 w-3 text-purple-500" />
                  <span className="text-muted-foreground truncate flex-1">
                    {achievement.achievement.name}
                  </span>
                  <Badge variant="secondary" className="text-xs px-1 py-0">
                    {achievement.achievement.difficulty}
                  </Badge>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Active Challenges */}
        {activeChallenges.length > 0 && (
          <div>
            <h4 className="text-xs font-medium text-muted-foreground mb-2">{t('settings.gamification.challenges.title')}</h4>
            <div className="space-y-1">
              {activeChallenges.slice(0, 2).map((challenge) => (
                <div key={challenge.id} className="flex items-center justify-between text-xs">
                  <div className="flex items-center space-x-1">
                    <Target className="h-3 w-3 text-blue-500" />
                    <span className="text-muted-foreground truncate">
                      {challenge.challenge.name}
                    </span>
                  </div>
                  <Badge variant="outline" className="text-xs px-1 py-0">
                    {Math.round(challenge.progress * 100)}%
                  </Badge>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Expanded Content */}
        {isExpanded && (
          <div className="space-y-3 pt-3 border-t">
            <GamificationNotifications />

            <div className="text-center">
              <ProfessionalButton
                variant="outline"
                size="sm"
                onClick={() => window.location.href = '/gamification'}
                className="text-xs"
              >
                {t('settings.gamification.dashboard.view_full_dashboard')}
              </ProfessionalButton>
            </div>
          </div>
        )}

        {/* Quick Action */}
        {!isExpanded && (
          <div className="text-center pt-2 border-t">
            <ProfessionalButton
              variant="ghost"
              size="sm"
              onClick={() => window.location.href = '/gamification'}
              className="text-xs text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300"
            >
              {t('settings.gamification.dashboard.view_dashboard')}
            </ProfessionalButton>
          </div>
        )}
      </ProfessionalCardContent>
    </ProfessionalCard>
  );
}