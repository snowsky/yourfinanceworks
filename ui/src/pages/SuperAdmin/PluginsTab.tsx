import React, { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { ProfessionalCard } from '@/components/ui/professional-card';
import { PluginSettingsModal } from '@/components/settings/PluginSettingsModal';
import { Loader2, Puzzle, Settings, ShieldCheck, ShieldOff } from 'lucide-react';
import { toast } from 'sonner';
import { pluginApi } from '../../lib/api/plugins';
import type { Tenant } from './types';

interface PluginEntry {
  name: string;
  displayName: string;
  version?: string;
  license_tier?: string;
}

interface PluginsTabProps {
  tenants: Tenant[];
}

export const PluginsTab: React.FC<PluginsTabProps> = ({ tenants }) => {
  const { t } = useTranslation();
  const [plugins, setPlugins] = useState<PluginEntry[]>([]);
  // Map: `${pluginId}:${tenantId}` → true/false
  const [accessMap, setAccessMap] = useState<Record<string, boolean>>({});
  const [loading, setLoading] = useState(true);
  const [toggling, setToggling] = useState<Record<string, boolean>>({});
  const [error, setError] = useState<string | null>(null);
  const [settingsTarget, setSettingsTarget] = useState<{
    pluginId: string;
    pluginName: string;
    tenantId: number;
    tenantName: string;
  } | null>(null);

  const key = (pluginId: string, tenantId: number) => `${pluginId}:${tenantId}`;

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [registryRes, grantsRes] = await Promise.all([
        fetch('/api/v1/plugins/registry').then(r => r.json()),
        pluginApi.listAllPluginAccess(),
      ]);

      const discoveredPlugins: PluginEntry[] = (registryRes.plugins || []).map((p: any) => ({
        name: p.name,
        displayName: p.display_name || p.name,
        version: p.version,
        license_tier: p.license_tier,
      }));
      setPlugins(discoveredPlugins);

      const map: Record<string, boolean> = {};
      for (const grant of grantsRes.grants) {
        map[key(grant.plugin_id, grant.tenant_id)] = true;
      }
      setAccessMap(map);
    } catch (err) {
      setError(t('superAdmin.plugins.load_error'));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleToggle = async (pluginId: string, tenantId: number, granted: boolean) => {
    const k = key(pluginId, tenantId);
    setToggling(prev => ({ ...prev, [k]: true }));
    try {
      if (granted) {
        await pluginApi.grantPluginAccess(tenantId, pluginId);
        setAccessMap(prev => ({ ...prev, [k]: true }));
        toast.success(t('superAdmin.plugins.grant_success', { plugin: pluginId }));
      } else {
        await pluginApi.revokePluginAccess(tenantId, pluginId);
        setAccessMap(prev => ({ ...prev, [k]: false }));
        toast.success(t('superAdmin.plugins.revoke_success', { plugin: pluginId }));
      }
    } catch (err: any) {
      toast.error(err?.detail || err?.message || t('superAdmin.plugins.toggle_error'));
    } finally {
      setToggling(prev => ({ ...prev, [k]: false }));
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    );
  }

  if (plugins.length === 0) {
    return (
      <ProfessionalCard>
        <div className="flex flex-col items-center gap-3 py-12 text-muted-foreground">
          <Puzzle className="h-10 w-10" />
          <p>{t('superAdmin.plugins.no_plugins')}</p>
        </div>
      </ProfessionalCard>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <ShieldCheck className="h-4 w-4" />
        <span>{t('superAdmin.plugins.description')}</span>
      </div>

      <TooltipProvider>
        <ProfessionalCard>
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="min-w-[180px]">{t('superAdmin.plugins.plugin_header')}</TableHead>
                  {tenants.map(tenant => (
                    <TableHead key={tenant.id} className="text-center min-w-[140px]">
                      <div className="flex flex-col items-center gap-0.5">
                        <span className="font-medium truncate max-w-[120px]" title={tenant.name}>
                          {tenant.name}
                        </span>
                        {!tenant.is_active && (
                          <Badge variant="outline" className="text-[10px] px-1 py-0 text-muted-foreground">
                            {t('superAdmin.plugins.inactive')}
                          </Badge>
                        )}
                      </div>
                    </TableHead>
                  ))}
                </TableRow>
              </TableHeader>
              <TableBody>
                {plugins.map(plugin => (
                  <TableRow key={plugin.name}>
                    <TableCell>
                      <div className="flex flex-col gap-0.5">
                        <span className="font-medium">{plugin.displayName}</span>
                        <div className="flex items-center gap-1.5">
                          <code className="text-[11px] text-muted-foreground">{plugin.name}</code>
                          {plugin.license_tier && (
                            <Badge
                              variant="outline"
                              className={`text-[10px] px-1 py-0 ${
                                plugin.license_tier === 'commercial'
                                  ? 'text-amber-600 border-amber-300'
                                  : 'text-blue-600 border-blue-300'
                              }`}
                            >
                              {plugin.license_tier}
                            </Badge>
                          )}
                        </div>
                      </div>
                    </TableCell>
                    {tenants.map(tenant => {
                      const k = key(plugin.name, tenant.id);
                      const isGranted = !!accessMap[k];
                      const isToggling = !!toggling[k];
                      return (
                        <TableCell key={tenant.id} className="text-center">
                          <div className="flex items-center justify-center gap-1.5">
                            {isToggling ? (
                              <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                            ) : (
                              <>
                                {isGranted ? (
                                  <ShieldCheck className="h-3.5 w-3.5 text-green-500" />
                                ) : (
                                  <ShieldOff className="h-3.5 w-3.5 text-muted-foreground/40" />
                                )}
                                <Switch
                                  checked={isGranted}
                                  onCheckedChange={checked => handleToggle(plugin.name, tenant.id, checked)}
                                  aria-label={`${isGranted ? t('superAdmin.plugins.revoke') : t('superAdmin.plugins.grant')} ${plugin.name} for ${tenant.name}`}
                                />
                                {isGranted && (
                                  <Tooltip>
                                    <TooltipTrigger asChild>
                                      <Button
                                        type="button"
                                        variant="outline"
                                        size="sm"
                                        className="h-7 px-2"
                                        aria-label={`Configure ${plugin.displayName} for ${tenant.name}`}
                                        title={`Configure ${plugin.displayName} for ${tenant.name}`}
                                        onClick={() =>
                                          setSettingsTarget({
                                            pluginId: plugin.name,
                                            pluginName: plugin.displayName,
                                            tenantId: tenant.id,
                                            tenantName: tenant.name,
                                          })
                                        }
                                      >
                                        <Settings className="h-3.5 w-3.5" />
                                      </Button>
                                    </TooltipTrigger>
                                    <TooltipContent>
                                      Configure {plugin.displayName} for {tenant.name}
                                    </TooltipContent>
                                  </Tooltip>
                                )}
                              </>
                            )}
                          </div>
                        </TableCell>
                      );
                    })}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </ProfessionalCard>
      </TooltipProvider>

      {settingsTarget && (
        <PluginSettingsModal
          open={Boolean(settingsTarget)}
          onOpenChange={(open) => {
            if (!open) setSettingsTarget(null);
          }}
          pluginId={settingsTarget.pluginId}
          pluginName={settingsTarget.pluginName}
          targetTenantId={settingsTarget.tenantId}
          targetTenantName={settingsTarget.tenantName}
        />
      )}
    </div>
  );
};
