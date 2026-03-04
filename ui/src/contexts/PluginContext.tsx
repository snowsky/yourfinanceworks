import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { apiRequest } from '@/lib/api';
import { loadPluginTranslations, unloadPluginTranslations } from '@/i18n';

export interface Plugin {
  id: string;
  name: string;
  description: string;
  icon: React.ReactNode;
  requiresLicense?: string;
  version?: string;
  author?: string;
  enabled: boolean;
  initializationError?: string;
  lastInitAttempt?: Date;
  category?: string;
  minAppVersion?: string;
  maxAppVersion?: string;
  dependencies?: string[];
  status?: 'active' | 'inactive' | 'error' | 'initializing' | 'disabled';
  lastUpdated?: Date;
  downloadCount?: number;
  rating?: number;
  homepage?: string;
  repository?: string;
  translationsLoaded?: boolean;
  translationError?: string;
}

interface PluginContextType {
  plugins: Plugin[];
  enabledPlugins: string[];
  togglePlugin: (pluginId: string, enabled: boolean, isAdmin?: boolean) => Promise<void>;
  isPluginEnabled: (pluginId: string) => boolean;
  getPlugin: (pluginId: string) => Plugin | undefined;
  loading: boolean;
  storageError: string | null;
  storageWarnings: string[];
  initializePlugin: (pluginId: string) => Promise<boolean>;
  getPluginInitializationStatus: (pluginId: string) => {
    isInitialized: boolean;
    error?: string;
    lastAttempt?: Date;
  };
  discoveryErrors: string[];
  refreshPluginDiscovery: () => Promise<void>;
  getStorageStats: () => {
    primaryExists: boolean;
    fallbackExists: boolean;
    integrityCheckPassed: boolean;
    version: string | null;
    quotaInfo: { used: number; available: number; percentage: number };
  };
}

// Plugin metadata validation
interface PluginMetadata {
  id: string;
  name: string;
  description: string;
  version?: string;
  author?: string;
  requiresLicense?: string;
  icon?: string;
  minAppVersion?: string;
  maxAppVersion?: string;
  dependencies?: string[];
  category?: string;
  lastUpdated?: string;
  downloadCount?: number;
  rating?: number;
  homepage?: string;
  repository?: string;
}

class PluginValidator {
  static validatePluginMetadata(metadata: any): { isValid: boolean; errors: string[]; plugin?: Plugin } {
    const errors: string[] = [];

    // Required fields validation
    if (!metadata.id || typeof metadata.id !== 'string') {
      errors.push('Plugin ID is required and must be a string');
    } else if (!/^[a-z0-9-]+$/.test(metadata.id)) {
      errors.push('Plugin ID must contain only lowercase letters, numbers, and hyphens');
    }

    if (!metadata.name || typeof metadata.name !== 'string') {
      errors.push('Plugin name is required and must be a string');
    } else if (metadata.name.length < 3 || metadata.name.length > 50) {
      errors.push('Plugin name must be between 3 and 50 characters');
    }

    if (!metadata.description || typeof metadata.description !== 'string') {
      errors.push('Plugin description is required and must be a string');
    } else if (metadata.description.length < 10 || metadata.description.length > 200) {
      errors.push('Plugin description must be between 10 and 200 characters');
    }

    // Optional fields validation
    if (metadata.version && (typeof metadata.version !== 'string' || !/^\d+\.\d+\.\d+$/.test(metadata.version))) {
      errors.push('Plugin version must be in semver format (e.g., 1.0.0)');
    }

    if (metadata.author && (typeof metadata.author !== 'string' || metadata.author.length > 50)) {
      errors.push('Plugin author must be a string with maximum 50 characters');
    }

    if (metadata.requiresLicense && !['commercial', 'enterprise', 'premium'].includes(metadata.requiresLicense)) {
      errors.push('Plugin requiresLicense must be one of: commercial, enterprise, premium');
    }

    if (metadata.dependencies && (!Array.isArray(metadata.dependencies) ||
        !metadata.dependencies.every(dep => typeof dep === 'string'))) {
      errors.push('Plugin dependencies must be an array of strings');
    }

    if (metadata.category && typeof metadata.category !== 'string') {
      errors.push('Plugin category must be a string');
    }

    const isValid = errors.length === 0;

    if (isValid) {
      const plugin: Plugin = {
        id: metadata.id,
        name: metadata.name,
        description: metadata.description,
        icon: metadata.icon || '🔌',
        requiresLicense: metadata.requiresLicense,
        version: metadata.version || '1.0.0',
        author: metadata.author || 'Unknown',
        enabled: false,
        category: metadata.category,
        minAppVersion: metadata.minAppVersion,
        maxAppVersion: metadata.maxAppVersion,
        dependencies: metadata.dependencies,
        status: 'inactive',
        lastUpdated: metadata.lastUpdated ? new Date(metadata.lastUpdated) : undefined,
        downloadCount: metadata.downloadCount,
        rating: metadata.rating,
        homepage: metadata.homepage,
        repository: metadata.repository
      };

      return { isValid: true, errors: [], plugin };
    }

    return { isValid: false, errors };
  }

