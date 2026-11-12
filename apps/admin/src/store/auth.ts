import { useSyncExternalStore } from "react";
import { create } from "zustand";
import { persist } from "zustand/middleware";

import { registerAuthHandlers, setAdminTokens } from "@/lib/api";
import type { User } from "@bhojango/types";

interface AdminAuthState {
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
  isAuthenticated: boolean;

  login: (accessToken: string, refreshToken: string | null, user: User) => void;
  logout: () => void;
}

export const useAdminAuth = create<AdminAuthState>()(
  persist(
    (set) => ({
      user: null,
      accessToken: null,
      refreshToken: null,
      isAuthenticated: false,

      login: (accessToken, refreshToken, user) => {
        setAdminTokens(accessToken, refreshToken);
        set({ accessToken, refreshToken, user, isAuthenticated: true });
      },

      logout: () => {
        setAdminTokens(null, null);
        set({ user: null, accessToken: null, refreshToken: null, isAuthenticated: false });
      },
    }),
    {
      name: "bhojango-admin-auth",
      onRehydrateStorage: () => (state) => {
        if (state?.accessToken) setAdminTokens(state.accessToken, state.refreshToken);
      },
    }
  )
);

// Bridge the axios layer back to the store: persist rotated tokens and honor forced logout.
registerAuthHandlers({
  onTokensRefreshed: (accessToken, refreshToken) =>
    useAdminAuth.setState({ accessToken, refreshToken }),
  onLogout: () => useAdminAuth.getState().logout(),
});

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
