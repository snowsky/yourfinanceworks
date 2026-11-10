import './authTestSetup';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

const getSSOStatus = vi.fn().mockResolvedValue({ google: false, microsoft: false, has_sso: false });
const getPasswordRequirements = vi.fn().mockRejectedValue(new Error('down'));
vi.mock('@/lib/api', () => ({
  authApi: {
    getSSOStatus: () => getSSOStatus(),
    getPasswordRequirements: () => getPasswordRequirements(),
  },
  API_BASE_URL: '/api',
  getErrorMessage: (e: unknown) => String(e),
}));

import Signup from '../Signup';

describe('Signup page', () => {
  it('uses the shared sign-in frame with switchers above the form', async () => {
    render(
      <MemoryRouter initialEntries={['/signup']}>
        <Signup />
      </MemoryRouter>,
    );
    await waitFor(() => expect(getSSOStatus).toHaveBeenCalled());
    const heading = screen.getByRole('heading', { level: 1, name: 'auth.signup.title' });
    expect(screen.getByText('auth.brand.headline')).toBeInTheDocument();
    for (const label of ['LANG', 'THEME']) {
      const switcher = screen.getByText(label);
      expect(switcher.compareDocumentPosition(heading) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    }
    expect(screen.getByRole('link', { name: 'auth.signup.sign_in' })).toHaveAttribute('href', '/login');
  });
});
