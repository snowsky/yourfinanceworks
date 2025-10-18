// Theme utilities for cookie consent components
export function getThemeClass(darkMode?: boolean): string {
  if (darkMode === undefined) {
    // Auto-detect system preference
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }
  
  return darkMode ? 'dark' : 'light';
}

export function applyTheme(element: HTMLElement, darkMode?: boolean): void {
  const theme = getThemeClass(darkMode);
  element.setAttribute('data-theme', theme);
}

export function createThemeObserver(callback: (isDark: boolean) => void): MediaQueryList {
  const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
  
  const handler = (e: MediaQueryListEvent) => {
    callback(e.matches);
  };
  
  mediaQuery.addEventListener('change', handler);
  
  return mediaQuery;
}