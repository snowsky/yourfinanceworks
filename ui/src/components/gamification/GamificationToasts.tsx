import React from 'react';
import { toast } from 'sonner';
import { Zap, Trophy, Flame, Star, Target, TrendingUp } from 'lucide-react';
import type { GamificationResult } from '@/types/gamification';

// Custom toast components for gamification events
export const showPointsToast = (points: number, action: string) => {
  toast.success(
    <div className="flex items-center space-x-2">
      <Zap className="h-4 w-4 text-primary" />
      <span>+{points} XP for {action}</span>
    </div>,
    {
      duration: 3000,
    }
  );
};

export const showAchievementToast = (achievementName: string, xp: number) => {
  toast.success(
    <div className="flex items-center space-x-2">
      <Trophy className="h-4 w-4 text-yellow-500" />
      <div>
        <div className="font-medium">Achievement Unlocked!</div>
        <div className="text-sm text-muted-foreground">{achievementName} (+{xp} XP)</div>
      </div>
    </div>,
    {
      duration: 5000,
    }
  );
};

export const showLevelUpToast = (newLevel: number) => {
  toast.success(
    <div className="flex items-center space-x-2">
      <Star className="h-4 w-4 text-purple-500" />
      <div>
        <div className="font-medium">Level Up!</div>
        <div className="text-sm text-muted-foreground">You reached Level {newLevel}</div>
      </div>
    </div>,
    {
      duration: 5000,
    }
  );
};

export const showStreakToast = (streakLength: number, habitType: string) => {
  const habitLabels = {
    daily_expense_tracking: 'expense tracking',
    weekly_budget_review: 'budget review',
    invoice_follow_up: 'invoice follow-up',
    receipt_documentation: 'receipt documentation'
  };
  
  const habitLabel = habitLabels[habitType as keyof typeof habitLabels] || habitType;
  
  toast.success(
    <div className="flex items-center space-x-2">
      <Flame className="h-4 w-4 text-orange-500" />
      <div>
        <div className="font-medium">{streakLength} Day Streak!</div>
        <div className="text-sm text-muted-foreground">Keep up your {habitLabel} habit</div>
      </div>
    </div>,
    {
      duration: 4000,
    }
  );
};

export const showStreakRiskToast = (habitType: string, streakLength: number) => {
  const habitLabels = {
    daily_expense_tracking: 'expense tracking',
    weekly_budget_review: 'budget review',
    invoice_follow_up: 'invoice follow-up',
    receipt_documentation: 'receipt documentation'
  };
  
  const habitLabel = habitLabels[habitType as keyof typeof habitLabels] || habitType;
  
  toast.warning(
    <div className="flex items-center space-x-2">
      <Flame className="h-4 w-4 text-orange-500" />
      <div>
        <div className="font-medium">Streak at Risk!</div>
        <div className="text-sm text-muted-foreground">
          Your {streakLength}-day {habitLabel} streak needs attention
        </div>
      </div>
    </div>,
    {
      duration: 6000,
    }
  );
};

export const showWelcomeBackToast = (daysSinceLastActivity: number) => {
  toast.info(
    <div className="flex items-center space-x-2">
      <Target className="h-4 w-4 text-primary" />
      <div>
        <div className="font-medium">Welcome Back!</div>
        <div className="text-sm text-muted-foreground">
          Ready to continue your financial journey?
        </div>
      </div>
    </div>,
    {
      duration: 5000,
    }
  );
};

export const showHealthScoreToast = (newScore: number, change: number) => {
  const isImprovement = change > 0;
  
  toast.success(
    <div className="flex items-center space-x-2">
      <TrendingUp className={`h-4 w-4 ${isImprovement ? 'text-success' : 'text-destructive'}`} />
      <div>
        <div className="font-medium">Health Score Updated</div>
        <div className="text-sm text-muted-foreground">
          {Math.round(newScore)}/100 ({isImprovement ? '+' : ''}{Math.round(change)})
        </div>
      </div>
    </div>,
    {
      duration: 4000,
    }
  );
};

// Main function to show appropriate toasts based on gamification result
export const showGamificationToasts = (result: GamificationResult) => {
  // Show points toast for any points awarded
  if (result.points_awarded > 0) {
    showPointsToast(result.points_awarded, 'financial activity');
  }

  // Show achievement toast
  if (result.achievements_unlocked && result.achievements_unlocked.length > 0) {
    result.achievements_unlocked.forEach(achievement => {
      showAchievementToast(achievement.name, achievement.reward_xp);
    });
  }

  // Show level up toast
  if (result.level_up) {
    showLevelUpToast(result.level_up.new_level);
  }

  // Show streak toasts
  if (result.streaks_updated && result.streaks_updated.length > 0) {
    result.streaks_updated.forEach(streak => {
      if (streak.is_active && streak.current_length > 1) {
        // Check if it's a milestone
        const milestones = [7, 30, 90, 365];
        if (milestones.includes(streak.current_length)) {
          showStreakToast(streak.current_length, streak.habit_type);
        }
      }
    });
  }

  // Show health score change toast
  if (result.financial_health_score_change && Math.abs(result.financial_health_score_change) >= 1) {
    // We don't have the new score here, so we'll skip this for now
    // This would need to be handled at a higher level where we have access to the current score
  }
};

// Utility function to show a generic gamification success toast
export const showGamificationSuccessToast = (message: string) => {
  toast.success(
    <div className="flex items-center space-x-2">
      <Trophy className="h-4 w-4 text-yellow-500" />
      <span>{message}</span>
    </div>,
    {
      duration: 3000,
    }
  );
};

// Utility function to show a generic gamification info toast
export const showGamificationInfoToast = (message: string) => {
  toast.info(
    <div className="flex items-center space-x-2">
      <Target className="h-4 w-4 text-primary" />
      <span>{message}</span>
    </div>,
    {
      duration: 4000,
    }
  );
};