import React from 'react';
import {
  ProfessionalCard,
  ProfessionalCardContent,
  ProfessionalCardHeader,
  ProfessionalCardTitle
} from '@/components/ui/professional-card';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import { Star, Zap, TrendingUp } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import type { UserGamificationProfile, LevelProgress } from '@/types/gamification';

interface LevelProgressCardProps {
  profile: UserGamificationProfile;
  levelProgress: LevelProgress;
}

export function LevelProgressCard({ profile, levelProgress }: LevelProgressCardProps) {
  const { t } = useTranslation();
  const progressPercentage = levelProgress.progress_percentage || 0;
  const xpNeeded = levelProgress.xp_needed || 0;
  const xpProgress = levelProgress.xp_progress || 0;

  return (
    <ProfessionalCard>
      <ProfessionalCardHeader>
        <ProfessionalCardTitle className="flex items-center space-x-2">
          <Star className="h-5 w-5 text-yellow-500" />
          <span>{t('settings.gamification.level_progress.title')}</span>
        </ProfessionalCardTitle>
      </ProfessionalCardHeader>
      <ProfessionalCardContent className="space-y-4">
        {/* Current Level Display */}
        <div className="text-center">
          <div className="inline-flex items-center justify-center w-20 h-20 bg-gradient-to-br from-yellow-400 to-yellow-600 rounded-full text-white text-2xl font-bold mb-2">
            {profile.level}
          </div>
          <p className="text-sm text-gray-600">{t('settings.gamification.level_progress.current_level')}</p>
        </div>

        {/* Progress Bar */}
        <div className="space-y-2">
          <div className="flex justify-between text-sm">
            <span className="text-gray-600">{t('settings.gamification.level_progress.progress_to_level', { level: profile.level + 1 })}</span>
            <span className="font-medium">{Math.round(progressPercentage)}%</span>
          </div>
          <Progress value={progressPercentage} className="h-3" />
          <div className="flex justify-between text-xs text-gray-500">
            <span>{xpProgress.toLocaleString()} XP</span>
            <span>{xpNeeded.toLocaleString()} {t('settings.gamification.level_progress.xp_needed')}</span>
          </div>
        </div>

        {/* XP Stats */}
        <div className="grid grid-cols-2 gap-4 pt-4 border-t">
          <div className="text-center">
            <div className="flex items-center justify-center space-x-1 text-blue-600 mb-1">
              <Zap className="h-4 w-4" />
              <span className="text-lg font-bold">{profile.total_experience_points.toLocaleString()}</span>
            </div>
            <p className="text-xs text-gray-600">{t('settings.gamification.level_progress.total_xp')}</p>
          </div>
          <div className="text-center">
            <div className="flex items-center justify-center space-x-1 text-green-600 mb-1">
              <TrendingUp className="h-4 w-4" />
              <span className="text-lg font-bold">{Math.round(profile.current_level_progress * 100)}%</span>
            </div>
            <p className="text-xs text-gray-600">{t('settings.gamification.level_progress.level_progress')}</p>
          </div>
        </div>

        {/* Level Benefits Preview */}
        <div className="bg-gray-50 rounded-lg p-3">
          <p className="text-xs font-medium text-gray-700 mb-2">{t('settings.gamification.level_progress.next_level_benefits')}:</p>
          <div className="flex flex-wrap gap-1">
            <Badge variant="outline" className="text-xs">
              {t('settings.gamification.level_progress.xp_bonus')}
            </Badge>
            <Badge variant="outline" className="text-xs">
              {t('settings.gamification.level_progress.new_achievements')}
            </Badge>
            <Badge variant="outline" className="text-xs">
              {t('settings.gamification.level_progress.exclusive_challenges')}
            </Badge>
          </div>
        </div>
      </ProfessionalCardContent>
    </ProfessionalCard>
  );
}