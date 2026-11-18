"use client";

/**
 * Client-side session context.
 *
 * The JWT itself lives in an httpOnly cookie owned by the backend — this
 * context only mirrors *who* is signed in (via GET /api/auth/me) so the UI can
 * react. Route protection on the server remains the source of truth.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { auth as authApi, ApiRequestError } from "@/lib/api";
import type { User } from "@/lib/types";

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<User | null>;
  login: (email: string, password: string) => Promise<User>;
  register: (data: {
    full_name: string;
    email: string;
    password: string;
    confirm_password: string;
    accept_terms: boolean;
  }) => Promise<User>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async (): Promise<User | null> => {
    try {
      const me = await authApi.me();
      setUser(me);
      setError(null);
      return me;
    } catch (err) {
      if (err instanceof ApiRequestError && err.status === 401) {
        setUser(null);
      } else {
        setError(err instanceof Error ? err.message : "Could not reach the server.");
      }
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    authApi.me().then((me) => {
      if (!active) return;
      setUser(me);
      setError(null);
    }).catch((err: unknown) => {
      if (!active) return;
      if (err instanceof ApiRequestError && err.status === 401) setUser(null);
      else setError(err instanceof Error ? err.message : "Could not reach the server.");
    }).finally(() => {
      if (active) setLoading(false);
    });
    return () => { active = false; };
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const res = await authApi.login({ email, password });
    setUser(res.user);
    setError(null);
    return res.user;
  }, []);

  const register = useCallback(
    async (data: {
      full_name: string;
      email: string;
      password: string;
      confirm_password: string;
      accept_terms: boolean;
    }) => {
      const res = await authApi.register(data);
      setUser(res.user);
      setError(null);
      return res.user;
    },
    [],
  );

  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } finally {
      setUser(null);
    }
  }, []);

  return (
    <AuthContext.Provider
      value={{ user, loading, error, refresh, login, register, logout }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
