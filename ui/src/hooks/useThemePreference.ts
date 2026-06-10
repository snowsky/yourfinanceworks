import { useCallback } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useTheme, type ThemeId } from "@/components/ui/theme-provider";
import { setPendingTheme, clearPendingTheme } from "@/components/ui/theme-sync-state";
import { authApi } from "@/lib/api";
import { isAuthenticated, updateCurrentUser } from "@/utils/auth";

/**
 * Theme hook with backend persistence.
 *
 * Wraps the local `useTheme()` so a theme change is applied instantly (and to
 * localStorage) AND saved to the user's profile via `PUT /auth/me`, giving
 * cross-device sync. The backend write is fire-and-forget: the local apply has
 * already happened, so a failed/absent network call never blocks the UI.
 *
 * When the user is not authenticated (e.g. the Login/Signup pages also render
 * the theme switcher) the backend call is skipped — the choice lives only in
 * localStorage until they sign in, at which point ThemeSync reconciles it.
 */
export function useThemePreference() {
  const ctx = useTheme();
  const queryClient = useQueryClient();

  const setTheme = useCallback(
    (id: ThemeId) => {
      // Instant local apply + persist to localStorage.
      ctx.setTheme(id);

      if (!isAuthenticated()) return;

      // Optimistically reflect the change in cached user data so other
      // consumers (and ThemeSync) see it immediately, then persist.
      updateCurrentUser({ theme: id });
      queryClient.setQueryData(["currentUser"], (old: unknown) =>
        old && typeof old === "object" ? { ...old, theme: id } : old
      );

      // Mark this choice as not-yet-confirmed by the server. If a reload aborts
      // the PUT below before it lands, the marker survives so ThemeSync keeps the
      // local choice (and re-pushes it) instead of reverting to a stale server read.
      setPendingTheme(id);
      authApi
        .updateCurrentUser({ theme: id })
        .then(() => clearPendingTheme(id))
        .catch(() => {
          // Keep the pending marker: local + localStorage stay authoritative and
          // ThemeSync reconciles the server on the next load. Nothing actionable here.
        });
    },
    [ctx, queryClient]
  );

  return { ...ctx, setTheme };
}
