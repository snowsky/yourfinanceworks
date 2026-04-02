import { STORAGE_KEYS, USE_STANDALONE_SETUP } from "./config";

export interface SetupConfig {
  apiUrl: string;
  apiKey: string;
}

export function authHeaders(): Record<string, string> {
  if (!USE_STANDALONE_SETUP) return {};
  const apiKey = localStorage.getItem(STORAGE_KEYS.apiKey);
  const apiUrl = localStorage.getItem(STORAGE_KEYS.apiUrl);
  return {
    ...(apiKey ? { "X-API-Key": apiKey } : {}),
    ...(apiUrl ? { "X-YFW-URL": apiUrl } : {}),
  };
}

export function saveSetupConfig(config: SetupConfig): void {
  localStorage.setItem(STORAGE_KEYS.apiUrl, config.apiUrl);
  localStorage.setItem(STORAGE_KEYS.apiKey, config.apiKey);
}

export function loadSetupConfig(): SetupConfig {
  return {
    apiUrl: localStorage.getItem(STORAGE_KEYS.apiUrl) ?? "",
    apiKey: localStorage.getItem(STORAGE_KEYS.apiKey) ?? "",
  };
}