  static validatePluginConfiguration(plugin: Plugin): { isValid: boolean; errors: string[] } {
    const errors: string[] = [];

    // Check for duplicate IDs (this would be called with the full plugin registry)
    // Additional configuration validation can be added here

    return { isValid: errors.length === 0, errors };
  }
}

// Plugin discovery system
class PluginDiscovery {
  private static readonly PLUGIN_REGISTRY_KEY = 'pluginRegistry';
  private static readonly DISCOVERY_CACHE_KEY = 'pluginDiscoveryCache';
  private static readonly CACHE_DURATION = 24 * 60 * 60 * 1000; // 24 hours

  static async discoverPlugins(): Promise<{ plugins: Plugin[]; errors: string[] }> {
    const errors: string[] = [];
    const discoveredPlugins: Plugin[] = [];

    try {
      // Clear old cache to ensure fresh discovery
      this.clearDiscoveryCache();

      // Built-in plugins registry
      const builtInPlugins = await this.getBuiltInPlugins();

      // Validate and add built-in plugins
      for (const pluginData of builtInPlugins) {
        const validation = PluginValidator.validatePluginMetadata(pluginData);
        if (validation.isValid && validation.plugin) {
          discoveredPlugins.push(validation.plugin);
        } else {
          errors.push(`Built-in plugin ${pluginData.id || 'unknown'}: ${validation.errors.join(', ')}`);
        }
      }

      // Try to discover external plugins (from API or filesystem)
      try {
        const externalPlugins = await this.discoverExternalPlugins();
        for (const pluginData of externalPlugins) {
          const validation = PluginValidator.validatePluginMetadata(pluginData);
          if (validation.isValid && validation.plugin) {
            // If the backend returns a plugin whose ID already exists in the
            // built-in list, silently prefer the built-in entry (it has richer
            // metadata: display name, icon, etc.).  This is the expected case
            // for the investments and time-tracking plugins.
            if (!discoveredPlugins.find(p => p.id === validation.plugin!.id)) {
              discoveredPlugins.push(validation.plugin);
            }
            // else: already covered by built-in; no error needed
          } else {
            errors.push(`External plugin ${pluginData.id || 'unknown'}: ${validation.errors.join(', ')}`);
          }
        }
      } catch (externalError) {
        console.warn('Failed to discover external plugins:', externalError);
        errors.push('Failed to discover external plugins - using built-in plugins only');
      }

      // Cache the results
      this.cacheDiscoveryResults({ plugins: discoveredPlugins, errors });

      console.log(`Discovered ${discoveredPlugins.length} plugins with ${errors.length} errors`);
      return { plugins: discoveredPlugins, errors };
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown discovery error';
      console.error('Plugin discovery failed:', errorMessage);
      errors.push(`Plugin discovery failed: ${errorMessage}`);

      // Return built-in plugins as fallback
      const fallbackPlugins = await this.getBuiltInPlugins();
      const validatedFallback: Plugin[] = [];

      for (const pluginData of fallbackPlugins) {
        const validation = PluginValidator.validatePluginMetadata(pluginData);
        if (validation.isValid && validation.plugin) {
          validatedFallback.push(validation.plugin);
        }
      }

      return { plugins: validatedFallback, errors };
    }
  }

  private static async getBuiltInPlugins(): Promise<PluginMetadata[]> {
    // Built-in plugins that are always available
    return [
      {
        id: 'investments',
        name: 'Investment Management',
        description: 'Track portfolios, holdings, transactions, and investment performance analytics',
        icon: '📈',
        version: '1.0.0',
        author: 'YourFinanceWORKS',
        category: 'finance',
        minAppVersion: '1.0.0',
        dependencies: [],
        lastUpdated: '2024-02-01',
        downloadCount: 1250,
        rating: 4.8,
        homepage: 'https://yourfinanceworks.com/plugins/investments',
        repository: 'https://github.com/yourfinanceworks/investment-plugin'
      },
      {
        id: 'time-tracking',
        name: 'Projects & Time Tracking',
        description: 'Manage projects, log time against tasks, run a live timer, and export monthly Excel reports',
        icon: '⏱️',
        version: '1.0.0',
        author: 'YourFinanceWORKS',
        category: 'productivity',
        minAppVersion: '1.0.0',
        dependencies: [],
        lastUpdated: '2026-03-02',
        downloadCount: 0,
        rating: 5.0,
      }
    ];
  }

