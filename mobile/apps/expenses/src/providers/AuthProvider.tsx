import { createContext, PropsWithChildren, useContext, useEffect, useMemo, useState } from "react";

import { authApi, type MobileUser } from "../lib/api";
import { clearSession, getAccessToken, getStoredUser, setAccessToken, setStoredUser } from "../lib/auth-storage";

type AuthContextValue = {
  isReady: boolean;
  user: MobileUser | null;
  accessToken: string | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshMe: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: PropsWithChildren) {
  const [isReady, setIsReady] = useState(false);
  const [user, setUser] = useState<MobileUser | null>(null);
  const [accessToken, setAccessTokenState] = useState<string | null>(null);

  useEffect(() => {
    async function bootstrap() {
      const [token, storedUser] = await Promise.all([getAccessToken(), getStoredUser()]);
      if (token) setAccessTokenState(token);
      if (storedUser) setUser(storedUser);
      setIsReady(true);
    }

    bootstrap();
  }, []);

  async function login(email: string, password: string) {
    const response = await authApi.login(email, password);
    await Promise.all([
      setAccessToken(response.access_token),
      setStoredUser(response.user)
    ]);
    setAccessTokenState(response.access_token);
    setUser(response.user);
  }

  async function refreshMe() {
    const current = await authApi.me();
    await setStoredUser(current);
    setUser(current);
  }

  async function logout() {
    await clearSession();
    setAccessTokenState(null);
    setUser(null);
  }

  const value = useMemo<AuthContextValue>(() => ({
    isReady,
    user,
    accessToken,
    login,
    logout,
    refreshMe
  }), [isReady, user, accessToken]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return value;
}
