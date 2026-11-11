import './authTestSetup';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

const api = vi.hoisted(() => {
  class ClientPortalAuthError extends Error {}
  return {
    ClientPortalAuthError,
    getMe: vi.fn(),
    getInvoices: vi.fn(),
    getBranding: vi.fn(),
    updateMe: vi.fn(),
    downloadPdf: vi.fn(),
    getToken: vi.fn(),
    getSlug: vi.fn(),
    clear: vi.fn(),
  };
});
vi.mock('@/lib/api/client-portal', () => ({
  ClientPortalAuthError: api.ClientPortalAuthError,
  clientPortalApi: {
    getMe: api.getMe,
    getInvoices: api.getInvoices,
    getBranding: api.getBranding,
    updateMe: api.updateMe,
    downloadPdf: api.downloadPdf,
  },
  clientPortalSession: { getToken: api.getToken, getSlug: api.getSlug, clear: api.clear },
}));

import PortalDashboard from '../portal/PortalDashboard';

const PROFILE = { name: 'Phil Barr', email: 'phil@example.com', phone: '555-0100', address: '1 Main St' };
const INVOICES = [
  { id: 1, number: 'INV-1', status: 'paid', amount: 100, outstanding: 0, currency: 'USD', due_date: '2026-10-01' },
  { id: 2, number: 'INV-2', status: 'partially_paid', amount: 300, outstanding: 120, currency: 'USD', due_date: '2026-11-01' },
  { id: 3, number: 'INV-3', status: 'on_hold', amount: 50, outstanding: 50, currency: 'USD', due_date: null },
];

const renderPage = () =>
  render(
    <MemoryRouter initialEntries={['/portal/dashboard']}>
      <Routes>
        <Route path="/portal/dashboard" element={<PortalDashboard />} />
        <Route path="/portal/:slug" element={<div>PORTAL LOGIN</div>} />
        <Route path="/" element={<div>HOME</div>} />
      </Routes>
    </MemoryRouter>,
  );

beforeEach(() => {
  Object.values(api).forEach((fn) => typeof fn === 'function' && 'mockReset' in fn && (fn as ReturnType<typeof vi.fn>).mockReset());
  api.getToken.mockReturnValue('tok');
  api.downloadPdf.mockResolvedValue(undefined);
  api.getSlug.mockReturnValue('acme');
  api.getMe.mockResolvedValue(PROFILE);
  api.getInvoices.mockResolvedValue({ invoices: INVOICES });
  api.getBranding.mockResolvedValue({ company_name: 'Acme Ltd', company_logo_url: null, brand_color: '#123456', accent_color: '#654321', footer_text: 'Thanks' });
});

describe('Client portal dashboard', () => {
  it('shows branding, totals and translated labels', async () => {
    renderPage();
    expect(await screen.findByText('Acme Ltd')).toBeInTheDocument();
    expect(screen.getByText('portal.dashboard.totalOutstanding')).toBeInTheDocument();
    // The page formats in the viewer's locale, so don't pin the currency symbol
    expect(screen.getByText(/170\.00/)).toBeInTheDocument();
    expect(screen.getByText('portal.dashboard.manyInvoices')).toBeInTheDocument();
    expect(screen.getByText('Thanks')).toBeInTheDocument();
    expect(screen.getByText('common.powered_by')).toBeInTheDocument();
  });

  it('translates known statuses and humanises unknown ones', async () => {
    renderPage();
    await screen.findByText('Acme Ltd');
    expect(screen.getByText('portal.status.partially_paid')).toBeInTheDocument();
    expect(screen.getAllByText('portal.status.paid').length).toBeGreaterThan(0);
  });

  it('labels each PDF button with its invoice number', async () => {
    renderPage();
    await screen.findByText('Acme Ltd');
    const buttons = screen.getAllByRole('button', { name: 'portal.dashboard.downloadPdfFor' });
    expect(buttons).toHaveLength(INVOICES.length);
    fireEvent.click(buttons[0]);
    expect(api.downloadPdf).toHaveBeenCalledWith(1, 'INV-1');
  });

  it('edits and saves the profile with labelled fields', async () => {
    api.updateMe.mockResolvedValue({ ...PROFILE, phone: '555-0199' });
    renderPage();
    await screen.findByText('Acme Ltd');
    fireEvent.click(screen.getByRole('button', { name: /portal.dashboard.edit/ }));
    const phone = screen.getByLabelText('portal.dashboard.phone');
    fireEvent.change(phone, { target: { value: '555-0199' } });
    fireEvent.click(screen.getByRole('button', { name: /portal.dashboard.save/ }));
    await waitFor(() => expect(api.updateMe).toHaveBeenCalledWith({ name: 'Phil Barr', phone: '555-0199', address: '1 Main St' }));
    expect(await screen.findByText('555-0199')).toBeInTheDocument();
  });

  it('signs out to the portal sign-in page', async () => {
    renderPage();
    await screen.findByText('Acme Ltd');
    fireEvent.click(screen.getByRole('button', { name: /portal.dashboard.signOut/ }));
    expect(api.clear).toHaveBeenCalled();
    expect(await screen.findByText('PORTAL LOGIN')).toBeInTheDocument();
  });

  it('returns to sign-in when the session has expired', async () => {
    api.getMe.mockRejectedValue(new api.ClientPortalAuthError('expired'));
    renderPage();
    expect(await screen.findByText('PORTAL LOGIN')).toBeInTheDocument();
    expect(api.clear).toHaveBeenCalled();
  });

  it('announces a load failure', async () => {
    api.getMe.mockRejectedValue(new Error('Server down'));
    renderPage();
    expect(await screen.findByRole('alert')).toHaveTextContent('Server down');
  });
});
