import React from 'react';
import { GamificationDashboard } from '@/components/gamification/GamificationDashboard';
interface GamificationTabProps {
  isAdmin?: boolean;
}

export const GamificationTab: React.FC<GamificationTabProps> = () => {
  return <GamificationDashboard />;
};

export default GamificationTab;
