import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';
import { PluginProvider, usePlugins } from '../PluginContext';
import { apiRequest } from '@/lib/api';

// Mock apiRequest
vi.mock('@/lib/api', () => ({
  apiRequest: vi.fn(),
}));

// Test component to access the context
const TestComponent = () => {
  const {
    plugins,
    enabledPlugins,
    togglePlugin,
    isPluginEnabled,
    loading,
    storageError,
    storageWarnings,
    discoveryErrors,
    initializePlugin,
    getPluginInitializationStatus,
    getStorageStats
  } = usePlugins();

  if (loading) {
    return <div>Loading...</div>;
  }

  const storageStats = getStorageStats();

  return (
    <div>
      <div data-testid="plugin-count">{plugins.length}</div>
      <div data-testid="enabled-count">{enabledPlugins.length}</div>
      <div data-testid="storage-error">{storageError || 'none'}</div>
      <div data-testid="storage-warnings">{storageWarnings.length}</div>
      <div data-testid="discovery-errors">{discoveryErrors.length}</div>
      <div data-testid="storage-quota-percentage">{storageStats.quotaInfo.percentage.toFixed(1)}</div>
      <div data-testid="storage-integrity-check">{storageStats.integrityCheckPassed.toString()}</div>
      <div data-testid="storage-primary-exists">{storageStats.primaryExists.toString()}</div>
      <div data-testid="storage-fallback-exists">{storageStats.fallbackExists.toString()}</div>
      {plugins.map(plugin => (
        <div key={plugin.id}>
          <span data-testid={`plugin-${plugin.id}`}>{plugin.name}</span>
          <span data-testid={`plugin-${plugin.id}-enabled`}>{plugin.enabled.toString()}</span>
          <span data-testid={`plugin-${plugin.id}-init-error`}>
            {plugin.initializationError || 'none'}
          </span>
          <button
            data-testid={`toggle-${plugin.id}`}
            onClick={() => togglePlugin(plugin.id, !plugin.enabled)}
          >
            Toggle {plugin.name}
          </button>
          <button
            data-testid={`init-${plugin.id}`}
            onClick={() => initializePlugin(plugin.id)}
          >
            Initialize {plugin.name}
          </button>
        </div>
      ))}
      <div data-testid="investments-enabled">{isPluginEnabled('investments').toString()}</div>
      <div data-testid="investments-init-status">
        {JSON.stringify(getPluginInitializationStatus('investments'))}
      </div>
    </div>
  );
};

