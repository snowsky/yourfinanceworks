import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { Badge } from '@/components/ui/badge';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Label } from '@/components/ui/label';
import { Trophy, Settings, AlertTriangle, Info } from 'lucide-react';
import { useGamification } from '@/hooks/useGamification';
import { DataRetentionPolicy, NotificationFrequency } from '@/types/gamification';
import { toast } from 'sonner';

export function GamificationToggle() {
  const { isEnabled, loading, enable, disable } = useGamification();
  const [showDialog, setShowDialog] = useState(false);
  const [isEnabling, setIsEnabling] = useState(false);
  const [dataRetentionPolicy, setDataRetentionPolicy] = useState<DataRetentionPolicy>(DataRetentionPolicy.PRESERVE);

  const handleToggle = async (enabled: boolean) => {
    if (enabled) {
      setIsEnabling(true);
      setShowDialog(true);
    } else {
      setIsEnabling(false);
      setShowDialog(true);
    }
  };

  const handleConfirm = async () => {
    try {
      if (isEnabling) {
        await enable({
          data_retention_policy: dataRetentionPolicy,
          preferences: {
            features: {
              points: true,
              achievements: true,
              streaks: true,
              challenges: true,
              social: false,
              notifications: true
            },
            privacy: {
              shareAchievements: false,
              showOnLeaderboard: false,
              allowFriendRequests: false
            },
            notifications: {
              streakReminders: true,
              achievementCelebrations: true,
              challengeUpdates: true,
              frequency: NotificationFrequency.DAILY
            }
          }
        });
        toast.success('Gamification enabled! Start earning points for your financial activities.');
        // Refresh page to reload gamification state
        window.location.reload();
      } else {
        await disable({
          data_retention_policy: dataRetentionPolicy
        });
        toast.success('Gamification disabled. Your financial app will work normally.');
        // Refresh page to reload gamification state
        window.location.reload();
      }
      setShowDialog(false);
    } catch (error) {
      console.error('Error toggling gamification:', error);
      toast.error(`Failed to ${isEnabling ? 'enable' : 'disable'} gamification`);
    }
  };

  return (
    <>
      <div className="flex items-center space-x-3">
        <div className="flex items-center space-x-2">
          <Trophy className="h-4 w-4 text-yellow-500" />
          <span className="text-sm font-medium">Gamification</span>
          <Badge variant={isEnabled ? "default" : "secondary"} className="text-xs">
            {isEnabled ? 'Enabled' : 'Disabled'}
          </Badge>
        </div>
        <Switch
          checked={isEnabled}
          onCheckedChange={handleToggle}
          disabled={loading}
        />
      </div>

      <Dialog open={showDialog} onOpenChange={setShowDialog}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center space-x-2">
              {isEnabling ? (
                <>
                  <Trophy className="h-5 w-5 text-yellow-500" />
                  <span>Enable Gamification</span>
                </>
              ) : (
                <>
                  <Settings className="h-5 w-5 text-gray-500" />
                  <span>Disable Gamification</span>
                </>
              )}
            </DialogTitle>
            <DialogDescription>
              {isEnabling ? (
                <>
                  Transform your financial management into an engaging experience with points, 
                  achievements, streaks, and challenges. You can disable this at any time.
                </>
              ) : (
                <>
                  This will disable all gamification features. Your financial app will continue 
                  to work normally without any game elements.
                </>
              )}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            {/* Data Retention Policy */}
            <div className="space-y-2">
              <Label htmlFor="retention-policy">Data Retention Policy</Label>
              <Select
                value={dataRetentionPolicy}
                onValueChange={(value) => setDataRetentionPolicy(value as DataRetentionPolicy)}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={DataRetentionPolicy.PRESERVE}>
                    <div className="space-y-1">
                      <div className="font-medium">Preserve Data</div>
                      <div className="text-xs text-gray-600">
                        Keep all progress and restore when re-enabled
                      </div>
                    </div>
                  </SelectItem>
                  <SelectItem value={DataRetentionPolicy.ARCHIVE}>
                    <div className="space-y-1">
                      <div className="font-medium">Archive Data</div>
                      <div className="text-xs text-gray-600">
                        Archive progress, can be restored later
                      </div>
                    </div>
                  </SelectItem>
                  <SelectItem value={DataRetentionPolicy.DELETE}>
                    <div className="space-y-1">
                      <div className="font-medium">Delete Data</div>
                      <div className="text-xs text-gray-600">
                        Permanently delete all gamification data
                      </div>
                    </div>
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Warning for delete policy */}
            {dataRetentionPolicy === DataRetentionPolicy.DELETE && (
              <div className="flex items-start space-x-2 p-3 bg-red-50 border border-red-200 rounded-lg">
                <AlertTriangle className="h-4 w-4 text-red-500 mt-0.5" />
                <div className="text-sm">
                  <p className="font-medium text-red-800">Warning</p>
                  <p className="text-red-600">
                    This will permanently delete all your points, achievements, streaks, and progress. 
                    This action cannot be undone.
                  </p>
                </div>
              </div>
            )}

            {/* Info about enabling */}
            {isEnabling && (
              <div className="flex items-start space-x-2 p-3 bg-blue-50 border border-blue-200 rounded-lg">
                <Info className="h-4 w-4 text-blue-500 mt-0.5" />
                <div className="text-sm">
                  <p className="font-medium text-blue-800">What you'll get:</p>
                  <ul className="text-blue-600 mt-1 space-y-1">
                    <li>• Earn points for financial activities</li>
                    <li>• Unlock achievements and badges</li>
                    <li>• Build streaks for consistent habits</li>
                    <li>• Join challenges to improve skills</li>
                    <li>• Track your financial health score</li>
                  </ul>
                </div>
              </div>
            )}
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setShowDialog(false)}>
              Cancel
            </Button>
            <Button onClick={handleConfirm}>
              {isEnabling ? 'Enable Gamification' : 'Disable Gamification'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}