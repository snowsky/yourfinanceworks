import './authTestSetup';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

const requestPasswordReset = vi.fn();
vi.mock('@/lib/api', () => ({
  authApi: { requestPasswordReset: (email: string) => requestPasswordReset(email) },
  getErrorMessage: (e: unknown) => (e instanceof Error ? e.message : String(e)),
}));

import ForgotPassword from '../ForgotPassword';

const renderPage = () =>
  render(
    <MemoryRouter initialEntries={['/forgot-password']}>
      <ForgotPassword />
    </MemoryRouter>,
  );

const submit = (email = 'a@b.co') => {
  fireEvent.change(screen.getByLabelText('forgotPassword.emailLabel'), { target: { value: email } });
  fireEvent.click(screen.getByRole('button', { name: 'forgotPassword.sendResetLink' }));
};

beforeEach(() => {
  requestPasswordReset.mockReset();
});

describe('Forgot password page', () => {
  it('uses the shared sign-in frame: brand panel and switchers', () => {
    renderPage();
    expect(screen.getByText('auth.brand.headline')).toBeInTheDocument();
    expect(screen.getByText('LANG')).toBeInTheDocument();
    expect(screen.getByText('THEME')).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 1, name: 'forgotPassword.title' })).toBeInTheDocument();
  });

  it('links back to sign in and to sign up', () => {
    renderPage();
    expect(screen.getByRole('link', { name: 'forgotPassword.backToLogin' })).toHaveAttribute('href', '/login');
    expect(screen.getByRole('link', { name: 'forgotPassword.signUp' })).toHaveAttribute('href', '/signup');
  });

  it('shows the check-your-email state after a successful request', async () => {
    requestPasswordReset.mockResolvedValue({ success: true });
    renderPage();
    submit('me@example.com');
    expect(await screen.findByRole('heading', { level: 1, name: 'forgotPassword.checkEmailTitle' })).toBeInTheDocument();
    expect(requestPasswordReset).toHaveBeenCalledWith('me@example.com');
    expect(screen.getByRole('link', { name: 'forgotPassword.backToLogin' })).toHaveAttribute('href', '/login');
  });

  it('returns to an empty form from "send another"', async () => {
    requestPasswordReset.mockResolvedValue({ success: true });
    renderPage();
    submit();
    fireEvent.click(await screen.findByRole('button', { name: 'forgotPassword.sendAnother' }));
    expect(screen.getByLabelText('forgotPassword.emailLabel')).toHaveValue('');
  });

  it('announces a failure in an alert and stays on the form', async () => {
    requestPasswordReset.mockRejectedValue(new Error('boom'));
    renderPage();
    submit();
    expect(await screen.findByRole('alert')).toHaveTextContent('boom');
    expect(screen.getByLabelText('forgotPassword.emailLabel')).toBeInTheDocument();
  });

  it('shows the generic error when the API reports no success', async () => {
    requestPasswordReset.mockResolvedValue({ success: false });
    renderPage();
    submit();
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('forgotPassword.toastError'));
  });
});
