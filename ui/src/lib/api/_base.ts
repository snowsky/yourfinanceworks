import { toast } from 'sonner';

// API base URL comes from env var. Set VITE_API_URL in your environment.
// When running in containers, use nginx proxy on port 8080
export const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1';

// Generic API request function with error handling
export async function apiRequest<T>(
  url: string,
  options: RequestInit = {},
  config: { isLogin?: boolean; skipTenant?: boolean } = {}
): Promise<T> {
  try {
    // Resolve tenant ID from selected tenant or user's default
    let tenantId: string | undefined = undefined;
    try {
      const selectedTenantId = localStorage.getItem('selected_tenant_id');
      if (selectedTenantId) {
        tenantId = selectedTenantId;
      } else {
        const userStr = localStorage.getItem('user');
        if (userStr) {
          const user = JSON.parse(userStr);
          if (user && user.tenant_id) {
            tenantId = String(user.tenant_id);
          }
        }
      }
    } catch (e) {
      console.error('Error parsing user for tenantId:', e);
    }

    const requestUrl = url.startsWith('http') ? url : `${API_BASE_URL}${url}`;
    let extraHeaders: Record<string, string> = {};
    if (options.headers) {
      if (options.headers instanceof Headers) {
        options.headers.forEach((value, key) => { extraHeaders[key] = value; });
      } else if (typeof options.headers === 'object' && !Array.isArray(options.headers)) {
        extraHeaders = options.headers as Record<string, string>;
      }
    }
    const headers: Record<string, string> = { ...extraHeaders };

    // Only set Content-Type for non-FormData requests
    if (!(options.body instanceof FormData)) {
      headers['Content-Type'] = 'application/json';
    }
    if (!config.skipTenant && tenantId) {
      const numericTenantId = parseInt(tenantId, 10);
      if (!isNaN(numericTenantId)) {
        headers['X-Tenant-ID'] = numericTenantId.toString();
      }
    }
    const response = await fetch(requestUrl, {
      ...options,
      headers,
      credentials: 'include',
    });

    // Log the raw response text for debugging
    const responseText = await response.text();

    if (!response.ok) {
      // Try to parse error response
      let errorData;
      try {
        errorData = JSON.parse(responseText);
      } catch (e) {
        // If JSON parsing fails, use status text
        throw new Error(`Error: ${response.status} ${response.statusText}`);
      }

      // Surface plugin cross-access approval requests to the UI layer.
      if (
        response.status === 428 &&
        errorData?.detail &&
        typeof errorData.detail === 'object' &&
        errorData.detail.error_code === 'PLUGIN_ACCESS_APPROVAL_REQUIRED'
      ) {
        window.dispatchEvent(new CustomEvent('plugin-access-approval-required', {
          detail: errorData.detail,
        }));
      }

      // Handle authentication errors
      if (!config.isLogin && response.status === 401) {
        // Don't log out for super-admin endpoints - they might fail for other reasons
        if (!requestUrl.includes('/super-admin/')) {
          // Session expired — clear local user data and redirect to login
          localStorage.removeItem('user');
          localStorage.removeItem('selected_tenant_id');
          // Show toast and redirect to login only if not already on login page
          const isPublicPluginPage = window.location.pathname.startsWith('/p/');
          if (!window.location.pathname.includes('/login') && !isPublicPluginPage) {
            toast.error('Session expired. Please log in again.');
            setTimeout(() => window.location.replace('/login'), 100);
          }
          throw new Error('Authentication failed. Please log in again.');
        } else {
          // For super-admin endpoints, just throw the error without logging out
          throw new Error(errorData.detail || 'Authentication failed');
        }
      }

      // Handle 403 (forbidden) errors - could be permission or tenant context issues
      if (response.status === 403) {
        // Check if it's a tenant context error (but not for super-admin endpoints)
        if (!requestUrl.includes('/super-admin/') && errorData.detail && errorData.detail.includes('Tenant context required')) {
          // This is a session/tenant context issue - log out the user
          localStorage.removeItem('user');
          localStorage.removeItem('selected_tenant_id');
          toast.error('Session expired. Please log in again.');
          window.location.replace('/login');
          throw new Error('Session expired. Please log in again.');
        } else {
          // User is authenticated but lacks permissions - don't log out
          throw new Error(errorData.detail || 'Access denied. You do not have permission to access this resource.');
        }
      }

      // Handle 400 errors that might be tenant context issues
      if (response.status === 400 && errorData.detail && typeof errorData.detail === 'string' && errorData.detail.includes('Tenant context required')) {
        // This is a session/tenant context issue - log out the user (but not for super-admin endpoints)
        if (!requestUrl.includes('/super-admin/')) {
          localStorage.removeItem('user');
          localStorage.removeItem('selected_tenant_id');
          toast.error('Session expired. Please log in again.');
          window.location.replace('/login');
          throw new Error('Session expired. Please log in again.');
        } else {
          // For super-admin endpoints, just throw the error
          throw new Error(errorData.detail || 'Request failed');
        }
      }

      // Determine error message
      let errorMessage = `Error: ${response.status} ${response.statusText}`;

      // Better handle validation errors (422)
      if (response.status === 422 && errorData.detail) {
        // Format validation errors nicely
        if (Array.isArray(errorData.detail)) {
          // Format validation errors from FastAPI
          const errorMessages = errorData.detail.map((err: any) => {
            const field = err.loc.slice(1).join('.');
            return `${field}: ${err.msg}`;
          }).join('; ');

          console.error('Validation error:', errorMessages);
          errorMessage = `Validation error: ${errorMessages}`;
        } else if (typeof errorData.detail === 'object' && errorData.detail !== null) {
          // Handle object error details (e.g., {error: "CODE", message: "text"})
          const message = errorData.detail.message || errorData.detail.error || JSON.stringify(errorData.detail);
          console.error('API error:', errorData.detail);
          errorMessage = message;
        } else {
          // Handle string error details
          console.error('API error:', errorData.detail);
          errorMessage = String(errorData.detail);
        }
      }
      // Handle other errors with object details
      else if (errorData.detail) {
        if (typeof errorData.detail === 'string') {
          errorMessage = errorData.detail;
        } else if (Array.isArray(errorData.detail)) {
          // Handle FastAPI validation errors format
          const validationError = errorData.detail[0];
          if (validationError?.msg) {
            // Extract the actual error message from "Value error, Organization name must be at least 2 characters long"
            errorMessage = validationError.msg.replace('Value error, ', '');
          } else if (validationError?.ctx?.error) {
            errorMessage = validationError.ctx.error;
          } else {
            errorMessage = JSON.stringify(validationError);
          }
        } else if (typeof errorData.detail === 'object' && errorData.detail !== null) {
          // Handle object error details (e.g., {error: "CODE", message: "text"})
          errorMessage = errorData.detail.message || errorData.detail.error || JSON.stringify(errorData.detail);
        } else {
          errorMessage = String(errorData.detail);
        }
      }

      // Throw error with status and response properties
      const error = new Error(errorMessage) as any;
      error.status = response.status;
      error.response = { status: response.status, data: errorData };
      throw error;
    }

    // For DELETE requests with 204 No Content
    if (response.status === 204) {
      return {} as T;
    }

    // Parse the response text as JSON
    let responseData;
    try {
      responseData = JSON.parse(responseText) as T;
    } catch (e) {
      throw new Error('Invalid JSON response from server');
    }

    return responseData;
  } catch (error) {
    console.error('API request failed:', error);
    // const errorMessage = error instanceof Error ? error.message : 'Unknown error';
    // toast.error(`Request failed: ${errorMessage}`);
    throw error;
  }
}

