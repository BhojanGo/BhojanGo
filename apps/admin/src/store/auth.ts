import { create } from "zustand";
import { persist } from "zustand/middleware";

import { setAdminToken } from "@/lib/api";
import type { User } from "@bhojango/types";

interface AdminAuthState {
  user: User | null;
  accessToken: string | null;
  isAuthenticated: boolean;

  login: (token: string, user: User) => void;
  logout: () => void;
}

export const useAdminAuth = create<AdminAuthState>()(
  persist(
    (set) => ({
      user: null,
      accessToken: null,
      isAuthenticated: false,

      login: (token, user) => {
        setAdminToken(token);
        set({ accessToken: token, user, isAuthenticated: true });
      },

      logout: () => {
        setAdminToken(null);
        set({ user: null, accessToken: null, isAuthenticated: false });
      },
    }),
    {
      name: "bhojango-admin-auth",
      onRehydrateStorage: () => (state) => {
        if (state?.accessToken) setAdminToken(state.accessToken);
      },
    }
  )
);
