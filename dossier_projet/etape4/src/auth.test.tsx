import { act, renderHook } from '@testing-library/react';
import type { ReactNode } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { AuthProvider, useAuth } from './auth';

const apiMocks = vi.hoisted(() => ({
  authenticate: vi.fn(),
  logout: vi.fn(),
  register: vi.fn(),
}));

vi.mock('./api', () => ({
  apiClient: {
    authenticate: apiMocks.authenticate,
    logout: apiMocks.logout,
  },
  dataApi: {
    register: apiMocks.register,
  },
  DataAPIError: class DataAPIError extends Error {},
}));

const wrapper = ({ children }: { children: ReactNode }) => (
  <AuthProvider>{children}</AuthProvider>
);

function tokenFor(userId: number): string {
  return `header.${btoa(JSON.stringify({ sub: String(userId) }))}.signature`;
}

afterEach(() => {
  localStorage.clear();
  vi.clearAllMocks();
});

describe('AuthProvider', () => {
  it('logs in with the real user identifier extracted from the JWT', async () => {
    apiMocks.authenticate.mockResolvedValue({ access_token: tokenFor(42) });
    const { result } = renderHook(() => useAuth(), { wrapper });

    await act(async () => result.current.login('alice', 'secret'));

    expect(result.current.user).toMatchObject({ user_id: 42, username: 'alice' });
    expect(localStorage.getItem('user_id')).toBe('42');
    expect(localStorage.getItem('username')).toBe('alice');
  });

  it('registers, authenticates and persists the new account session', async () => {
    apiMocks.register.mockResolvedValue({ id: 8 });
    apiMocks.authenticate.mockResolvedValue({ access_token: tokenFor(8) });
    const { result } = renderHook(() => useAuth(), { wrapper });

    await act(async () => result.current.register({
      pseudonyme: 'new-user',
      email: 'new@example.test',
      mot_de_passe: 'secret',
      consentement_collecte: true,
    }));

    expect(apiMocks.register).toHaveBeenCalledOnce();
    expect(result.current.user).toMatchObject({ user_id: 8, username: 'new-user' });
  });

  it('logs out and clears persisted session data', async () => {
    localStorage.setItem('jwt_token', tokenFor(5));
    localStorage.setItem('username', 'alice');
    localStorage.setItem('user_id', '5');
    const { result } = renderHook(() => useAuth(), { wrapper });

    expect(result.current.user).toMatchObject({ user_id: 5 });

    act(() => result.current.logout());

    expect(apiMocks.logout).toHaveBeenCalledOnce();
    expect(result.current.user).toBeNull();
    expect(localStorage.getItem('user_id')).toBeNull();
  });
});
