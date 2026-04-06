/**
 * PublicPluginWrapper
 *
 * Wraps a plugin's public portal page (`/p/{pluginId}/`) and enforces the
 * tenant's public-access settings before rendering.
 *
 * Access modes (configured in Settings → Plugins → Public Access):
 *   - disabled (default): shows "page not available"
 *   - require_login: true  → redirects unauthenticated visitors to /login
 *   - require_login: false → renders freely for anyone
 *
 * Works for both in-process plugins (renders children) and sidecar plugins
 * (renders an iframe pointing to the sidecar's public UI).
 */
import React, { useEffect, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { pluginApi } from '@/lib/api/plugins';
import { getTenantId } from '@/lib/api/_base';

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
    const tenantId = getTenantId();
    if (!tenantId) {
      // No tenant context at all — treat as disabled
      setConfig({ enabled: false, require_login: true, public_page: null });
      setLoading(false);
      return;
    }

    pluginApi
      .getPluginPublicConfig(pluginId, tenantId)
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

  // Sidecar: render via iframe
  if (iframeUrl) {
    return (
      <iframe
        src={iframeUrl}
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
