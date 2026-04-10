import { useEffect, useState } from 'react';
import type { LucideIcon } from 'lucide-react';
import type { PluginNavItem, PluginPublicPage, PluginRouteConfig } from '@/types/plugin-routes';
import { apiRequest } from '@/lib/api';

export interface LoadedPluginModule {
  navItems?: PluginNavItem[];
  pluginRoutes?: PluginRouteConfig[];
  pluginIcons?: Record<string, LucideIcon>;
  /** True for sidecar plugins whose nav items come from the API registry, not the Vite glob. */
  isSidecar?: boolean;
  /** Base URL for the sidecar plugin UI (e.g. /plugins/socialhub/). Only set when isSidecar=true. */
  uiEntry?: string;
  /** Canonical name/slug of the plugin (e.g. statement-tools). */
  pluginId: string;
  /** Raw metadata from the plugin manifest. */
  pluginMetadata?: any;
  /**
   * Public portal page for this plugin.
   * Exported by in-process plugins from plugin/ui/index.ts,
   * or derived from the manifest for sidecar plugins.
   */
  publicPage?: PluginPublicPage;
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
  if (!localStorage.getItem('user')) {
    return [];
  }
  try {
    const data = await apiRequest<{ plugins: any[] }>('/plugins/registry');
    return (data.plugins ?? [])
      .filter((p: any) => p.is_sidecar && Array.isArray(p.nav_items) && p.nav_items.length > 0)
      .map((p: any) => {
        const publicPage: PluginPublicPage | undefined = p.public_page?.ui_entry
          ? {
              pluginId: p.name as string,
              pluginName: p.description as string,
              path: (p.public_page.path as string) ?? `/p/${p.name}`,
              uiEntry: p.public_page.ui_entry as string,
            }
          : undefined;
        return {
          navItems: p.nav_items as PluginNavItem[],
          isSidecar: true,
          uiEntry: p.ui_entry as string,
          pluginId: p.name as string,
          publicPage,
        };
      });
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
        .map((m) => {
          if (!m) return null;
          // Extract pluginId from metadata if not explicitly set
          const metadata = (m as any).pluginMetadata;
          const pluginId = m.pluginId || (m as any).id || metadata?.id || metadata?.name;
          return { ...m, pluginId };
        })
        .filter((m): m is LoadedPluginModule => m !== null && !!m.pluginId)
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
