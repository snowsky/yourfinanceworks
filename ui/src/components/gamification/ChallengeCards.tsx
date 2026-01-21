import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { ProfessionalCard, ProfessionalCardContent, ProfessionalCardHeader, ProfessionalCardTitle } from '@/components/ui/professional-card';
import { Badge } from '@/components/ui/badge';
import { ProfessionalButton } from '@/components/ui/professional-button';
import { Progress } from '@/components/ui/progress';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Target, Calendar, Users, Star, Clock, CheckCircle, XCircle } from 'lucide-react';
import { gamificationApi } from '@/lib/api';
import type { UserChallenge, Challenge } from '@/types/gamification';
import { LoadingSpinner } from '@/components/ui/loading-spinner';
import { toast } from 'sonner';

const challengeTypeIcons = {
  personal: Target,
  community: Users,
  seasonal: Star
};

const challengeTypeColors = {
  personal: 'text-blue-500 bg-blue-50 border-blue-200',
  community: 'text-green-500 bg-green-50 border-green-200',
  seasonal: 'text-purple-500 bg-purple-50 border-purple-200'
};

interface ChallengeCardProps {
  challenge: UserChallenge;
  onOptIn?: (challengeId: number) => void;
  onOptOut?: (challengeId: number) => void;
}

function ChallengeCard({ challenge, onOptIn, onOptOut }: ChallengeCardProps) {
  const IconComponent = challengeTypeIcons[challenge.challenge.challenge_type as keyof typeof challengeTypeIcons] || Target;
  const typeColor = challengeTypeColors[challenge.challenge.challenge_type as keyof typeof challengeTypeColors] || 'text-gray-500 bg-gray-50 border-gray-200';

  const progress = Math.round(challenge.progress * 100);
  const isCompleted = challenge.is_completed;
  const isOptedIn = challenge.opted_in;

  const daysRemaining = challenge.challenge.end_date
    ? Math.max(0, Math.ceil((new Date(challenge.challenge.end_date).getTime() - new Date().getTime()) / (1000 * 60 * 60 * 24)))
    : challenge.challenge.duration_days;

  const handleOptToggle = async () => {
    try {
      if (isOptedIn) {
        await gamificationApi.optOutOfChallenge(challenge.challenge.id);
        onOptOut?.(challenge.challenge.id);
        toast.success('Opted out of challenge');
      } else {
        await gamificationApi.optIntoChallenge(challenge.challenge.id);
        onOptIn?.(challenge.challenge.id);
        toast.success('Opted into challenge');
      }
    } catch (error) {
      console.error('Error toggling challenge opt-in:', error);
      toast.error('Failed to update challenge participation');
    }
  };

  return (
    <ProfessionalCard className={`transition-all duration-200 hover:shadow-md ${isCompleted ? 'ring-2 ring-green-200 bg-green-50 dark:bg-green-900/10 dark:ring-green-900/30' : ''}`}>
      <ProfessionalCardHeader>
        <ProfessionalCardTitle className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <div className={`p-2 rounded-lg border ${typeColor}`}>
              <IconComponent className="h-4 w-4" />
            </div>
            <div>
              <h3 className="font-medium text-sm">{challenge.challenge.name}</h3>
              <p className="text-xs text-gray-600 capitalize">
                {challenge.challenge.challenge_type} Challenge
              </p>
            </div>
          </div>
          <div className="text-right">
            {isCompleted ? (
              <Badge variant="default" className="bg-green-100 text-green-800">
                <CheckCircle className="h-3 w-3 mr-1" />
                Completed
              </Badge>
            ) : (
              <Badge variant="outline" className={`text-xs ${typeColor}`}>
                {daysRemaining} days left
              </Badge>
            )}
          </div>
        </ProfessionalCardTitle>
      </ProfessionalCardHeader>
      <ProfessionalCardContent className="space-y-4">
        <p className="text-sm text-gray-600">
          {challenge.challenge.description}
        </p>

        {/* Progress */}
        {isOptedIn && !isCompleted && (
          <div className="space-y-2">
            <div className="flex justify-between text-sm">
              <span className="text-gray-600">Progress</span>
              <span className="font-medium">{progress}%</span>
            </div>
            <Progress value={progress} className="h-2" />
          </div>
        )}

        {/* Requirements */}
        <div className="space-y-2">
          <p className="text-xs font-medium text-gray-700">Requirements:</p>
          <div className="space-y-1">
            {challenge.challenge.requirements.map((req, index) => (
              <div key={index} className="flex items-center justify-between text-xs">
                <span className="text-gray-600">
                  {req.type.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())}
                </span>
                <span className="font-medium">
                  {req.target} {req.period && `per ${req.period}`}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Rewards */}
        {challenge.challenge.reward_xp > 0 && (
          <div className="flex items-center space-x-2 text-sm">
            <Star className="h-4 w-4 text-yellow-500" />
            <span className="text-gray-600">Reward:</span>
            <span className="font-medium text-blue-600">{challenge.challenge.reward_xp} XP</span>
          </div>
        )}

        {/* Time info */}
        <div className="flex items-center justify-between text-xs text-gray-500">
          <div className="flex items-center space-x-1">
            <Clock className="h-3 w-3" />
            <span>
              {challenge.challenge.start_date
                ? `Started ${new Date(challenge.challenge.start_date).toLocaleDateString()}`
                : `Duration: ${challenge.challenge.duration_days} days`
              }
            </span>
          </div>
          {challenge.completed_at && (
            <div className="flex items-center space-x-1 text-green-600">
              <CheckCircle className="h-3 w-3" />
              <span>Completed {new Date(challenge.completed_at).toLocaleDateString()}</span>
            </div>
          )}
        </div>

        {/* Action Button */}
        {!isCompleted && (
          <ProfessionalButton
            variant={isOptedIn ? "outline" : "default"}
            size="sm"
            onClick={handleOptToggle}
            className="w-full"
          >
            {isOptedIn ? (
              <>
                <XCircle className="h-4 w-4 mr-2" />
                Opt Out
              </>
            ) : (
              <>
                <Target className="h-4 w-4 mr-2" />
                Join Challenge
              </>
            )}
          </ProfessionalButton>
        )}
      </ProfessionalCardContent>
    </ProfessionalCard>
  );
}

interface ChallengeCardsProps {
  challenges?: UserChallenge[];
}

export function ChallengeCards({ challenges: propChallenges }: ChallengeCardsProps) {
  const { t } = useTranslation();
  const [myChallenges, setMyChallenges] = useState<UserChallenge[]>([]);
  const [availableChallenges, setAvailableChallenges] = useState<Challenge[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchChallenges = async () => {
      try {
        setLoading(true);
        setError(null);

        const [myData, availableData] = await Promise.all([
          gamificationApi.getMyChallenges(false, false), // Get all challenges
          gamificationApi.getAvailableChallenges()
        ]);

        setMyChallenges(myData);
        setAvailableChallenges(availableData);
      } catch (err) {
        console.error('Error fetching challenges:', err);
        setError(err instanceof Error ? err.message : 'Failed to load challenges');
      } finally {
        setLoading(false);
      }
    };

    if (!propChallenges) {
      fetchChallenges();
    } else {
      setMyChallenges(propChallenges);
      setLoading(false);
    }
  }, [propChallenges]);

  const handleOptIn = (challengeId: number) => {
    // Refresh challenges after opt-in
    if (!propChallenges) {
      // Only refresh if we're managing our own state
      const fetchUpdated = async () => {
        try {
          const updated = await gamificationApi.getMyChallenges(false, false);
          setMyChallenges(updated);
        } catch (err) {
          console.error('Error refreshing challenges:', err);
        }
      };
      fetchUpdated();
    }
  };

  const handleOptOut = (challengeId: number) => {
    // Refresh challenges after opt-out
    if (!propChallenges) {
      const fetchUpdated = async () => {
        try {
          const updated = await gamificationApi.getMyChallenges(false, false);
          setMyChallenges(updated);
        } catch (err) {
          console.error('Error refreshing challenges:', err);
        }
      };
      fetchUpdated();
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center p-8">
        <LoadingSpinner />
        <span className="ml-2">Loading challenges...</span>
      </div>
    );
  }

  if (error) {
    return (
      <ProfessionalCard variant="elevated" className="border-red-200 bg-red-50 dark:bg-red-900/10 dark:border-red-900/30">
        <ProfessionalCardContent className="p-6">
          <div className="flex items-center space-x-2 text-red-600 dark:text-red-400">
            <Target className="h-5 w-5" />
            <span className="font-medium">Error loading challenges</span>
          </div>
          <p className="text-red-600 dark:text-red-400 text-sm mt-2">{error}</p>
        </ProfessionalCardContent>
      </ProfessionalCard>
    );
  }

  const activeChallenges = myChallenges.filter(c => c.opted_in && !c.is_completed);
  const completedChallenges = myChallenges.filter(c => c.is_completed);

  return (
    <div className="space-y-6">
      <Tabs defaultValue="active" className="space-y-4">
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="active">
            Active ({activeChallenges.length})
          </TabsTrigger>
          <TabsTrigger value="available">
            Available ({availableChallenges.length})
          </TabsTrigger>
          <TabsTrigger value="completed">
            Completed ({completedChallenges.length})
          </TabsTrigger>
        </TabsList>

        <TabsContent value="active">
          {activeChallenges.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {activeChallenges.map((challenge) => (
                <ChallengeCard
                  key={challenge.id}
                  challenge={challenge}
                  onOptIn={handleOptIn}
                  onOptOut={handleOptOut}
                />
              ))}
            </div>
          ) : (
            <ProfessionalCard variant="minimal">
              <ProfessionalCardContent className="p-8 text-center">
                <Target className="h-12 w-12 mx-auto text-muted-foreground/30 mb-4" />
                <h3 className="text-lg font-semibold mb-2">{t('settings.gamification.challenges.no_active_challenges')}</h3>
                <p className="text-muted-foreground">
                  {t('settings.gamification.challenges.no_active_challenges_description')}
                </p>
              </ProfessionalCardContent>
            </ProfessionalCard>
          )}
        </TabsContent>

        <TabsContent value="available">
          {availableChallenges.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {availableChallenges.map((challenge) => {
                // Convert Challenge to UserChallenge format for display
                const userChallenge: UserChallenge = {
                  id: 0,
                  challenge,
                  progress: 0,
                  is_completed: false,
                  opted_in: false,
                  started_at: new Date().toISOString(),
                  milestones: [],
                  created_at: new Date().toISOString(),
                  updated_at: new Date().toISOString()
                };

                return (
                  <ChallengeCard
                    key={challenge.id}
                    challenge={userChallenge}
                    onOptIn={handleOptIn}
                    onOptOut={handleOptOut}
                  />
                );
              })}
            </div>
          ) : (
            <ProfessionalCard variant="minimal">
              <ProfessionalCardContent className="p-8 text-center">
                <Calendar className="h-12 w-12 mx-auto text-muted-foreground/30 mb-4" />
                <h3 className="text-lg font-semibold mb-2">{t('settings.gamification.challenges.no_available_challenges')}</h3>
                <p className="text-muted-foreground">
                  {t('settings.gamification.challenges.no_available_challenges_description')}
                </p>
              </ProfessionalCardContent>
            </ProfessionalCard>
          )}
        </TabsContent>

        <TabsContent value="completed">
          {completedChallenges.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {completedChallenges.map((challenge) => (
                <ChallengeCard
                  key={challenge.id}
                  challenge={challenge}
                  onOptIn={handleOptIn}
                  onOptOut={handleOptOut}
                />
              ))}
            </div>
          ) : (
            <ProfessionalCard variant="minimal">
              <ProfessionalCardContent className="p-8 text-center">
                <CheckCircle className="h-12 w-12 mx-auto text-muted-foreground/30 mb-4" />
                <h3 className="text-lg font-semibold mb-2">{t('settings.gamification.challenges.no_completed_challenges')}</h3>
                <p className="text-muted-foreground">
                  {t('settings.gamification.challenges.no_completed_challenges_description')}
                </p>
              </ProfessionalCardContent>
            </ProfessionalCard>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}