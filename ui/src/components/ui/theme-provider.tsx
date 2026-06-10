import React, { createContext, useContext, useEffect, useState } from 'react';

/**
 * Theme system
 * -------------
 * Themes are data-driven via the THEMES registry below. Adding a new theme is
 * a matter of (1) appending an entry here and (2) declaring its CSS-variable
 * block in `index.css`. Nothing else needs to change — the Settings theme
 * picker renders straight from this registry.
 *
 * Each theme declares a `base` ('light' | 'dark') so Tailwind's `dark:`
 * variants keep resolving, plus an optional `className` that layers
 * theme-specific CSS-variable overrides on top of that base.
 */

export type ThemeId =
  | 'light'
  | 'dark'
  | 'system'
  | 'premium-dark'
  | 'terminal'
  | 'amber-terminal'
  | 'sepia';

// Backwards-compatible alias — older code imported `Theme`.
export type Theme = ThemeId;

/**
 * The single localStorage key for the persisted theme. Exported so the pre-React
 * bootstrap in `main.tsx` reads the same key the provider writes — there must be
 * exactly one theme source of truth (a second one fighting it strips classes on
 * reload). See `applyTheme`.
 */
export const THEME_STORAGE_KEY = 'invoice-app-theme';

export interface ThemeDefinition {
  id: ThemeId;
  /** English fallback label; UI translates via `settings.appearance.themes.<id>`. */
  label: string;
  /** English fallback description. */
  description: string;
  /** Whether Tailwind dark-mode (`dark:` variants) should be active. */
  base: 'light' | 'dark';
  /** Extra class applied to <html> for CSS-variable overrides beyond the base. */
  className?: string;
  /** Colors used to render the preview swatch in the picker. */
  preview: { bg: string; surface: string; accent: string; text: string };
}

export const THEMES: ThemeDefinition[] = [
  {
    id: 'light',
    label: 'Light',
    description: 'Warm paper, ink text, and a deep green accent.',
    base: 'light',
    preview: { bg: '#fbfbfa', surface: '#ffffff', accent: '#0e7a4d', text: '#1a1a18' },
  },
  {
    id: 'dark',
    label: 'Dark',
    description: 'Warm ink surfaces with a bright green accent.',
    base: 'dark',
    preview: { bg: '#161614', surface: '#1e1e1b', accent: '#3ecf8e', text: '#f2f2ee' },
  },
  {
    id: 'premium-dark',
    label: 'Premium Dark',
    description: 'Indigo glass surfaces with a soft neon glow.',
    base: 'dark',
    className: 'theme-premium-dark',
    preview: { bg: '#0e1015', surface: '#171a23', accent: '#6366f1', text: '#e8eaf2' },
  },
  {
    id: 'terminal',
    label: 'Terminal',
    description: 'Green CRT phosphor on near-black — for night owls.',
    base: 'dark',
    className: 'theme-terminal',
    preview: { bg: '#060c08', surface: '#0c150f', accent: '#22e06a', text: '#7df0a3' },
  },
  {
    id: 'amber-terminal',
    label: 'Amber Terminal',
    description: 'Vintage amber phosphor console with a green accent.',
    base: 'dark',
    // Composes with the green terminal: inherits its scoped flourishes
    // (mono font, scanlines, caret) and overrides only the color variables.
    className: 'theme-terminal theme-terminal-amber',
    preview: { bg: '#0a0703', surface: '#140d05', accent: '#f5a623', text: '#f0c878' },
  },
  {
    id: 'sepia',
    label: 'Sepia',
    description: 'Warm paper tones and ink — calm, low-glare reading.',
    base: 'light',
    className: 'theme-sepia',
    preview: { bg: '#efe6d3', surface: '#f7f0e1', accent: '#9a6a3c', text: '#3a2f24' },
  },
  {
    id: 'system',
    label: 'System',
    description: 'Follow your operating-system appearance automatically.',
    base: 'light', // resolved at runtime; not used directly for `system`
    preview: { bg: '#9aa3ad', surface: '#ffffff', accent: '#3b82f6', text: '#1f2937' },
  },
];

