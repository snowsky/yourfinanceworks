import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { apiRequest } from '@/lib/api/_base';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { toast } from 'sonner';
import { Loader2, Locking } from 'lucide-react';

interface PluginPaywallProps {
  pluginId: string;
  tenantId?: string;
  onPaymentSuccess: () => void;
}

export function PluginPaywall({ pluginId, tenantId, onPaymentSuccess }: PluginPaywallProps) {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(false);

  const handleCheckout = async () => {
    if (!tenantId) {
      toast.error('Tenant ID required');
      return;
    }
    setLoading(true);
    try {
      const tokenKey = `plugin_token_${pluginId}`;
      const tokenStr = localStorage.getItem(tokenKey);
      if (!tokenStr) {
         toast.error("Not authenticated");
         return;
      }
      const tokenData = JSON.parse(tokenStr);
      
      const session = await apiRequest<{checkout_url: string}>(`/plugins/${pluginId}/public-paywall/checkout`, {
        method: 'POST',
        body: JSON.stringify({ tenant_id: parseInt(tenantId, 10), plugin_user_id: tokenData.user.id })
      });
      window.location.href = session.checkout_url;
    } catch (err: any) {
      toast.error(err.message || 'Checkout failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex h-screen w-screen items-center justify-center bg-muted/30">
      <Card className="w-full max-w-md text-center">
        <CardHeader>
          <div className="mx-auto mb-4 bg-primary/10 p-3 rounded-full w-12 h-12 flex items-center justify-center">
             <span className="text-xl">🔒</span>
          </div>
          <CardTitle>
             {t('plugins.paywall.title', 'Premium Feature')}
          </CardTitle>
          <CardDescription>
             {t('plugins.paywall.description', 'Subscribe to access this plugin and unlock new capabilities.')}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Button onClick={handleCheckout} className="w-full" disabled={loading}>
            {loading && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
            {t('plugins.paywall.subscribe', 'Subscribe Now')}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
