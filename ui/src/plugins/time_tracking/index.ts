/**
 * Time Tracking Plugin
 *
 * Self-contained plugin for project management and time tracking.
 */

// Plugin metadata
export const pluginMetadata = {
  name: 'time-tracking',
  displayName: 'Projects & Time Tracking',
  version: '1.0.0',
  licenseTier: 'agpl',
  description: 'Project management, time logging, timer, and monthly Excel export',
};

// Plugin routes configuration
export const pluginRoutes = [
  { path: '/projects', component: 'ProjectsList', label: 'Projects' },
  { path: '/projects/:id', component: 'ProjectDetail', label: 'Project Detail' },
  { path: '/time', component: 'MyTime', label: 'My Time' },
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
