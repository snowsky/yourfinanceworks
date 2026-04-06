import React, { useState, useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { Switch } from '@/components/ui/switch';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Loader2, Puzzle, TrendingUp, FolderKanban, Info, Shield, RefreshCw, CheckCircle, XCircle, AlertCircle, Clock, ExternalLink, Star, Download, Calendar, Tag, Settings, ArrowRightLeft, Trash2, GitBranch, Search, X, RotateCcw, KeyRound } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog';
import { usePlugins, Plugin } from '@/contexts/PluginContext';
import { useFeatures } from '@/contexts/FeatureContext';
import { FeatureGate } from '@/components/FeatureGate';
import { ProfessionalCard, ProfessionalCardContent } from '@/components/ui/professional-card';
import { ProfessionalButton } from '@/components/ui/professional-button';
import { toast } from 'sonner';
import { PluginSettingsModal } from './PluginSettingsModal';
import { PluginAccessModal } from './PluginAccessModal';
import { InstallPluginModal } from './InstallPluginModal';
import { pluginApi } from '@/lib/api/plugins';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";


type ReinstallState = 'idle' | 'confirm' | 'running' | 'done' | 'failed';

interface PluginCardProps {
  plugin: Plugin;
  onToggle: (pluginId: string, enabled: boolean, isAdmin?: boolean) => Promise<void>;
  onUninstall?: (pluginId: string) => Promise<void>;
  onReinstall?: (pluginId: string, options?: { githubToken?: string; gitUrl?: string; ref?: string }) => Promise<string>;
  canToggle: boolean;
  licenseMessage?: string;
  isAdmin: boolean;
  isExpired?: boolean;
}

