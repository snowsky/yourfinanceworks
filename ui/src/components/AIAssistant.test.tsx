import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import AIAssistant from './AIAssistant';

const mocks = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn(), settings: { enable_ai_assistant: true }, startJob: vi.fn(), getJob: vi.fn() }));
vi.mock('@/lib/api', () => ({ api: mocks }));
vi.mock('@tanstack/react-query', () => ({ useQuery: ({ queryKey }: { queryKey: string[] }) => ({
  data: queryKey[0] === 'settings' ? mocks.settings : [], isLoading: false,
}) }));
vi.mock('react-i18next', () => ({ useTranslation: () => ({ t: translate }) }));
function translate(key: string) { return key; }
vi.mock('@/contexts/PageContext', () => ({ usePageContext: () => ({ pageContext: null }) }));
vi.mock('@/lib/api/settings', () => ({ promptImprovementApi: { startJob: mocks.startJob, getJob: mocks.getJob } }));
vi.mock('./PaymentCharts', () => ({ default: () => null }));

afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

let pending: ((value: { ok: boolean; json: () => Promise<unknown> }) => void)[];
beforeEach(() => {
  pending = [];
  vi.mocked(localStorage.getItem).mockImplementation(key => key === 'user'
    ? JSON.stringify({ id: 1, role: 'admin', tenant_id: 1 }) : null);
  mocks.get.mockResolvedValue([]);
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    if (url.endsWith('/chat')) return new Promise(resolve => pending.push(resolve));
    return { ok: true, json: async () => ({ success: true }) };
  }));
});

it('keeps both responses when requests finish out of order', async () => {
  render(<AIAssistant />);
  fireEvent.click(screen.getByRole('button'));
  await screen.findByText('aiAssistant.welcomeMessage');
  const input = screen.getByPlaceholderText('aiAssistant.inputPlaceholder');
  for (const message of ['Question alpha', 'Question beta']) {
    fireEvent.change(input, { target: { value: message } });
    fireEvent.keyPress(input, { key: 'Enter', charCode: 13 });
    await waitFor(() => expect(pending).toHaveLength(message.endsWith('alpha') ? 1 : 2));
  }
  const finish = (index: number, text: string) => act(async () => pending[index]({
    ok: true, json: async () => ({ success: true, data: { response: text } }),
  }));
  await finish(1, 'Answer beta');
  await finish(0, 'Answer alpha');
  expect(screen.getByText('Answer alpha')).toBeInTheDocument();
  expect(screen.getByText('Answer beta')).toBeInTheDocument();
  expect(screen.queryByText('aiAssistant.thinking')).not.toBeInTheDocument();
});


it('renders a proposal and only executes after confirmation', async () => {
  render(<AIAssistant />);
  fireEvent.click(screen.getByRole('button'));
  await screen.findByText('aiAssistant.welcomeMessage');
  const input = screen.getByPlaceholderText('aiAssistant.inputPlaceholder');
  fireEvent.change(input, { target: { value: 'Create an expense' } });
  fireEvent.keyPress(input, { key: 'Enter', charCode: 13 });
  await waitFor(() => expect(pending).toHaveLength(1));
  await act(async () => pending[0]({ ok: true, json: async () => ({ success: true, data: {
    type: 'proposed_action', action: 'create_expense', params: { amount: 20, currency: 'CAD', expense_date: '2026-11-12' },
  } }) }));
  expect(screen.getByDisplayValue('CAD')).toBeInTheDocument();
  expect(screen.getByDisplayValue('2026-11-12')).toBeInTheDocument();
  expect(pending).toHaveLength(1);
  fireEvent.click(screen.getByRole('button', { name: 'Confirm' }));
  fireEvent.click(screen.getByRole('button', { name: 'Confirm' }));
  await waitFor(() => expect(pending).toHaveLength(2));
  await act(async () => pending[1]({ ok: true, json: async () => ({ success: false, error: 'Permission denied' }) }));
  expect(screen.getByRole('alert')).toHaveTextContent('Permission denied');
  expect(screen.queryByText('Done.')).not.toBeInTheDocument();
});

it('polls the job card without overwriting a newer answer and stops on unmount', async () => {
  let poll: () => Promise<void>;
  const realInterval = globalThis.setInterval;
  const interval = vi.spyOn(globalThis, 'setInterval').mockImplementation(((fn: () => Promise<void>, ms: number) => {
    if (ms === 3000) { poll = fn; return 12345; }
    return realInterval(fn, ms);
  }) as typeof setInterval);
  const clear = vi.spyOn(globalThis, 'clearInterval');
  mocks.startJob.mockResolvedValue({ job_id: 'job', status: 'running', current_iteration: 1, max_iterations: 3 });
  mocks.getJob.mockResolvedValue({ job_id: 'job', status: 'running', current_iteration: 2, max_iterations: 3 });
  const view = render(<AIAssistant />);
  fireEvent.click(screen.getByRole('button'));
  await screen.findByText('aiAssistant.welcomeMessage');
  fireEvent.click(screen.getByRole('button', { name: 'Improve Prompt' }));
  await screen.findByText('Analyzing issue...');
  const input = screen.getByPlaceholderText('aiAssistant.inputPlaceholder');
  fireEvent.change(input, { target: { value: 'Question alpha' } });
  fireEvent.keyPress(input, { key: 'Enter', charCode: 13 });
  await waitFor(() => expect(pending).toHaveLength(1));
  await act(async () => pending[0]({ ok: true, json: async () => ({ success: true, data: { response: 'Answer alpha' } }) }));
  await act(async () => poll());
  expect(screen.getByText('Answer alpha')).toBeInTheDocument();
  expect(screen.getByText('Iteration 2 / 3')).toBeInTheDocument();
  view.unmount();
  expect(clear).toHaveBeenCalledWith(12345);
  interval.mockRestore();
});
