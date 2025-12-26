import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Trophy, Target, TrendingUp, Star, Award, Lock, RefreshCw, Info, Power } from 'lucide-react';
import { gamificationApi } from '@/lib/api';
import { LoadingSpinner } from '@/components/ui/loading-spinner';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { toast } from 'sonner';

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
  bronze: 'bg-amber-100 text-amber-800 border-amber-200',
  silver: 'bg-gray-100 text-gray-800 border-gray-200',
  gold: 'bg-yellow-100 text-yellow-800 border-yellow-200',
  platinum: 'bg-purple-100 text-purple-800 border-purple-200'
};

interface AchievementRule {
  achievement_id: string;
  name: string;
  description: string;
  category: string;
  difficulty: string;
  requirements: Array<{
    type: string;
    target: number;
    [key: string]: any;
  }>;
  reward_xp: number;
  reward_badge_url?: string;
  is_active: boolean;
}

interface AchievementRuleCardProps {
  rule: AchievementRule;
  onToggle: (achievementId: string, newStatus: boolean) => void;
  isToggling?: boolean;
}

function AchievementRuleCard({ rule, onToggle, isToggling = false }: AchievementRuleCardProps) {
  const IconComponent = categoryIcons[rule.category as keyof typeof categoryIcons] || Award;
  const iconColor = categoryColors[rule.category as keyof typeof categoryColors] || 'text-gray-500';
  const difficultyColor = difficultyColors[rule.difficulty as keyof typeof difficultyColors] || 'bg-gray-100 text-gray-800';
  
  const [isOpen, setIsOpen] = useState(false);

  const formatRequirement = (req: any) => {
    switch (req.type) {
      case 'expense_count':
        return `Track ${req.target} expense${req.target > 1 ? 's' : ''}`;
      case 'invoice_count':
        return `Create ${req.target} invoice${req.target > 1 ? 's' : ''}`;
      case 'receipt_count':
        return `Upload ${req.target} receipt${req.target > 1 ? 's' : ''}`;
      case 'streak_length':
        return `Maintain a ${req.target}-day streak`;
      case 'budget_review_count':
        return `Review budget ${req.target} time${req.target > 1 ? 's' : ''}`;
      case 'perfect_week':
        return `Complete ${req.target} perfect week${req.target > 1 ? 's' : ''}`;
      case 'financial_health_score':
        return `Achieve ${req.target} financial health score`;
      case 'total_xp':
        return `Earn ${req.target} total XP`;
      case 'level_reached':
        return `Reach level ${req.target}`;
      default:
        return `${req.type}: ${req.target}`;
    }
  };

  const handleToggle = async () => {
    const newStatus = !rule.is_active;
    onToggle(rule.achievement_id, newStatus);
  };

  return (
    <Card className={`transition-all duration-200 ${!rule.is_active ? 'opacity-60' : ''}`}>
      <Collapsible open={isOpen} onOpenChange={setIsOpen}>
        <CollapsibleTrigger asChild>
          <CardContent className="p-4 cursor-pointer hover:bg-gray-50">
            <div className="flex items-start space-x-3">
              <div className={`flex-shrink-0 p-2 rounded-lg ${rule.is_active ? 'bg-blue-100' : 'bg-gray-100'}`}>
                <IconComponent className={`h-6 w-6 ${iconColor}`} />
              </div>
              
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between mb-2">
                  <h3 className={`font-medium text-sm ${rule.is_active ? 'text-gray-900' : 'text-gray-500'}`}>
                    {rule.name}
                  </h3>
                  <div className="flex items-center space-x-2">
                    <Badge variant="outline" className={`text-xs border ${difficultyColor}`}>
                      {rule.difficulty}
                    </Badge>
                    <div className="flex items-center space-x-1">
                      <Switch
                        checked={rule.is_active}
                        onCheckedChange={handleToggle}
                        disabled={isToggling}
                      />
                    </div>
                  </div>
                </div>
                
                <p className="text-xs text-gray-600 mb-2 line-clamp-2">
                  {rule.description}
                </p>
                
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-3 text-xs text-gray-500">
                    <div className="flex items-center space-x-1">
                      <Star className="h-3 w-3" />
                      <span>{rule.reward_xp} XP</span>
                    </div>
                    <div className="flex items-center space-x-1">
                      <Target className="h-3 w-3" />
                      <span>{rule.requirements.length} requirement{rule.requirements.length > 1 ? 's' : ''}</span>
                    </div>
                    <div className="flex items-center space-x-1">
                      <Power className="h-3 w-3" />
                      <span>{rule.is_active ? 'Active' : 'Inactive'}</span>
                    </div>
                  </div>
                  <Button variant="ghost" size="sm" className="h-6 w-6 p-0">
                    <Info className={`h-4 w-4 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
                  </Button>
                </div>
              </div>
            </div>
          </CardContent>
        </CollapsibleTrigger>
        
        <CollapsibleContent>
          <CardContent className="px-4 pb-4 pt-0">
            <div className="ml-9 space-y-2">
              <div className="text-sm font-medium text-gray-700 mb-2">Requirements:</div>
              {rule.requirements.map((req, index) => (
                <div key={index} className="flex items-center space-x-2 text-sm text-gray-600 bg-gray-50 rounded p-2">
                  <div className="w-2 h-2 bg-blue-500 rounded-full flex-shrink-0"></div>
                  <span>{formatRequirement(req)}</span>
                </div>
              ))}
              {rule.reward_badge_url && (
                <div className="text-xs text-gray-500 mt-2">
                  <Badge variant="outline" className="text-xs">
                    Badge: {rule.reward_badge_url.split('/').pop()}
                  </Badge>
                </div>
              )}
            </div>
          </CardContent>
        </CollapsibleContent>
      </Collapsible>
    </Card>
  );
}

export function AchievementRules() {
  const [rules, setRules] = useState<AchievementRule[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [refreshing, setRefreshing] = useState(false);
  const [toggling, setToggling] = useState<string | null>(null);

  const fetchRules = async () => {
    try {
      setLoading(true);
      setError(null);

      const response = await gamificationApi.getAchievementRules();
      setRules(response.rules || []);
    } catch (err) {
      console.error('Error fetching achievement rules:', err);
      setError(err instanceof Error ? err.message : 'Failed to load achievement rules');
    } finally {
      setLoading(false);
    }
  };

  const handleToggleRule = async (achievementId: string, newStatus: boolean) => {
    try {
      setToggling(achievementId);
      
      const result = await gamificationApi.toggleAchievementRule(achievementId);
      
      // Update local state
      setRules(prevRules => 
        prevRules.map(rule => 
          rule.achievement_id === achievementId 
            ? { ...rule, is_active: result.is_active }
            : rule
        )
      );
      
      toast.success(result.message);
    } catch (err) {
      console.error('Error toggling achievement rule:', err);
      toast.error(err instanceof Error ? err.message : 'Failed to toggle achievement rule');
      
      // Revert the change in local state
      setRules(prevRules => 
        prevRules.map(rule => 
          rule.achievement_id === achievementId 
            ? { ...rule, is_active: !newStatus }
            : rule
        )
      );
    } finally {
      setToggling(null);
    }
  };

  const handleRefresh = async () => {
    try {
      setRefreshing(true);
      const response = await gamificationApi.getAchievementRules();
      setRules(response.rules || []);
    } catch (err) {
      console.error('Error refreshing achievement rules:', err);
    } finally {
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchRules();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center p-8">
        <LoadingSpinner />
        <span className="ml-2">Loading achievement rules...</span>
      </div>
    );
  }

  if (error) {
    return (
      <Card className="border-red-200 bg-red-50">
        <CardContent className="p-6">
          <div className="flex items-center space-x-2 text-red-600">
            <Trophy className="h-5 w-5" />
            <span className="font-medium">Error loading achievement rules</span>
          </div>
          <p className="text-red-600 text-sm mt-2">{error}</p>
        </CardContent>
      </Card>
    );
  }

  const categories = [
    { id: 'all', name: 'All Rules', icon: Award },
    { id: 'expense_tracking', name: 'Expense Tracking', icon: Target },
    { id: 'invoice_management', name: 'Invoice Management', icon: TrendingUp },
    { id: 'habit_formation', name: 'Habit Formation', icon: Star },
    { id: 'financial_health', name: 'Financial Health', icon: Trophy },
    { id: 'exploration', name: 'Exploration', icon: Award }
  ];

  const filteredRules = selectedCategory === 'all' 
    ? rules 
    : rules.filter(r => r.category === selectedCategory);

  const activeRulesCount = filteredRules.filter(r => r.is_active).length;
  const totalCount = filteredRules.length;

  return (
    <div className="space-y-6">
      {/* Header with Info */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <Trophy className="h-5 w-5 text-purple-500" />
              <span>Achievement Rules</span>
            </div>
            <div className="flex items-center space-x-2">
              <Badge variant="outline" className="text-sm">
                {activeRulesCount} / {totalCount} Active
              </Badge>
              <Button
                variant="ghost"
                size="sm"
                onClick={handleRefresh}
                disabled={refreshing}
                className="h-8 w-8 p-0"
              >
                <RefreshCw className={`h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
              </Button>
            </div>
          </CardTitle>
          <CardDescription>
            View all achievement rules and their requirements. These rules define how users can unlock achievements and earn XP.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            <div className="flex justify-between text-sm">
              <span className="text-gray-600">Active Rules</span>
              <span className="font-medium">{totalCount > 0 ? Math.round((activeRulesCount / totalCount) * 100) : 0}%</span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div 
                className="bg-green-600 h-2 rounded-full transition-all duration-300" 
                style={{ width: `${totalCount > 0 ? (activeRulesCount / totalCount) * 100 : 0}%` }}
              ></div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Category Tabs */}
      <Tabs value={selectedCategory} onValueChange={setSelectedCategory}>
        <TabsList className="grid w-full grid-cols-3 lg:grid-cols-6">
          {categories.map((category) => {
            const IconComponent = category.icon;
            return (
              <TabsTrigger key={category.id} value={category.id} className="text-xs">
                <IconComponent className="h-4 w-4 mr-1" />
                <span className="hidden sm:inline">{category.name}</span>
              </TabsTrigger>
            );
          })}
        </TabsList>

        {categories.map((category) => (
          <TabsContent key={category.id} value={category.id}>
            {filteredRules.length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {filteredRules.map((rule) => (
                  <AchievementRuleCard 
                    key={rule.achievement_id} 
                    rule={rule} 
                    onToggle={handleToggleRule}
                    isToggling={toggling === rule.achievement_id}
                  />
                ))}
              </div>
            ) : (
              <Card>
                <CardContent className="p-8 text-center">
                  <Lock className="h-12 w-12 mx-auto text-gray-400 mb-4" />
                  <h3 className="text-lg font-semibold mb-2">No Rules Found</h3>
                  <p className="text-gray-600">
                    No achievement rules found in this category.
                  </p>
                </CardContent>
              </Card>
            )}
          </TabsContent>
        ))}
      </Tabs>
    </div>
  );
}
