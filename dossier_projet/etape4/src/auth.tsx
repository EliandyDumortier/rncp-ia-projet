import { createContext, useContext, useState, useCallback, type ReactNode } from 'react';
import type { User, FlashMessage, FlashType } from './types';
import { apiClient, dataApi } from './api';

function extractUserIdFromJWT(token: string): number {
  try {
    const parts = token.split('.');
    if (parts.length !== 3) throw new Error('Invalid JWT');
    const payload = JSON.parse(atob(parts[1]));
    const sub = payload.sub;
    if (!sub) throw new Error('Missing sub in JWT');
    return parseInt(sub, 10);
  } catch (e) {
    console.error('Failed to extract user_id from JWT:', e);
    throw e;
  }
}

interface AuthContextValue {
  user: User | null;
  login: (username: string, password: string) => Promise<void>;
  register: (data: {
    pseudonyme: string;
    email: string;
    mot_de_passe: string;
    consentement_collecte: boolean;
    consentement_marketing?: boolean;
  }) => Promise<void>;
  logout: () => void;
  flashMessages: FlashMessage[];
  flash: (text: string, type: FlashType) => void;
  dismissFlash: (id: number) => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

let flashId = 0;

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(() => {
    const token = localStorage.getItem('jwt_token');
    const username = localStorage.getItem('username');
    const userId = localStorage.getItem('user_id');
    if (token && username && userId) {
      return { user_id: parseInt(userId, 10), username, jwt_token: token };
    }
    return null;
  });
  const [flashMessages, setFlashMessages] = useState<FlashMessage[]>([]);

  const login = useCallback(async (username: string, password: string) => {
    const data = await apiClient.authenticate(username, password);
    const real_user_id = extractUserIdFromJWT(data.access_token);
    const newUser: User = { user_id: real_user_id, username, jwt_token: data.access_token };
    localStorage.setItem('user_id', String(real_user_id));
    localStorage.setItem('username', username);
    setUser(newUser);
  }, []);

  const register = useCallback(async (data: {
    pseudonyme: string;
    email: string;
    mot_de_passe: string;
    consentement_collecte: boolean;
    consentement_marketing?: boolean;
  }) => {
    await dataApi.register(data);
    const authData = await apiClient.authenticate(data.pseudonyme, data.mot_de_passe);
    const real_user_id = extractUserIdFromJWT(authData.access_token);
    const newUser: User = { user_id: real_user_id, username: data.pseudonyme, jwt_token: authData.access_token };
    localStorage.setItem('user_id', String(real_user_id));
    localStorage.setItem('username', data.pseudonyme);
    setUser(newUser);
  }, []);

  const logout = useCallback(() => {
    apiClient.logout();
    localStorage.removeItem('user_id');
    localStorage.removeItem('username');
    setUser(null);
  }, []);

  const flash = useCallback((text: string, type: FlashType) => {
    const id = ++flashId;
    setFlashMessages((prev) => [...prev, { id, type, text }]);
    setTimeout(() => {
      setFlashMessages((prev) => prev.filter((m) => m.id !== id));
    }, 5000);
  }, []);

  const dismissFlash = useCallback((id: number) => {
    setFlashMessages((prev) => prev.filter((m) => m.id !== id));
  }, []);

  return (
    <AuthContext.Provider value={{ user, login, register, logout, flashMessages, flash, dismissFlash }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
