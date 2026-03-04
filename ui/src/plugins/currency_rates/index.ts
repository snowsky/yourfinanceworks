/**
 * Currency Rates Plugin — Frontend Entry Point
 *
 * Declares the route config consumed by App.tsx via buildPluginElement().
 * This is the only file App.tsx needs to know about for this plugin.
 */

import React from 'react';
import type { PluginRouteConfig, PluginNavItem } from '@/types/plugin-routes';

export const pluginMetadata = {
  name: 'currency-rates',
  displayName: 'Currency Rates',
  version: '1.0.0',
  licenseTier: 'agpl',
  description: 'Live currency conversion powered by open.er-api.com, with offline fallback.',
};

const CurrencyRatesPage = React.lazy(() => import('@/pages/currency_rates/CurrencyRates'));

export const pluginRoutes: PluginRouteConfig[] = [
  {
    path: '/currency-rates',
    component: CurrencyRatesPage,
    pluginId: 'currency-rates',
    pluginName: 'Currency Rates',
    label: 'Currency Rates',
  },
];

// ---------------------------------------------------------------------------
// Sidebar nav item — auto-discovered by AppSidebar via import.meta.glob
// ---------------------------------------------------------------------------
export const navItems: PluginNavItem[] = [
  {
    id: 'currency-rates',
    path: '/currency-rates',
    label: 'Currency Rates',
    icon: 'DollarSign',
    priority: 3,
    tourId: 'nav-currency-rates',
  },
];

export const pluginFeatures = [
  'live-currency-rates',
  'currency-conversion',
  'offline-fallback',
];
