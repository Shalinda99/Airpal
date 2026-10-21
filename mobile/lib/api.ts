import AsyncStorage from '@react-native-async-storage/async-storage';

import { secureStorage } from './secureStorage';

export const API_URL = process.env.EXPO_PUBLIC_API_URL ?? 'http://localhost:8000/api/v1';

const ACCESS = 'airpal.access';
const REFRESH = 'airpal.refresh';

export class ApiError extends Error {
  constructor(public status: number, public detail: string) {
    super(detail);
  }
}

type Listener = () => void;
let onSessionExpired: Listener = () => {};
export function setSessionExpiredHandler(fn: Listener) {
  onSessionExpired = fn;
}

export async function saveTokens(access: string, refresh: string) {
  await secureStorage.set(ACCESS, access);
  await secureStorage.set(REFRESH, refresh);
}

export async function clearTokens() {
  await secureStorage.remove(ACCESS);
  await secureStorage.remove(REFRESH);
}

export async function hasSession() {
  return !!(await secureStorage.get(REFRESH));
}

let refreshing: Promise<boolean> | null = null;

async function refreshTokens(): Promise<boolean> {
  if (!refreshing) {
    refreshing = (async () => {
      const refresh = await secureStorage.get(REFRESH);
      if (!refresh) return false;
      try {
        const res = await fetch(`${API_URL}/auth/refresh`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token: refresh }),
        });
        if (!res.ok) return false;
        const data = await res.json();
        await saveTokens(data.access_token, data.refresh_token);
        return true;
      } catch {
        return false;
      } finally {
        refreshing = null;
      }
    })();
  }
  return refreshing;
}

export async function api<T = any>(
  path: string,
  opts: { method?: string; body?: unknown; auth?: boolean } = {},
  retry = true,
): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (opts.auth !== false) {
    const token = await secureStorage.get(ACCESS);
    if (token) headers.Authorization = `Bearer ${token}`;
  }
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      method: opts.method ?? 'GET',
      headers,
      body: opts.body === undefined ? undefined : JSON.stringify(opts.body),
    });
  } catch {
    throw new ApiError(0, 'Network unavailable');
  }
  if (res.status === 401 && retry && opts.auth !== false) {
    if (await refreshTokens()) return api<T>(path, opts, false);
    await clearTokens();
    onSessionExpired();
  }
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  const data = text ? JSON.parse(text) : null;
  if (!res.ok) {
    const d = data?.detail;
    throw new ApiError(res.status, typeof d === 'string' ? d : d?.error ?? `Request failed (${res.status})`);
  }
  return data as T;
}

export type Cached<T> = { data: T; fromCache: boolean; cachedAt?: number };

/** Network first; falls back to the last stored copy when offline. */
export async function cachedGet<T>(key: string, path: string): Promise<Cached<T>> {
  try {
    const data = await api<T>(path);
    await AsyncStorage.setItem(`cache:${key}`, JSON.stringify({ data, at: Date.now() }));
    return { data, fromCache: false };
  } catch (e) {
    if (e instanceof ApiError && e.status !== 0) throw e;
    const raw = await AsyncStorage.getItem(`cache:${key}`);
    if (raw) {
      const { data, at } = JSON.parse(raw);
      return { data, fromCache: true, cachedAt: at };
    }
    throw e;
  }
}

export async function clearCaches() {
  const keys = (await AsyncStorage.getAllKeys()).filter((k) => k.startsWith('cache:'));
  await AsyncStorage.multiRemove(keys);
}
