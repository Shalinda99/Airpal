import React, { createContext, useCallback, useContext, useEffect, useState } from 'react';

import { api, clearCaches, clearTokens, hasSession, saveTokens, setSessionExpiredHandler } from './api';
import type { Me } from './types';

type AuthState = {
  me: Me | null;
  loading: boolean;
  guest: () => Promise<void>;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  deleteAccount: () => Promise<void>;
  refreshMe: () => Promise<void>;
};

const Ctx = createContext<AuthState>(null as unknown as AuthState);
export const useAuth = () => useContext(Ctx);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);

  const refreshMe = useCallback(async () => {
    setMe(await api<Me>('/me'));
  }, []);

  useEffect(() => {
    setSessionExpiredHandler(() => setMe(null));
    (async () => {
      try {
        if (await hasSession()) await refreshMe();
      } catch {
        setMe(null);
      } finally {
        setLoading(false);
      }
    })();
  }, [refreshMe]);

  const startSession = async (tokens: { access_token: string; refresh_token: string }) => {
    await saveTokens(tokens.access_token, tokens.refresh_token);
    await refreshMe();
  };

  const value: AuthState = {
    me,
    loading,
    refreshMe,
    guest: async () => startSession(await api('/auth/guest', { method: 'POST', auth: false })),
    login: async (email, password) =>
      startSession(await api('/auth/login', { method: 'POST', auth: false, body: { email, password } })),
    register: async (email, password) =>
      startSession(await api('/auth/register', { method: 'POST', auth: false, body: { email, password } })),
    logout: async () => {
      await clearTokens();
      await clearCaches();
      setMe(null);
    },
    deleteAccount: async () => {
      await api('/me', { method: 'DELETE' });
      await clearTokens();
      await clearCaches();
      setMe(null);
    },
  };
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}
