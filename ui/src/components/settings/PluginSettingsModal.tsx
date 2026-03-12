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
import { Loader2, Settings } from 'lucide-react';
import { toast } from 'sonner';
import { pluginApi } from '@/lib/api';

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

  useEffect(() => {
    if (open) {
      loadConfig();
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

  const handleSave = async () => {
    setSaving(true);
    try {
      await pluginApi.updatePluginConfig(pluginId, config);
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

        <div className="py-4">
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="w-6 h-6 animate-spin" />
            </div>
          ) : (
            renderConfigForm()
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
