import { useEffect, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTheme } from "@/components/ui/theme-provider";
import { authApi } from "@/lib/api";
import { isAuthenticated } from "@/utils/auth";

/**
 * Applies the authenticated user's saved theme preference once after login,
 * giving cross-device sync. Renders nothing.
 *
 * Important: this calls the RAW provider `setTheme` (local apply only) — never
 * the persisting `useThemePreference`, so pulling the server value does not
 * echo a redundant write back to the backend. The pull happens once per
 * mount/login (guarded by a ref); after that, the local choice wins so an
 * in-session theme change is not clobbered by a background user refetch.
 */
export function ThemeSync() {
  const { setTheme } = useTheme();
  const appliedRef = useRef(false);

  const { data: user } = useQuery({
    queryKey: ["currentUser"],
    queryFn: () => authApi.getCurrentUser(),
    enabled: isAuthenticated(),
    staleTime: 5 * 60 * 1000,
  });

  useEffect(() => {
    if (appliedRef.current) return;
    const serverTheme = user?.theme;
    if (!serverTheme) return;

    appliedRef.current = true;
    // setTheme validates against the registry and falls back if unknown.
    setTheme(serverTheme);
  }, [user, setTheme]);

  return null;
}
