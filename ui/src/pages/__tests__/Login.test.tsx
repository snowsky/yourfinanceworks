import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

const getSSOStatus = vi.fn();
vi.mock('@/lib/api', () => ({
  authApi: {
    getSSOStatus: () => getSSOStatus(),
    login: vi.fn(),
    verifyMFAAttempt: vi.fn(),
    getMFAAttempt: vi.fn(),
  },
  API_BASE_URL: '/api',
  getErrorMessage: (e: unknown) => String(e),
}));
vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (k: string) => k }),
}));
vi.mock('sonner', () => ({ toast: { info: vi.fn(), success: vi.fn(), error: vi.fn() } }));
vi.mock('@/components/ui/theme-switcher', () => ({ ThemeSwitcher: () => <div>THEME</div> }));
vi.mock('@/components/ui/language-switcher', () => ({ LanguageSwitcher: () => <div>LANG</div> }));

import Login from '../Login';

const renderLogin = () =>
  render(
    <MemoryRouter initialEntries={['/login']}>
      <Login />
    </MemoryRouter>,
  );

const NO_SSO = { google: false, microsoft: false, has_sso: false };

beforeEach(() => {
  getSSOStatus.mockReset();
  getSSOStatus.mockResolvedValue(NO_SSO);
});

describe('Login page', () => {
  it('shows the product-preview brand panel without certification claims', () => {
    renderLogin();
    expect(screen.getByText('auth.brand.headline')).toBeInTheDocument();
    expect(screen.getByText('auth.brand.cash_position')).toBeInTheDocument();
    expect(screen.queryByText(/ISO 27001/)).not.toBeInTheDocument();
    expect(screen.queryByText(/SOC 2/)).not.toBeInTheDocument();
    expect(screen.queryByText(/256-bit/)).not.toBeInTheDocument();
  });

  it('hides the sample figures from assistive tech', () => {
    renderLogin();
    expect(screen.getByText('auth.brand.cash_position').closest('[aria-hidden="true"]')).not.toBeNull();
  });

  it('places SSO buttons above the email field when SSO is enabled', async () => {
    getSSOStatus.mockResolvedValue({ google: true, microsoft: true, has_sso: true });
    renderLogin();
    const google = await screen.findByRole('button', { name: /auth.sign_in_with_google/ });
    const microsoft = screen.getByRole('button', { name: /auth.sign_in_with_microsoft/ });
    const email = screen.getByLabelText('auth.email');
    expect(google.compareDocumentPosition(email) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(microsoft.compareDocumentPosition(email) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.getByText('auth.or_sign_in_with_email')).toBeInTheDocument();
  });

  it('shows no SSO buttons or divider when the status check fails', async () => {
    getSSOStatus.mockRejectedValue(new Error('down'));
    renderLogin();
    await waitFor(() => expect(getSSOStatus).toHaveBeenCalled());
    expect(screen.queryByRole('button', { name: /sign_in_with/ })).not.toBeInTheDocument();
    expect(screen.queryByText('auth.or_sign_in_with_email')).not.toBeInTheDocument();
  });

  it('toggles password visibility with a labelled control', () => {
    renderLogin();
    const password = screen.getByLabelText('auth.password');
    expect(password).toHaveAttribute('type', 'password');
    fireEvent.click(screen.getByRole('button', { name: 'auth.show_password' }));
    expect(password).toHaveAttribute('type', 'text');
    fireEvent.click(screen.getByRole('button', { name: 'auth.hide_password' }));
    expect(password).toHaveAttribute('type', 'password');
  });

  it('keeps the forgot-password link after the password field in tab order', () => {
    renderLogin();
    const password = screen.getByLabelText('auth.password');
    const forgot = screen.getByRole('link', { name: 'auth.forgot_password' });
    expect(forgot).toHaveAttribute('href', '/forgot-password');
    expect(password.compareDocumentPosition(forgot) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it('renders the language and theme switchers', () => {
    renderLogin();
    expect(screen.getByText('LANG')).toBeInTheDocument();
    expect(screen.getByText('THEME')).toBeInTheDocument();
  });
});
