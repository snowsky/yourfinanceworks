import { vi } from 'vitest';

// Shared mocks for the sign-in family page tests. Import this file first.
// One stable `t`, as in the real hook, so effects keyed on it run once.
vi.mock('react-i18next', () => {
  const t = (k: string) => k;
  return { useTranslation: () => ({ t }) };
});
vi.mock('sonner', () => ({ toast: { info: vi.fn(), success: vi.fn(), error: vi.fn() } }));
vi.mock('@/components/ui/theme-switcher', () => ({ ThemeSwitcher: () => <div>THEME</div> }));
vi.mock('@/components/ui/language-switcher', () => ({ LanguageSwitcher: () => <div>LANG</div> }));
