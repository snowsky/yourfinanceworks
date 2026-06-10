/**
 * Cross-session marker for a theme the user picked locally but whose persisting
 * `PUT /auth/me` has not yet been confirmed by the server.
 *
 * Why this exists: the theme PUT is fire-and-forget, and a full page reload
 * within ~1s of picking both wipes the React Query cache and aborts that
 * in-flight PUT. On the next load `ThemeSync` would then re-pull a *stale*
 * server theme and clobber the just-picked choice. A pending marker in
 * localStorage survives the reload, so `ThemeSync` knows the local value is a
 * newer-but-unconfirmed choice (keep it, re-push it) rather than something the
 * server legitimately changed elsewhere (apply it — cross-device sync).
 */
const PENDING_KEY = "invoice-app-theme-pending";

/** Record a locally-chosen theme as not-yet-confirmed by the server. */
export function setPendingTheme(id: string): void {
  try {
    localStorage.setItem(PENDING_KEY, id);
  } catch {
    // Storage unavailable (private mode / quota); cross-device sync degrades
    // gracefully — worst case the original race can still occur.
  }
}

/** The theme this device chose but hasn't confirmed the server received, or null. */
export function getPendingTheme(): string | null {
  try {
    return localStorage.getItem(PENDING_KEY);
  } catch {
    return null;
  }
}

/**
 * Clear the pending marker. When `id` is given, only clear if it still matches —
 * so a slow confirmation for an older pick doesn't wipe a newer pending choice.
 */
export function clearPendingTheme(id?: string): void {
  try {
    if (id != null && localStorage.getItem(PENDING_KEY) !== id) return;
    localStorage.removeItem(PENDING_KEY);
  } catch {
    // Nothing actionable.
  }
}
