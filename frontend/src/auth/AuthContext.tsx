import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { PropsWithChildren } from "react";
import api, { refreshSession, setAccessToken } from "../api/client";
import type { TokenResponse, User } from "../types";

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  signIn: (identifier: string, password: string, expectedRole: User["role"]) => Promise<User>;
  signOut: () => Promise<void>;
  updateUser: (user: User) => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: PropsWithChildren) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    refreshSession()
      .then((data) => {
        if (active) {
          setUser(data?.user ?? null);
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const signIn = useCallback(async (identifier: string, password: string, expectedRole: User["role"]) => {
    const loginIdentifier = identifier.trim();
    const credentials = loginIdentifier.includes("@")
      ? { email: loginIdentifier, password, expected_role: expectedRole }
      : { username: loginIdentifier, password, expected_role: expectedRole };
    const { data } = await api.post<TokenResponse>("/auth/login", credentials);
    setAccessToken(data.access_token);
    setUser(data.user);
    return data.user;
  }, []);

  const signOut = useCallback(async () => {
    try {
      await api.post("/auth/logout");
    } finally {
      setAccessToken(null);
      setUser(null);
    }
  }, []);

  const updateUser = useCallback((nextUser: User) => setUser(nextUser), []);
  const value = useMemo(() => ({ user, loading, signIn, signOut, updateUser }), [user, loading, signIn, signOut, updateUser]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within AuthProvider");
  return context;
}
