import React from 'react';
import type { PluginNavItem, PluginRouteConfig } from '@/types/plugin-routes';

export const pluginMetadata = {
  name: 'docvault',
  displayName: 'DocVault',
  version: '1.0.0',
  licenseTier: 'commercial',
  description: 'Document and expiry manager with MFA-gated sensitive details.',
};

const DocVaultPage = React.lazy(() => import('./DocVault'));

export const pluginRoutes: PluginRouteConfig[] = [
  {
    path: '/docvault',
    component: DocVaultPage,
    pluginId: 'docvault',
    pluginName: 'DocVault',
    label: 'DocVault',
    requiresRole: ['admin', 'user'],
  },
];

export const navItems: PluginNavItem[] = [
  {
    id: 'docvault',
    path: '/docvault',
    label: 'DocVault',
    icon: 'LockKeyhole',
    priority: 3,
    tourId: 'nav-docvault',
  },
];

export const pluginFeatures = [
  'expiry-tracking',
  'ai-card-scanning',
  'mfa-gated-vault',
  'document-tags',
  'password-private-key-management',
];