describe('PluginContext', () => {
  let mockLocalStorage: any;

  beforeEach(() => {
    // Mock localStorage
    mockLocalStorage = {
      getItem: vi.fn(),
      setItem: vi.fn(),
      removeItem: vi.fn(),
      clear: vi.fn(),
    };
    Object.defineProperty(window, 'localStorage', {
      value: mockLocalStorage,
      writable: true,
    });

    // Mock window.dispatchEvent
    vi.spyOn(window, 'dispatchEvent').mockImplementation(() => true);

    // Default apiRequest mock
    (apiRequest as any).mockImplementation((path: string) => {
      if (path === '/plugins/registry') return Promise.resolve({ plugins: [] });
      if (path === '/plugins/settings') return Promise.resolve({ enabled_plugins: [] });
      return Promise.resolve({});
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('should load plugins from registry', async () => {
    mockLocalStorage.getItem.mockReturnValue(null);
    (apiRequest as any).mockImplementation((path: string) => {
      if (path === '/plugins/registry') return Promise.resolve({ plugins: [] });
      if (path === '/plugins/settings') return Promise.resolve({ enabled_plugins: [] });
      return Promise.resolve({});
    });

    render(
      <PluginProvider>
        <TestComponent />
      </PluginProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('plugin-count')).toHaveTextContent('2'); // Investments and Time Tracking are built-in
    });

    expect(screen.getByTestId('plugin-investments')).toHaveTextContent('Investment Management');
    expect(screen.getByTestId('plugin-investments-enabled')).toHaveTextContent('false');
    expect(screen.getByTestId('investments-enabled')).toHaveTextContent('false');
  });

  it('should load enabled plugins from API', async () => {
    (apiRequest as any).mockImplementation((path: string) => {
      if (path === '/plugins/registry') return Promise.resolve({ plugins: [] });
      if (path === '/plugins/settings') return Promise.resolve({ enabled_plugins: ['investments'] });
      return Promise.resolve({});
    });

    render(
      <PluginProvider>
        <TestComponent />
      </PluginProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('plugin-investments-enabled')).toHaveTextContent('true');
    });

    expect(screen.getByTestId('enabled-count')).toHaveTextContent('1');
    expect(screen.getByTestId('investments-enabled')).toHaveTextContent('true');
  });

  it('should handle API errors gracefully during startup', async () => {
    (apiRequest as any).mockImplementation((path: string) => {
      if (path === '/plugins/registry') return Promise.resolve({ plugins: [] });
      if (path === '/plugins/settings') return Promise.reject(new Error('API error'));
      return Promise.resolve({});
    });

    render(
      <PluginProvider>
        <TestComponent />
      </PluginProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('plugin-count')).toHaveTextContent('2');
    });

    // It should fallback to empty list but keep discovery errors/status
    expect(screen.getByTestId('enabled-count')).toHaveTextContent('0');
  });

  it('should handle invalid JSON in localStorage', async () => {
    mockLocalStorage.getItem.mockReturnValue('invalid json');

    render(
      <PluginProvider>
        <TestComponent />
      </PluginProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('storage-error')).toHaveTextContent('Failed to load plugin states - using defaults');
    });

    expect(screen.getByTestId('enabled-count')).toHaveTextContent('0');
  });

  it('should validate plugin data and filter invalid entries', async () => {
    mockLocalStorage.getItem.mockReturnValue('["investments", "", null, 123, "valid-plugin"]');

    render(
      <PluginProvider>
        <TestComponent />
      </PluginProvider>
    );

    await waitFor(() => {
      // Only 1 enabled plugin should remain (investments) since "valid-plugin" doesn't exist in discovery
      expect(screen.getByTestId('enabled-count')).toHaveTextContent('1');
    });

    // Should only keep valid string plugin IDs that exist in the discovered plugins
    expect(screen.getByTestId('investments-enabled')).toHaveTextContent('true');
  });

  it('should toggle plugin state and persist to API', async () => {
    const user = userEvent.setup();
    (apiRequest as any).mockImplementation((path: string) => {
      if (path === '/plugins/registry') return Promise.resolve({ plugins: [] });
      if (path === '/plugins/settings') return Promise.resolve({ enabled_plugins: [] });
      if (path.includes('/enable')) return Promise.resolve({ success: true, enabled_plugins: ['investments'] });
      return Promise.resolve({});
    });

    render(
      <PluginProvider>
        <TestComponent />
      </PluginProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('plugin-investments-enabled')).toHaveTextContent('false');
    });

    // Toggle plugin on
    await user.click(screen.getByTestId('toggle-investments'));

    await waitFor(() => {
      expect(screen.getByTestId('plugin-investments-enabled')).toHaveTextContent('true');
    });

    expect(apiRequest).toHaveBeenCalledWith('/plugins/settings/investments/enable', expect.objectContaining({ method: 'POST' }));
    expect(window.dispatchEvent).toHaveBeenCalledWith(
      expect.objectContaining({
        type: 'plugin-toggled',
        detail: { pluginId: 'investments', enabled: true }
      })
    );
  });

  it('should re-load settings on auth-changed event', async () => {
    (apiRequest as any).mockImplementation((path: string) => {
      if (path === '/plugins/registry') return Promise.resolve({ plugins: [] });
      if (path === '/plugins/settings') return Promise.resolve({ enabled_plugins: [] });
      return Promise.resolve({});
    });

    render(
      <PluginProvider>
        <TestComponent />
      </PluginProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('enabled-count')).toHaveTextContent('0');
    });

    // Change mock behavior for the next call
    (apiRequest as any).mockImplementation((path: string) => {
      if (path === '/plugins/registry') return Promise.resolve({ plugins: [] });
      if (path === '/plugins/settings') return Promise.resolve({ enabled_plugins: ['investments'] });
      return Promise.resolve({});
    });

    // Trigger auth-changed
    window.dispatchEvent(new Event('auth-changed'));

    await waitFor(() => {
      expect(screen.getByTestId('enabled-count')).toHaveTextContent('1');
    });

    expect(screen.getByTestId('investments-enabled')).toHaveTextContent('true');
  });

  it('should handle API failures during toggle', async () => {
    const user = userEvent.setup();
    (apiRequest as any).mockImplementation((path: string) => {
      if (path === '/plugins/registry') return Promise.resolve({ plugins: [] });
      if (path === '/plugins/settings') return Promise.resolve({ enabled_plugins: [] });
      if (path.includes('/enable')) return Promise.reject(new Error('API failure'));
      return Promise.resolve({});
    });

    render(
      <PluginProvider>
        <TestComponent />
      </PluginProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('plugin-investments-enabled')).toHaveTextContent('false');
    });

    // Toggle should fail and revert state
    const toggleButton = screen.getByTestId('toggle-investments');
    await user.click(toggleButton);

    // Wait for the error handling (revert)
    await waitFor(() => {
      expect(screen.getByTestId('plugin-investments-enabled')).toHaveTextContent('false');
    });
  });

  it('should initialize plugins successfully', async () => {
    const user = userEvent.setup();

    render(
      <PluginProvider>
        <TestComponent />
      </PluginProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('plugin-count')).toHaveTextContent('2');
    });

    // Initialize plugin
    await user.click(screen.getByTestId('init-investments'));

    await waitFor(() => {
      expect(window.dispatchEvent).toHaveBeenCalledWith(
        expect.objectContaining({
          type: 'plugin-initialized',
          detail: { pluginId: 'investments', success: true }
        })
      );
    });

    expect(screen.getByTestId('plugin-investments-init-error')).toHaveTextContent('none');
  });

  it('should track plugin initialization status', async () => {
    render(
      <PluginProvider>
        <TestComponent />
      </PluginProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('plugin-count')).toHaveTextContent('2');
    });

    // Check initial initialization status
    const initStatus = JSON.parse(screen.getByTestId('investments-init-status').textContent || '{}');
    expect(initStatus.isInitialized).toBe(false);
    expect(initStatus.error).toBeUndefined();
  });

  it('should discover plugins and handle discovery errors', async () => {
    render(
      <PluginProvider>
        <TestComponent />
      </PluginProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('plugin-count')).toHaveTextContent('2');
    });

    // Should have discovered the built-in investment plugin
    expect(screen.getByTestId('plugin-investments')).toHaveTextContent('Investment Management');

    // Should have no discovery errors for built-in plugins
    expect(screen.getByTestId('discovery-errors')).toHaveTextContent('0');
  });
});