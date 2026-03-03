/**
 * Time Tracking Plugin
 *
 * Self-contained plugin for project management and time tracking.
 */

import React from 'react';
import type { PluginRouteConfig } from '@/types/plugin-routes';

// Plugin metadata
export const pluginMetadata = {
  name: 'time-tracking',
  displayName: 'Projects & Time Tracking',
  version: '1.0.0',
  licenseTier: 'agpl',
  description: 'Project management, time logging, timer, and monthly Excel export',
};

// ---------------------------------------------------------------------------
// Lazy page components
// ---------------------------------------------------------------------------
const TimeTrackingPage = React.lazy(() => import('@/pages/projects/TimeTracking'));
const ProjectDetailPage = React.lazy(() => import('@/pages/projects/ProjectDetail'));

// ---------------------------------------------------------------------------
// Route configuration — consumed by <PluginRoutes> in App.tsx
// ---------------------------------------------------------------------------
export const pluginRoutes: PluginRouteConfig[] = [
  {
    path: '/time-tracking',
    component: TimeTrackingPage,
    pluginId: 'time-tracking',
    pluginName: 'Projects & Time Tracking',
    label: 'Time Tracking',
    errorBoundary: false,
  },
  {
    path: '/projects/:id',
    component: ProjectDetailPage,
    pluginId: 'time-tracking',
    pluginName: 'Projects & Time Tracking',
    label: 'Project Detail',
    requiresRole: ['admin', 'user'],
    errorBoundary: false,
  },
];

// Plugin features
export const pluginFeatures = [
  'project-management',
  'task-management',
  'time-logging',
  'live-timer',
  'expense-tagging',
  'invoice-generation',
  'monthly-excel-export',
  'profitability-summary',
];

