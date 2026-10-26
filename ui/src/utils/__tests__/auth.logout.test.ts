import { vi } from 'vitest';
import { clearAuthSession, logout } from '../auth';

beforeEach(() => { vi.clearAllMocks(); });

it('notifies auth subscribers only after the server confirms cookie clearance', async () => {
  const events = vi.spyOn(window, 'dispatchEvent');
  let finish!: (value: Response) => void;
  vi.mocked(fetch).mockImplementationOnce(() => new Promise(resolve => { finish = resolve; }));
  const pending = clearAuthSession();
  expect(events).not.toHaveBeenCalled();
  expect(localStorage.removeItem).not.toHaveBeenCalled();
  finish({ ok: true } as Response);
  await pending;
  expect(events).toHaveBeenCalledWith(expect.objectContaining({ type: 'auth-changed' }));
  expect(events.mock.invocationCallOrder[0]).toBeGreaterThan(vi.mocked(localStorage.removeItem).mock.invocationCallOrder[2]);
  events.mockRestore();
});

it.each(['server', 'network'])('standalone logout rejects %s failures before local cleanup or redirect', async kind => {
  if (kind === 'server') vi.mocked(fetch).mockResolvedValueOnce({ ok: false, status: 500 } as Response);
  else vi.mocked(fetch).mockRejectedValueOnce(new Error('offline'));
  const initialLocation = window.location.href;
  await expect(logout()).rejects.toThrow();
  expect(localStorage.removeItem).not.toHaveBeenCalled();
  expect(window.location.href).toBe(initialLocation);
});

it.each(['https://api.example.test/api/v1', 'https://api.example.test/api/v1/'])('uses configured API origin %s for cookie logout', async apiBase => {
  vi.stubEnv('VITE_API_URL', apiBase);
  vi.resetModules();
  try {
    const configuredAuth = await import('../auth');
    vi.mocked(fetch).mockResolvedValueOnce({ ok: true } as Response);
    await configuredAuth.clearAuthSession();
    expect(fetch).toHaveBeenCalledWith('https://api.example.test/api/v1/auth/logout', { method: 'POST', credentials: 'include' });
  } finally {
    vi.unstubAllEnvs();
    vi.resetModules();
  }
});
