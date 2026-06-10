import { describe, it, expect, afterEach, vi, beforeEach } from "vitest";
import { render, cleanup, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ThemeProvider } from "@/components/ui/theme-provider";
import { ThemeSync } from "@/components/ui/ThemeSync";
import {
  setPendingTheme,
  getPendingTheme,
  clearPendingTheme,
} from "@/components/ui/theme-sync-state";

const getCurrentUser = vi.fn();
const updateCurrentUser = vi.fn((_data?: unknown) => Promise.resolve({}));

vi.mock("@/lib/api", () => ({
  authApi: {
    getCurrentUser: () => getCurrentUser(),
    updateCurrentUser: (data: unknown) => updateCurrentUser(data),
  },
}));

vi.mock("@/utils/auth", () => ({
  isAuthenticated: () => true,
}));

const STORAGE_KEY = "invoice-app-theme";

// The global test setup stubs localStorage with a non-persisting mock; these
// tests exercise real round-tripping (the pending marker), so install a working
// in-memory localStorage and a matchMedia stub for this file only.
beforeEach(() => {
  const store = new Map<string, string>();
  Object.defineProperty(window, "localStorage", {
    configurable: true,
    writable: true,
    value: {
      getItem: (k: string) => (store.has(k) ? store.get(k)! : null),
      setItem: (k: string, v: string) => void store.set(k, String(v)),
      removeItem: (k: string) => void store.delete(k),
      clear: () => store.clear(),
      key: (i: number) => Array.from(store.keys())[i] ?? null,
      get length() {
        return store.size;
      },
    },
  });
  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    writable: true,
    value: () => ({
      matches: false,
      addEventListener: () => {},
      removeEventListener: () => {},
    }),
  });
});

function renderSync() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <ThemeProvider defaultTheme="system" storageKey={STORAGE_KEY}>
        <ThemeSync />
      </ThemeProvider>
    </QueryClientProvider>
  );
}

describe("theme-sync-state pending marker", () => {
  afterEach(() => localStorage.clear());

  it("stores and reads the pending theme", () => {
    setPendingTheme("dark");
    expect(getPendingTheme()).toBe("dark");
  });

  it("clears unconditionally with no id", () => {
    setPendingTheme("dark");
    clearPendingTheme();
    expect(getPendingTheme()).toBeNull();
  });

  it("only clears when the id still matches (newer pick wins)", () => {
    setPendingTheme("dark");
    setPendingTheme("premium-dark"); // a newer pick supersedes
    clearPendingTheme("dark"); // a late confirmation for the old pick
    expect(getPendingTheme()).toBe("premium-dark");
  });
});

describe("ThemeSync reload race", () => {
  beforeEach(() => {
    getCurrentUser.mockReset();
    updateCurrentUser.mockReset();
    updateCurrentUser.mockResolvedValue({});
  });

  afterEach(() => {
    cleanup();
    localStorage.clear();
    document.documentElement.className = "";
  });

  it("does NOT clobber a pending local choice with a stale server value, and re-pushes it", async () => {
    // Simulate a reload right after picking 'dark': localStorage already holds
    // 'dark', the pending marker is set, but the server still returns 'light'
    // because the persisting PUT was aborted by the reload.
    localStorage.setItem(STORAGE_KEY, "dark");
    setPendingTheme("dark");
    getCurrentUser.mockResolvedValue({ theme: "light" });

    renderSync();

    await waitFor(() => expect(getCurrentUser).toHaveBeenCalled());
    // The local choice survives: <html> stays dark, never flips to light.
    await waitFor(() =>
      expect(document.documentElement.classList.contains("dark")).toBe(true)
    );
    expect(document.documentElement.classList.contains("light")).toBe(false);
    // And the interrupted write is reconciled by re-pushing the pending theme.
    await waitFor(() =>
      expect(updateCurrentUser).toHaveBeenCalledWith({ theme: "dark" })
    );
    // Re-push succeeded → pending marker cleared.
    await waitFor(() => expect(getPendingTheme()).toBeNull());
  });

  it("applies the server value when there is no pending local choice (cross-device sync)", async () => {
    localStorage.setItem(STORAGE_KEY, "light");
    getCurrentUser.mockResolvedValue({ theme: "premium-dark" });

    renderSync();

    await waitFor(() =>
      expect(
        document.documentElement.classList.contains("theme-premium-dark")
      ).toBe(true)
    );
    expect(document.documentElement.classList.contains("dark")).toBe(true);
    // No reconciling PUT needed when nothing was pending.
    expect(updateCurrentUser).not.toHaveBeenCalled();
  });
});
