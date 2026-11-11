import './authTestSetup';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

const api = vi.hoisted(() => ({
  getBranding: vi.fn(),
  requestLink: vi.fn(),
  verify: vi.fn(),
  setSlug: vi.fn(),
  getSlug: vi.fn(),
  setToken: vi.fn(),
}));
vi.mock('@/lib/api/client-portal', () => ({
  clientPortalApi: { getBranding: api.getBranding, requestLink: api.requestLink, verify: api.verify },
  clientPortalSession: { setSlug: api.setSlug, getSlug: api.getSlug, setToken: api.setToken },
}));

import PortalLogin from '../portal/PortalLogin';
import PortalVerify from '../portal/PortalVerify';

const BRANDING = {
  company_name: 'Acme Ltd',
  company_logo_url: null,
  brand_color: '#123456',
  accent_color: '#654321',
  footer_text: 'Thanks for your business',
};

const renderAt = (url: string) =>
  render(
    <MemoryRouter initialEntries={[url]}>
      <Routes>
        <Route path="/portal/verify/:token" element={<PortalVerify />} />
        <Route path="/portal/dashboard" element={<div>DASHBOARD</div>} />
        <Route path="/portal/:slug" element={<PortalLogin />} />
      </Routes>
    </MemoryRouter>,
  );

beforeEach(() => {
  Object.values(api).forEach((fn) => fn.mockReset());
  api.getBranding.mockResolvedValue(BRANDING);
});

describe('Client portal login', () => {
  it('shows the tenant branding, not ours, with theme-aware colours', async () => {
    const { container } = renderAt('/portal/acme');
    expect(await screen.findByRole('heading', { level: 1, name: 'Acme Ltd' })).toBeInTheDocument();
    expect(screen.getByText('Thanks for your business')).toBeInTheDocument();
    expect(api.setSlug).toHaveBeenCalledWith('acme');
    expect(screen.queryByText('auth.brand.headline')).not.toBeInTheDocument();
    // No fixed greys or whites that would ignore the dark theme
    expect(container.innerHTML).not.toMatch(/\b(bg-white|bg-gray-\d+|text-gray-\d+|border-gray-\d+)\b/);
    expect(screen.getByRole('button', { name: 'portal.login.submit' })).toHaveStyle({ backgroundColor: '#123456' });
  });

  it('keeps the submit button disabled until an email is entered', async () => {
    renderAt('/portal/acme');
    const button = await screen.findByRole('button', { name: 'portal.login.submit' });
    expect(button).toBeDisabled();
    fireEvent.change(screen.getByLabelText('portal.login.emailLabel'), { target: { value: 'c@d.co' } });
    expect(button).toBeEnabled();
  });

  it('requests a link and confirms it was sent', async () => {
    api.requestLink.mockResolvedValue({ status: 'ok', message: '' });
    renderAt('/portal/acme');
    fireEvent.change(await screen.findByLabelText('portal.login.emailLabel'), { target: { value: 'c@d.co' } });
    fireEvent.click(screen.getByRole('button', { name: 'portal.login.submit' }));
    expect(await screen.findByText('portal.login.sentTitle')).toBeInTheDocument();
    expect(api.requestLink).toHaveBeenCalledWith('acme', 'c@d.co');
  });

  it('announces a failed request', async () => {
    api.requestLink.mockRejectedValue(new Error('Too many requests'));
    renderAt('/portal/acme');
    fireEvent.change(await screen.findByLabelText('portal.login.emailLabel'), { target: { value: 'c@d.co' } });
    fireEvent.click(screen.getByRole('button', { name: 'portal.login.submit' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Too many requests');
  });

  it('says so when the portal does not exist', async () => {
    api.getBranding.mockRejectedValue(new Error('Portal not found'));
    renderAt('/portal/nope');
    expect(await screen.findByRole('alert')).toHaveTextContent('portal.notFound.title');
    expect(screen.queryByLabelText('portal.login.emailLabel')).not.toBeInTheDocument();
  });
});

describe('Client portal verify', () => {
  it('stores the session and opens the dashboard', async () => {
    api.verify.mockResolvedValue({ access_token: 'tok' });
    renderAt('/portal/verify/abc');
    expect(await screen.findByText('DASHBOARD')).toBeInTheDocument();
    expect(api.verify).toHaveBeenCalledWith('abc');
    expect(api.setToken).toHaveBeenCalledWith('tok');
  });

  it('shows a status line while verifying', () => {
    api.verify.mockReturnValue(new Promise(() => {}));
    renderAt('/portal/verify/abc');
    expect(screen.getByRole('status')).toHaveTextContent('portal.verify.signingIn');
  });

  it('explains a failed link and offers a new one', async () => {
    api.verify.mockRejectedValue(new Error('Link expired'));
    api.getSlug.mockReturnValue('acme');
    renderAt('/portal/verify/abc');
    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('portal.verify.failedTitle');
    expect(alert).toHaveTextContent('Link expired');
    expect(screen.getByRole('link', { name: 'portal.verify.requestNew' })).toHaveAttribute('href', '/portal/acme');
    await waitFor(() => expect(api.setToken).not.toHaveBeenCalled());
  });
});
