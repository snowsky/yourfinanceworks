import React from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Trophy, Target, Flame, TrendingUp, Star, Award, Calendar, Zap } from 'lucide-react';
import { useGamification } from '@/hooks/useGamification';
import { LevelProgressCard } from './LevelProgressCard';
import { AchievementGrid } from './AchievementGrid';
import { StreakDisplay } from './StreakDisplay';
import { ChallengeCards } from './ChallengeCards';
import { FinancialHealthScore } from './FinancialHealthScore';
import { RecentPointsHistory } from './RecentPointsHistory';
import { GamificationToggle } from './GamificationToggle';
import { AchievementRules } from './AchievementRules';
import { LoadingSpinner } from '@/components/ui/loading-spinner';

export function GamificationDashboard() {
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
      <div className="flex items-center justify-center p-8">
        <LoadingSpinner />
        <span className="ml-2">Loading gamification data...</span>
      </div>
    );
  }

  if (error) {
    return (
      <Card className="border-red-200 bg-red-50">
        <CardContent className="p-6">
          <div className="flex items-center space-x-2 text-red-600">
            <Trophy className="h-5 w-5" />
            <span className="font-medium">Error loading gamification</span>
          </div>
          <p className="text-red-600 text-sm mt-2">{error}</p>
        </CardContent>
      </Card>
    );
  }

  if (!isEnabled) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center space-x-2">
            <Trophy className="h-5 w-5" />
            <span>Gamification</span>
          </CardTitle>
          <CardDescription>
            Transform your financial management into an engaging, habit-building experience
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="text-center py-8">
            <div className="mb-4">
              <Trophy className="h-16 w-16 mx-auto text-gray-400" />
            </div>
            <h3 className="text-lg font-semibold mb-2">Gamification is disabled</h3>
            <p className="text-gray-600 mb-6">
              Enable gamification to earn points, unlock achievements, and build better financial habits.
            </p>
            <GamificationToggle />
          </div>
        </CardContent>
      </Card>
    );
  }

  if (!canShowGamification || !dashboard) {
    return (
      <Card>
        <CardContent className="p-6">
          <div className="text-center">
            <Trophy className="h-12 w-12 mx-auto text-gray-400 mb-4" />
            <p className="text-gray-600">Gamification data not available</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header with toggle */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center space-x-2">
            <Trophy className="h-6 w-6 text-yellow-500" />
            <span>Your Progress</span>
          </h1>
          <p className="text-gray-600">Track your financial habits and achievements</p>
        </div>
        <GamificationToggle />
      </div>

      {/* Quick Stats Overview */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center space-x-2">
              <Star className="h-5 w-5 text-yellow-500" />
              <div>
                <p className="text-sm text-gray-600">Level</p>
                <p className="text-2xl font-bold">{profile.level}</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center space-x-2">
              <Zap className="h-5 w-5 text-blue-500" />
              <div>
                <p className="text-sm text-gray-600">Total XP</p>
                <p className="text-2xl font-bold">{profile.total_experience_points.toLocaleString()}</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center space-x-2">
              <Award className="h-5 w-5 text-purple-500" />
              <div>
                <p className="text-sm text-gray-600">Achievements</p>
                <p className="text-2xl font-bold">{dashboard.recent_achievements.length}</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center space-x-2">
              <TrendingUp className="h-5 w-5 text-green-500" />
              <div>
                <p className="text-sm text-gray-600">Health Score</p>
                <p className="text-2xl font-bold">{Math.round(profile.financial_health_score)}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Main Dashboard Content */}
      <Tabs defaultValue="overview" className="space-y-4">
        <TabsList className="grid w-full grid-cols-6">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="achievements">Achievements</TabsTrigger>
          <TabsTrigger value="rules">Rules</TabsTrigger>
          <TabsTrigger value="streaks">Streaks</TabsTrigger>
          <TabsTrigger value="challenges">Challenges</TabsTrigger>
          <TabsTrigger value="health">Health Score</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Level Progress */}
            <LevelProgressCard 
              profile={profile}
              levelProgress={dashboard.level_progress}
            />

            {/* Financial Health Score */}
            <FinancialHealthScore 
              score={profile.financial_health_score}
              trend={dashboard.financial_health_trend}
            />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Active Streaks */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center space-x-2">
                  <Flame className="h-5 w-5 text-orange-500" />
                  <span>Active Streaks</span>
                </CardTitle>
              </CardHeader>
              <CardContent>
                {dashboard.active_streaks.length > 0 ? (
                  <div className="space-y-3">
                    {dashboard.active_streaks.slice(0, 3).map((streak) => (
                      <StreakDisplay key={streak.id} streak={streak} compact />
                    ))}
                  </div>
                ) : (
                  <p className="text-gray-600 text-center py-4">
                    No active streaks. Start tracking expenses daily to build your first streak!
                  </p>
                )}
              </CardContent>
            </Card>

            {/* Recent Points */}
            <RecentPointsHistory points={dashboard.recent_points} />
          </div>

          {/* Recent Achievements */}
          {dashboard.recent_achievements.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center space-x-2">
                  <Award className="h-5 w-5 text-purple-500" />
                  <span>Recent Achievements</span>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {dashboard.recent_achievements.slice(0, 6).map((achievement) => (
                    <div key={achievement.id} className="flex items-center space-x-3 p-3 bg-gray-50 rounded-lg">
                      <div className="flex-shrink-0">
                        <Badge variant="secondary" className="bg-purple-100 text-purple-700">
                          {achievement.achievement.difficulty}
                        </Badge>
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium truncate">
                          {achievement.achievement.name}
                        </p>
                        <p className="text-xs text-gray-600">
                          {achievement.unlocked_at ? 
                            new Date(achievement.unlocked_at).toLocaleDateString() : 
                            `${Math.round(achievement.progress * 100)}% complete`
                          }
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="achievements">
          <AchievementGrid />
        </TabsContent>

        <TabsContent value="rules">
          <AchievementRules />
        </TabsContent>

        <TabsContent value="streaks">
          <div className="space-y-6">
            {dashboard.active_streaks.map((streak) => (
              <StreakDisplay key={streak.id} streak={streak} />
            ))}
            {dashboard.active_streaks.length === 0 && (
              <Card>
                <CardContent className="p-8 text-center">
                  <Flame className="h-12 w-12 mx-auto text-gray-400 mb-4" />
                  <h3 className="text-lg font-semibold mb-2">No Active Streaks</h3>
                  <p className="text-gray-600">
                    Start tracking your expenses daily to build your first streak!
                  </p>
                </CardContent>
              </Card>
            )}
          </div>
        </TabsContent>

        <TabsContent value="challenges">
          <ChallengeCards />
        </TabsContent>

        <TabsContent value="health">
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