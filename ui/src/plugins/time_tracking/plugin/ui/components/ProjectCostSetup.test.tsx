import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { ProjectCostSetup } from './ProjectCostSetup';
const state = vi.hoisted(() => ({ preview: vi.fn(), apply: vi.fn(), value: {} as Record<string, unknown> }));
vi.mock('../profitability-hooks', () => ({ useCostSetup: () => state.value }));
vi.mock('react-i18next', () => ({ useTranslation: () => ({ t: (key: string) => key }) }));
afterEach(cleanup);
function setup() { state.value = { access: { allowed: true }, details: { data: { users: [{ id: 2, email: 'owner@example.com' }], entries: [{ id: 9, user_id: 2, description: 'Design', started_at: '2026-11-01', status: 'logged' }], expenses: [{ id: 7, vendor: 'Supplier', amount: 80, currency: 'USD' }], tasks: [] } }, rates: {}, saveRate: {}, preview: { mutateAsync: state.preview }, apply: { mutateAsync: state.apply }, replace: {} }; }
it('requires preview before apply and lists supplier affected entries', () => { setup(); render(<ProjectCostSetup projectId={1} currency="USD" eligibleExpenseIds={[7]} />); expect(screen.getByRole('button', { name: 'apply' })).toBeDisabled(); expect(screen.getAllByText(/Design/).length).toBeGreaterThan(0); expect(screen.getByText(/Supplier/)).toBeInTheDocument(); fireEvent.click(screen.getByLabelText(/Design/)); expect(screen.getByText(/affected_entries: Design/)).toBeInTheDocument(); });
it('requires refreshed preview after a stale apply failure', async () => { setup(); state.preview.mockResolvedValue({ project_id: 1, entry_ids: [9], entries: [{ entry_id: 9, work_date: '2026-11-01', hourly_cost: '40', after_cost: '80', currency: 'USD' }], before_total: '0', after_total: '80', fingerprint: 'x' }); state.apply.mockRejectedValue(Object.assign(new Error('Preview is stale'), { status: 409 })); render(<ProjectCostSetup projectId={1} currency="USD" eligibleExpenseIds={[]} />); fireEvent.click(screen.getByLabelText(/Design/)); fireEvent.click(screen.getByRole('button', { name: 'preview' })); await screen.findAllByText(/80 USD/); fireEvent.click(screen.getByRole('button', { name: 'apply' })); expect(await screen.findByRole('alert')).toHaveTextContent('refresh_preview'); expect(screen.getByRole('button', { name: 'apply' })).toBeDisabled(); });

it('lets administrators preview completed legacy time entries', async () => {
  setup();
  const value = state.value as { details: { data: { entries: { status: string }[] } } };
  value.details.data.entries[0].status = 'completed';
  state.preview.mockResolvedValue({ project_id: 1, entry_ids: [9], entries: [], before_total: '0', after_total: '80', fingerprint: 'completed' });
  render(<ProjectCostSetup projectId={1} currency="USD" eligibleExpenseIds={[]} />);
  fireEvent.click(screen.getByLabelText(/Design/));
  fireEvent.click(screen.getByRole('button', { name: 'preview' }));
  await screen.findByText(/80 USD/);
  expect(state.preview).toHaveBeenLastCalledWith([9]);
});

it.each([
  ['preview', 500, 'preview_error'],
  ['preview', 409, 'preview_error'],
  ['apply', 500, 'apply_error'],
  ['apply', 403, 'apply_error'],
])('uses action-specific guidance for %s status %s', async (action, status, message) => {
  setup();
  state.preview.mockResolvedValue({ project_id: 1, entry_ids: [9], entries: [], before_total: '0', after_total: '80', fingerprint: 'x' });
  const failure = Object.assign(new Error('failed'), { status });
  if (action === 'preview') state.preview.mockRejectedValue(failure);
  else state.apply.mockRejectedValue(failure);
  render(<ProjectCostSetup projectId={1} currency="USD" />);
  fireEvent.click(screen.getByLabelText(/Design/));
  fireEvent.click(screen.getByRole('button', { name: 'preview' }));
  if (action === 'apply') {
    await screen.findByText(/80 USD/);
    fireEvent.click(screen.getByRole('button', { name: 'apply' }));
  }
  expect(await screen.findByRole('alert')).toHaveTextContent(message);
  expect(screen.queryByText('refresh_preview')).not.toBeInTheDocument();
});

it.each(['save_rate', 'replace', 'restore_hourly'])('reports %s failures without preview advice', async action => {
  setup();
  const failure = vi.fn().mockRejectedValue(Object.assign(new Error('failed'), { status: 409 }));
  state.value.saveRate = { mutateAsync: failure };
  state.value.replace = { mutateAsync: failure };
  render(<ProjectCostSetup projectId={1} currency="USD" eligibleExpenseIds={[7]} />);
  if (action === 'save_rate') {
    fireEvent.change(screen.getByLabelText('contributor'), { target: { value: '2' } });
    fireEvent.change(screen.getByLabelText('hourly_rate'), { target: { value: '40' } });
    fireEvent.change(screen.getByLabelText('effective_date'), { target: { value: '2026-11-01' } });
    fireEvent.submit(screen.getByRole('button', { name: 'save_rate' }).closest('form')!);
  } else {
    fireEvent.click(screen.getByLabelText(/Design/));
    if (action === 'replace') fireEvent.click(screen.getByLabelText(/Supplier/));
    fireEvent.click(screen.getByRole('button', { name: action }));
  }
  expect(await screen.findByRole('alert')).toHaveTextContent(`${action}_error`);
  expect(screen.queryByText('refresh_preview')).not.toBeInTheDocument();
});
