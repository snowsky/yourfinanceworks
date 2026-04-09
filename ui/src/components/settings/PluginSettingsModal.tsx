import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Loader2, Settings, Globe, Copy, Check } from 'lucide-react';
import { toast } from 'sonner';
import { pluginApi } from '@/lib/api';
import { getTenantId } from '@/lib/api/_base';

interface PublicAccessState {
  enabled: boolean;
  require_login: boolean;
  stripe_price_id: string | null;
  free_clicks: number;
  publicPagePath: string | null;
}

interface PluginSettingsModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  pluginId: string;
  pluginName: string;
}

export const PluginSettingsModal: React.FC<PluginSettingsModalProps> = ({
  open,
  onOpenChange,
  pluginId,
  pluginName,
}) => {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [config, setConfig] = useState<Record<string, any>>({});
  const [publicAccess, setPublicAccess] = useState<PublicAccessState | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (open) {
      loadConfig();
      loadPublicAccessConfig();
    }
  }, [open, pluginId]);

  const loadConfig = async () => {
    setLoading(true);
    try {
      const response = await pluginApi.getPluginConfig(pluginId);
      setConfig(response.config || {});
    } catch (error) {
      console.error('Failed to load plugin config:', error);
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';

      if (errorMessage.includes('401') || errorMessage.includes('Authentication')) {
        toast.error('Session expired. Please log in again.');
      } else {
        toast.error(`Failed to load plugin settings: ${errorMessage}`);
      }
    } finally {
      setLoading(false);
    }
  };

  const loadPublicAccessConfig = async () => {
    try {
      const response = await pluginApi.getPublicAccessConfig(pluginId);
      if (response.public_page) {
        setPublicAccess({
          enabled: response.enabled,
          require_login: response.require_login,
          stripe_price_id: response.stripe_price_id || null,
          free_clicks: response.free_clicks || 0,
          publicPagePath: response.public_page?.path ?? null,
        });
      } else {
        setPublicAccess(null);
      }
    } catch {
      // Plugin doesn't support public access — silently ignore
      setPublicAccess(null);
    }
  };

  const publicUrl = publicAccess?.publicPagePath
    ? `${window.location.origin}${publicAccess.publicPagePath}?t=${getTenantId() || ''}`
    : null;

  const handleCopyLink = () => {
    if (!publicUrl) return;
    navigator.clipboard.writeText(publicUrl).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await Promise.all([
        pluginApi.updatePluginConfig(pluginId, config),
        publicAccess !== null
          ? pluginApi.updatePublicAccessConfig(pluginId, {
              enabled: publicAccess.enabled,
              require_login: publicAccess.require_login,
              stripe_price_id: publicAccess.stripe_price_id,
              free_clicks: publicAccess.free_clicks,
            })
          : Promise.resolve(),
      ]);
      toast.success('Plugin settings updated successfully');
      onOpenChange(false);
    } catch (error) {
      console.error('Failed to save plugin config:', error);
      toast.error('Failed to save plugin settings');
    } finally {
      setSaving(false);
    }
  };

  const renderInvestmentsConfig = () => {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="space-y-0.5">
            <Label htmlFor="enable-ai-import">
              {t('plugins.investments.enable_ai_import', 'Enable Holdings/Transactions Import with AI')}
            </Label>
            <p className="text-sm text-muted-foreground">
              {t(
                'plugins.investments.ai_import_description',
                'Use AI to extract both holdings and transaction history from uploaded files in a single operation'
              )}
            </p>
          </div>
          <Switch
            id="enable-ai-import"
            checked={config.enable_ai_import || false}
            onCheckedChange={(checked) =>
              setConfig({ ...config, enable_ai_import: checked })
            }
          />

        </div>
      </div>
    );
  };

  const renderConfigForm = () => {
    switch (pluginId) {
      case 'investments':
        return renderInvestmentsConfig();
      default:
        return (
          <p className="text-sm text-muted-foreground">
            {t('plugins.no_settings_available', 'No settings available for this plugin')}
          </p>
        );
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Settings className="w-5 h-5" />
            {t('plugins.configure_plugin', 'Configure Plugin')}: {pluginName}
          </DialogTitle>
          <DialogDescription>
            {t('plugins.configure_description', 'Manage settings and features for this plugin')}
          </DialogDescription>
        </DialogHeader>

        <div className="py-4 space-y-6">
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="w-6 h-6 animate-spin" />
            </div>
          ) : (
            renderConfigForm()
          )}

          {/* Public Access section — only shown when plugin declares a public_page */}
          {publicAccess !== null && (
            <div className="border rounded-lg p-4 space-y-4">
              <div className="flex items-center gap-2 font-medium text-sm">
                <Globe className="w-4 h-4" />
                {t('plugins.public_access.title', 'Public Access')}
              </div>

              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label htmlFor="public-access-enabled">
                    {t('plugins.public_access.enable', 'Enable public link')}
                  </Label>
                  <p className="text-xs text-muted-foreground">
                    {t('plugins.public_access.enable_desc', 'Allow access via a shareable URL')}
                  </p>
                </div>
                <Switch
                  id="public-access-enabled"
                  checked={publicAccess.enabled}
                  onCheckedChange={(checked) =>
                    setPublicAccess({ ...publicAccess, enabled: checked })
                  }
                />
              </div>

              {publicAccess.enabled && (
                <>
                  <div className="flex items-center justify-between">
                    <div className="space-y-0.5">
                      <Label htmlFor="require-login">
                        {t('plugins.public_access.require_login', 'Require login')}
                      </Label>
                      <p className="text-xs text-muted-foreground">
                        {t(
                          'plugins.public_access.require_login_desc',
                          'Visitors must be logged in to access this page',
                        )}
                      </p>
                    </div>
                    <Switch
                      id="require-login"
                      checked={publicAccess.require_login}
                      onCheckedChange={(checked) =>
                        setPublicAccess({ ...publicAccess, require_login: checked })
                      }
                    />
                  </div>

                    <div className="flex items-center justify-between">
                    <div className="space-y-0.5">
                      <Label htmlFor="free-clicks">
                        {t('plugins.public_access.free_clicks', 'Free Clicks Allowed')}
                      </Label>
                      <p className="text-xs text-muted-foreground">
                        {t(
                          'plugins.public_access.free_clicks_desc',
                          'Number of interactions before showing paywall. 0 for immediate.',
                        )}
                      </p>
                    </div>
                    <Input
                      id="free-clicks"
                      type="number"
                      className="w-[100px]"
                      value={publicAccess.free_clicks}
                      onChange={(e) =>
                        setPublicAccess({ ...publicAccess, free_clicks: parseInt(e.target.value) || 0 })
                      }
                      min={0}
                    />
                  </div>

                  <div className="flex items-center justify-between">
                    <div className="space-y-0.5">
                      <Label htmlFor="stripe-price-id">
                        {t('plugins.public_access.stripe_price_id', 'Stripe Price ID')}
                      </Label>
                      <p className="text-xs text-muted-foreground">
                        {t(
                          'plugins.public_access.stripe_price_id_desc',
                          'Optional paywall. Leave empty for free access.',
                        )}
                      </p>
                    </div>
                    <Input
                      id="stripe-price-id"
                      className="w-[200px]"
                      value={publicAccess.stripe_price_id || ''}
                      onChange={(e) =>
                        setPublicAccess({ ...publicAccess, stripe_price_id: e.target.value })
                      }
                      placeholder="price_1..."
                    />
                  </div>

                  {publicUrl && (
                    <div className="flex items-center gap-2 p-2 bg-muted rounded text-xs font-mono break-all">
                      <span className="flex-1">{publicUrl}</span>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="shrink-0 h-6 w-6 p-0"
                        onClick={handleCopyLink}
                      >
                        {copied ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
                      </Button>
                    </div>
                  )}
                </>
              )}

            </div>
          )}
        </div>

        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={saving}>
            {t('common.cancel', 'Cancel')}
          </Button>
          <Button onClick={handleSave} disabled={saving || loading}>
            {saving && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
            {t('common.save', 'Save')}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};
