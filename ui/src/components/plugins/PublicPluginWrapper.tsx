/**
 * PublicPluginWrapper
 *
 * Every plugin can expose a shareable public URL at `/p/{pluginId}/`.
 * Example: https://demo.yourfinanceworks.com/p/socialhub
 *
 * Refined Click Counting & Paywall:
 * - Configurable free click limit.
 * - Floating modal paywall (Dialog) instead of full-page redirect.
 */
import React, { useEffect, useState, useCallback, useRef } from 'react';
import { useLocation } from 'react-router-dom';
import { pluginApi } from '@/lib/api/plugins';
import { PluginAuth } from '@/pages/PluginAuth';
import { PluginPaywall } from '@/pages/PluginPaywall';
import { apiRequest } from '@/lib/api/_base';
import { toast } from 'sonner';

interface PublicAccessConfig {
  enabled: boolean;
  require_login: boolean;
  stripe_price_id?: string | null;
  free_clicks: number;
  public_page: { path: string; label: string; ui_entry?: string } | null;
}

interface PaywallStatus {
  is_paid: boolean;
  usage_count: number;
  free_clicks: number;
  trial_limit_reached: boolean;
}

interface Props {
  pluginId: string;
  /** For in-process plugins: pass children. */
  children?: React.ReactNode;
  /** For sidecar plugins: pass the iframe URL directly. */
  iframeUrl?: string;
}

export function PublicPluginWrapper({ pluginId, children, iframeUrl }: Props) {
  const location = useLocation();
  const [config, setConfig] = useState<PublicAccessConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [needsAuth, setNeedsAuth] = useState(false);
  const [status, setStatus] = useState<PaywallStatus | null>(null);
  const [incrementing, setIncrementing] = useState(false);
  
  const searchParams = new URLSearchParams(location.search);
  const explicitTenantId = searchParams.get('t') || undefined;
  
  const iframeRef = useRef<HTMLIFrameElement>(null);

  useEffect(() => {
    pluginApi
      .getPluginPublicConfig(pluginId, explicitTenantId)
      .then((data) => {
        setConfig(data);
        checkAccess(data);
      })
      .catch(() => {
        setError('Could not load page configuration.');
        setLoading(false);
      });
  }, [pluginId, explicitTenantId]);

  const checkAccess = async (cfg: PublicAccessConfig) => {
    if (!cfg.enabled) {
      setLoading(false);
      return;
    }

    if (cfg.require_login) {
      const tokenKey = `plugin_token_${pluginId}`;
      const tokenStr = localStorage.getItem(tokenKey);
      if (!tokenStr) {
        setNeedsAuth(true);
        setLoading(false);
        return;
      }
      
      const tokenData = JSON.parse(tokenStr);

      if (cfg.stripe_price_id) {
        try {
          const res = await apiRequest<PaywallStatus>(`/plugins/${pluginId}/public-paywall/status`, {
            method: 'POST',
            body: JSON.stringify({
               tenant_id: parseInt(explicitTenantId || String(tokenData.tenant_id), 10),
               plugin_user_id: tokenData.user.id
            })
          });
          setStatus(res);
        } catch (err) {
          console.error("Paywall check failed", err);
        }
      }
    }
    setLoading(false);
  };

  const handleIncrementUsage = useCallback(async () => {
    if (!status || status.is_paid || incrementing) return;
    
    const tokenKey = `plugin_token_${pluginId}`;
    const tokenStr = localStorage.getItem(tokenKey);
    if (!tokenStr) return;
    const tokenData = JSON.parse(tokenStr);

    setIncrementing(true);
    try {
      const res = await apiRequest<{ usage_count: number }>(`/plugins/${pluginId}/public-paywall/increment-usage`, {
        method: 'POST',
        body: JSON.stringify({
          tenant_id: parseInt(explicitTenantId || String(tokenData.tenant_id), 10),
          plugin_user_id: tokenData.user.id
        })
      });
      
      const newUsage = res.usage_count;
      setStatus(prev => prev ? ({
        ...prev, 
        usage_count: newUsage,
        trial_limit_reached: prev.free_clicks > 0 && newUsage >= prev.free_clicks
      }) : null);
    } catch (err) {
      console.error("Failed to increment usage", err);
    } finally {
      // Small debounce
      setTimeout(() => setIncrementing(false), 500);
    }
  }, [pluginId, explicitTenantId, status, incrementing]);

  // Handle clicks on In-process plugins
  const handleWrapperClick = () => {
    handleIncrementUsage();
  };

  // Handle Focus (clicks) on Sidecar iframes
  useEffect(() => {
    const handleBlur = () => {
      if (document.activeElement === iframeRef.current) {
        handleIncrementUsage();
      }
    };
    window.addEventListener('blur', handleBlur);
    return () => window.removeEventListener('blur', handleBlur);
  }, [handleIncrementUsage]);

  const handleAuthenticated = () => {
     setNeedsAuth(false);
     setLoading(true);
     if (config) {
       checkAccess(config);
     }
  };

  const handleModalOpenChange = (open: boolean) => {
    // Prevent closing if limit reached and not paid
    if (!open && status?.trial_limit_reached && !status?.is_paid) {
       toast.error("Please upgrade to continue using this plugin.");
       return;
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen bg-background">
        <div className="text-sm text-muted-foreground animate-pulse">Loading plugin...</div>
      </div>
    );
  }

  if (error) {
    return <UnavailableMessage message={error} />;
  }

  if (!config?.enabled) {
    return <UnavailableMessage message="This page is not publicly available." />;
  }

  if (needsAuth) {
    return <PluginAuth pluginId={pluginId} tenantId={explicitTenantId} onAuthenticated={handleAuthenticated} />;
  }

  const resolvedIframeUrl = iframeUrl ?? config.public_page?.ui_entry ?? undefined;
  
  return (
    <div 
      className="relative w-full h-full min-h-screen" 
      onClickCapture={handleWrapperClick}
    >
      {resolvedIframeUrl ? (
        <iframe
          ref={iframeRef}
          src={resolvedIframeUrl}
          className="w-full h-screen border-none"
          title={pluginId}
        />
      ) : (
        children
      )}

      {/* Paywall Modal */}
      {status && config?.stripe_price_id && (
        <PluginPaywall 
          pluginId={pluginId} 
          tenantId={explicitTenantId} 
          open={status.trial_limit_reached && !status.is_paid}
          onOpenChange={handleModalOpenChange}
        />
      )}
    </div>
  );
}

function UnavailableMessage({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center justify-center h-screen gap-4 text-muted-foreground">
      <div className="text-4xl">🔒</div>
      <div className="text-lg font-medium">{message}</div>
    </div>
  );
}
