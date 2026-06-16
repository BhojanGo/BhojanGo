"use client";

import { useEffect } from "react";
import { useAuthStore } from "@/store/auth";
import { api } from "@/lib/api";

export function AuthBootstrap({ children }: { children: React.ReactNode }) {
  const { accessToken, setUser, logout } = useAuthStore();

  useEffect(() => {
    if (!accessToken) return;

    api
      .get("/user/me")
      .then((res) => {
        setUser(res.data);
      })
      .catch((err) => {
        if (err.response?.status === 401) {
          logout();
        }
      });
  }, [accessToken, setUser, logout]);

  return <>{children}</>;
}
