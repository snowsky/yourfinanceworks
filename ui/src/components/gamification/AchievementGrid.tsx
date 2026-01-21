import { useState, useEffect } from 'react';
import {
  ProfessionalCard,
  ProfessionalCardContent,
  ProfessionalCardHeader,
  ProfessionalCardTitle
} from '@/components/ui/professional-card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Award, Trophy, Star, Target, TrendingUp, Lock, RefreshCw } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { gamificationApi } from '@/lib/api';
import type { UserAchievement } from '@/types/gamification';
import { LoadingSpinner } from '@/components/ui/loading-spinner';
import { ProfessionalButton } from '@/components/ui/professional-button';

const categoryIcons = {
  expense_tracking: Target,
  invoice_management: TrendingUp,
  habit_formation: Star,
  financial_health: Trophy,
  exploration: Award
};

const categoryColors = {
  expense_tracking: 'text-blue-500',
  invoice_management: 'text-green-500',
  habit_formation: 'text-purple-500',
  financial_health: 'text-yellow-500',
  exploration: 'text-pink-500'
};

const difficultyColors = {
  bronze: 'bg-amber-100 text-amber-800',
  silver: 'bg-gray-100 text-gray-800',
  gold: 'bg-yellow-100 text-yellow-800',
  platinum: 'bg-purple-100 text-purple-800'
};

interface AchievementCardProps {
  achievement: UserAchievement;
  t: (key: string, options?: any) => string;
}

function AchievementCard({ achievement, t }: AchievementCardProps) {
  const IconComponent = categoryIcons[achievement.achievement.category as keyof typeof categoryIcons] || Award;
  const iconColor = categoryColors[achievement.achievement.category as keyof typeof categoryColors] || 'text-gray-500';
  const difficultyColor = difficultyColors[achievement.achievement.difficulty as keyof typeof difficultyColors] || 'bg-gray-100 text-gray-800';

  const isCompleted = achievement.is_completed;
  const progress = Math.round(achievement.progress * 100);

  return (
    <ProfessionalCard className={`transition-all duration-200 hover:shadow-md ${isCompleted ? 'ring-2 ring-green-200 bg-green-50 dark:bg-green-900/10 dark:ring-green-900/30' : ''}`}>
      <ProfessionalCardContent className="p-4">
        <div className="flex items-start space-x-3">
          <div className={`flex-shrink-0 p-2 rounded-lg ${isCompleted ? 'bg-green-100 dark:bg-green-900/30' : 'bg-gray-100 dark:bg-muted'}`}>
            {isCompleted ? (
              <Trophy className="h-6 w-6 text-green-600 dark:text-green-400" />
            ) : (
              <IconComponent className={`h-6 w-6 ${iconColor}`} />
            )}
          </div>

          <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between mb-2">
              <h3 className={`font-medium text-sm ${isCompleted ? 'text-green-800 dark:text-green-300' : 'text-foreground'}`}>
                {achievement.achievement.name}
              </h3>
              <Badge variant="secondary" className={`text-xs ${difficultyColor}`}>
                {achievement.achievement.difficulty}
              </Badge>
            </div>

            <p className="text-xs text-muted-foreground mb-3 line-clamp-2">
              {achievement.achievement.description}
            </p>

            {!isCompleted && (
              <div className="space-y-1">
                <div className="flex justify-between text-xs">
                  <span className="text-muted-foreground">{t('settings.gamification.achievements.progress')}</span>
                  <span className="font-medium">{progress}%</span>
                </div>
                <Progress value={progress} className="h-2" />
              </div>
            )}

            {isCompleted && achievement.unlocked_at && (
              <div className="flex items-center space-x-1 text-xs text-green-600 dark:text-green-400">
                <Trophy className="h-3 w-3" />
                <span>{t('settings.gamification.achievements.unlocked')} {new Date(achievement.unlocked_at).toLocaleDateString()}</span>
              </div>
            )}

            {achievement.achievement.reward_xp > 0 && (
              <div className="flex items-center space-x-1 text-xs text-blue-600 dark:text-blue-400 mt-2">
                <Star className="h-3 w-3" />
                <span>{achievement.achievement.reward_xp} XP</span>
              </div>
            )}
          </div>
        </div>
      </ProfessionalCardContent>
    </ProfessionalCard>
  );
}

