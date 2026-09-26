"use client";

import { useRouter } from "next/navigation";
import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { authApi } from "@/lib/api";
import type { User } from "@/types/api";

/**
 * Who is signed in.
 *
 * The tokens themselves are httpOnly cookies, so nothing here can read them: this holds
 * only the profile the server already returned, which is enough to greet the user and
 * hide the controls their role does not allow. Authorisation is still the server's job.
 */

interface SessionContextValue {
  user: User;
  isManager: boolean;
  /** Re-read the profile after it has been edited. */
  refresh: () => Promise<void>;
  signOut: () => Promise<void>;
}

const SessionContext = createContext<SessionContextValue | null>(null);

export function SessionProvider({ user, children }: { user: User; children: ReactNode }) {
  const [current, setCurrent] = useState(user);
  const router = useRouter();

  const refresh = useCallback(async () => {
    setCurrent(await authApi.me());
  }, []);

  const signOut = useCallback(async () => {
    try {
      await authApi.logout();
    } finally {
      // Whatever the server said, the session is over as far as this tab is concerned.
      router.replace("/login");
      router.refresh();
    }
  }, [router]);

  const value = useMemo(
    () => ({ user: current, isManager: current.role === "manager", refresh, signOut }),
    [current, refresh, signOut],
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionContextValue {
  const context = useContext(SessionContext);
  if (!context) throw new Error("useSession must be used inside a SessionProvider");
  return context;
}