  private static async discoverExternalPlugins(): Promise<PluginMetadata[]> {
    // Fetch plugin metadata from the backend registry endpoint.
    // The backend scans api/plugins/*/plugin.json at startup, so this list
    // is always in sync with what is actually installed on the server.
    //
    // ID normalisation: the backend plugin.json "name" field is used as the
    // slug, but some legacy manifests use a different slug than the frontend
    // built-in list.  This map translates backend names → canonical frontend IDs
    // so deduplication works correctly.
    const BACKEND_ID_ALIAS: Record<string, string> = {
      'investment-management': 'investments',
    };

    try {
      const { apiRequest } = await import('@/lib/api');
      const data = await apiRequest<{ plugins: any[] }>('/plugins/registry', { method: 'GET' });

      return (data.plugins || []).map((p: any): PluginMetadata => {
        const rawId = p.name as string;
        const id = BACKEND_ID_ALIAS[rawId] ?? rawId;   // normalise ID
        return {
          id,
          name: p.name,
          description: p.description || '',
          version: p.version,
          author: p.author,
          requiresLicense: p.license_tier === 'commercial' ? 'commercial' : undefined,
          category: p.metadata?.category,
          lastUpdated: p.metadata?.lastUpdated,
          homepage: p.metadata?.documentation_url,
          repository: p.metadata?.repository,
        };
      });
    } catch (err) {
      console.warn('Failed to fetch plugin registry from server, using built-in list as fallback:', err);
      return [];
    }
  }


  private static getCachedDiscovery(): { plugins: Plugin[]; errors: string[] } | null {
    if (!PluginStorage.isStorageAvailable()) {
      return null;
    }

    try {
      const cached = localStorage.getItem(this.DISCOVERY_CACHE_KEY);
      if (!cached) {
        return null;
      }

      const parsed = JSON.parse(cached);
      const cacheTime = new Date(parsed.timestamp);
      const now = new Date();

      if (now.getTime() - cacheTime.getTime() > this.CACHE_DURATION) {
        localStorage.removeItem(this.DISCOVERY_CACHE_KEY);
        return null;
      }

      return parsed.data;
    } catch (error) {
      console.warn('Failed to load cached plugin discovery:', error);
      return null;
    }
  }

  private static cacheDiscoveryResults(results: { plugins: Plugin[]; errors: string[] }): void {
    if (!PluginStorage.isStorageAvailable()) {
      return;
    }

    try {
      const cacheData = {
        timestamp: new Date().toISOString(),
        data: results
      };

      localStorage.setItem(this.DISCOVERY_CACHE_KEY, JSON.stringify(cacheData));
    } catch (error) {
      console.warn('Failed to cache plugin discovery results:', error);
    }
  }

  static clearDiscoveryCache(): void {
    if (PluginStorage.isStorageAvailable()) {
      localStorage.removeItem(this.DISCOVERY_CACHE_KEY);
    }
  }
}
class PluginStorage {
  private static readonly STORAGE_KEY = 'enabledPlugins';
  private static readonly FALLBACK_KEY = 'enabledPlugins_fallback';
  private static readonly INTEGRITY_KEY = 'enabledPlugins_checksum';
  private static readonly STORAGE_VERSION_KEY = 'enabledPlugins_version';
  private static readonly CURRENT_VERSION = '1.0';
  private static readonly MAX_STORAGE_SIZE = 5000000; // 5MB
  private static readonly MAX_PLUGIN_ID_LENGTH = 100;
  private static readonly MAX_RETRY_ATTEMPTS = 3;

  static isStorageAvailable(): boolean {
    try {
      const test = '__storage_test__';
      localStorage.setItem(test, test);
      localStorage.removeItem(test);
      return true;
    } catch {
      return false;
    }
  }

  static getStorageQuotaInfo(): { used: number; available: number; percentage: number } {
    if (!this.isStorageAvailable()) {
      return { used: 0, available: 0, percentage: 100 };
    }

    try {
      // Estimate storage usage by checking all localStorage items
      let totalSize = 0;
      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i);
        if (key) {
          const value = localStorage.getItem(key) || '';
          totalSize += key.length + value.length;
        }
      }

      // Most browsers have a 5-10MB limit for localStorage
      const estimatedLimit = 10 * 1024 * 1024; // 10MB estimate
      const available = Math.max(0, estimatedLimit - totalSize);
      const percentage = (totalSize / estimatedLimit) * 100;

