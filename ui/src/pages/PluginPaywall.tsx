import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { apiRequest } from '@/lib/api/_base';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { toast } from 'sonner';
import { Loader2, Lock } from 'lucide-react';

interface PluginPaywallProps {
  pluginId: string;
  tenantId?: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function PluginPaywall({ pluginId, tenantId, open, onOpenChange }: PluginPaywallProps) {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(false);

  const handleCheckout = async () => {
    const tokenKey = `plugin_token_${pluginId}`;
    const tokenStr = localStorage.getItem(tokenKey);
    let resolvedTenantId = tenantId;
    let tokenData: any = null;

    if (tokenStr) {
      try {
        tokenData = JSON.parse(tokenStr);
        if (!resolvedTenantId) resolvedTenantId = tokenData.tenant_id?.toString();
      } catch {}
    }

    if (!resolvedTenantId) {
      toast.error('Tenant ID required.');
      return;
    }

    if (!tokenData) {
      toast.error("Not authenticated");
      return;
    }

    setLoading(true);
    try {
      const session = await apiRequest<{ checkout_url: string }>(`/plugins/${pluginId}/public-paywall/checkout`, {
        method: 'POST',
        body: JSON.stringify({ tenant_id: parseInt(resolvedTenantId, 10), plugin_user_id: tokenData.user.id })
      });
      window.location.href = session.checkout_url;
    } catch (err: any) {
      toast.error(err.message || 'Checkout failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog 
      open={open} 
      onOpenChange={onOpenChange}
      // Force the modal to stay open if it's the only way to access the plugin
      modal={true}
    >
      <DialogContent 
        className="sm:max-w-md text-center"
        // Prevent closing by clicking outside if we want to force the paywall
        onPointerDownOutside={(e) => e.preventDefault()}
        onEscapeKeyDown={(e) => e.preventDefault()}
      >
        <DialogHeader>
          <div className="mx-auto mb-4 bg-primary/10 p-3 rounded-full w-12 h-12 flex items-center justify-center">
            <Lock className="w-6 h-6 text-primary" />
          </div>
          <DialogTitle className="text-2xl text-center">
            {t('plugins.paywall.title', 'Premium Feature')}
          </DialogTitle>
          <DialogDescription className="text-center pt-2">
            {t('plugins.paywall.description', 'This plugin has reached the free usage limit. Subscribe to unlock full access.')}
          </DialogDescription>
        </DialogHeader>
        
        <div className="py-6">
          <div className="bg-muted/50 rounded-lg p-4 mb-6">
            <h4 className="font-semibold text-sm mb-1">{t('plugins.paywall.why_upgrade', 'Why Upgrade?')}</h4>
            <p className="text-xs text-muted-foreground italic">
              {t('plugins.paywall.why_upgrade_desc', 'Unlock advanced tools, priority support, and unlimited interactions.')}
            </p>
          </div>
          
          <Button onClick={handleCheckout} className="w-full text-lg h-12" disabled={loading}>
            {loading && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
            {t('plugins.paywall.subscribe', 'Unlock Full Access')}
          </Button>
          
          <p className="text-[10px] text-muted-foreground mt-4 text-center">
            {t('plugins.paywall.secure_stripe', 'Payments are securely processed via Stripe')}
          </p>
        </div>
      </DialogContent>
    </Dialog>
  );
}
