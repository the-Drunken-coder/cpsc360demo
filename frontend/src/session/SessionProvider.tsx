import { Button, NonIdealState, Spinner } from "@blueprintjs/core";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, onUnauthorized, setToken } from "../api/client";
import type { User } from "../api/types";

const HANDLE_KEY = "cpsc360.handle";
const DEFAULT_HANDLE = "jrivera";

function storedHandle(): string {
  try {
    return localStorage.getItem(HANDLE_KEY) ?? DEFAULT_HANDLE;
  } catch {
    return DEFAULT_HANDLE;
  }
}

function storeHandle(handle: string): void {
  try {
    localStorage.setItem(HANDLE_KEY, handle);
  } catch {
    // Storage can be unavailable in private windows; the session still works for this tab.
  }
}

interface SessionValue {
  user: User;
  users: User[];
  canWrite: boolean;
  isLead: boolean;
  switchUser: (handle: string) => Promise<void>;
}

const SessionContext = createContext<SessionValue | null>(null);

export function useSession(): SessionValue {
  const value = useContext(SessionContext);
  if (!value) throw new Error("useSession outside SessionProvider");
  return value;
}

export function SessionProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [user, setUser] = useState<User | null>(null);
  const [error, setError] = useState<string | null>(null);
  const users = useQuery({ queryKey: ["users"], queryFn: api.users, staleTime: Infinity });

  const login = useCallback(async (handle: string) => {
    const session = await api.createSession(handle);
    setToken(session.token);
    storeHandle(session.user.handle);
    setUser(session.user);
    return session;
  }, []);

  const start = useCallback(() => {
    setError(null);
    login(storedHandle())
      .catch(() => login(DEFAULT_HANDLE))
      .catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)));
  }, [login]);

  useEffect(() => {
    start();
    onUnauthorized(async () => {
      try {
        return (await login(storedHandle())).token;
      } catch {
        return null;
      }
    });
  }, [login, start]);

  const switchUser = useCallback(async (handle: string) => {
    await login(handle);
    await queryClient.resetQueries({ predicate: (q) => q.queryKey[0] !== "users" });
  }, [login, queryClient]);

  const value = useMemo<SessionValue | null>(() => user && {
    user,
    users: users.data ?? [user],
    canWrite: user.role !== "viewer",
    isLead: user.role === "lead",
    switchUser,
  }, [user, users.data, switchUser]);

  if (error) {
    return <NonIdealState icon="offline" title="API unavailable" description={`Could not start a session: ${error}`}
      action={<Button icon="refresh" text="Retry" onClick={start} />} />;
  }
  if (!value) return <NonIdealState icon={<Spinner />} title="Starting session" />;
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}