      return {
        used: totalSize,
        available,
        percentage: Math.min(100, Math.max(0, percentage))
      };
    } catch (error) {
      console.warn('Failed to calculate storage quota:', error);
      return { used: 0, available: 0, percentage: 0 };
    }
  }

  static generateChecksum(data: string): string {
    // Simple checksum for data integrity validation
    let hash = 0;
    for (let i = 0; i < data.length; i++) {
      const char = data.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash = hash & hash; // Convert to 32-bit integer
    }
    return hash.toString(16);
  }

  static validatePluginData(data: any): { valid: string[]; invalid: any[]; errors: string[] } {
    const errors: string[] = [];
    const invalid: any[] = [];

    if (!Array.isArray(data)) {
      errors.push('Plugin data is not an array, resetting to empty array');
      return { valid: [], invalid: [data], errors };
    }

    const valid = data.filter(item => {
      if (typeof item !== 'string') {
        invalid.push(item);
        errors.push(`Invalid plugin ID type: ${typeof item}`);
        return false;
      }

      if (item.length === 0) {
        invalid.push(item);
        errors.push('Empty plugin ID found');
        return false;
      }

      if (item.length > this.MAX_PLUGIN_ID_LENGTH) {
        invalid.push(item);
        errors.push(`Plugin ID too long: ${item.substring(0, 20)}...`);
        return false;
      }

      // Validate plugin ID format (alphanumeric, hyphens, underscores)
      if (!/^[a-zA-Z0-9_-]+$/.test(item)) {
        invalid.push(item);
        errors.push(`Invalid plugin ID format: ${item}`);
        return false;
      }

      return true;
    });

    if (errors.length > 0) {
      console.warn('Plugin data validation issues:', errors);
    }

    return { valid, invalid, errors };
  }

  static validateDataIntegrity(data: string, expectedChecksum: string): boolean {
    const actualChecksum = this.generateChecksum(data);
    return actualChecksum === expectedChecksum;
  }

  static cleanupOldData(): void {
    if (!this.isStorageAvailable()) {
      return;
    }

    try {
      // Remove old cache entries that might be taking up space
      const keysToCheck = [
        'pluginDiscoveryCache',
        'enabledPlugins_backup',
        'plugin_cache_old',
        'plugin_temp'
      ];

      keysToCheck.forEach(key => {
        if (localStorage.getItem(key)) {
          localStorage.removeItem(key);
          console.log(`Cleaned up old storage key: ${key}`);
        }
      });
    } catch (error) {
      console.warn('Failed to cleanup old data:', error);
    }
  }

  static load(): { data: string[], error: string | null, warnings: string[] } {
    const warnings: string[] = [];

    if (!this.isStorageAvailable()) {
      console.warn('localStorage is not available, using in-memory storage');
      return {
        data: [],
        error: 'Storage not available - using in-memory mode',
        warnings: ['localStorage is not available']
      };
    }

    // Check storage quota
    const quotaInfo = this.getStorageQuotaInfo();
    if (quotaInfo.percentage > 90) {
      warnings.push(`Storage quota is ${quotaInfo.percentage.toFixed(1)}% full`);
      console.warn('Storage quota warning:', quotaInfo);
    }

    try {
      const stored = localStorage.getItem(this.STORAGE_KEY);
      if (!stored) {
        return { data: [], error: null, warnings };
      }

      // Check data integrity if checksum exists
      const storedChecksum = localStorage.getItem(this.INTEGRITY_KEY);
      if (storedChecksum && !this.validateDataIntegrity(stored, storedChecksum)) {
        warnings.push('Data integrity check failed, attempting fallback recovery');
        console.warn('Plugin data integrity check failed');

        // Try fallback storage
        return this.loadFromFallback(warnings);
      }

      // Check storage version compatibility
      const storedVersion = localStorage.getItem(this.STORAGE_VERSION_KEY);
      if (storedVersion && storedVersion !== this.CURRENT_VERSION) {
        warnings.push(`Storage version mismatch: ${storedVersion} vs ${this.CURRENT_VERSION}`);
        console.warn('Storage version mismatch, data migration may be needed');
      }

      const parsed = JSON.parse(stored);
      const validation = this.validatePluginData(parsed);

      if (validation.errors.length > 0) {
        warnings.push(...validation.errors);
      }

      return { data: validation.valid, error: null, warnings };
    } catch (error) {
      console.error('Failed to load plugin states from primary storage:', error);

      // Try fallback storage
      return this.loadFromFallback(warnings);
    }
  }

  private static loadFromFallback(existingWarnings: string[] = []): { data: string[], error: string | null, warnings: string[] } {
    const warnings = [...existingWarnings];

    try {
      const fallback = localStorage.getItem(this.FALLBACK_KEY);
      if (fallback) {
        const parsed = JSON.parse(fallback);
        const validation = this.validatePluginData(parsed);

        if (validation.errors.length > 0) {
          warnings.push(...validation.errors);
        }

        console.info('Loaded plugin states from fallback storage');
        return {
          data: validation.valid,
          error: 'Loaded from fallback storage due to primary storage corruption',
          warnings
        };
      }
    } catch (fallbackError) {
      console.error('Fallback storage also failed:', fallbackError);
      warnings.push('Fallback storage also failed');
    }

    return {
      data: [],
      error: 'Failed to load plugin states - using defaults',
      warnings
    };
  }

  static save(plugins: string[]): { success: boolean, error: string | null, warnings: string[] } {
    const warnings: string[] = [];

    if (!this.isStorageAvailable()) {
      return {
        success: false,
        error: 'Storage not available',
        warnings: ['localStorage is not available']
      };
    }

    // Check storage quota before attempting to save
    const quotaInfo = this.getStorageQuotaInfo();
    if (quotaInfo.percentage > 95) {
      warnings.push('Storage quota critically low, attempting cleanup');
      this.cleanupOldData();
    }

    const validation = this.validatePluginData(plugins);
    if (validation.errors.length > 0) {
      warnings.push(...validation.errors);
    }

    const dataToStore = JSON.stringify(validation.valid);
    const checksum = this.generateChecksum(dataToStore);

    // Check if data size is reasonable
    const estimatedSize = dataToStore.length * 2; // Account for UTF-16 encoding
    if (estimatedSize > this.MAX_STORAGE_SIZE) {
      return {
        success: false,
        error: 'Plugin data too large for storage',
        warnings
      };
    }

    // Attempt to save with retry logic
    for (let attempt = 1; attempt <= this.MAX_RETRY_ATTEMPTS; attempt++) {
      try {
        // Save main data
        localStorage.setItem(this.STORAGE_KEY, dataToStore);
        localStorage.setItem(this.INTEGRITY_KEY, checksum);
        localStorage.setItem(this.STORAGE_VERSION_KEY, this.CURRENT_VERSION);

        // Save to fallback location
        try {
          localStorage.setItem(this.FALLBACK_KEY, dataToStore);
        } catch (fallbackError) {
          warnings.push('Failed to save to fallback storage');
          console.warn('Failed to save to fallback storage:', fallbackError);
        }

        return { success: true, error: null, warnings };
      } catch (error) {
        console.error(`Save attempt ${attempt} failed:`, error);

        if (error instanceof DOMException && error.name === 'QuotaExceededError') {
          if (attempt < this.MAX_RETRY_ATTEMPTS) {
            // Try to free up space
            warnings.push(`Storage quota exceeded, attempting cleanup (attempt ${attempt})`);
            this.cleanupOldData();

            // Remove fallback to free space
            try {
              localStorage.removeItem(this.FALLBACK_KEY);
            } catch (cleanupError) {
              console.warn('Failed to cleanup fallback storage:', cleanupError);
            }

            continue; // Retry
          } else {
            return {
              success: false,
              error: 'Storage quota exceeded and cleanup failed',
              warnings
            };
          }
        }

        if (attempt === this.MAX_RETRY_ATTEMPTS) {
          return {
            success: false,
            error: `Failed to save plugin states after ${this.MAX_RETRY_ATTEMPTS} attempts`,
            warnings
          };
        }
      }
    }

    return {
      success: false,
      error: 'Unexpected error during save operation',
      warnings
    };
  }

  static getStorageStats(): {
    primaryExists: boolean;
    fallbackExists: boolean;
    integrityCheckPassed: boolean;
    version: string | null;
    quotaInfo: { used: number; available: number; percentage: number };
  } {
    if (!this.isStorageAvailable()) {
      return {
        primaryExists: false,
        fallbackExists: false,
        integrityCheckPassed: false,
        version: null,
        quotaInfo: { used: 0, available: 0, percentage: 100 }
      };
    }

    try {
      const primaryData = localStorage.getItem(this.STORAGE_KEY);
      const fallbackData = localStorage.getItem(this.FALLBACK_KEY);
      const checksum = localStorage.getItem(this.INTEGRITY_KEY);
      const version = localStorage.getItem(this.STORAGE_VERSION_KEY);

      let integrityCheckPassed = false;
      if (primaryData && checksum) {
        integrityCheckPassed = this.validateDataIntegrity(primaryData, checksum);
      }

      return {
        primaryExists: !!primaryData,
        fallbackExists: !!fallbackData,
        integrityCheckPassed,
        version,
        quotaInfo: this.getStorageQuotaInfo()
      };
    } catch (error) {
      console.warn('Failed to get storage stats:', error);
      return {
        primaryExists: false,
        fallbackExists: false,
        integrityCheckPassed: false,
        version: null,
        quotaInfo: { used: 0, available: 0, percentage: 0 }
      };
    }
  }
}

