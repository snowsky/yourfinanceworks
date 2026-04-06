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
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Loader2, Settings, Globe, Copy, Check, CreditCard } from 'lucide-react';
import { toast } from 'sonner';
import { pluginApi } from '@/lib/api';
import { getTenantId } from '@/lib/api/_base';

interface PublicAccessState {
  enabled: boolean;
  require_login: boolean;
  publicPagePath: string | null;
}

interface BillingState {
  enabled: boolean;
  provider: string;
  free_endpoint_calls: number;
  usage_count: number;
  checkout_url: string;
  price_label: string;
  title: string;
  description: string;
  button_label: string;
  payment_completed: boolean;
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
  const [billing, setBilling] = useState<BillingState | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (open) {
      loadConfig();
      loadPublicAccessConfig();
      loadBillingConfig();
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

  const loadBillingConfig = async () => {
    try {
      const response = await pluginApi.getBillingConfig(pluginId);
      setBilling({
        enabled: response.enabled,
        provider: response.provider || 'stripe',
        free_endpoint_calls: response.free_endpoint_calls || 0,
        usage_count: response.usage_count || 0,
        checkout_url: response.checkout_url || '',
        price_label: response.price_label || '',
        title: response.title || '',
        description: response.description || '',
        button_label: response.button_label || '',
        payment_completed: response.payment_completed || false,
      });
    } catch {
      setBilling(null);
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
            })
          : Promise.resolve(),
        billing !== null
          ? pluginApi.updateBillingConfig(pluginId, billing)
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

          {billing !== null && (
            <div className="border rounded-lg p-4 space-y-4">
              <div className="flex items-center gap-2 font-medium text-sm">
                <CreditCard className="w-4 h-4" />
                Billing & Paywall
              </div>

              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label htmlFor="billing-enabled">Enable paid access</Label>
                  <p className="text-xs text-muted-foreground">
                    After free usage is exhausted, the public page will show a payment prompt.
                  </p>
                </div>
                <Switch
                  id="billing-enabled"
                  checked={billing.enabled}
                  onCheckedChange={(checked) => setBilling({ ...billing, enabled: checked })}
                />
              </div>

              {billing.enabled && (
                <>
                  <div className="grid gap-4 sm:grid-cols-2">
                    <div className="space-y-2">
                      <Label htmlFor="billing-provider">Provider</Label>
                      <Input
                        id="billing-provider"
                        value={billing.provider}
                        onChange={(event) => setBilling({ ...billing, provider: event.target.value || 'stripe' })}
                        placeholder="stripe"
                      />
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="free-endpoint-calls">Free endpoint calls</Label>
                      <Input
                        id="free-endpoint-calls"
                        type="number"
                        min={0}
                        value={billing.free_endpoint_calls}
                        onChange={(event) =>
                          setBilling({
                            ...billing,
                            free_endpoint_calls: Math.max(Number(event.target.value || 0), 0),
                          })
                        }
                      />
                    </div>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="checkout-url">Checkout URL</Label>
                    <Input
                      id="checkout-url"
                      value={billing.checkout_url}
                      onChange={(event) => setBilling({ ...billing, checkout_url: event.target.value })}
                      placeholder="https://buy.stripe.com/..."
                    />
                    <p className="text-xs text-muted-foreground">
                      Paste a Stripe Payment Link or your own checkout route.
                    </p>
                  </div>

                  <div className="grid gap-4 sm:grid-cols-2">
                    <div className="space-y-2">
                      <Label htmlFor="price-label">Price label</Label>
                      <Input
                        id="price-label"
                        value={billing.price_label}
                        onChange={(event) => setBilling({ ...billing, price_label: event.target.value })}
                        placeholder="$19 / month"
                      />
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="button-label">Button label</Label>
                      <Input
                        id="button-label"
                        value={billing.button_label}
                        onChange={(event) => setBilling({ ...billing, button_label: event.target.value })}
                        placeholder="Continue to payment"
                      />
                    </div>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="billing-title">Paywall title</Label>
                    <Input
                      id="billing-title"
                      value={billing.title}
                      onChange={(event) => setBilling({ ...billing, title: event.target.value })}
                      placeholder="Unlock full access"
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="billing-description">Paywall description</Label>
                    <Textarea
                      id="billing-description"
                      value={billing.description}
                      onChange={(event) => setBilling({ ...billing, description: event.target.value })}
                      placeholder="You have used the free quota for this public plugin."
                      rows={3}
                    />
                  </div>

                  <div className="flex items-center justify-between rounded-md bg-muted/40 px-3 py-2 text-sm">
                    <span className="text-muted-foreground">Tracked usage</span>
                    <span className="font-medium">{billing.usage_count}</span>
                  </div>

                  <div className="flex items-center justify-between">
                    <div className="space-y-0.5">
                      <Label htmlFor="payment-completed">Grant paid access</Label>
                      <p className="text-xs text-muted-foreground">
                        Use this to manually unlock the public plugin after payment is confirmed.
                      </p>
                    </div>
                    <Switch
                      id="payment-completed"
                      checked={billing.payment_completed}
                      onCheckedChange={(checked) => setBilling({ ...billing, payment_completed: checked })}
                    />
                  </div>
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
