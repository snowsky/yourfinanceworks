import { useEffect, useState } from 'react';
import type { LucideIcon } from 'lucide-react';
import type { PluginNavItem, PluginRouteConfig } from '@/types/plugin-routes';
import { apiRequest } from '@/lib/api';

export interface LoadedPluginModule {
  navItems?: PluginNavItem[];
  pluginRoutes?: PluginRouteConfig[];
  pluginIcons?: Record<string, LucideIcon>;
  /** True for sidecar plugins whose nav items come from the API registry, not the Vite glob. */
  isSidecar?: boolean;
}

// Lazy glob both repo-based and dynamic plugins
const _pluginGlob = import.meta.glob([
  '../plugins/*/index.{ts,tsx}',
  '../plugins/*/plugin/ui/index.{ts,tsx}',
  '../plugins_dynamic/*/index.{ts,tsx}',
  '../plugins_dynamic/*/plugin/ui/index.{ts,tsx}',
  '../../../yfw-*/plugin/ui/index.{ts,tsx}'
]) as Record<
  string,
  () => Promise<LoadedPluginModule>
>;

let _cache: LoadedPluginModule[] | null = null;
const _listeners = new Set<() => void>();

async function _fetchSidecarNavItems(): Promise<LoadedPluginModule[]> {
  try {
    const data = await apiRequest<{ plugins: any[] }>('/plugins/registry');
    return (data.plugins ?? [])
      .filter((p: any) => p.is_sidecar && Array.isArray(p.nav_items) && p.nav_items.length > 0)
      .map((p: any) => ({ navItems: p.nav_items as PluginNavItem[], isSidecar: true }));
  } catch {
    return [];
  }
}

function _load() {
  Promise.allSettled([
    // Static plugins discovered via Vite glob at build time
    Promise.allSettled(Object.entries(_pluginGlob).map(([path, load]) =>
      load().catch((err) => {
        console.warn(`[plugins] Failed to load plugin from ${path}:`, err);
        return null;
      })
    )).then((results) =>
      results
        .filter((r): r is PromiseFulfilledResult<LoadedPluginModule | null> => r.status === 'fulfilled')
        .map((r) => r.value)
        .filter((m): m is LoadedPluginModule => m !== null)
    ),
    // Sidecar plugins: nav items come from the API registry manifest at runtime
    _fetchSidecarNavItems(),
  ]).then(([staticResult, sidecarResult]) => {
    const staticModules = staticResult.status === 'fulfilled' ? staticResult.value : [];
    const sidecarModules = sidecarResult.status === 'fulfilled' ? sidecarResult.value : [];
    _cache = [...staticModules, ...sidecarModules];
    _listeners.forEach((fn) => fn());
  });
}

// Start loading immediately at module init (once, shared across all consumers).
_load();

export function usePluginModules(): LoadedPluginModule[] {
  const [modules, setModules] = useState<LoadedPluginModule[]>(_cache ?? []);

  useEffect(() => {
    if (_cache !== null) {
      setModules(_cache);
      return;
    }
    const notify = () => setModules(_cache ?? []);
    _listeners.add(notify);
    return () => { _listeners.delete(notify); };
  }, []);

  return modules;
}