const THEME_IDS = new Set<ThemeId>(THEMES.map((t) => t.id));

// A theme's `className` may list multiple space-separated classes (e.g. a
// variant that shares another theme's scoped flourishes via composition).
const splitClasses = (className?: string): string[] =>
  className ? className.split(/\s+/).filter(Boolean) : [];

// Every class this provider might add to <html>, so we can clear them cleanly.
const MANAGED_CLASSES = [
  'light',
  'dark',
  ...THEMES.flatMap((t) => splitClasses(t.className)),
];

export function getThemeDefinition(id: ThemeId): ThemeDefinition {
  return THEMES.find((t) => t.id === id) ?? THEMES[0];
}

type ThemeProviderProps = {
  children: React.ReactNode;
  defaultTheme?: ThemeId;
  storageKey?: string;
};

type ThemeProviderState = {
  theme: ThemeId;
  setTheme: (theme: ThemeId) => void;
  /** The concrete theme actually applied ('system' resolved to light/dark). */
  resolvedTheme: Exclude<ThemeId, 'system'>;
  themes: ThemeDefinition[];
};

const initialState: ThemeProviderState = {
  theme: 'system',
  setTheme: () => null,
  resolvedTheme: 'light',
  themes: THEMES,
};

const ThemeProviderContext = createContext<ThemeProviderState>(initialState);

/**
 * Resolve a theme id to the classes on <html>: clears every managed class, then
 * adds the base ('light'/'dark') plus any scoped class. Exported so the pre-React
 * bootstrap can apply the persisted theme before first paint (no flash) using the
 * exact same logic the provider uses on mount.
 */
export function applyTheme(theme: ThemeId): Exclude<ThemeId, 'system'> {
  const root = window.document.documentElement;
  root.classList.remove(...MANAGED_CLASSES);

  let active: ThemeId = theme;
  if (theme === 'system') {
    active = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }

  const def = getThemeDefinition(active);
  root.classList.add(def.base);
  const extra = splitClasses(def.className);
  if (extra.length) root.classList.add(...extra);

  return active as Exclude<ThemeId, 'system'>;
}

export function ThemeProvider({
  children,
  defaultTheme = 'system',
  storageKey = THEME_STORAGE_KEY,
  ...props
}: ThemeProviderProps) {
  const [theme, setThemeState] = useState<ThemeId>(() => {
    const stored = localStorage.getItem(storageKey) as ThemeId | null;
    return stored && THEME_IDS.has(stored) ? stored : defaultTheme;
  });
  const [resolvedTheme, setResolvedTheme] = useState<Exclude<ThemeId, 'system'>>('light');

  useEffect(() => {
    setResolvedTheme(applyTheme(theme));
  }, [theme]);

  // Keep `system` in sync when the OS appearance changes live.
  useEffect(() => {
    if (theme !== 'system') return;
    const mql = window.matchMedia('(prefers-color-scheme: dark)');
    const handler = () => setResolvedTheme(applyTheme('system'));
    mql.addEventListener('change', handler);
    return () => mql.removeEventListener('change', handler);
  }, [theme]);

  const value: ThemeProviderState = {
    theme,
    resolvedTheme,
    themes: THEMES,
    setTheme: (next: ThemeId) => {
      const safe = THEME_IDS.has(next) ? next : defaultTheme;
      localStorage.setItem(storageKey, safe);
      setThemeState(safe);
    },
  };

  return (
    <ThemeProviderContext.Provider {...props} value={value}>
      {children}
    </ThemeProviderContext.Provider>
  );
}

export const useTheme = () => {
  const context = useContext(ThemeProviderContext);

  if (context === undefined)
    throw new Error('useTheme must be used within a ThemeProvider');

  return context;
};
