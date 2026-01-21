import React from 'react';
import { GamificationDashboard } from '@/components/gamification/GamificationDashboard';
import { useTranslation } from 'react-i18next';

interface GamificationTabProps {
  isAdmin?: boolean;
}

export const GamificationTab: React.FC<GamificationTabProps> = ({ isAdmin = false }) => {
  const { t } = useTranslation();

  return (
    // {/* Gamification Dashboard - Show only if enabled */}
    <div className="mt-8">
      <GamificationDashboard />
    </div>
  );
};

export default GamificationTab;
