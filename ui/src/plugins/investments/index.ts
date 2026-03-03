/**
 * Investment Management Plugin
 *
 * This plugin provides comprehensive investment portfolio management capabilities
 * including holdings tracking, performance analytics, and tax reporting.
 */

import React from 'react';
import type { PluginRouteConfig } from '@/types/plugin-routes';

// ---------------------------------------------------------------------------
// Page exports (re-exported for use by other parts of the app if needed)
// ---------------------------------------------------------------------------
export { default as InvestmentDashboard } from '@/pages/investments/InvestmentDashboard';
export { default as CreatePortfolio } from '@/pages/investments/CreatePortfolio';
export { default as PortfolioDetail } from '@/pages/investments/PortfolioDetail';

// Component exports
export { default as HoldingsList } from '@/components/investments/HoldingsList';
export { default as CreateHoldingDialog } from '@/components/investments/CreateHoldingDialog';
export { default as EditHoldingDialog } from '@/components/investments/EditHoldingDialog';

// ---------------------------------------------------------------------------
// Plugin metadata
// ---------------------------------------------------------------------------
export const pluginMetadata = {
  name: 'investments',
  displayName: 'Investment Management',
  version: '1.0.0',
  licenseTier: 'commercial',
  description: 'Comprehensive investment portfolio management with holdings tracking, performance analytics, and tax reporting',
};

// ---------------------------------------------------------------------------
// Lazy page components (used by pluginRoutes below)
// ---------------------------------------------------------------------------
const InvestmentDashboardPage = React.lazy(() => import('@/pages/investments/InvestmentDashboard'));
const CreatePortfolioPage = React.lazy(() => import('@/pages/investments/CreatePortfolio'));
const PortfolioDetailPage = React.lazy(() => import('@/pages/investments/PortfolioDetail'));
const PortfolioPerformancePage = React.lazy(() => import('@/pages/investments/PortfolioPerformance'));
const InvestmentAnalyticsPage = React.lazy(() => import('@/pages/investments/InvestmentAnalytics'));
const TaxExportPage = React.lazy(() => import('@/pages/investments/TaxExport'));
const RebalancingToolPage = React.lazy(() => import('@/pages/investments/RebalancingTool'));
const CrossPortfolioAnalysisPage = React.lazy(() => import('@/pages/investments/CrossPortfolioAnalysis'));

// ---------------------------------------------------------------------------
// Route configuration — consumed by <PluginRoutes> in App.tsx
// ---------------------------------------------------------------------------
export const pluginRoutes: PluginRouteConfig[] = [
  {
    path: '/investments',
    component: InvestmentDashboardPage,
    pluginId: 'investments',
    pluginName: 'Investment Management',
    label: 'Investment Dashboard',
  },
  {
    path: '/investments/portfolio/new',
    component: CreatePortfolioPage,
    pluginId: 'investments',
    pluginName: 'Investment Management',
    label: 'Create Portfolio',
    requiresRole: ['admin', 'user'],
  },
  {
    path: '/investments/portfolio/:id',
    component: PortfolioDetailPage,
    pluginId: 'investments',
    pluginName: 'Investment Management',
    label: 'Portfolio Details',
  },
  {
    path: '/investments/portfolio/:id/performance',
    component: PortfolioPerformancePage,
    pluginId: 'investments',
    pluginName: 'Investment Management',
    label: 'Portfolio Performance',
  },
  {
    path: '/investments/portfolio/:id/rebalance',
    component: RebalancingToolPage,
    pluginId: 'investments',
    pluginName: 'Investment Management',
    label: 'Rebalancing Tool',
  },
  {
    path: '/investments/analytics',
    component: InvestmentAnalyticsPage,
    pluginId: 'investments',
    pluginName: 'Investment Management',
    label: 'Investment Analytics',
  },
  {
    path: '/investments/tax-export',
    component: TaxExportPage,
    pluginId: 'investments',
    pluginName: 'Investment Management',
    label: 'Tax Export',
  },
  {
    path: '/investments/cross-portfolio',
    component: CrossPortfolioAnalysisPage,
    pluginId: 'investments',
    pluginName: 'Investment Management',
    label: 'Cross-Portfolio Analysis',
  },
];

// ---------------------------------------------------------------------------
// Plugin features & permissions
// ---------------------------------------------------------------------------
export const pluginFeatures = [
  'portfolio-management',
  'holdings-tracking',
  'transaction-recording',
  'performance-analytics',
  'asset-allocation',
  'dividend-tracking',
  'tax-reporting',
  'price-management',
];

export const pluginPermissions = [
  'investments:read',
  'investments:create',
  'investments:update',
  'investments:delete',
];

