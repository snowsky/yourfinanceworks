import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent, act } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

const getSSOStatus = vi.fn();
const login = vi.fn();
const verifyMFAAttempt = vi.fn();
vi.mock('@/lib/api', () => ({
  authApi: {
    getSSOStatus: () => getSSOStatus(),
    login: (...a: unknown[]) => login(...a),
    verifyMFAAttempt: (...a: unknown[]) => verifyMFAAttempt(...a),
    getMFAAttempt: vi.fn(),
  },
  API_BASE_URL: '/api',
  getErrorMessage: (e: unknown) => String(e),
}));
vi.mock('react-i18next', () => {
  const t = (k: string) => k;
  return { useTranslation: () => ({ t }) };
});
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
  login.mockReset();
  verifyMFAAttempt.mockReset();
});

const signInToMfaStep = async () => {
  login.mockResolvedValue({
    mfa_required: true,
    mfa_session_id: 'sess-1',
    current_factor_id: 'f1',
    current_factor_label: 'Work phone',
  });
  fireEvent.change(screen.getByLabelText('auth.email'), { target: { value: 'a@b.co' } });
  fireEvent.change(screen.getByLabelText('auth.password'), { target: { value: 'pw' } });
  fireEvent.click(screen.getByRole('button', { name: 'auth.login' }));
  return screen.findByLabelText('auth.mfa.code_label');
};

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
    // Let the rejected status settle into the fail-closed fallback
    await act(async () => { await Promise.resolve(); });
    expect(getSSOStatus).toHaveBeenCalledTimes(1);
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

  describe('verification step', () => {
    it('replaces the sign-in form with a translated code prompt', async () => {
      getSSOStatus.mockResolvedValue({ google: true, microsoft: false, has_sso: true });
      renderLogin();
      await screen.findByRole('button', { name: /auth.sign_in_with_google/ });
      const code = await signInToMfaStep();
      expect(screen.getByRole('heading', { level: 1, name: 'auth.mfa.title' })).toBeInTheDocument();
      expect(screen.getByText('Work phone')).toBeInTheDocument();
      expect(code).toHaveAttribute('inputmode', 'numeric');
      expect(screen.queryByLabelText('auth.password')).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /sign_in_with/ })).not.toBeInTheDocument();
      expect(screen.queryByText(/MFA Chain Challenge/)).not.toBeInTheDocument();
    });

    it('sends the code with the session and factor', async () => {
      verifyMFAAttempt.mockResolvedValue({ is_complete: false, next_factor_id: 'f2', next_factor_label: 'Backup key' });
      renderLogin();
      const code = await signInToMfaStep();
      fireEvent.change(code, { target: { value: '12a3456789' } });
      expect(code).toHaveValue('123456');
      fireEvent.click(screen.getByRole('button', { name: 'auth.mfa.verify' }));
      await waitFor(() =>
        expect(verifyMFAAttempt).toHaveBeenCalledWith({
          session_id: 'sess-1',
          factor_id: 'f1',
          user_input: '123456',
          window: 1,
        }),
      );
      expect(await screen.findByText('Backup key')).toBeInTheDocument();
    });

    it('goes back to the sign-in form', async () => {
      renderLogin();
      await signInToMfaStep();
      fireEvent.click(screen.getByRole('button', { name: 'auth.mfa.back_to_sign_in' }));
      expect(screen.getByLabelText('auth.password')).toHaveValue('');
      expect(screen.getByRole('heading', { level: 1, name: 'auth.login' })).toBeInTheDocument();
      expect(screen.queryByLabelText('auth.mfa.code_label')).not.toBeInTheDocument();
    });
  });
});
