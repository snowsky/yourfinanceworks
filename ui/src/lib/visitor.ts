const VISITOR_ID_KEY = 'yfw_public_visitor_id';

/**
 * Get or generate a persistent visitor ID for anonymous usage-tracking.
 * Stored in localStorage to persist across browser sessions.
 */
export function getVisitorId(): string {
  if (typeof window === 'undefined') return '';
  
  let id = localStorage.getItem(VISITOR_ID_KEY);
  if (!id) {
    if (typeof crypto !== 'undefined' && crypto.randomUUID) {
      id = crypto.randomUUID();
    } else {
      id = Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 15);
    }
    localStorage.setItem(VISITOR_ID_KEY, id);
  }
  return id || '';
}

/**
 * Extract tenant ID from URL query parameters (e.g., ?t=1).
 */
export function getPublicTenantId(): string | null {
  if (typeof window === 'undefined') return null;
  const params = new URLSearchParams(window.location.search);
  return params.get('t') || params.get('tenantId');
}