export function AchievementGrid() {
  const { t } = useTranslation();
  const [achievements, setAchievements] = useState<UserAchievement[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [refreshing, setRefreshing] = useState(false);

  const fetchAchievements = async () => {
    try {
      setLoading(true);
      setError(null);

      const data = await gamificationApi.getAchievements();
      setAchievements(data);
    } catch (err) {
      console.error('Error fetching achievements:', err);
      setError(err instanceof Error ? err.message : 'Failed to load achievements');
    } finally {
      setLoading(false);
    }
  };

  const handleRefresh = async () => {
    try {
      setRefreshing(true);
      const data = await gamificationApi.getAchievements();
      setAchievements(data);
    } catch (err) {
      console.error('Error refreshing achievements:', err);
    } finally {
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchAchievements();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center p-8">
        <LoadingSpinner />
        <span className="ml-2">{t('settings.gamification.achievements.loading')}</span>
      </div>
    );
  }

  if (error) {
    return (
      <ProfessionalCard variant="elevated" className="border-red-200 bg-red-50 dark:bg-red-900/10 dark:border-red-900/30">
        <ProfessionalCardContent className="p-6">
          <div className="flex items-center space-x-2 text-red-600 dark:text-red-400">
            <Award className="h-5 w-5" />
            <span className="font-medium">{t('settings.gamification.achievements.error')}</span>
          </div>
          <p className="text-red-600 dark:text-red-400 text-sm mt-2">{error}</p>
        </ProfessionalCardContent>
      </ProfessionalCard>
    );
  }

  const categories = [
    { id: 'all', name: t('settings.gamification.achievements.categories.all'), icon: Award },
    { id: 'expense_tracking', name: t('settings.gamification.achievements.categories.expense_tracking'), icon: Target },
    { id: 'invoice_management', name: t('settings.gamification.achievements.categories.invoice_management'), icon: TrendingUp },
    { id: 'habit_formation', name: t('settings.gamification.achievements.categories.habit_formation'), icon: Star },
    { id: 'financial_health', name: t('settings.gamification.achievements.categories.financial_health'), icon: Trophy },
    { id: 'exploration', name: t('settings.gamification.achievements.categories.exploration'), icon: Award }
  ];

  const filteredAchievements = selectedCategory === 'all'
    ? achievements
    : achievements.filter(a => a.achievement.category === selectedCategory);

  const completedCount = filteredAchievements.filter(a => a.is_completed).length;
  const totalCount = filteredAchievements.length;

  return (
    <div className="space-y-6">
      {/* Header Stats */}
      <ProfessionalCard>
        <ProfessionalCardHeader>
          <ProfessionalCardTitle className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <Award className="h-5 w-5 text-purple-500" />
              <span>{t('settings.gamification.achievements.title')}</span>
            </div>
            <div className="flex items-center space-x-2">
              <Badge variant="outline" className="text-sm">
                {t('settings.gamification.achievements.completed_count', { completed: completedCount, total: totalCount })}
              </Badge>
              <ProfessionalButton
                variant="ghost"
                size="sm"
                onClick={handleRefresh}
                disabled={refreshing}
                className="h-8 w-8 p-0"
              >
                <RefreshCw className={`h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
              </ProfessionalButton>
            </div>
          </ProfessionalCardTitle>
        </ProfessionalCardHeader>
        <ProfessionalCardContent>
          <div className="space-y-2">
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">{t('settings.gamification.achievements.overall_progress')}</span>
              <span className="font-medium">{totalCount > 0 ? Math.round((completedCount / totalCount) * 100) : 0}%</span>
            </div>
            <Progress value={totalCount > 0 ? (completedCount / totalCount) * 100 : 0} className="h-2" />
          </div>
        </ProfessionalCardContent>
      </ProfessionalCard>

      {/* Category Tabs */}
      <Tabs value={selectedCategory} onValueChange={setSelectedCategory}>
        <TabsList className="grid w-full grid-cols-3 lg:grid-cols-6 h-auto p-1 bg-muted/50 rounded-lg border border-border/50">
          {categories.map((category) => {
            const IconComponent = category.icon;
            return (
              <TabsTrigger key={category.id} value={category.id} className="text-xs data-[state=active]:bg-background data-[state=active]:text-foreground data-[state=active]:shadow-sm py-2">
                <IconComponent className="h-4 w-4 mr-1" />
                <span className="hidden sm:inline">{category.name}</span>
              </TabsTrigger>
            );
          })}
        </TabsList>

        {categories.map((category) => (
          <TabsContent key={category.id} value={category.id} className="mt-6">
            {filteredAchievements.length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {filteredAchievements.map((achievement) => (
                  <AchievementCard key={achievement.id} achievement={achievement} t={t} />
                ))}
              </div>
            ) : (
              <ProfessionalCard variant="dashed">
                <ProfessionalCardContent className="p-12 text-center">
                  <div className="bg-muted/30 p-4 rounded-full w-20 h-20 mx-auto flex items-center justify-center mb-4">
                    <Lock className="h-10 w-10 text-muted-foreground/40" />
                  </div>
                  <h3 className="text-lg font-semibold mb-2">{t('settings.gamification.achievements.no_achievements')}</h3>
                  <p className="text-muted-foreground max-w-sm mx-auto">
                    {t('settings.gamification.achievements.no_achievements_description')}
                  </p>
                </ProfessionalCardContent>
              </ProfessionalCard>
            )}
          </TabsContent>
        ))}
      </Tabs>
    </div>
  );
}