const PluginContext = createContext<PluginContextType | undefined>(undefined);

export const PluginProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [enabledPlugins, setEnabledPlugins] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [storageError, setStorageError] = useState<string | null>(null);
  const [storageWarnings, setStorageWarnings] = useState<string[]>([]);
  const [pluginInitializationErrors, setPluginInitializationErrors] = useState<Record<string, { error: string; lastAttempt: Date }>>({});
  const [discoveryErrors, setDiscoveryErrors] = useState<string[]>([]);

  // Available plugins registry - will be populated by discovery
  const [plugins, setPlugins] = useState<Plugin[]>([]);

  // Load enabled plugins from API on mount and initialize them
  useEffect(() => {
    const loadPluginStates = async () => {
      try {
        // First, discover available plugins
        console.log('Discovering available plugins...');
        const { plugins: discoveredPlugins, errors: discoveryErrors } = await PluginDiscovery.discoverPlugins();

        setPlugins(discoveredPlugins);
        setDiscoveryErrors(discoveryErrors);

        if (discoveryErrors.length > 0) {
          console.warn('Plugin discovery warnings:', discoveryErrors);
          window.dispatchEvent(new CustomEvent('plugin-discovery-warnings', {
            detail: { errors: discoveryErrors }
          }));
        }

        // Load enabled plugin states from API
        try {
          const data = await apiRequest<{
            tenant_id: number;
            enabled_plugins: string[];
            updated_at: string;
          }>('/plugins/settings', {
            method: 'GET'
          });

          const enabledPluginsFromApi = data.enabled_plugins || [];

          // Filter enabled plugins to only include discovered plugins
          const validEnabledPlugins = enabledPluginsFromApi.filter(pluginId =>
            discoveredPlugins.some(plugin => plugin.id === pluginId)
          );

          setEnabledPlugins(validEnabledPlugins);
          console.log('Loaded plugin settings from API:', validEnabledPlugins);

          // Initialize enabled plugins
          if (validEnabledPlugins.length > 0) {
            console.log('Initializing enabled plugins:', validEnabledPlugins);

            const initPromises = validEnabledPlugins.map(async (pluginId) => {
              try {
                await initializePluginWithRegistry(pluginId, discoveredPlugins);
              } catch (error) {
                console.error(`Failed to initialize plugin ${pluginId} on startup:`, error);
              }
            });

            await Promise.allSettled(initPromises);
          }
        } catch (apiError) {
          console.warn('Failed to load plugin settings from API, using empty list:', apiError);
          setEnabledPlugins([]);
          setStorageError('Failed to load plugin settings from server');

          window.dispatchEvent(new CustomEvent('plugin-storage-warning', {
            detail: { error: 'Failed to load plugin settings from server' }
          }));
        }
      } catch (error) {
        console.error('Failed to load plugin system:', error);
        setStorageError('Failed to initialize plugin system');

        window.dispatchEvent(new CustomEvent('plugin-storage-mode', {
          detail: {
            mode: 'disabled',
            reason: 'Plugin system initialization failed completely'
          }
        }));

        setPlugins([]);
        setEnabledPlugins([]);
      } finally {
        setLoading(false);
      }
    };

    loadPluginStates();
  }, []);

  // Plugin initialization function that uses a specific plugin registry
  const initializePluginWithRegistry = async (pluginId: string, pluginRegistry: Plugin[]): Promise<boolean> => {
    const plugin = pluginRegistry.find(p => p.id === pluginId);
    if (!plugin) {
      console.error(`Plugin with ID "${pluginId}" not found`);
      return false;
    }

    try {
      console.log(`Initializing plugin: ${plugin.name}`);

      // Set status to initializing
      setPlugins(prev => prev.map(p =>
        p.id === pluginId ? { ...p, status: 'initializing' as const } : p
      ));

      // Clear any previous initialization errors
      setPluginInitializationErrors(prev => {
        const updated = { ...prev };
        delete updated[pluginId];
        return updated;
      });

      // Simulate plugin initialization logic
      // In a real implementation, this would load plugin modules, register routes, etc.
      await new Promise(resolve => setTimeout(resolve, 100)); // Simulate async initialization

      // Plugin-specific initialization logic
      switch (pluginId) {
        case 'investments':
          // Validate that investment routes and components are available
          if (typeof window !== 'undefined') {
            // Check if investment-related modules can be loaded
            try {
              // This would be replaced with actual module loading logic
              console.log('Investment plugin initialized successfully');
            } catch (error) {
              throw new Error('Failed to load investment module components');
            }
          }
          break;
        default:
          console.log(`No specific initialization logic for plugin: ${pluginId}`);
      }

      // Set status to active
      setPlugins(prev => prev.map(p =>
        p.id === pluginId ? { ...p, status: 'active' as const } : p
      ));

      // Dispatch successful initialization event
      window.dispatchEvent(new CustomEvent('plugin-initialized', {
        detail: { pluginId, success: true }
      }));

      console.log(`Plugin ${plugin.name} initialized successfully`);
      return true;
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown initialization error';
      console.error(`Failed to initialize plugin ${plugin.name}:`, errorMessage);

      // Set status to error
      setPlugins(prev => prev.map(p =>
        p.id === pluginId ? { ...p, status: 'error' as const } : p
      ));

      // Store initialization error
      setPluginInitializationErrors(prev => ({
        ...prev,
        [pluginId]: {
          error: errorMessage,
          lastAttempt: new Date()
        }
      }));

      // Dispatch failed initialization event
      window.dispatchEvent(new CustomEvent('plugin-initialization-failed', {
        detail: { pluginId, error: errorMessage }
      }));

      // Automatically disable the plugin if initialization fails
      if (enabledPlugins.includes(pluginId)) {
        console.log(`Automatically disabling failed plugin: ${plugin.name}`);
        const updatedPlugins = enabledPlugins.filter(id => id !== pluginId);
        setEnabledPlugins(updatedPlugins);

        // Set status to disabled
        setPlugins(prev => prev.map(p =>
          p.id === pluginId ? { ...p, status: 'disabled' as const } : p
        ));

        // Persist the disabled state
        const { success } = PluginStorage.save(updatedPlugins);
        if (!success) {
          console.warn('Failed to persist plugin disable after initialization failure');
        }
      }

      return false;
    }
  };

  // Plugin initialization function
  const initializePlugin = async (pluginId: string): Promise<boolean> => {
    return initializePluginWithRegistry(pluginId, plugins);
  };

  // Get plugin initialization status
  const getPluginInitializationStatus = (pluginId: string) => {
    const initError = pluginInitializationErrors[pluginId];
    return {
      isInitialized: !initError && enabledPlugins.includes(pluginId),
      error: initError?.error,
      lastAttempt: initError?.lastAttempt
    };
  };

  // Refresh plugin discovery
  const refreshPluginDiscovery = async (): Promise<void> => {
    try {
      console.log('Refreshing plugin discovery...');

      // Clear discovery cache to force fresh discovery
      PluginDiscovery.clearDiscoveryCache();

      // Discover plugins again
      const { plugins: discoveredPlugins, errors: discoveryErrors } = await PluginDiscovery.discoverPlugins();

      setPlugins(discoveredPlugins);
      setDiscoveryErrors(discoveryErrors);

      // Filter enabled plugins to only include currently discovered plugins
      const validEnabledPlugins = enabledPlugins.filter(pluginId =>
        discoveredPlugins.some(plugin => plugin.id === pluginId)
      );

      // If some enabled plugins were filtered out, update storage and state
      if (validEnabledPlugins.length !== enabledPlugins.length) {
        const removedPlugins = enabledPlugins.filter(id => !validEnabledPlugins.includes(id));
        console.warn('Removing enabled plugins that are no longer available:', removedPlugins);
        setEnabledPlugins(validEnabledPlugins);
        PluginStorage.save(validEnabledPlugins);
      }

      // Dispatch refresh event
      window.dispatchEvent(new CustomEvent('plugin-discovery-refreshed', {
        detail: {
          pluginCount: discoveredPlugins.length,
          errors: discoveryErrors
        }
      }));

      console.log(`Plugin discovery refreshed: ${discoveredPlugins.length} plugins found`);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown refresh error';
      console.error('Failed to refresh plugin discovery:', errorMessage);
      setDiscoveryErrors([`Failed to refresh plugin discovery: ${errorMessage}`]);

      // Dispatch error event
      window.dispatchEvent(new CustomEvent('plugin-discovery-error', {
        detail: { error: errorMessage }
      }));
    }
  };

  const togglePlugin = async (pluginId: string, enabled: boolean, isAdmin: boolean = true): Promise<void> => {
    // Validate admin access
    if (!isAdmin) {
      throw new Error('Unauthorized: Only administrators can manage plugins');
    }

    // Validate plugin ID
    const plugin = plugins.find(p => p.id === pluginId);
    if (!plugin) {
      throw new Error(`Plugin with ID "${pluginId}" not found`);
    }

    // Validate license requirements when enabling a plugin
    if (enabled && plugin.requiresLicense) {
      console.log(`License validation for plugin ${pluginId} with requirement: ${plugin.requiresLicense}`);
    }

    try {
      // If enabling the plugin, try to initialize it first
      if (enabled) {
        const initSuccess = await initializePlugin(pluginId);
        if (!initSuccess) {
          throw new Error(`Failed to initialize plugin: ${plugin.name}`);
        }

        // Load plugin translations
        try {
          await loadPluginTranslations(pluginId);
          console.log(`Loaded translations for plugin: ${pluginId}`);
          // Update plugin translation status
          setPlugins(prev => prev.map(p =>
            p.id === pluginId
              ? { ...p, translationsLoaded: true, translationError: undefined }
              : p
          ));
        } catch (translationError) {
          console.warn(`Failed to load translations for plugin ${pluginId}:`, translationError);
          // Update plugin translation error status
          setPlugins(prev => prev.map(p =>
            p.id === pluginId
              ? { ...p, translationsLoaded: false, translationError: translationError instanceof Error ? translationError.message : 'Unknown translation error' }
              : p
          ));
          // Don't fail plugin enable if translations fail
        }
      } else {
        // Unload plugin translations when disabling
        try {
          unloadPluginTranslations(pluginId);
          console.log(`Unloaded translations for plugin: ${pluginId}`);
          // Update plugin translation status
          setPlugins(prev => prev.map(p =>
            p.id === pluginId
              ? { ...p, translationsLoaded: false, translationError: undefined }
              : p
          ));
        } catch (translationError) {
          console.warn(`Failed to unload translations for plugin ${pluginId}:`, translationError);
        }
      }

      const updatedPlugins = enabled
        ? [...enabledPlugins, pluginId]
        : enabledPlugins.filter(id => id !== pluginId);

      // Optimistically update state
      setEnabledPlugins(updatedPlugins);

      // Persist to API
      try {
        const endpoint = enabled
          ? `/plugins/settings/${pluginId}/enable`
          : `/plugins/settings/${pluginId}/disable`;

        const result = await apiRequest<{
          tenant_id: number;
          enabled_plugins: string[];
          message: string;
        }>(endpoint, {
          method: 'POST'
        });

        console.log(`Plugin ${pluginId} ${enabled ? 'enabled' : 'disabled'} successfully`);

        // Clear any previous storage errors on successful save
        if (storageError) {
          setStorageError(null);
        }

        // Dispatch event for other components to react to plugin changes
        window.dispatchEvent(new CustomEvent('plugin-toggled', {
          detail: { pluginId, enabled }
        }));
      } catch (apiError) {
        // Revert optimistic update on API failure
        setEnabledPlugins(enabledPlugins);
        const errorMessage = apiError instanceof Error ? apiError.message : 'Failed to save plugin state';
        setStorageError(errorMessage);

        // Dispatch storage error event
        window.dispatchEvent(new CustomEvent('plugin-storage-error', {
          detail: { error: errorMessage, pluginId, enabled }
        }));

        throw apiError;
      }
    } catch (error) {
      console.error('Failed to toggle plugin:', error);
      throw error;
    }
  };

  // Add event listeners for retry operations
  useEffect(() => {
    const handleStorageRetry = async () => {
      console.log('Retrying plugin storage operations...');

      // Attempt to reload plugin states
      try {
        const { data, error, warnings } = PluginStorage.load();

        if (!error) {
          setStorageError(null);
          setStorageWarnings(warnings);

          // Filter to valid plugins
          const validEnabledPlugins = data.filter(pluginId =>
            plugins.some(plugin => plugin.id === pluginId)
          );

          setEnabledPlugins(validEnabledPlugins);

          // Notify success
          window.dispatchEvent(new CustomEvent('plugin-storage-retry-success'));
        } else {
          // Still failing, keep current error state
          console.warn('Storage retry still failing:', error);
        }
      } catch (retryError) {
        console.error('Storage retry failed:', retryError);
      }
    };

    const handleDiscoveryRefresh = async () => {
      console.log('Refreshing plugin discovery...');
      try {
        await refreshPluginDiscovery();
      } catch (error) {
        console.error('Discovery refresh failed:', error);
      }
    };

    const handleRetryInitialization = async (event: CustomEvent) => {
      const { pluginId } = event.detail;
      console.log(`Retrying initialization for plugin: ${pluginId}`);

      try {
        const success = await initializePlugin(pluginId);
        if (success) {
          // Clear the initialization error
          setPluginInitializationErrors(prev => {
            const updated = { ...prev };
            delete updated[pluginId];
            return updated;
          });
        }
      } catch (error) {
        console.error(`Retry initialization failed for ${pluginId}:`, error);
      }
    };

    const handlePluginErrorDisable = async (event: CustomEvent) => {
      const { pluginId, reason } = event.detail;
      console.warn(`Disabling plugin ${pluginId} due to error: ${reason}`);

      if (enabledPlugins.includes(pluginId)) {
        try {
          // Disable the plugin
          await togglePlugin(pluginId, false, true);

          // Add to initialization errors to show the reason
          setPluginInitializationErrors(prev => ({
            ...prev,
            [pluginId]: {
              error: `Plugin disabled: ${reason}`,
              lastAttempt: new Date()
            }
          }));

          // Dispatch notification event
          window.dispatchEvent(new CustomEvent('plugin-auto-disabled', {
            detail: { pluginId, reason }
          }));
        } catch (error) {
          console.error(`Failed to auto-disable plugin ${pluginId}:`, error);
        }
      }
    };

    // Add event listeners
    window.addEventListener('plugin-storage-retry', handleStorageRetry);
    window.addEventListener('plugin-discovery-refresh', handleDiscoveryRefresh);
    window.addEventListener('plugin-retry-initialization', handleRetryInitialization as EventListener);
    window.addEventListener('plugin-error-disable', handlePluginErrorDisable as EventListener);

    return () => {
      window.removeEventListener('plugin-storage-retry', handleStorageRetry);
      window.removeEventListener('plugin-discovery-refresh', handleDiscoveryRefresh);
      window.removeEventListener('plugin-retry-initialization', handleRetryInitialization as EventListener);
      window.removeEventListener('plugin-error-disable', handlePluginErrorDisable as EventListener);
    };
  }, [plugins, enabledPlugins]);

  // Update plugins with enabled state and initialization errors
  const pluginsWithState = plugins.map(plugin => {
    const initError = pluginInitializationErrors[plugin.id];
    let status: Plugin['status'] = 'inactive';

    if (initError) {
      status = 'error';
    } else if (enabledPlugins.includes(plugin.id)) {
      status = 'active';
    } else {
      status = 'inactive';
    }

    return {
      ...plugin,
      enabled: enabledPlugins.includes(plugin.id),
      initializationError: initError?.error,
      lastInitAttempt: initError?.lastAttempt,
      status
    };
  });

  const isPluginEnabled = (pluginId: string): boolean => {
    return enabledPlugins.includes(pluginId);
  };

  const getPlugin = (pluginId: string): Plugin | undefined => {
    return pluginsWithState.find(plugin => plugin.id === pluginId);
  };

  const getStorageStats = () => {
    return PluginStorage.getStorageStats();
  };

  return (
    <PluginContext.Provider value={{
      plugins: pluginsWithState,
      enabledPlugins,
      togglePlugin,
      isPluginEnabled,
      getPlugin,
      loading,
      storageError,
      storageWarnings,
      initializePlugin,
      getPluginInitializationStatus,
      discoveryErrors,
      refreshPluginDiscovery,
      getStorageStats
    }}>
      {children}
    </PluginContext.Provider>
  );
};

export const usePlugins = (): PluginContextType => {
  const context = useContext(PluginContext);
  if (!context) {
    throw new Error('usePlugins must be used within PluginProvider');
  }
  return context;
};