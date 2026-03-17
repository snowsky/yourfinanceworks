import { apiRequest } from './_base';
import type {
  ModuleStatus,
  EnableGamificationRequest,
  DisableGamificationRequest,
  UserGamificationProfile,
  GamificationPreferences,
  GamificationDashboard,
  LevelProgress,
  UserAchievement,
  Achievement,
  UserStreak,
  Challenge,
  UserChallenge,
  FinancialEvent,
  ProcessFinancialEventResponse,
} from '@/types/gamification';

// Gamification API methods
export const gamificationApi = {
  // Module status and control
  getStatus: () =>
    apiRequest<ModuleStatus>('/gamification/status'),

  enable: (request: EnableGamificationRequest) =>
    apiRequest<UserGamificationProfile>('/gamification/enable', {
      method: 'POST',
      body: JSON.stringify(request),
    }),

  disable: (request: DisableGamificationRequest) =>
    apiRequest<{ message: string }>('/gamification/disable', {
      method: 'POST',
      body: JSON.stringify(request),
    }),

  // User profile and preferences
  getProfile: () =>
    apiRequest<UserGamificationProfile | null>('/gamification/profile'),

  updatePreferences: (preferences: GamificationPreferences) =>
    apiRequest<UserGamificationProfile>('/gamification/preferences', {
      method: 'PUT',
      body: JSON.stringify(preferences),
    }),

  // Dashboard data
  getDashboard: () =>
    apiRequest<GamificationDashboard | null>('/gamification/dashboard'),

  // Level progression
  getLevelProgress: () =>
    apiRequest<LevelProgress | null>('/gamification/level/progress'),

  getLevelRewards: (level: number) =>
    apiRequest<any>(`/gamification/level/rewards/${level}`),

  getLevelCurve: () =>
    apiRequest<any>('/gamification/level/curve'),

  // Achievements
  getAchievements: (category?: string, completedOnly = false) =>
    apiRequest<UserAchievement[]>(`/gamification/achievements?${new URLSearchParams({
      ...(category && { category }),
      completed_only: completedOnly.toString()
    })}`),

  getAchievementProgress: (achievementId: string) =>
    apiRequest<any>(`/gamification/achievements/${achievementId}/progress`),

  getMilestoneAchievements: (category: string) =>
    apiRequest<Achievement[]>(`/gamification/achievements/milestones/${category}`),

  // Achievement Rules
  getAchievementRules: () =>
    apiRequest<{ rules: any[], total_count: number }>('/gamification/admin/achievements/rules'),

  toggleAchievementRule: (achievementId: string) =>
    apiRequest<{ achievement_id: string, is_active: boolean, message: string }>(`/gamification/admin/achievements/rules/${achievementId}/toggle`, {
      method: 'PUT',
    }),

  // Streaks
  getStreaks: () =>
    apiRequest<UserStreak[]>('/gamification/streaks'),

  getStreakAnalytics: () =>
    apiRequest<any>('/gamification/streaks/analytics'),

  handleStreakBreak: (habitType: string) =>
    apiRequest<any>(`/gamification/streaks/${habitType}/break`, {
      method: 'POST',
    }),

  // Challenges
  getAvailableChallenges: (challengeType?: string) =>
    apiRequest<Challenge[]>(`/gamification/challenges/available?${new URLSearchParams({
      ...(challengeType && { challenge_type: challengeType })
    })}`),

  getWeeklyChallenges: () =>
    apiRequest<Challenge[]>('/gamification/challenges/weekly'),

  getMonthlyChallenges: () =>
    apiRequest<Challenge[]>('/gamification/challenges/monthly'),

  optIntoChallenge: (challengeId: number) =>
    apiRequest<UserChallenge>(`/gamification/challenges/${challengeId}/opt-in`, {
      method: 'POST',
    }),

  optOutOfChallenge: (challengeId: number) =>
    apiRequest<{ message: string }>(`/gamification/challenges/${challengeId}/opt-out`, {
      method: 'POST',
    }),

  getMyChallenges: (activeOnly = true, completedOnly = false) =>
    apiRequest<UserChallenge[]>(`/gamification/challenges/my?${new URLSearchParams({
      active_only: activeOnly.toString(),
      completed_only: completedOnly.toString()
    })}`),

  getChallengeProgress: (challengeId: number) =>
    apiRequest<any>(`/gamification/challenges/${challengeId}/progress`),

  // Financial Health Score
  getFinancialHealthScore: () =>
    apiRequest<any>('/gamification/health-score'),

  getHealthScoreComponents: () =>
    apiRequest<any>('/gamification/health-score/components'),

  recalculateHealthScore: () =>
    apiRequest<{ message: string; new_score: number }>('/gamification/health-score/recalculate', {
      method: 'POST',
    }),

  // Event processing
  processEvent: (event: FinancialEvent) =>
    apiRequest<ProcessFinancialEventResponse>('/gamification/events/process', {
      method: 'POST',
      body: JSON.stringify({ event }),
    }),

  // Validation
  validate: () =>
    apiRequest<any>('/gamification/validate'),
};
