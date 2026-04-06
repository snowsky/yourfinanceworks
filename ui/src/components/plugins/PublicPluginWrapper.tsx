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
  public_page: { path: string; label: string; ui_entry?: string } | null;
}

interface Props {
  pluginId: string;
  /** For in-process plugins: pass children. */
  children?: React.ReactNode;
  /** For sidecar plugins: pass the iframe URL directly. */
  iframeUrl?: string;
}

export function PublicPluginWrapper({ pluginId, children, iframeUrl }: Props) {
  const navigate = useNavigate();
  const location = useLocation();
  const [config, setConfig] = useState<PublicAccessConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Extract the explicit tenant ID from the URL (used for sharing single-domain installations across multiple orgs)
    const searchParams = new URLSearchParams(location.search);
    const explicitTenantId = searchParams.get('t') || undefined;

    pluginApi
      .getPluginPublicConfig(pluginId, explicitTenantId)
      .then((data) => {
        setConfig(data);
        setLoading(false);
      })
      .catch(() => {
        setError('Could not load page configuration.');
        setLoading(false);
      });
  }, [pluginId]);

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

  if (config.require_login) {
    const user = localStorage.getItem('user');
    if (!user) {
      // Redirect to login with a return URL
      navigate(`/login?redirect=${encodeURIComponent(location.pathname + location.search)}`, {
        replace: true,
      });
      return null;
    }
  }

  // Sidecar: render via iframe (explicit prop takes priority; fall back to manifest ui_entry)
  const resolvedIframeUrl = iframeUrl ?? config.public_page?.ui_entry ?? undefined;
  if (resolvedIframeUrl) {
    return (
      <iframe
        src={resolvedIframeUrl}
        style={{ width: '100%', height: 'calc(100vh - 4rem)', border: 'none' }}
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
