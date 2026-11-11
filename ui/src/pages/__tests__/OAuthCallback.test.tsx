import './authTestSetup';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { toast } from 'sonner';
import OAuthCallback from '../OAuthCallback';

const renderAt = (url: string) =>
  render(
    <MemoryRouter initialEntries={[url]}>
      <Routes>
        <Route path="/oauth-callback" element={<OAuthCallback />} />
        <Route path="/login" element={<div>LOGIN</div>} />
        <Route path="/dashboard" element={<div>DASHBOARD</div>} />
        <Route path="/invoices" element={<div>INVOICES</div>} />
      </Routes>
    </MemoryRouter>,
  );

const encode = (o: unknown) => btoa(JSON.stringify(o)).replace(/\+/g, '-').replace(/\//g, '_');

// The shared test setup replaces localStorage with spies
beforeEach(() => {
  vi.mocked(localStorage.setItem).mockClear();
  vi.mocked(toast.error).mockClear();
});

describe('OAuth callback page', () => {
  it('stores the user and continues to the requested page', () => {
    renderAt(`/oauth-callback?user=${encode({ id: 7, email: 'a@b.co' })}&next=/invoices`);
    expect(screen.getByText('INVOICES')).toBeInTheDocument();
    expect(localStorage.setItem).toHaveBeenCalledWith('user', JSON.stringify({ id: 7, email: 'a@b.co' }));
  });

  it('defaults to the dashboard', () => {
    renderAt(`/oauth-callback?user=${encode({ id: 7 })}`);
    expect(screen.getByText('DASHBOARD')).toBeInTheDocument();
  });

  it('returns to sign in with a translated message when the user is missing', () => {
    renderAt('/oauth-callback');
    expect(screen.getByText('LOGIN')).toBeInTheDocument();
    expect(toast.error).toHaveBeenCalledWith('auth.oauth_invalid');
    expect(localStorage.setItem).not.toHaveBeenCalled();
  });

  it('returns to sign in with a translated message when the payload is unreadable', () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    renderAt('/oauth-callback?user=%%%not-base64');
    expect(screen.getByText('LOGIN')).toBeInTheDocument();
    expect(toast.error).toHaveBeenCalledWith('auth.oauth_failed');
  });
});
