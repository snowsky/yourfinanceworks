import React from 'react';
import { GamificationDashboard } from '@/components/gamification/GamificationDashboard';
import { useTranslation } from 'react-i18next';
import { Trophy } from 'lucide-react';

interface GamificationTabProps {
  isAdmin?: boolean;
}

export const GamificationTab: React.FC<GamificationTabProps> = ({ isAdmin = false }) => {
  const { t } = useTranslation();

  return (
    <div className="space-y-6">
      {/* Gradient Banner */}
      <div className="bg-gradient-to-r from-primary/10 via-primary/5 to-transparent rounded-2xl border border-primary/20 p-6 backdrop-blur-sm">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center flex-shrink-0">
            <Trophy className="w-6 h-6 text-primary" />
          </div>
          <div>
            <h2 className="text-2xl font-bold tracking-tight">{t('settings.tabs.gamification', 'Gamification')}</h2>
            <p className="text-muted-foreground mt-0.5">{t('settings.gamification.description', 'Track achievements, leaderboards, and team performance')}</p>
          </div>
        </div>
      </div>
      <GamificationDashboard />
    </div>
  );
};

export default GamificationTab;
