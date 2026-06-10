import { createRoot } from 'react-dom/client'
import App from './App.tsx'
import './index.css'
import './i18n' // Initialize i18n
import { applyTheme, THEME_STORAGE_KEY, type ThemeId } from './components/ui/theme-provider'

// Apply the persisted theme before React renders so there's no flash of the
// wrong theme. Uses the same registry-driven logic (and the same storage key)
// as ThemeProvider — there must be a single theme source of truth, or a second
// toggler strips the base class on reload.
applyTheme((localStorage.getItem(THEME_STORAGE_KEY) as ThemeId | null) ?? 'system');

createRoot(document.getElementById("root")!).render(<App />);
