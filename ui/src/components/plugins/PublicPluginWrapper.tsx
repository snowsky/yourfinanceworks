/**
 * PublicPluginWrapper
 *
 * Every plugin can expose a shareable public URL at `/p/{pluginId}/`.
 * Example: https://demo.yourfinanceworks.com/p/socialhub
 *
 * The URL namespace `/p/` stands for "public plugin portal". Tenants control
 * access per-plugin in Settings → Plugins → Configure → Public Access:
 *   - disabled (default) → shows "page not available"
 *   - enabled + require_login: true  → unauthenticated visitors are redirected
 *     to /login and returned here after signing in
 *   - enabled + require_login: false → accessible to anyone without login
 *
 * The public page path is declared by each plugin in its plugin.json manifest:
 *   "public_page": { "path": "/p/socialhub", "ui_entry": "/plugins/socialhub/public/" }
 *
 * Plugin types:
 *   - In-process plugins (e.g. yfw-surveys): export a React component as
 *     `publicPage` from plugin/ui/index.ts — rendered as children
 *   - Sidecar plugins (e.g. yfw-socialhub): declare a `ui_entry` URL in
 *     plugin.json — rendered as an iframe
 *
 * Tenant resolution (for unauthenticated visitors):
 *   The tenant is identified from the Host header subdomain on the backend
 *   (e.g. demo.yourfinanceworks.com → subdomain "demo"). No login is needed
 *   to check whether a public page is enabled.
 */
import React, { useEffect, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { pluginApi } from '@/lib/api/plugins';

interface PublicAccessConfig {
  enabled: boolean;
  require_login: boolean;
  stripe_price_id?: string | null;
  public_page: { path: string; label: string; ui_entry?: string } | null;
}

interface Props {
  pluginId: string;
  /** For in-process plugins: pass children. */
  children?: React.ReactNode;
  /** For sidecar plugins: pass the iframe URL directly. */
  iframeUrl?: string;
}

import { PluginAuth } from '@/pages/PluginAuth';
import { PluginPaywall } from '@/pages/PluginPaywall';
import { apiRequest } from '@/lib/api/_base';

export function PublicPluginWrapper({ pluginId, children, iframeUrl }: Props) {
  const navigate = useNavigate();
  const location = useLocation();
  const [config, setConfig] = useState<PublicAccessConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [needsAuth, setNeedsAuth] = useState(false);
  const [needsPayment, setNeedsPayment] = useState(false);
  
  const searchParams = new URLSearchParams(location.search);
  const explicitTenantId = searchParams.get('t') || undefined;

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
      const tokenStr = localStorage.getItem(`plugin_token_${pluginId}`);
      if (!tokenStr) {
        setNeedsAuth(true);
        setLoading(false);
        return;
      }
      
      const tokenData = JSON.parse(tokenStr);

      if (cfg.stripe_price_id) {
        try {
          const res = await apiRequest<{is_paid: boolean}>(`/plugins/${pluginId}/public-paywall/status`, {
            method: 'POST',
            body: JSON.stringify({
               tenant_id: parseInt(explicitTenantId || String(tokenData.tenant_id), 10),
               plugin_user_id: tokenData.user.id
            })
          });
          if (!res.is_paid) {
            setNeedsPayment(true);
          }
        } catch (err) {
          console.error("Paywall check failed", err);
          setNeedsPayment(true);
        }
      }
    }
    setLoading(false);
  };

  const handleAuthenticated = () => {
     setNeedsAuth(false);
     setLoading(true);
     if (config) {
       checkAccess(config);
     }
  };

  const handlePaymentSuccess = () => {
     setNeedsPayment(false);
     setLoading(true);
     if (config) {
       checkAccess(config);
     }
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh' }}>
        <div style={{ color: '#6b7280', fontSize: 14 }}>Loading…</div>
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

  if (needsPayment) {
    return <PluginPaywall pluginId={pluginId} tenantId={explicitTenantId} onPaymentSuccess={handlePaymentSuccess} />;
  }

  // Sidecar: render via iframe (explicit prop takes priority; fall back to manifest ui_entry)
  const resolvedIframeUrl = iframeUrl ?? config.public_page?.ui_entry ?? undefined;
  if (resolvedIframeUrl) {
    return (
      <iframe
        src={resolvedIframeUrl}
        style={{ width: '100%', height: '100vh', border: 'none' }}
        title={pluginId}
      />
    );
  }

  // In-process: render children
  return <>{children}</>;
}

function UnavailableMessage({ message }: { message: string }) {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100vh',
        gap: 12,
        color: '#6b7280',
        fontFamily: 'system-ui, sans-serif',
      }}
    >
      <div style={{ fontSize: 32 }}>🔒</div>
      <div style={{ fontSize: 16, fontWeight: 500 }}>{message}</div>
    </div>
  );
}