// Helper to get i18n error message from backend error code
export function getErrorMessage(error: any, t: (key: string) => string): string {
  // Check if the error message is a known error code
  if (error?.message) {
    const code = error.message;
    // Try to map to i18n error code
    const i18nMsg = t(`errors.${code}`);
    if (i18nMsg && i18nMsg !== `errors.${code}`) {
      return i18nMsg;
    }
    // Fallback to the original error message if no translation is found
    return code;
  }
  // Fallback to generic error
  return t('errors.unknown_error');
}

// Shared helper — resolves tenant ID from localStorage without duplicating the IIFE everywhere
export function getTenantId(): string | undefined {
  const selected = localStorage.getItem('selected_tenant_id');
  if (selected) return selected;
  try {
    const user = JSON.parse(localStorage.getItem('user') || '{}');
    return user.tenant_id?.toString();
  } catch {
    return undefined;
  }
}

export interface CsvExportDownload {
  blob: Blob;
  filename: string;
}

export const downloadCsvExport = async (
  endpoint: string,
  params: Record<string, string | number | boolean | undefined>
): Promise<CsvExportDownload> => {
  const tenantId = getTenantId();

  const searchParams = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === '') return;
    searchParams.set(key, String(value));
  });

  const headers: Record<string, string> = {};
  if (tenantId) headers['X-Tenant-ID'] = tenantId;

  const queryString = searchParams.toString();
  const response = await fetch(
    `${API_BASE_URL}${endpoint}${queryString ? `?${queryString}` : ''}`,
    { method: 'GET', headers, credentials: 'include' }
  );

  if (!response.ok) {
    const responseText = await response.text();
    try {
      const errorData = JSON.parse(responseText);
      throw new Error(errorData.detail || 'Failed to export CSV');
    } catch {
      throw new Error(responseText || 'Failed to export CSV');
    }
  }

  const contentDisposition = response.headers.get('content-disposition') || '';
  let filename = 'export.csv';
  const filenameMatch = contentDisposition.match(/filename\*=UTF-8''([^;]+)|filename="?([^";]+)"?/i);
  if (filenameMatch) {
    filename = decodeURIComponent((filenameMatch[1] || filenameMatch[2] || '').trim()) || filename;
  }

  const blob = await response.blob();
  return { blob, filename };
};
