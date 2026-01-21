import { useState } from 'react';
import { ProfessionalButton } from '@/components/ui/professional-button';
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
import { Trophy, Settings, AlertTriangle, Info, CheckCircle2, Moon, Sparkles, TrendingUp } from 'lucide-react';
import { useGamification } from '@/hooks/useGamification';
import { useTranslation } from 'react-i18next';
import { DataRetentionPolicy, NotificationFrequency } from '@/types/gamification';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';

export function GamificationToggle() {
  const { t } = useTranslation();
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
        toast.success(t('settings.gamification.notifications.enabled_success'));
        // Refresh page to reload gamification state
        window.location.reload();
      } else {
        await disable({
          data_retention_policy: dataRetentionPolicy
        });
        toast.success(t('settings.gamification.notifications.disabled_success'));
        // Refresh page to reload gamification state
        window.location.reload();
      }
      setShowDialog(false);
    } catch (error) {
      console.error('Error toggling gamification:', error);
      toast.error(t('settings.gamification.notifications.toggle_error', { action: isEnabling ? 'enable' : 'disable' }));
    }
  };

  return (
    <>
      <div className="flex items-center gap-4 bg-muted/40 p-2 rounded-lg border border-border/50 shadow-sm">
        <div className="flex items-center gap-2 px-2">
          <div className={cn("p-1.5 rounded-full", isEnabled ? "bg-yellow-100 dark:bg-yellow-900/30 text-yellow-600 dark:text-yellow-400" : "bg-muted text-muted-foreground")}>
            <Trophy className="h-4 w-4" />
          </div>
          <span className="text-sm font-medium hidden sm:inline-block">{t('settings.gamification.title')}</span>
          <Badge variant={isEnabled ? "default" : "secondary"} className={cn("text-xs font-normal", isEnabled ? "bg-green-100 text-green-700 hover:bg-green-200 border-green-200" : "")}>
            {isEnabled ? t('settings.gamification.enabled') : t('settings.gamification.disabled')}
          </Badge>
        </div>
        <Switch
          checked={isEnabled}
          onCheckedChange={handleToggle}
          disabled={loading}
          className="data-[state=checked]:bg-green-600"
        />
      </div>

      <Dialog open={showDialog} onOpenChange={setShowDialog}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-xl">
              {isEnabling ? (
                <>
                  <div className="bg-yellow-100 p-2 rounded-full">
                    <Trophy className="h-5 w-5 text-yellow-600" />
                  </div>
                  <span>{t('settings.gamification.toggle_title')}</span>
                </>
              ) : (
                <>
                  <div className="bg-gray-100 p-2 rounded-full">
                    <Settings className="h-5 w-5 text-gray-500" />
                  </div>
                  <span>{t('settings.gamification.disable_title')}</span>
                </>
              )}
            </DialogTitle>
            <DialogDescription className="pt-2 text-base">
              {isEnabling ? t('settings.gamification.enable_description') : t('settings.gamification.disable_description')}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-6 py-4">
            {/* Data Retention Policy */}
            <div className="space-y-3">
              <Label htmlFor="retention-policy" className="text-sm font-medium text-foreground">
                {t('settings.gamification.data_retention_policy')}
              </Label>
              <Select
                value={dataRetentionPolicy}
                onValueChange={(value) => setDataRetentionPolicy(value as DataRetentionPolicy)}
              >
                <SelectTrigger className="w-full h-auto py-3">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={DataRetentionPolicy.PRESERVE} className="py-3">
                    <div className="space-y-1">
                      <div className="font-semibold flex items-center gap-2">
                        <CheckCircle2 className="w-4 h-4 text-green-600" />
                        {t('settings.gamification.preserve_data.label')}
                      </div>
                      <div className="text-xs text-muted-foreground pl-6">
                        {t('settings.gamification.preserve_data.description')}
                      </div>
                    </div>
                  </SelectItem>
                  <SelectItem value={DataRetentionPolicy.ARCHIVE} className="py-3">
                    <div className="space-y-1">
                      <div className="font-semibold flex items-center gap-2">
                        <Moon className="w-4 h-4 text-blue-600" />
                        {t('settings.gamification.archive_data.label')}
                      </div>
                      <div className="text-xs text-muted-foreground pl-6">
                        {t('settings.gamification.archive_data.description')}
                      </div>
                    </div>
                  </SelectItem>
                  <SelectItem value={DataRetentionPolicy.DELETE} className="py-3">
                    <div className="space-y-1">
                      <div className="font-semibold flex items-center gap-2 text-red-600">
                        <AlertTriangle className="w-4 h-4" />
                        {t('settings.gamification.delete_data.label')}
                      </div>
                      <div className="text-xs text-muted-foreground pl-6">
                        {t('settings.gamification.delete_data.description')}
                      </div>
                    </div>
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Warning for delete policy */}
            {dataRetentionPolicy === DataRetentionPolicy.DELETE && (
              <Alert variant="destructive">
                <AlertTriangle className="h-4 w-4" />
                <AlertTitle>{t('settings.gamification.warning')}</AlertTitle>
                <AlertDescription>
                  {t('settings.gamification.delete_warning')}
                </AlertDescription>
              </Alert>
            )}

            {/* Info about enabling */}
            {isEnabling && (
              <Alert className="bg-blue-50 border-blue-200 dark:bg-blue-900/10 dark:border-blue-800">
                <Sparkles className="h-4 w-4 text-blue-600 dark:text-blue-400" />
                <AlertTitle className="text-blue-800 dark:text-blue-300">{t('settings.gamification.what_you_get')}</AlertTitle>
                <AlertDescription className="text-blue-700 dark:text-blue-400 mt-2">
                  <ul className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-sm">
                    <li className="flex items-center gap-2">
                      <Trophy className="w-3 h-3" /> {t('settings.gamification.benefits.points')}
                    </li>
                    <li className="flex items-center gap-2">
                      <Sparkles className="w-3 h-3" /> {t('settings.gamification.benefits.achievements')}
                    </li>
                    <li className="flex items-center gap-2">
                      <TrendingUp className="w-3 h-3" /> {t('settings.gamification.benefits.streaks')}
                    </li>
                  </ul>
                </AlertDescription>
              </Alert>
            )}
          </div>

          <DialogFooter className="gap-2 sm:gap-0">
            <ProfessionalButton variant="ghost" onClick={() => setShowDialog(false)}>
              {t('common.cancel')}
            </ProfessionalButton>
            <ProfessionalButton
              variant={isEnabling ? "gradient" : "destructive"}
              onClick={handleConfirm}
              className={isEnabling ? "bg-gradient-to-r from-yellow-500 to-amber-600 hover:from-yellow-600 hover:to-amber-700 border-0" : ""}
            >
              {isEnabling ? t('settings.gamification.toggle_title') : t('settings.gamification.disable_title')}
            </ProfessionalButton>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

export default GamificationToggle;