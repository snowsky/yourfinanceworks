import { useEffect, useState } from 'react';
import type { LucideIcon } from 'lucide-react';
import type { PluginNavItem, PluginRouteConfig } from '@/types/plugin-routes';

export interface LoadedPluginModule {
  navItems?: PluginNavItem[];
  pluginRoutes?: PluginRouteConfig[];
  pluginIcons?: Record<string, LucideIcon>;
}

// Lazy glob both repo-based and dynamic plugins
const _pluginGlob = import.meta.glob([
  '../plugins/*/index.ts',
  '../plugins/*/plugin/ui/index.ts',
  '../plugins_dynamic/*/index.ts',
  '../plugins_dynamic/*/plugin/ui/index.ts',
  '../../../yfw-*/plugin/ui/index.ts'
]) as Record<
  string,
  () => Promise<LoadedPluginModule>
>;

let _cache: LoadedPluginModule[] | null = null;
const _listeners = new Set<() => void>();

function _load() {
  Promise.allSettled(Object.entries(_pluginGlob).map(([path, load]) =>
    load().catch((err) => {
      console.warn(`[plugins] Failed to load plugin from ${path}:`, err);
      return null;
    })
  )).then((results) => {
    _cache = results
      .filter((r): r is PromiseFulfilledResult<LoadedPluginModule | null> => r.status === 'fulfilled')
      .map((r) => r.value)
      .filter((m): m is LoadedPluginModule => m !== null);
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