const PluginCard: React.FC<PluginCardProps> = ({ plugin, onToggle, onUninstall, onReinstall, canToggle, licenseMessage, isAdmin, isExpired }) => {
  const [isToggling, setIsToggling] = useState(false);
  const [isUninstalling, setIsUninstalling] = useState(false);
  const [showUninstallDialog, setShowUninstallDialog] = useState(false);
  const [showSettingsModal, setShowSettingsModal] = useState(false);
  const [showPermissionDialog, setShowPermissionDialog] = useState(false);
  const [reinstallState, setReinstallState] = useState<ReinstallState>('idle');
  const [reinstallToken, setReinstallToken] = useState('');
  const [reinstallUrl, setReinstallUrl] = useState('');
  const [reinstallRef, setReinstallRef] = useState('main');
  const [reinstallJob, setReinstallJob] = useState<import('@/lib/api/plugins').InstallJob | null>(null);
  const reinstallPollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const needsUrl = !plugin.git_source;
  const { t } = useTranslation();

  const stopReinstallPolling = () => {
    if (reinstallPollRef.current) {
      clearInterval(reinstallPollRef.current);
      reinstallPollRef.current = null;
    }
  };

  const handleReinstallConfirm = async () => {
    if (!onReinstall) return;
    try {
      const jobId = await onReinstall(plugin.id, {
        githubToken: reinstallToken.trim() || undefined,
        gitUrl: needsUrl ? reinstallUrl.trim() || undefined : undefined,
        ref: needsUrl ? reinstallRef.trim() || 'main' : undefined,
      });
      const initial = await pluginApi.getInstallStatus(jobId);
      setReinstallJob(initial);
      setReinstallState('running');
      stopReinstallPolling();
      reinstallPollRef.current = setInterval(async () => {
        try {
          const updated = await pluginApi.getInstallStatus(jobId);
          setReinstallJob(updated);
          if (updated.status === 'done') {
            stopReinstallPolling();
            setReinstallState('done');
            toast.success(`${plugin.name} reinstalled. Restart the server to activate.`);
          } else if (updated.status === 'failed') {
            stopReinstallPolling();
            setReinstallState('failed');
          }
        } catch { /* silently retry */ }
      }, 2000);
    } catch (error) {
      setReinstallState('failed');
      toast.error(`Failed to start reinstall: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  };

  const handleReinstallClose = () => {
    stopReinstallPolling();
    setReinstallState('idle');
    setReinstallToken('');
    setReinstallUrl('');
    setReinstallRef('main');
    setReinstallJob(null);
  };

  const handleUninstall = async () => {
    if (!onUninstall) return;
    setIsUninstalling(true);
    try {
      await onUninstall(plugin.id);
      toast.success(`${plugin.name} uninstalled. Restart the server to complete removal.`);
    } catch (error) {
      toast.error(`Failed to uninstall: ${error instanceof Error ? error.message : 'Unknown error'}`);
    } finally {
      setIsUninstalling(false);
      setShowUninstallDialog(false);
    }
  };


  const handleToggle = async (enabled: boolean) => {
    if (!canToggle) {
      if (licenseMessage) {
        toast.error(licenseMessage);
      } else {
        toast.error('This plugin requires a license upgrade');
      }
      return;
    }

    if (!isAdmin) {
      toast.error('Unauthorized: Only administrators can manage plugins');
      return;
    }

    if (enabled && plugin.required_access && plugin.required_access.length > 0) {
      setShowPermissionDialog(true);
      return;
    }

    await executeToggle(enabled);
  };

  const executeToggle = async (enabled: boolean) => {
    setIsToggling(true);
    try {
      await onToggle(plugin.id, enabled, isAdmin);
      toast.success(
        enabled
          ? `${plugin.name} plugin enabled`
          : `${plugin.name} plugin disabled`
      );
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error occurred';

      // Enhanced error handling for admin access control and license validation
      if (errorMessage.includes('unauthorized') || errorMessage.includes('permission')) {
        toast.error('Unauthorized: Only administrators can manage plugins');
      } else if (errorMessage.includes('license') || errorMessage.includes('License')) {
        toast.error(`License validation failed: ${errorMessage}`);
      } else if (errorMessage.includes('Storage')) {
        toast.error(`Storage error: Plugin settings may not be saved. ${errorMessage}`);
      } else if (errorMessage.includes('quota')) {
        toast.error('Storage quota exceeded. Please clear some browser data and try again.');
      } else if (errorMessage.includes('initialize')) {
        toast.error(`Plugin initialization failed: ${errorMessage}`);
      } else {
        toast.error(`Failed to ${enabled ? 'enable' : 'disable'} plugin: ${errorMessage}`);
      }
    } finally {
      setIsToggling(false);
    }
  };

  const getPluginIcon = (plugin: Plugin) => {
    // If plugin has a custom icon (emoji or text), use it
    if (typeof plugin.icon === 'string' && plugin.icon !== '🔌') {
      return (
        <div className="w-8 h-8 flex items-center justify-center text-2xl bg-gradient-to-br from-blue-50 to-indigo-50 rounded-lg border border-blue-200">
          {plugin.icon}
        </div>
      );
    }

    // Plugin-specific branded icons
    switch (plugin.id) {
      case 'investments':
        return (
          <div className="w-8 h-8 flex items-center justify-center bg-gradient-to-br from-green-500 to-emerald-600 rounded-lg shadow-sm">
            <TrendingUp className="w-5 h-5 text-white" />
          </div>
        );
      case 'time-tracking':
        return (
          <div className="w-8 h-8 flex items-center justify-center bg-gradient-to-br from-violet-500 to-purple-600 rounded-lg shadow-sm">
            <FolderKanban className="w-5 h-5 text-white" />
          </div>
        );
      default:
        return (
          <div className="w-8 h-8 flex items-center justify-center bg-gradient-to-br from-gray-400 to-gray-500 rounded-lg shadow-sm">
            <Puzzle className="w-5 h-5 text-white" />
          </div>
        );
    }
  };

  const getStatusIcon = (plugin: Plugin) => {
    if (plugin.initializationError) {
      return <XCircle className="w-4 h-4 text-red-500" />;
    }

    switch (plugin.status) {
      case 'active':
        return <CheckCircle className="w-4 h-4 text-green-500" />;
      case 'initializing':
        return <Clock className="w-4 h-4 text-blue-500 animate-pulse" />;
      case 'error':
        return <XCircle className="w-4 h-4 text-red-500" />;
      case 'disabled':
        return <XCircle className="w-4 h-4 text-gray-400" />;
      case 'inactive':
      default:
        return <AlertCircle className="w-4 h-4 text-gray-400" />;
    }
  };

  const getStatusText = (plugin: Plugin) => {
    if (plugin.initializationError) {
      return t('plugins.status.error');
    }

    switch (plugin.status) {
      case 'active':
        return t('plugins.status.active');
      case 'initializing':
        return t('plugins.status.initializing');
      case 'error':
        return t('plugins.status.error');
      case 'disabled':
        return t('plugins.status.disabled');
      case 'inactive':
      default:
        return plugin.enabled ? t('plugins.status.enabled') : t('plugins.status.inactive');
    }
  };

  const getStatusColor = (plugin: Plugin) => {
    if (plugin.initializationError) {
      return 'text-red-600 bg-red-50 border-red-200';
    }

    switch (plugin.status) {
      case 'active':
        return 'text-green-600 bg-green-50 border-green-200';
      case 'initializing':
        return 'text-blue-600 bg-blue-50 border-blue-200';
      case 'error':
        return 'text-red-600 bg-red-50 border-red-200';
      case 'disabled':
        return 'text-gray-600 bg-gray-50 border-gray-200';
      case 'inactive':
      default:
        return plugin.enabled ? 'text-green-600 bg-green-50 border-green-200' : 'text-gray-600 bg-gray-50 border-gray-200';
    }
  };

  return (
    <Card className={`transition-all duration-200 ${plugin.enabled ? 'ring-2 ring-blue-500/20 bg-blue-50/30' : ''}`}>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            {getPluginIcon(plugin)}
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <CardTitle className="text-lg">{plugin.name}</CardTitle>
                {getStatusIcon(plugin)}
              </div>
              <div className="flex items-center gap-2 mt-1 flex-wrap">
                {plugin.version && (
                  <Badge variant="outline" className="text-xs">
                    v{plugin.version}
                  </Badge>
                )}
                {plugin.category && (
                  <Badge variant="secondary" className="text-xs">
                    <Tag className="w-3 h-3 mr-1" />
                    {plugin.category}
                  </Badge>
                )}
                {plugin.requiresLicense && (
                  <Badge variant="secondary" className="text-xs">
                    <Shield className="w-3 h-3 mr-1" />
                    {plugin.requiresLicense}
                  </Badge>
                )}
                <Badge
                  variant="outline"
                  className={`text-xs ${getStatusColor(plugin)}`}
                >
                  {getStatusText(plugin)}
                </Badge>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {isToggling && <Loader2 className="w-4 h-4 animate-spin" />}
            <Switch
              checked={plugin.enabled}
              onCheckedChange={handleToggle}
              disabled={isToggling || !canToggle}
            />
          </div>
        </div>
      </CardHeader>

      {/* Uninstall confirmation dialog */}
      <AlertDialog open={showUninstallDialog} onOpenChange={setShowUninstallDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center gap-2">
              <Trash2 className="w-5 h-5 text-red-600" />
              Uninstall {plugin.name}?
            </AlertDialogTitle>
            <AlertDialogDescription>
              This will remove the plugin files from disk and disable it. The plugin data in the
              database will remain. A server restart is required to complete removal.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleUninstall}
              className="bg-red-600 hover:bg-red-700"
            >
              {isUninstalling ? <Loader2 className="w-4 h-4 mr-1 animate-spin" /> : null}
              Uninstall
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog open={showPermissionDialog} onOpenChange={setShowPermissionDialog}>
        <AlertDialogContent className="max-w-2xl">
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center gap-2">
              <Shield className="w-5 h-5 text-blue-600" />
              {t('plugins.required_access_title')}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {t('plugins.required_access_description', { pluginName: plugin.name })}
            </AlertDialogDescription>
          </AlertDialogHeader>

          <div className="my-4 border rounded-md overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b">
                <tr>
                  <th className="px-4 py-2 text-left font-medium text-gray-700">{t('plugins.target_plugin')}</th>
                  <th className="px-4 py-2 text-left font-medium text-gray-700">{t('plugins.access_type')}</th>
                  <th className="px-4 py-2 text-left font-medium text-gray-700">{t('plugins.reason_for_access')}</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {plugin.required_access?.map((req, idx) => (
                  <tr key={idx} className="bg-white">
                    <td className="px-4 py-2 font-medium">{req.target_plugin}</td>
                    <td className="px-4 py-2">
                      <Badge variant="outline" className={req.access_type === 'write' ? 'text-orange-600 bg-orange-50 border-orange-200' : 'text-blue-600 bg-blue-50 border-blue-200'}>
                        {req.access_type === 'write' ? t('plugins.write_access') : t('plugins.read_access')}
                      </Badge>
                    </td>
                    <td className="px-4 py-2 text-gray-600">{req.reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <AlertDialogFooter>
            <AlertDialogCancel onClick={() => setShowPermissionDialog(false)}>
              {t('plugins.cancel_enablement')}
            </AlertDialogCancel>
            <AlertDialogAction 
              onClick={async () => {
                setShowPermissionDialog(false);
                await executeToggle(true);
              }}
              className="bg-blue-600 hover:bg-blue-700"
            >
              {t('plugins.grant_access_and_enable')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Reinstall dialog — confirm + progress */}
      <Dialog open={reinstallState !== 'idle'} onOpenChange={(open) => { if (!open) handleReinstallClose(); }}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <RotateCcw className="w-5 h-5 text-blue-600" />
              Reinstall {plugin.name}
            </DialogTitle>
            <DialogDescription>
              Re-clone and reinstall from the original git source. A server restart is required after reinstallation.
            </DialogDescription>
          </DialogHeader>

          {reinstallState === 'confirm' && (
            <>
              <div className="space-y-3 py-1">
                {plugin.git_source ? (
                  <div className="text-sm text-muted-foreground rounded-md bg-muted px-3 py-2 font-mono break-all">
                    {plugin.git_source.git_url}@{plugin.git_source.ref}
                  </div>
                ) : (
                  <>
                    <div className="space-y-1.5">
                      <Label htmlFor="reinstall-url" className="flex items-center gap-1.5 text-sm">
                        <GitBranch className="w-3.5 h-3.5" />
                        Repository URL
                      </Label>
                      <Input
                        id="reinstall-url"
                        placeholder="https://github.com/org/my-plugin"
                        value={reinstallUrl}
                        onChange={e => setReinstallUrl(e.target.value)}
                      />
                    </div>
                    <div className="space-y-1.5">
                      <Label htmlFor="reinstall-ref" className="flex items-center gap-1.5 text-sm">
                        Branch / Tag
                      </Label>
                      <Input
                        id="reinstall-ref"
                        placeholder="main"
                        value={reinstallRef}
                        onChange={e => setReinstallRef(e.target.value)}
                      />
                    </div>
                  </>
                )}
                <div className="space-y-1.5">
                  <Label htmlFor="reinstall-token" className="flex items-center gap-1.5 text-sm">
                    <KeyRound className="w-3.5 h-3.5" />
                    GitHub Token <span className="text-muted-foreground font-normal">(optional — for private repos)</span>
                  </Label>
                  <Input
                    id="reinstall-token"
                    type="password"
                    placeholder="ghp_…"
                    value={reinstallToken}
                    onChange={e => setReinstallToken(e.target.value)}
                    autoComplete="off"
                  />
                </div>
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={handleReinstallClose}>Cancel</Button>
                <Button
                  className="bg-blue-600 hover:bg-blue-700"
                  onClick={handleReinstallConfirm}
                  disabled={needsUrl && !reinstallUrl.trim()}
                >
                  Reinstall
                </Button>
              </DialogFooter>
            </>
          )}

          {(reinstallState === 'running' || reinstallState === 'done' || reinstallState === 'failed') && reinstallJob && (
            <>
              <div className="py-1 space-y-3">
                <div className="flex items-center gap-2">
                  {reinstallState === 'running' && <Badge className="bg-blue-100 text-blue-700 border-blue-200"><Loader2 className="w-3 h-3 mr-1 animate-spin" /> Reinstalling…</Badge>}
                  {reinstallState === 'done' && <Badge className="bg-green-100 text-green-700 border-green-200"><CheckCircle className="w-3 h-3 mr-1" /> Done</Badge>}
                  {reinstallState === 'failed' && <Badge className="bg-red-100 text-red-700 border-red-200"><XCircle className="w-3 h-3 mr-1" /> Failed</Badge>}
                </div>
                <div className="rounded-md border bg-gray-50 p-3 space-y-2">
                  {reinstallJob.steps.map((step, i) => (
                    <div key={i} className="flex items-start gap-2 text-sm">
                      {step.status === 'done' && <CheckCircle className="w-4 h-4 text-green-500 shrink-0" />}
                      {step.status === 'failed' && <XCircle className="w-4 h-4 text-red-500 shrink-0" />}
                      {step.status === 'running' && <Loader2 className="w-4 h-4 text-blue-500 animate-spin shrink-0" />}
                      {step.status === 'pending' && <Clock className="w-4 h-4 text-gray-300 shrink-0" />}
                      <div className="flex-1">
                        <span className={step.status === 'pending' ? 'text-gray-400' : 'text-gray-800'}>{step.label}</span>
                        {step.detail && <p className="text-xs text-muted-foreground mt-0.5">{step.detail}</p>}
                      </div>
                    </div>
                  ))}
                  {reinstallState === 'running' && reinstallJob.steps.length === 0 && (
                    <div className="flex items-center gap-2 text-sm text-gray-400">
                      <Loader2 className="w-4 h-4 animate-spin" /> Starting…
                    </div>
                  )}
                </div>
                {reinstallState === 'failed' && reinstallJob.error && (
                  <Alert className="border-red-200 bg-red-50">
                    <XCircle className="h-4 w-4 text-red-600" />
                    <AlertDescription className="text-red-800 text-sm">{reinstallJob.error}</AlertDescription>
                  </Alert>
                )}
              </div>
              <DialogFooter>
                {reinstallState === 'failed' && (
                  <Button variant="outline" onClick={() => { setReinstallState('confirm'); setReinstallJob(null); }} className="mr-auto">
                    <RotateCcw className="w-4 h-4 mr-1" /> Try Again
                  </Button>
                )}
                <Button variant={reinstallState === 'done' ? 'default' : 'outline'} onClick={handleReinstallClose}>
                  {reinstallState === 'done' ? 'Done' : 'Close'}
                </Button>
              </DialogFooter>
            </>
          )}
        </DialogContent>
      </Dialog>

      <CardContent>
        <CardDescription className="text-sm text-gray-600 mb-3">
          {plugin.description}
        </CardDescription>

        <div className="space-y-2">
          {plugin.author && (
            <div className="flex items-center gap-2 text-xs text-gray-500">
              <span className="font-medium">{t('plugins.author')}:</span>
              <span>{plugin.author}</span>
            </div>
          )}

          {plugin.dependencies && plugin.dependencies.length > 0 && (
            <div className="flex items-start gap-2 text-xs text-gray-500">
              <span className="font-medium">{t('plugins.dependencies')}:</span>
              <div className="flex flex-wrap gap-1">
                {plugin.dependencies.map((dep, index) => (
                  <Badge key={index} variant="outline" className="text-xs">
                    {dep}
                  </Badge>
                ))}
              </div>
            </div>
          )}

          <div className="flex items-center gap-4 text-xs text-gray-500">
            {plugin.rating && (
              <div className="flex items-center gap-1">
                <Star className="w-3 h-3 text-yellow-500 fill-current" />
                <span>{plugin.rating.toFixed(1)}</span>
              </div>
            )}

            {plugin.downloadCount && (
              <div className="flex items-center gap-1">
                <Download className="w-3 h-3" />
                <span>{plugin.downloadCount.toLocaleString()} {t('plugins.downloads')}</span>
              </div>
            )}

            {plugin.lastUpdated && (
              <div className="flex items-center gap-1">
                <Calendar className="w-3 h-3" />
                <span>{t('plugins.updated')} {
                  plugin.lastUpdated instanceof Date
                    ? plugin.lastUpdated.toLocaleDateString()
                    : new Date(plugin.lastUpdated).toLocaleDateString()
                }</span>
              </div>
            )}
          </div>

          {(plugin.homepage || plugin.repository) && (
            <div className="flex items-center gap-2 pt-2">
              {plugin.homepage && (
                <Button
                  variant="outline"
                  size="sm"
                  className="text-xs h-7"
                  onClick={() => window.open(plugin.homepage, '_blank')}
                >
                  <ExternalLink className="w-3 h-3 mr-1" />
                  {t('plugins.homepage')}
                </Button>
              )}
              {plugin.repository && (
                <Button
                  variant="outline"
                  size="sm"
                  className="text-xs h-7"
                  onClick={() => window.open(plugin.repository, '_blank')}
                >
                  <ExternalLink className="w-3 h-3 mr-1" />
                  {t('plugins.repository')}
                </Button>
              )}
            </div>
          )}

          {/* Configure button — shown for all plugins when admin */}
          {isAdmin && (
            <div className="pt-2">
              <Button
                variant="outline"
                size="sm"
                className="text-xs h-7"
                onClick={() => setShowSettingsModal(true)}
              >
                <Settings className="w-3 h-3 mr-1" />
                {t('plugins.configure', 'Configure')}
              </Button>
            </div>
          )}

          {/* Uninstall button — admin only, not for sidecar plugins */}
          {isAdmin && onUninstall && !plugin.is_sidecar && (
            <div className="pt-2">
              <Button
                variant="outline"
                size="sm"
                className="text-xs h-7 text-red-600 border-red-200 hover:bg-red-50"
                onClick={() => setShowUninstallDialog(true)}
                disabled={isUninstalling}
              >
                {isUninstalling
                  ? <Loader2 className="w-3 h-3 mr-1 animate-spin" />
                  : <Trash2 className="w-3 h-3 mr-1" />}
                Uninstall
              </Button>
            </div>
          )}

          {/* Sidecar plugin note — uninstall not available */}
          {plugin.is_sidecar && (
            <div className="pt-2 text-xs text-muted-foreground flex items-center gap-1">
              <Info className="w-3 h-3 shrink-0" />
              Managed as an external service. Stop the Docker container to remove it.
            </div>
          )}

          {/* Reinstall button — admin only, external plugins only */}
          {isAdmin && onReinstall && (
            <div className="pt-1">
              <Button
                variant="outline"
                size="sm"
                className="text-xs h-7 text-blue-600 border-blue-200 hover:bg-blue-50"
                onClick={() => setReinstallState('confirm')}
              >
                <RotateCcw className="w-3 h-3 mr-1" />
                Reinstall
              </Button>
            </div>
          )}
        </div>

        {(!canToggle || !isAdmin) && !isExpired && (
          <Alert className="mt-3 border-amber-200 bg-amber-50">
            <Info className="h-4 w-4 text-amber-600" />
            <AlertDescription className="text-amber-800 text-sm">
              {!isAdmin ? (
                <span>
                  <strong>{t('plugins.administrator_access_required')}:</strong> {t('plugins.admin_only_message')}
                </span>
              ) : (
                <span>
                  <strong>{licenseMessage || t('plugins.license_upgrade_message')}</strong>
                </span>
              )}
            </AlertDescription>
          </Alert>
        )}
      </CardContent>

      {/* Plugin Settings Modal */}
      <PluginSettingsModal
        open={showSettingsModal}
        onOpenChange={setShowSettingsModal}
        pluginId={plugin.id}
        pluginName={plugin.name}
      />
    </Card>
  );
};

interface PluginsTabProps {

  isAdmin: boolean;
}

export const PluginsTab: React.FC<PluginsTabProps> = ({ isAdmin }) => {
  const { t } = useTranslation();
  return (
    <FeatureGate
      feature="plugin_management"
      fallback={
        <ProfessionalCard variant="elevated" className="border-blue-200/50 dark:border-blue-800/50 bg-blue-50/50 dark:bg-blue-900/10">
          <ProfessionalCardContent className="p-12 text-center">
            <div className="w-16 h-16 bg-blue-100 dark:bg-blue-900/30 rounded-full flex items-center justify-center mx-auto mb-6 shadow-sm">
              <Puzzle className="w-8 h-8 text-blue-600 dark:text-blue-400" />
            </div>
            <h3 className="text-2xl font-bold text-foreground mb-3">{t('plugins.business_license_required')}</h3>
            <p className="text-muted-foreground mb-8 max-w-lg mx-auto leading-relaxed">
              {t('plugins.business_license_description')}
            </p>
            <div className="bg-background/80 backdrop-blur-sm rounded-xl p-6 mb-8 max-w-lg mx-auto shadow-sm border border-border/50">
              <h4 className="font-semibold text-foreground mb-4 flex items-center gap-2">
                <Shield className="h-4 w-4 text-primary" />
                {t('plugins.business_license_benefits')}
              </h4>
              <ul className="text-left space-y-3 text-sm text-foreground/80">
                <li className="flex items-start">
                  <div className="mr-3 p-0.5 bg-green-100 rounded-full mt-0.5"><div className="w-2 h-2 bg-green-600 rounded-full" /></div>
                  <span>{t('plugins.benefits.enable_disable')}</span>
                </li>
                <li className="flex items-start">
                  <div className="mr-3 p-0.5 bg-green-100 rounded-full mt-0.5"><div className="w-2 h-2 bg-green-600 rounded-full" /></div>
                  <span>{t('plugins.benefits.sidebar_integration')}</span>
                </li>
                <li className="flex items-start">
                  <div className="mr-3 p-0.5 bg-green-100 rounded-full mt-0.5"><div className="w-2 h-2 bg-green-600 rounded-full" /></div>
                  <span>{t('plugins.benefits.customize_experience')}</span>
                </li>
                <li className="flex items-start">
                  <div className="mr-3 p-0.5 bg-green-100 rounded-full mt-0.5"><div className="w-2 h-2 bg-green-600 rounded-full" /></div>
                  <span>{t('plugins.benefits.advanced_ecosystem')}</span>
                </li>
              </ul>
            </div>
            <div className="flex justify-center gap-4">
              <ProfessionalButton
                variant="gradient"
                onClick={() => window.location.href = '/settings?tab=license'}
                size="lg"
              >
                {t('plugins.activate_business_license')}
              </ProfessionalButton>
              <ProfessionalButton
                variant="outline"
                onClick={() => window.open('https://docs.example.com/plugin-management', '_blank')}
                size="lg"
              >
                {t('plugins.learn_more')}
              </ProfessionalButton>
            </div>
          </ProfessionalCardContent>
        </ProfessionalCard>
      }
    >
      <PluginsTabContent isAdmin={isAdmin} />
    </FeatureGate>
  );
};

const PluginsTabContent: React.FC<PluginsTabProps> = ({ isAdmin }) => {
  const { t } = useTranslation();
  const { plugins, togglePlugin, loading, storageError, discoveryErrors, refreshPluginDiscovery } = usePlugins();
  const { isFeatureEnabled, isFeatureExpired, refetch: refetchFeatures, licenseStatus } = useFeatures();
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [, setForceUpdate] = useState(0);
  const [isAccessModalOpen, setIsAccessModalOpen] = useState(false);
  const [isInstallModalOpen, setIsInstallModalOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');


  // Listen for feature updates and force re-render
  useEffect(() => {
    const handleFeatureUpdate = async () => {
      // Force re-render by updating state
      setForceUpdate(prev => prev + 1);
      // Also refresh features to ensure we have the latest data
      await refetchFeatures();
    };

    window.addEventListener('feature-context-updated', handleFeatureUpdate as EventListener);
    return () => {
      window.removeEventListener('feature-context-updated', handleFeatureUpdate as EventListener);
    };
  }, [refetchFeatures]);

  // Listen for storage events and show appropriate notifications
  useEffect(() => {
    const handleStorageWarning = (event: CustomEvent) => {
      toast.warning(t('plugins.plugin_storage_warning', { error: event.detail.error }));
    };

    const handleStorageError = (event: CustomEvent) => {
      toast.error(t('plugins.plugin_storage_error', { error: event.detail.error }));
    };

    const handlePluginInitialized = (event: CustomEvent) => {
      const { pluginId } = event.detail;
      const plugin = plugins.find(p => p.id === pluginId);
      if (plugin) {
        toast.success(t('plugins.plugin_initialized_success', { pluginName: plugin.name }));
      }
    };

    const handlePluginInitializationFailed = (event: CustomEvent) => {
      const { pluginId, error } = event.detail;
      const plugin = plugins.find(p => p.id === pluginId);
      if (plugin) {
        toast.error(t('plugins.plugin_initialization_failed', { pluginName: plugin.name, error }));
      }
    };

    const handleDiscoveryWarnings = (event: CustomEvent) => {
      const { errors } = event.detail;
      toast.warning(t('plugins.plugin_discovery_warnings', { count: errors.length }));
    };

    const handleDiscoveryRefreshed = (event: CustomEvent) => {
      const { pluginCount } = event.detail;
      toast.success(t('plugins.plugin_discovery_refreshed', { count: pluginCount }));
    };

    const handleDiscoveryError = (event: CustomEvent) => {
      const { error } = event.detail;
      toast.error(t('plugins.plugin_discovery_failed', { error }));
    };

    window.addEventListener('plugin-storage-warning', handleStorageWarning as EventListener);
    window.addEventListener('plugin-storage-error', handleStorageError as EventListener);
    window.addEventListener('plugin-initialized', handlePluginInitialized as EventListener);
    window.addEventListener('plugin-initialization-failed', handlePluginInitializationFailed as EventListener);
    window.addEventListener('plugin-discovery-warnings', handleDiscoveryWarnings as EventListener);
    window.addEventListener('plugin-discovery-refreshed', handleDiscoveryRefreshed as EventListener);
    window.addEventListener('plugin-discovery-error', handleDiscoveryError as EventListener);

    return () => {
      window.removeEventListener('plugin-storage-warning', handleStorageWarning as EventListener);
      window.removeEventListener('plugin-storage-error', handleStorageError as EventListener);
      window.removeEventListener('plugin-initialized', handlePluginInitialized as EventListener);
      window.removeEventListener('plugin-initialization-failed', handlePluginInitializationFailed as EventListener);
      window.removeEventListener('plugin-discovery-warnings', handleDiscoveryWarnings as EventListener);
      window.removeEventListener('plugin-discovery-refreshed', handleDiscoveryRefreshed as EventListener);
      window.removeEventListener('plugin-discovery-error', handleDiscoveryError as EventListener);
    };
  }, [plugins, t]);


  const handleRefreshDiscovery = async () => {
    setIsRefreshing(true);
    try {
      await refreshPluginDiscovery();
    } catch (error) {
      console.error('Failed to refresh plugin discovery:', error);
    } finally {
      setIsRefreshing(false);
    }
  };

  const handleUninstall = async (pluginId: string) => {
    await pluginApi.uninstallPlugin(pluginId);
    await refreshPluginDiscovery();
  };

  const handleReinstall = async (pluginId: string, options?: { githubToken?: string; gitUrl?: string; ref?: string }): Promise<string> => {
    const { job_id } = await pluginApi.reinstallPlugin(pluginId, options);
    return job_id;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center p-8">
        <Loader2 className="w-8 h-8 animate-spin" />
        <span className="ml-2">{t('plugins.loading')}</span>
      </div>
    );
  }

  const checkPluginLicense = (plugin: Plugin) => {
    const isGlobalLicenseExpired = licenseStatus?.is_license_expired || isFeatureExpired('plugin_management');

    if (isGlobalLicenseExpired) {
      return {
        canToggle: false,
        isExpired: true
      };
    }

    if (!plugin.requiresLicense) {
      return { canToggle: true };
    }

    // Check if the plugin feature is enabled (has valid license)
    const hasLicense = isFeatureEnabled(plugin.id);

    // Check if the plugin feature was previously licensed but is now expired
    const isExpired = isFeatureExpired(plugin.id);

    if (!hasLicense) {
      let licenseMessage = t('plugins.this_plugin_requires_license', { licenseType: plugin.requiresLicense });

      if (isExpired) {
        licenseMessage = '';
      } else {
        licenseMessage = t('plugins.license_renewal_message', { licenseType: plugin.requiresLicense });
      }

      return {
        canToggle: false,
        licenseMessage,
        isExpired
      };
    }

    return { canToggle: true };
  };



  const filteredPlugins = searchQuery.trim()
    ? plugins.filter(p => {
        const q = searchQuery.toLowerCase();
        return (
          p.name.toLowerCase().includes(q) ||
          (p.description && p.description.toLowerCase().includes(q)) ||
          (p.category && p.category.toLowerCase().includes(q)) ||
          (p.author && p.author.toLowerCase().includes(q))
        );
      })
    : plugins;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-medium">{t('plugins.title')}</h3>
          <p className="text-sm text-muted-foreground">
            {t('plugins.description')}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {isAdmin && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => setIsAccessModalOpen(true)}
              className="flex items-center gap-2 border-primary/20 hover:bg-primary/5"
            >
              <ArrowRightLeft className="w-4 h-4 text-primary" />
              Manage Data Access
            </Button>
          )}
          {isAdmin && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => setIsInstallModalOpen(true)}
              className="flex items-center gap-2 border-blue-200 hover:bg-blue-50 text-blue-700"
            >
              <GitBranch className="w-4 h-4" />
              Install from Git
            </Button>
          )}
          <Button
            variant="outline"
            size="sm"
            onClick={handleRefreshDiscovery}
            disabled={isRefreshing || loading}
            className="flex items-center gap-2"
          >
            <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin' : ''}`} />
            {t('plugins.refresh_plugins')}
          </Button>
        </div>
      </div>

      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
        <Input
          placeholder={t('plugins.search_placeholder', 'Search plugins...')}
          value={searchQuery}
          onChange={e => setSearchQuery(e.target.value)}
          className="pl-9 pr-9"
        />
        {searchQuery && (
          <button
            className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
            onClick={() => setSearchQuery('')}
            aria-label="Clear search"
          >
            <X className="w-4 h-4" />
          </button>
        )}
      </div>

      {/* Discovery Errors Alert */}
      {discoveryErrors.length > 0 && (
        <Alert className="border-amber-200 bg-amber-50">
          <Info className="h-4 w-4 text-amber-600" />
          <AlertDescription className="text-amber-800">
            <strong>{t('plugins.discovery_issues')}</strong>
            <ul className="mt-2 list-disc list-inside text-sm">
              {discoveryErrors.map((error, index) => (
                <li key={index}>{error}</li>
              ))}
            </ul>
          </AlertDescription>
        </Alert>
      )}

      {/* Storage Error Alert */}
      {storageError && (
        <Alert className="border-amber-200 bg-amber-50">
          <Info className="h-4 w-4 text-amber-600" />
          <AlertDescription className="text-amber-800">
            <strong>{t('plugins.storage_issue')}</strong> {storageError}
            <br />
            {t('plugins.storage_warning')}
          </AlertDescription>
        </Alert>
      )}

      {!isAdmin && (
        <Alert className="border-red-200 bg-red-50">
          <Shield className="h-4 w-4 text-red-600" />
          <AlertDescription className="text-red-800">
            <strong>{t('plugins.administrator_access_required')}:</strong> {t('plugins.plugin_management_restricted')}
          </AlertDescription>
        </Alert>
      )}


      <div className="grid gap-4">
        {filteredPlugins.map(plugin => {
          const licenseCheck = checkPluginLicense(plugin);
          const { canToggle, licenseMessage, isExpired } = licenseCheck;

          return (
            <div key={plugin.id} className={isExpired ? 'opacity-75' : ''}>
              <PluginCard
                plugin={plugin}
                onToggle={togglePlugin}
                onUninstall={isAdmin ? handleUninstall : undefined}
                onReinstall={isAdmin && plugin.is_external ? handleReinstall : undefined}
                canToggle={canToggle && isAdmin}
                licenseMessage={licenseMessage}
                isAdmin={isAdmin}
                isExpired={isExpired}
              />
            </div>
          );
        })}
      </div>

      {filteredPlugins.length === 0 && (
        <div className="text-center py-8">
          <Puzzle className="w-12 h-12 text-gray-400 mx-auto mb-4" />
          {searchQuery ? (
            <>
              <h3 className="text-lg font-medium text-gray-900 mb-2">{t('plugins.no_search_results', 'No plugins match your search')}</h3>
              <p className="text-gray-600">{t('plugins.try_different_search', 'Try a different keyword or clear the search.')}</p>
            </>
          ) : (
            <>
              <h3 className="text-lg font-medium text-gray-900 mb-2">{t('plugins.no_plugins_available')}</h3>
              <p className="text-gray-600">{t('plugins.no_plugins_installed')}</p>
            </>
          )}
        </div>
      )}

      <PluginAccessModal
        open={isAccessModalOpen}
        onOpenChange={setIsAccessModalOpen}
        isAdmin={isAdmin}
      />

      <InstallPluginModal
        open={isInstallModalOpen}
        onOpenChange={setIsInstallModalOpen}
        onInstalled={async () => {
          await refreshPluginDiscovery();
          toast.info('Plugin installed — restart the server to activate it.');
        }}
      />
    </div>
  );
};
