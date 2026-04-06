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
import { pluginApi, type PublicPluginConfig } from '@/lib/api/plugins';

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
  const [config, setConfig] = useState<PublicPluginConfig | null>(null);
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
  }, [pluginId, location.search]);

  useEffect(() => {
    if (!config?.enabled || config.billing?.payment_required) {
      return;
    }

    const searchParams = new URLSearchParams(location.search);
    const explicitTenantId = searchParams.get('t') || undefined;

    const recordUsage = async (endpointKey: string, quantity = 1) => {
      try {
        const billing = await pluginApi.recordPublicUsage(pluginId, {
          tenantId: explicitTenantId,
          endpointKey,
          quantity,
        });
        setConfig((current) => current ? { ...current, billing } : current);
      } catch {
        // Ignore metering failures to avoid blocking the plugin experience.
      }
    };

    const handleWindowUsage = (event: Event) => {
      const customEvent = event as CustomEvent<{ pluginId?: string; endpointKey?: string; quantity?: number }>;
      if (customEvent.detail?.pluginId && customEvent.detail.pluginId !== pluginId) {
        return;
      }
      recordUsage(customEvent.detail?.endpointKey || 'service_call', customEvent.detail?.quantity || 1);
    };

    const handleMessageUsage = (event: MessageEvent) => {
      const data = event.data;
      if (!data || data.type !== 'plugin-public-usage') {
        return;
      }
      if (data.pluginId && data.pluginId !== pluginId) {
        return;
      }
      recordUsage(data.endpointKey || 'service_call', data.quantity || 1);
    };

    window.addEventListener('plugin-public-usage', handleWindowUsage as EventListener);
    window.addEventListener('message', handleMessageUsage);

    return () => {
      window.removeEventListener('plugin-public-usage', handleWindowUsage as EventListener);
      window.removeEventListener('message', handleMessageUsage);
    };
  }, [config?.enabled, config?.billing?.payment_required, location.search, pluginId]);

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

  if (config.billing?.payment_required) {
    return <PaymentRequiredMessage config={config} />;
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

function PaymentRequiredMessage({ config }: { config: PublicPluginConfig }) {
  const billing = config.billing;
  const title = billing.title || 'Payment required';
  const description = billing.description || 'The free usage quota for this public plugin has been used.';
  const buttonLabel = billing.button_label || 'Continue to payment';

  const usageSummary = billing.free_endpoint_calls < 0
    ? `${billing.usage_count} billable service calls tracked`
    : billing.free_endpoint_calls === 0
      ? 'Payment is required before the first billable service call'
      : `${billing.usage_count} / ${billing.free_endpoint_calls} free service calls used`;

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '2rem',
        background:
          'radial-gradient(circle at top, rgba(59,130,246,0.14), transparent 45%), linear-gradient(180deg, #f8fafc 0%, #eef2ff 100%)',
        fontFamily: 'system-ui, sans-serif',
      }}
    >
      <div
        style={{
          width: '100%',
          maxWidth: 560,
          borderRadius: 24,
          background: 'rgba(255,255,255,0.92)',
          border: '1px solid rgba(148,163,184,0.2)',
          boxShadow: '0 24px 80px rgba(15,23,42,0.12)',
          padding: '2rem',
        }}
      >
        <div style={{ fontSize: 14, fontWeight: 700, color: '#2563eb', letterSpacing: '0.08em', textTransform: 'uppercase' }}>
          {billing.provider || 'Stripe'}
        </div>
        <h1 style={{ marginTop: 12, marginBottom: 12, fontSize: 32, lineHeight: 1.1, color: '#0f172a' }}>{title}</h1>
        <p style={{ margin: 0, fontSize: 16, lineHeight: 1.6, color: '#475569' }}>{description}</p>

        <div
          style={{
            marginTop: 24,
            padding: 16,
            borderRadius: 18,
            background: '#f8fafc',
            border: '1px solid rgba(148,163,184,0.2)',
            display: 'flex',
            justifyContent: 'space-between',
            gap: 16,
            alignItems: 'center',
          }}
        >
          <div>
            <div style={{ fontSize: 13, color: '#64748b', marginBottom: 4 }}>Usage</div>
            <div style={{ fontSize: 16, color: '#0f172a', fontWeight: 600 }}>
              {usageSummary}
            </div>
          </div>
          {billing.price_label && (
            <div style={{ fontSize: 20, fontWeight: 700, color: '#0f172a' }}>{billing.price_label}</div>
          )}
        </div>

        {billing.checkout_url ? (
          <a
            href={billing.checkout_url}
            style={{
              marginTop: 24,
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: '100%',
              padding: '0.95rem 1.25rem',
              borderRadius: 14,
              background: '#0f172a',
              color: '#fff',
              fontWeight: 600,
              textDecoration: 'none',
            }}
          >
            {buttonLabel}
          </a>
        ) : (
          <div style={{ marginTop: 24, color: '#b45309', background: '#fffbeb', border: '1px solid #fde68a', borderRadius: 14, padding: 16 }}>
            Payment is required, but checkout is not configured for this plugin yet.
          </div>
        )}
      </div>
    </div>
  );
}
