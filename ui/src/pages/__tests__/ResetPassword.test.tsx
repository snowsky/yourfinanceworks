import './authTestSetup';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

const resetPassword = vi.fn();
const getPasswordRequirements = vi.fn();
vi.mock('@/lib/api', () => ({
  authApi: {
    resetPassword: (token: string, pw: string) => resetPassword(token, pw),
    getPasswordRequirements: () => getPasswordRequirements(),
  },
  getErrorMessage: (e: unknown) => (e instanceof Error ? e.message : String(e)),
}));

import ResetPassword from '../ResetPassword';

const REQUIREMENTS = {
  min_length: 8,
  complexity: {
    require_uppercase: true,
    require_lowercase: true,
    require_numbers: true,
    require_special_chars: true,
    special_chars: '!@#$%^&*()_+-=[]{}|;:,.<>?',
  },
};

const renderPage = async (url = '/reset-password?token=tok123') => {
  render(
    <MemoryRouter initialEntries={[url]}>
      <ResetPassword />
    </MemoryRouter>,
  );
  await waitFor(() => expect(getPasswordRequirements).toHaveBeenCalled());
};

const fill = (pw: string, confirm = pw) => {
  fireEvent.change(screen.getByLabelText('resetPassword.newPasswordLabel'), { target: { value: pw } });
  fireEvent.change(screen.getByLabelText('resetPassword.confirmPasswordLabel'), { target: { value: confirm } });
  fireEvent.click(screen.getByRole('button', { name: 'resetPassword.resetPasswordButton' }));
};

beforeEach(() => {
  resetPassword.mockReset();
  getPasswordRequirements.mockReset();
  getPasswordRequirements.mockResolvedValue(REQUIREMENTS);
});

describe('Reset password page', () => {
  it('uses the shared sign-in frame: brand panel and switchers', async () => {
    await renderPage();
    expect(screen.getByText('auth.brand.headline')).toBeInTheDocument();
    expect(screen.getByText('LANG')).toBeInTheDocument();
    expect(screen.getByText('THEME')).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 1, name: 'resetPassword.title' })).toBeInTheDocument();
  });

  it('gives both password fields a labelled show/hide control', async () => {
    await renderPage();
    const toggles = screen.getAllByRole('button', { name: 'auth.show_password' });
    expect(toggles).toHaveLength(2);
    fireEvent.click(toggles[0]);
    expect(screen.getByLabelText('resetPassword.newPasswordLabel')).toHaveAttribute('type', 'text');
    expect(screen.getByLabelText('resetPassword.confirmPasswordLabel')).toHaveAttribute('type', 'password');
  });

  it('explains a missing token and disables the submit button', async () => {
    await renderPage('/reset-password');
    expect(screen.getByRole('alert')).toHaveTextContent('resetPassword.noToken');
    expect(screen.getByRole('button', { name: 'resetPassword.resetPasswordButton' })).toBeDisabled();
  });

  it('rejects mismatched passwords without calling the API', async () => {
    await renderPage();
    fill('Abcdef1!', 'Abcdef2!');
    expect(await screen.findByRole('alert')).toHaveTextContent('resetPassword.passwordsNotMatch');
    expect(resetPassword).not.toHaveBeenCalled();
  });

  it('rejects a weak password with translated reasons', async () => {
    await renderPage();
    fill('abcdefgh');
    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('resetPassword.requireUppercase');
    expect(alert).toHaveTextContent('resetPassword.requireNumber');
    expect(alert).toHaveTextContent('resetPassword.requireSpecialChar');
    expect(resetPassword).not.toHaveBeenCalled();
  });

  it('submits a valid password and shows the success state', async () => {
    resetPassword.mockResolvedValue({ success: true });
    await renderPage();
    fill('Abcdef1!');
    expect(await screen.findByRole('heading', { level: 1, name: 'resetPassword.successTitle' })).toBeInTheDocument();
    expect(resetPassword).toHaveBeenCalledWith('tok123', 'Abcdef1!');
    expect(screen.getByRole('link', { name: 'resetPassword.goToLogin' })).toHaveAttribute('href', '/login');
  });

  it('shows the server message when the reset is refused', async () => {
    resetPassword.mockResolvedValue({ success: false, message: 'Link expired' });
    await renderPage();
    fill('Abcdef1!');
    expect(await screen.findByRole('alert')).toHaveTextContent('Link expired');
  });
});
