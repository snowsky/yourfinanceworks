import { act, renderHook, waitFor } from '@testing-library/react'
import { vi } from 'vitest'
import type { User } from '@/utils/auth'
import { useAuth } from '../useAuth'
import { authApi } from '@/lib/api'
import { toast } from 'sonner'
const { navigate, clear } = vi.hoisted(() => ({ navigate: vi.fn(), clear: vi.fn() }))
vi.mock('react-router-dom', () => ({ useNavigate: () => navigate }))
vi.mock('@tanstack/react-query', () => ({ useQueryClient: () => ({ clear }) }))
vi.mock('@/lib/api', () => ({ authApi: { getCurrentUser: vi.fn() } }))
vi.mock('sonner', () => ({ toast: { error: vi.fn() } }))
vi.mock('react-i18next', () => ({ useTranslation: () => ({ t: (_key: string, options: { defaultValue: string }) => options.defaultValue }) }))
const user: User = { id: 1, email: 'user@example.com', role: 'admin' }
beforeEach(() => {
 vi.clearAllMocks()
 vi.mocked(authApi.getCurrentUser).mockResolvedValue(user)
 vi.mocked(localStorage.getItem).mockImplementation(key => key === 'user' ? JSON.stringify(user) : '1')
})
async function authenticatedHook() {
 const hook = renderHook(() => useAuth())
 await waitFor(() => expect(hook.result.current.isLoading).toBe(false))
 return hook
}
it('waits for cookie logout before clearing identity, tenant, cache and navigating', async () => {
 let finish!: (value: Response) => void
 vi.mocked(fetch).mockImplementationOnce(() => new Promise(resolve => { finish = resolve }))
 const { result } = await authenticatedHook()
 let pending!: Promise<unknown>
 act(() => { pending = result.current.logout() as unknown as Promise<unknown> })
 expect(fetch).toHaveBeenCalledWith('/api/v1/auth/logout', { method: 'POST', credentials: 'include' })
 expect(result.current.isAuthenticated).toBe(true)
 expect(localStorage.removeItem).not.toHaveBeenCalled()
 expect(clear).not.toHaveBeenCalled()
 expect(navigate).not.toHaveBeenCalled()
 await act(async () => { finish({ ok: true } as Response); await pending })
 expect(result.current.isAuthenticated).toBe(false)
 for (const key of ['user', 'token', 'selected_tenant_id']) expect(localStorage.removeItem).toHaveBeenCalledWith(key)
 expect(clear).toHaveBeenCalledOnce()
 expect(navigate).toHaveBeenCalledWith('/login')
})
it.each(['server', 'network'])('retains the session and reports a retryable %s failure', async kind => {
 if (kind === 'server') vi.mocked(fetch).mockResolvedValueOnce({ ok: false, status: 503 } as Response)
 else vi.mocked(fetch).mockRejectedValueOnce(new Error('offline'))
 const { result } = await authenticatedHook()
 await act(async () => { await result.current.logout() })
 expect(result.current.isAuthenticated).toBe(true)
 expect(localStorage.removeItem).not.toHaveBeenCalled()
 expect(clear).not.toHaveBeenCalled()
 expect(navigate).not.toHaveBeenCalled()
 expect(toast.error).toHaveBeenCalledWith('Unable to log out. Please try again.')
 vi.mocked(fetch).mockResolvedValueOnce({ ok: true } as Response)
 await act(async () => { await result.current.logout() })
 expect(navigate).toHaveBeenCalledWith('/login')
})
it('loads canonical current user on mount', async () => {
 const { result } = await authenticatedHook()
 expect(result.current.user).toEqual(user)
 expect(result.current.userRole).toBe('admin')
})
it('clears an expired session on authentication failure', async () => {
 vi.mocked(authApi.getCurrentUser).mockRejectedValueOnce({ status: 401 })
 const { result } = await authenticatedHook()
 expect(result.current.user).toBeNull()
 expect(result.current.isAuthenticated).toBe(false)
})
