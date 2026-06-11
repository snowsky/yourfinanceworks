import React, { useEffect, useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Trophy, Star, Flame, Zap, Gift, Sparkles, X } from 'lucide-react';
import type { Achievement, UserStreak } from '@/types/gamification';

interface LevelUpData {
  old_level: number;
  new_level: number;
  xp_to_next: number;
}

interface CelebrationModalProps {
  isOpen: boolean;
  onClose: () => void;
  type: 'achievement' | 'level_up' | 'streak_milestone';
  data: Achievement | LevelUpData | UserStreak;
  pointsAwarded?: number;
}

export function CelebrationModal({ 
  isOpen, 
  onClose, 
  type, 
  data, 
  pointsAwarded = 0 
}: CelebrationModalProps) {
  const [showConfetti, setShowConfetti] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setShowConfetti(true);
      // Auto-close after 5 seconds if user doesn't interact
      const timer = setTimeout(() => {
        onClose();
      }, 5000);
      return () => clearTimeout(timer);
    }
  }, [isOpen, onClose]);

  const renderAchievementCelebration = (achievement: Achievement) => (
    <div className="text-center space-y-4">
      <div className="relative">
        <div className="w-24 h-24 mx-auto bg-gradient-to-br from-yellow-400 to-yellow-600 rounded-full flex items-center justify-center mb-4">
          <Trophy className="h-12 w-12 text-white" />
        </div>
        {showConfetti && (
          <div className="absolute inset-0 flex items-center justify-center">
            <Sparkles className="h-8 w-8 text-yellow-400 animate-pulse" />
          </div>
        )}
      </div>
      
      <div className="space-y-2">
        <h2 className="text-2xl font-bold text-foreground">Achievement Unlocked!</h2>
        <h3 className="text-xl font-semibold text-yellow-600">{achievement.name}</h3>
        <p className="text-muted-foreground">{achievement.description}</p>
      </div>
      
      <div className="flex items-center justify-center space-x-4">
        <Badge variant="secondary" className="bg-purple-100 text-purple-700">
          {achievement.difficulty}
        </Badge>
        {achievement.reward_xp > 0 && (
          <div className="flex items-center space-x-1 text-blue-600">
            <Zap className="h-4 w-4" />
            <span className="font-medium">+{achievement.reward_xp} XP</span>
          </div>
        )}
      </div>
    </div>
  );

  const renderLevelUpCelebration = (levelData: LevelUpData) => (
    <div className="text-center space-y-4">
      <div className="relative">
        <div className="w-24 h-24 mx-auto bg-gradient-to-br from-blue-400 to-blue-600 rounded-full flex items-center justify-center mb-4">
          <Star className="h-12 w-12 text-white" />
        </div>
        {showConfetti && (
          <div className="absolute inset-0 flex items-center justify-center">
            <Sparkles className="h-8 w-8 text-blue-400 animate-pulse" />
          </div>
        )}
      </div>
      
      <div className="space-y-2">
        <h2 className="text-2xl font-bold text-foreground">Level Up!</h2>
        <div className="flex items-center justify-center space-x-2">
          <span className="text-lg text-muted-foreground">Level {levelData.old_level}</span>
          <span className="text-2xl">→</span>
          <span className="text-2xl font-bold text-blue-600">Level {levelData.new_level}</span>
        </div>
        <p className="text-muted-foreground">
          Congratulations! You've reached a new level in your financial journey.
        </p>
      </div>

      <div className="bg-primary/10 border border-primary/30 rounded-lg p-4">
        <h4 className="font-medium text-foreground mb-2">New Level Benefits:</h4>
        <div className="flex flex-wrap justify-center gap-2">
          <Badge variant="outline" className="bg-primary/10 text-primary">
            +5% XP Bonus
          </Badge>
          <Badge variant="outline" className="bg-primary/10 text-primary">
            New Achievements
          </Badge>
          <Badge variant="outline" className="bg-primary/10 text-primary">
            Exclusive Challenges
          </Badge>
        </div>
      </div>

      {pointsAwarded > 0 && (
        <div className="flex items-center justify-center space-x-1 text-success">
          <Gift className="h-4 w-4" />
          <span className="font-medium">Level up bonus: +{pointsAwarded} XP</span>
        </div>
      )}
    </div>
  );

  const renderStreakMilestoneCelebration = (streak: UserStreak) => (
    <div className="text-center space-y-4">
      <div className="relative">
        <div className="w-24 h-24 mx-auto bg-gradient-to-br from-orange-400 to-orange-600 rounded-full flex items-center justify-center mb-4">
          <Flame className="h-12 w-12 text-white" />
        </div>
        {showConfetti && (
          <div className="absolute inset-0 flex items-center justify-center">
            <Sparkles className="h-8 w-8 text-orange-400 animate-pulse" />
          </div>
        )}
      </div>
      
      <div className="space-y-2">
        <h2 className="text-2xl font-bold text-foreground">Streak Milestone!</h2>
        <div className="flex items-center justify-center space-x-2">
          <Flame className="h-6 w-6 text-orange-500" />
          <span className="text-2xl font-bold text-orange-600">{streak.current_length} Days</span>
        </div>
        <p className="text-muted-foreground">
          Amazing consistency! You've maintained your {streak.habit_type.replace('_', ' ')} streak.
        </p>
      </div>
      
      <div className="bg-orange-50 border border-orange-200 rounded-lg p-4">
        <h4 className="font-medium text-orange-800 mb-2">Keep it up!</h4>
        <p className="text-orange-700 text-sm">
          Consistent habits are the foundation of financial success. 
          Your dedication is paying off!
        </p>
      </div>
      
      {pointsAwarded > 0 && (
        <div className="flex items-center justify-center space-x-1 text-success">
          <Zap className="h-4 w-4" />
          <span className="font-medium">Streak bonus: +{pointsAwarded} XP</span>
        </div>
      )}
    </div>
  );

  const renderCelebration = () => {
    switch (type) {
      case 'achievement':
        return renderAchievementCelebration(data as Achievement);
      case 'level_up':
        return renderLevelUpCelebration(data as LevelUpData);
      case 'streak_milestone':
        return renderStreakMilestoneCelebration(data as UserStreak);
      default:
        return null;
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-md">
        <div className="absolute right-4 top-4">
          <Button
            variant="ghost"
            size="sm"
            onClick={onClose}
            className="h-6 w-6 p-0"
          >
            <X className="h-4 w-4" />
          </Button>
        </div>
        
        <div className="pt-6">
          {renderCelebration()}
        </div>
        
        <div className="flex justify-center pt-4">
          <Button onClick={onClose} className="w-full">
            Continue
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}