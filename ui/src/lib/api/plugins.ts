import { apiRequest } from './_base';

// Plugin Management API
export const pluginApi = {
  getPluginConfig: (pluginId: string) => {
    return apiRequest<{ plugin_id: string; config: Record<string, any> }>(`/plugins/settings/${pluginId}/config`);
  },

  updatePluginConfig: (pluginId: string, config: Record<string, any>) => {
    return apiRequest<{ plugin_id: string; config: Record<string, any>; message: string }>(`/plugins/settings/${pluginId}/config`, {
      method: 'PUT',
      body: JSON.stringify({ config }),
    });
  },
};
