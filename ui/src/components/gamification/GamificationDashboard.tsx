import React from 'react';
import {
  ProfessionalCard,
  ProfessionalCardContent,
  ProfessionalCardHeader,
  ProfessionalCardTitle,
  ProfessionalCardDescription,
  MetricCard
} from '@/components/ui/professional-card';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Trophy, Target, Flame, TrendingUp, Star, Award, Calendar, Zap, AlertTriangle, Activity } from 'lucide-react';
import { useGamification } from '@/hooks/useGamification';
import { useTranslation } from 'react-i18next';
import { LevelProgressCard } from './LevelProgressCard';
import { AchievementGrid } from './AchievementGrid';
import { StreakDisplay } from './StreakDisplay';
import { ChallengeCards } from './ChallengeCards';
import { FinancialHealthScore } from './FinancialHealthScore';
import { RecentPointsHistory } from './RecentPointsHistory';
import { GamificationToggle } from './GamificationToggle';
import { AchievementRules } from './AchievementRules';
import { LoadingSpinner } from '@/components/ui/loading-spinner';
import { cn } from '@/lib/utils';

export function GamificationDashboard() {
  const { t } = useTranslation();
  const {
    profile,
    dashboard,
    loading,
    error,
    canShowGamification,
    isEnabled,
    refreshDashboard
  } = useGamification();

  if (loading) {
    return (
      <ProfessionalCard variant="elevated">
        <ProfessionalCardContent className="flex flex-col items-center justify-center p-16">
          <LoadingSpinner className="w-8 h-8 text-primary mb-4" />
          <span className="text-muted-foreground font-medium">{t('settings.gamification.loading')}</span>
        </ProfessionalCardContent>
      </ProfessionalCard>
    );
  }

  if (error) {
    return (
      <ProfessionalCard variant="elevated" className="border-red-200 bg-red-50 dark:bg-red-900/10 dark:border-red-900/30">
        <ProfessionalCardContent className="p-6">
          <div className="flex items-center space-x-2 text-red-600 dark:text-red-400">
            <AlertTriangle className="h-5 w-5" />
            <span className="font-medium">{t('settings.gamification.error')}</span>
          </div>
          <p className="text-red-600 dark:text-red-400 text-sm mt-2">{error}</p>
        </ProfessionalCardContent>
      </ProfessionalCard>
    );
  }

  if (!isEnabled) {
    return (
      <ProfessionalCard variant="elevated" className="overflow-hidden">
        <ProfessionalCardHeader className="bg-muted/30 pb-8 border-b border-border/50">
          <div className="flex flex-col items-center text-center space-y-2">
            <div className="p-3 bg-yellow-100 rounded-full mb-2">
              <Trophy className="h-8 w-8 text-yellow-600" />
            </div>
            <ProfessionalCardTitle className="text-2xl">
              {t('settings.gamification.title')}
            </ProfessionalCardTitle>
            <ProfessionalCardDescription className="max-w-md mx-auto">
              {t('settings.gamification.description')}
            </ProfessionalCardDescription>
          </div>
        </ProfessionalCardHeader>
        <ProfessionalCardContent className="p-8">
          <div className="flex flex-col items-center justify-center space-y-6">
            <div className="text-center max-w-lg space-y-2">
              <h3 className="text-lg font-semibold text-foreground">
                {t('settings.gamification.title')} {t('settings.gamification.disabled')}
              </h3>
              <p className="text-muted-foreground">
                {t('settings.gamification.enable_description')}
              </p>
            </div>
            <div className="w-full max-w-md bg-muted/30 p-4 rounded-xl border border-border/50">
              <GamificationToggle />
            </div>
          </div>
        </ProfessionalCardContent>
      </ProfessionalCard>
    );
  }

  if (!canShowGamification || !dashboard) {
    return (
      <ProfessionalCard variant="elevated">
        <ProfessionalCardContent className="p-12">
          <div className="text-center">
            <Trophy className="h-12 w-12 mx-auto text-muted-foreground/30 mb-4" />
            <p className="text-muted-foreground text-lg">{t('settings.gamification.not_available')}</p>
          </div>
        </ProfessionalCardContent>
      </ProfessionalCard>
    );
  }

  return (
    <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
      {/* Header with toggle */}
      <ProfessionalCard variant="glass" className="border-border/50 bg-gradient-to-br from-card to-muted/20">
        <ProfessionalCardContent className="p-6">
          <div className="flex flex-col md:flex-row items-center justify-between gap-6">
            <div className="flex items-center gap-4">
              <div className="p-3 bg-yellow-100 dark:bg-yellow-900/30 rounded-xl shadow-sm">
                <Trophy className="h-8 w-8 text-yellow-600 dark:text-yellow-400" />
              </div>
              <div>
                <h1 className="text-2xl font-bold tracking-tight text-foreground">
                  {t('settings.gamification.dashboard.title')}
                </h1>
                <p className="text-muted-foreground">
                  {t('settings.gamification.dashboard.subtitle')}
                </p>
              </div>
            </div>
            <div className="w-full md:w-auto">
              <GamificationToggle />
            </div>
          </div>
        </ProfessionalCardContent>
      </ProfessionalCard>

      {/* Quick Stats Overview */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title={t('settings.gamification.dashboard.level')}
          value={profile.level}
          icon={Star}
          variant="default"
          change={{
            value: 0,
            type: 'neutral'
          }}
          description="Current Level"
          className="bg-card shadow-sm border-border/50"
        />
        <MetricCard
          title={t('settings.gamification.dashboard.total_xp')}
          value={profile.total_experience_points.toLocaleString()}
          icon={Zap}
          variant="default"
          change={{
            value: dashboard.level_progress.progress_percentage || 0,
            type: 'increase'
          }}
          description="XP this level"
          className="bg-card shadow-sm border-border/50"
        />
        <MetricCard
          title={t('settings.gamification.dashboard.achievements')}
          value={dashboard.recent_achievements.length}
          icon={Award}
          variant="default"
          change={{
            value: 0,
            type: 'neutral'
          }}
          description="Unlocked"
          className="bg-card shadow-sm border-border/50"
        />
        <MetricCard
          title={t('settings.gamification.dashboard.wellness_score')}
          value={Math.round(profile.financial_health_score)}
          icon={TrendingUp}
          variant="success"
          change={{
            value: dashboard.financial_health_trend.length > 0
              ? dashboard.financial_health_trend[dashboard.financial_health_trend.length - 1].score
              : 0,
            type: dashboard.financial_health_trend.length > 0 &&
              dashboard.financial_health_trend[dashboard.financial_health_trend.length - 1].score >= 0
              ? 'increase'
              : 'decrease'
          }}
          description="vs last month"
          className="bg-card shadow-sm border-border/50"
        />
      </div>

      {/* Main Dashboard Content */}
      <Tabs defaultValue="overview" className="space-y-6">
        <TabsList className="grid w-full grid-cols-3 lg:grid-cols-6 h-auto p-1.5 bg-muted/50 rounded-xl border border-border/50">
          <TabsTrigger value="overview" className="rounded-lg data-[state=active]:bg-primary data-[state=active]:text-primary-foreground data-[state=active]:shadow-md py-2.5 transition-all font-medium">{t('settings.gamification.dashboard.overview')}</TabsTrigger>
          <TabsTrigger value="achievements" className="rounded-lg data-[state=active]:bg-primary data-[state=active]:text-primary-foreground data-[state=active]:shadow-md py-2.5 transition-all font-medium">{t('settings.gamification.dashboard.achievements_tab')}</TabsTrigger>
          <TabsTrigger value="streaks" className="rounded-lg data-[state=active]:bg-primary data-[state=active]:text-primary-foreground data-[state=active]:shadow-md py-2.5 transition-all font-medium">{t('settings.gamification.dashboard.streaks')}</TabsTrigger>
          <TabsTrigger value="challenges" className="rounded-lg data-[state=active]:bg-primary data-[state=active]:text-primary-foreground data-[state=active]:shadow-md py-2.5 transition-all font-medium">{t('settings.gamification.dashboard.challenges')}</TabsTrigger>
          <TabsTrigger value="wellness" className="rounded-lg data-[state=active]:bg-primary data-[state=active]:text-primary-foreground data-[state=active]:shadow-md py-2.5 transition-all font-medium">{t('settings.gamification.dashboard.wellness')}</TabsTrigger>
          <TabsTrigger value="rules" className="rounded-lg data-[state=active]:bg-primary data-[state=active]:text-primary-foreground data-[state=active]:shadow-md py-2.5 transition-all font-medium">{t('settings.gamification.dashboard.rules')}</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-6 animate-in fade-in zoom-in-95 duration-200">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Level Progress */}
            <LevelProgressCard
              profile={profile}
              levelProgress={dashboard.level_progress}
            />

            {/* Financial Wellness Score */}
            <FinancialHealthScore
              score={profile.financial_health_score}
              trend={dashboard.financial_health_trend}
            />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Active Streaks */}
            <ProfessionalCard variant="elevated">
              <ProfessionalCardHeader>
                <ProfessionalCardTitle className="flex items-center space-x-2">
                  <Flame className="h-5 w-5 text-orange-500" />
                  <span>{t('settings.gamification.streaks.title')}</span>
                </ProfessionalCardTitle>
              </ProfessionalCardHeader>
              <ProfessionalCardContent>
                {dashboard.active_streaks.length > 0 ? (
                  <div className="space-y-3">
                    {dashboard.active_streaks.slice(0, 3).map((streak) => (
                      <StreakDisplay key={streak.id} streak={streak} compact />
                    ))}
                  </div>
                ) : (
                  <div className="flex flex-col items-center justify-center py-6 text-center">
                    <div className="p-3 bg-muted rounded-full mb-3">
                      <Flame className="h-6 w-6 text-muted-foreground" />
                    </div>
                    <p className="text-muted-foreground text-sm">
                      {t('settings.gamification.streaks.start_tracking')}
                    </p>
                  </div>
                )}
              </ProfessionalCardContent>
            </ProfessionalCard>

            {/* Recent Points */}
            <RecentPointsHistory points={dashboard.recent_points} />
          </div>

          {/* Recent Achievements */}
          {dashboard.recent_achievements.length > 0 && (
            <ProfessionalCard variant="elevated">
              <ProfessionalCardHeader>
                <ProfessionalCardTitle className="flex items-center space-x-2">
                  <Award className="h-5 w-5 text-purple-500" />
                  <span>{t('settings.gamification.achievements.title')}</span>
                </ProfessionalCardTitle>
              </ProfessionalCardHeader>
              <ProfessionalCardContent>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {dashboard.recent_achievements.slice(0, 6).map((achievement) => (
                    <div key={achievement.id} className="flex items-center space-x-3 p-3 bg-muted/40 rounded-xl border border-border/50 hover:bg-muted/60 transition-colors">
                      <div className="flex-shrink-0">
                        <Badge variant="secondary" className="bg-purple-100 text-purple-700 hover:bg-purple-200 border-purple-200">
                          {t(`settings.gamification.achievements.difficulty.${achievement.achievement.difficulty.toLowerCase()}`)}
                        </Badge>
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium truncate text-foreground">
                          {achievement.achievement.name}
                        </p>
                        <p className="text-xs text-muted-foreground mt-0.5">
                          {achievement.unlocked_at ?
                            new Date(achievement.unlocked_at).toLocaleDateString() :
                            `${Math.round(achievement.progress * 100)}% ${t('settings.gamification.achievements.progress')}`
                          }
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              </ProfessionalCardContent>
            </ProfessionalCard>
          )}
        </TabsContent>

        <TabsContent value="achievements" className="animate-in fade-in zoom-in-95 duration-200">
          <AchievementGrid />
        </TabsContent>

        <TabsContent value="rules" className="animate-in fade-in zoom-in-95 duration-200">
          <AchievementRules />
        </TabsContent>

        <TabsContent value="streaks" className="animate-in fade-in zoom-in-95 duration-200">
          <div className="space-y-6">
            {dashboard.active_streaks.map((streak) => (
              <StreakDisplay key={streak.id} streak={streak} />
            ))}
            {dashboard.active_streaks.length === 0 && (
              <ProfessionalCard variant="elevated" className="border-dashed">
                <ProfessionalCardContent className="p-12 text-center">
                  <div className="p-4 bg-orange-50 dark:bg-orange-900/20 rounded-full mx-auto w-fit mb-4">
                    <Flame className="h-8 w-8 text-orange-500" />
                  </div>
                  <h3 className="text-xl font-bold mb-2">{t('settings.gamification.streaks.no_active_streaks')}</h3>
                  <p className="text-muted-foreground text-lg max-w-md mx-auto">
                    {t('settings.gamification.streaks.start_tracking')}
                  </p>
                </ProfessionalCardContent>
              </ProfessionalCard>
            )}
          </div>
        </TabsContent>

        <TabsContent value="challenges" className="animate-in fade-in zoom-in-95 duration-200">
          <ChallengeCards />
        </TabsContent>

        <TabsContent value="wellness" className="animate-in fade-in zoom-in-95 duration-200">
          <div className="space-y-6">
            <FinancialHealthScore
              score={profile.financial_health_score}
              trend={dashboard.financial_health_trend}
              detailed
            />
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}