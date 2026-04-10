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

  useEffect(() => {
    const handleMessage = async (event: MessageEvent) => {
      // Security: For sidecar plugins, we expect PLUGIN_READY to start the handshake
      if (event.data?.type === 'PLUGIN_READY' && iframeRef.current) {
        try {
          // Fetch a fresh plugin-specific token for the current dashboard user
          const response = await apiRequest<{ token: string }>(`/plugins/token/${pluginId}`, {
            method: 'POST'
          });

          if (response && response.token) {
            // Securely post the token back to the plugin iframe
            iframeRef.current.contentWindow?.postMessage({
              type: 'AUTH_TOKEN',
              token: response.token
            }, '*'); // In production, replace '*' with the actual plugin origin if known
          }
        } catch (err) {
          console.error(`[SidecarPluginUI] Failed to generate auth token for ${pluginId}:`, err);
        }
      }
    };

    window.addEventListener('message', handleMessage);
    return () => window.removeEventListener('message', handleMessage);
  }, [pluginId]);

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
