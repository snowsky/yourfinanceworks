import { describe, it, expect, vi, beforeEach } from 'vitest';
import { canDeleteExpense } from '../utils/auth';

// Mock localStorage
const localStorageMock = (() => {
    let store: Record<string, string> = {};
    return {
        getItem: (key: string) => store[key] || null,
        setItem: (key: string, value: string) => {
            store[key] = value.toString();
        },
        removeItem: (key: string) => {
            delete store[key];
        },
        clear: () => {
            store = {};
        },
    };
})();

Object.defineProperty(window, 'localStorage', {
    value: localStorageMock,
});

describe('Admin Expense Deletion Logic', () => {
    beforeEach(() => {
        window.localStorage.clear();
        vi.clearAllMocks();
    });

    it('allows admin to delete approved expense', () => {
        // Setup admin user
        window.localStorage.setItem('user', JSON.stringify({ role: 'admin' }));
        window.localStorage.setItem('token', 'fake-token');

        const expense = { status: 'approved' };
        expect(canDeleteExpense(expense)).toBe(true);
    });

    it('allows admin to delete pending approval expense', () => {
        // Setup admin user
        window.localStorage.setItem('user', JSON.stringify({ role: 'admin' }));
        window.localStorage.setItem('token', 'fake-token');

        const expense = { status: 'pending_approval' };
        expect(canDeleteExpense(expense)).toBe(true);
    });

    it('prevents regular user from deleting approved expense', () => {
        // Setup regular user
        window.localStorage.setItem('user', JSON.stringify({ role: 'user' }));
        window.localStorage.setItem('token', 'fake-token');

        const expense = { status: 'approved' };
        expect(canDeleteExpense(expense)).toBe(false);
    });

    it('prevents regular user from deleting pending approval expense', () => {
        // Setup regular user
        window.localStorage.setItem('user', JSON.stringify({ role: 'user' }));
        window.localStorage.setItem('token', 'fake-token');

        const expense = { status: 'pending_approval' };
        expect(canDeleteExpense(expense)).toBe(false);
    });

    it('allows regular user to delete draft expense', () => {
        // Setup regular user
        window.localStorage.setItem('user', JSON.stringify({ role: 'user' }));
        window.localStorage.setItem('token', 'fake-token');

        const expense = { status: 'draft' };
        expect(canDeleteExpense(expense)).toBe(true);
    });
});
