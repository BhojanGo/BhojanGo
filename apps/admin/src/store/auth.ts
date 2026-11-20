import { useSyncExternalStore } from "react";
import { create } from "zustand";
import { persist } from "zustand/middleware";

import { endSession, registerAuthHandlers } from "@/lib/api";

/** The signed-in admin as /auth/login returns them. */
export interface User {
  id: string;
  email: string | null;
  full_name: string;
  role: string;
  country: string;
}

// R22 security review (S8): the tokens are in httpOnly cookies (lib/api.ts); this store
// keeps only who is signed in, for the console's shell.
interface AdminAuthState {
  user: User | null;
  isAuthenticated: boolean;

  /** After the last sign-in step: its answer has already set the session's cookies. */
  login: (user: User) => void;
  /** Ends the session on the server (clears the cookies) and here. */
  logout: () => Promise<void>;
  /** Forget the session here only (the server already ended it). */
  forget: () => void;
}

// Sessions from before R22 kept the tokens in localStorage: remove them (the admin signs in again once).
if (typeof window !== "undefined") {
  try {
    window.localStorage.removeItem("bhojango-admin-auth");
  } catch {
    // storage blocked: nothing was kept there either
  }
}

export const useAdminAuth = create<AdminAuthState>()(
  persist(
    (set) => ({
      user: null,
      isAuthenticated: false,

      login: (user) => set({ user, isAuthenticated: true }),

      logout: async () => {
        set({ user: null, isAuthenticated: false });
        await endSession();
      },

      forget: () => set({ user: null, isAuthenticated: false }),
    }),
    {
      name: "bhojango-admin-auth-v2",
      partialize: (s) => ({ user: s.user, isAuthenticated: s.isAuthenticated }),
    }
  )
);

// The axios layer signs the console out here when the session can't be renewed.
registerAuthHandlers({ onLogout: () => useAdminAuth.getState().forget() });

/**
 * True once the persisted session has been read on the client. The first
 * render after a full page load uses the server snapshot (signed out), so an
 * auth guard must wait for this before redirecting to /login.
 */
export function useAuthHydrated(): boolean {
  // false on the server snapshot, true once rendering on the client
  return useSyncExternalStore(noopSubscribe, () => true, () => false);
}

const noopSubscribe = () => () => {};
