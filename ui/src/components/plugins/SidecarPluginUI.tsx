import React, { useEffect, useRef } from 'react';
import { apiRequest } from '@/lib/api';

interface SidecarPluginUIProps {
  pluginId: string;
  uiEntry: string;
  title?: string;
}

/**
 * SidecarPluginUI handles the secure authentication handshake for sidecar plugins
 * embedded in the main dashboard.
 * 
 * It listens for the 'PLUGIN_READY' message from the plugin iframe and fetches
 * an authentication token from the host API to securely identify the current user
 * to the sidecar.
 */
export function SidecarPluginUI({ pluginId, uiEntry, title }: SidecarPluginUIProps) {
  const iframeRef = useRef<HTMLIFrameElement>(null);

  const iframeOrigin = uiEntry.startsWith('http')
    ? new URL(uiEntry).origin
    : window.location.origin;

  useEffect(() => {
    const handleMessage = async (event: MessageEvent) => {
      // Only respond to messages from our own iframe, not arbitrary origins
      if (event.source !== iframeRef.current?.contentWindow) return;

      if (event.data?.type === 'PLUGIN_READY' && iframeRef.current) {
        try {
          const response = await apiRequest<{ token: string }>(`/plugins/token/${pluginId}`, {
            method: 'POST'
          });

          if (response && response.token) {
            iframeRef.current.contentWindow?.postMessage(
              { type: 'AUTH_TOKEN', token: response.token },
              iframeOrigin
            );
          }
        } catch (err) {
          console.error(`[SidecarPluginUI] Failed to generate auth token for ${pluginId}:`, err);
        }
      }
    };

    window.addEventListener('message', handleMessage);
    return () => window.removeEventListener('message', handleMessage);
  }, [pluginId, iframeOrigin]);

  return (
    <div style={{ width: '100%', height: 'calc(100vh - 4rem)', overflow: 'hidden' }}>
      <iframe
        ref={iframeRef}
        src={uiEntry}
        style={{ width: '100%', height: '100%', border: 'none' }}
        title={title || pluginId}
      />
    </div>
  );
}
