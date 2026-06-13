import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, opts?: Record<string, any>) => {
      let s = (opts?.defaultValue as string) ?? key;
      if (opts) for (const [k, v] of Object.entries(opts)) {
        if (k !== 'defaultValue') s = s.replace(`{{${k}}}`, String(v));
      }
      return s;
    },
  }),
}));

const api = vi.hoisted(() => ({
  getChecklist: vi.fn(),
  dismissChecklist: vi.fn(),
}));
vi.mock('@/lib/api', () => ({ onboardingApi: api }));
vi.mock('sonner', () => ({ toast: { error: vi.fn() } }));

import { OnboardingChecklist } from './OnboardingChecklist';

function renderCard() {
  return render(
    <MemoryRouter>
      <OnboardingChecklist />
    </MemoryRouter>,
  );
}

const mixed = {
  steps: [
    { key: 'add_client', done: true },
    { key: 'create_invoice', done: true },
    { key: 'record_expense', done: false },
    { key: 'customize_branding', done: false },
    { key: 'send_invoice', done: false },
  ],
  completed: 2,
  total: 5,
  all_complete: false,
  dismissed: false,
};

describe('OnboardingChecklist', () => {
  beforeEach(() => {
    api.getChecklist.mockReset();
    api.dismissChecklist.mockReset();
  });

  it('renders rows; incomplete steps are links, done steps are not', async () => {
    api.getChecklist.mockResolvedValue(mixed);
    renderCard();
    const recordExpense = await screen.findByText('Record your first expense');
    expect(recordExpense.closest('a')).not.toBeNull();
    const addClient = screen.getByText('Add your first client');
    expect(addClient.closest('a')).toBeNull();
  });

  it('renders nothing when dismissed', async () => {
    api.getChecklist.mockResolvedValue({ ...mixed, dismissed: true });
    const { container } = renderCard();
    await waitFor(() => expect(api.getChecklist).toHaveBeenCalled());
    expect(container.querySelector('a')).toBeNull();
    expect(screen.queryByText('Add your first client')).toBeNull();
  });

  it('renders nothing when all complete', async () => {
    api.getChecklist.mockResolvedValue({ ...mixed, completed: 5, all_complete: true });
    const { container } = renderCard();
    await waitFor(() => expect(api.getChecklist).toHaveBeenCalled());
    expect(screen.queryByText('Add your first client')).toBeNull();
    expect(container.textContent).not.toContain('Get started');
  });

  it('dismiss click calls the API and hides the card', async () => {
    api.getChecklist.mockResolvedValue(mixed);
    api.dismissChecklist.mockResolvedValue({ ...mixed, dismissed: true });
    renderCard();
    const btn = await screen.findByRole('button', { name: /dismiss/i });
    fireEvent.click(btn);
    await waitFor(() => expect(api.dismissChecklist).toHaveBeenCalled());
    await waitFor(() => expect(screen.queryByText('Add your first client')).toBeNull());
  });
});
