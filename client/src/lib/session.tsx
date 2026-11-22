"use client";

/*
 * Who is logged in, shared with every page.
 *
 * On first load we ask the backend for a fresh access token using the
 * refresh cookie; if it works, the user is logged in again without typing
 * anything. Logging out clears the cookie on the server and the token here.
 */

import { createContext, useCallback, useContext, useEffect, useState } from "react";

import { api, refreshSession, setAccessToken } from "@/lib/api";
import type { User } from "@/lib/types";

type SessionState = {
  user: User | null;
  status: "checking" | "signed-in" | "signed-out";
  signIn: (access: string, user: User) => void;
  signOut: () => Promise<void>;
};

const SessionContext = createContext<SessionState | null>(null);

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [status, setStatus] = useState<SessionState["status"]>("checking");

  useEffect(() => {
    refreshSession().then((result) => {
      setUser(result ? result.user : null);
      setStatus(result ? "signed-in" : "signed-out");
    });
  }, []);

  const signIn = useCallback((access: string, signedInUser: User) => {
    setAccessToken(access);
    setUser(signedInUser);
    setStatus("signed-in");
  }, []);

  const signOut = useCallback(async () => {
    await api.logout().catch(() => undefined);
    setAccessToken(null);
    setUser(null);
    setStatus("signed-out");
  }, []);

  return (
    <SessionContext.Provider value={{ user, status, signIn, signOut }}>
      {children}
    </SessionContext.Provider>
  );
}

export function useSession(): SessionState {
  const session = useContext(SessionContext);
  if (session === null) throw new Error("useSession must be used inside SessionProvider.");
  return session;
}
