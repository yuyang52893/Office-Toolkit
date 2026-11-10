"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import {
  getCurrentUser,
  loginAccount,
  logoutAccount,
} from "@/lib/auth-api";
import {
  AUTH_TOKEN_CLEARED_EVENT,
  clearToken,
  getToken,
  setToken,
} from "@/lib/auth-storage";
import { ApiError } from "@/lib/errors";
import type { AuthUser } from "@/lib/types";

type AuthContextValue = {
  user: AuthUser | null;
  loading: boolean;
  refreshError: string;
  login: (username: string, password: string) => Promise<AuthUser>;
  logout: () => Promise<void>;
  refresh: () => Promise<AuthUser | null>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshError, setRefreshError] = useState("");

  const refresh = useCallback(async () => {
    if (!getToken()) {
      setUser(null);
      setLoading(false);
      return null;
    }
    setLoading(true);
    setRefreshError("");
    try {
      const current = await getCurrentUser();
      setUser(current);
      return current;
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        clearToken(false);
        setUser(null);
      } else {
        setRefreshError("登录状态验证失败，请重试");
      }
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void refresh();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [refresh]);

  useEffect(() => {
    const handleTokenCleared = () => {
      setUser(null);
      setLoading(false);
      setRefreshError("");
    };
    window.addEventListener(AUTH_TOKEN_CLEARED_EVENT, handleTokenCleared);
    return () => window.removeEventListener(AUTH_TOKEN_CLEARED_EVENT, handleTokenCleared);
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const result = await loginAccount(username, password);
    setToken(result.access_token);
    setUser(result.user);
    setRefreshError("");
    return result.user;
  }, []);

  const logout = useCallback(async () => {
    try {
      await logoutAccount();
    } catch {
      // Local logout must still complete if the server token is already invalid.
    } finally {
      clearToken(false);
      setUser(null);
      setRefreshError("");
    }
  }, []);

  const value = useMemo(
    () => ({ user, loading, refreshError, login, logout, refresh }),
    [user, loading, refreshError, login, logout, refresh],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (!value) {
    throw new Error("useAuth must be used inside AuthProvider");
  }
  return value;
}
