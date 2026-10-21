import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import {
  authApi,
  getStoredToken,
  setStoredToken,
  UserDTO,
} from "./api";

const PERMISSION_EQUIVALENTS: Record<string, string[]> = {
  "tickets:view": ["tickets:read"],
  "tickets:read": ["tickets:view"],
  "tickets:edit_status": ["tickets:update", "tickets:create"],
  "tickets:assign": ["tickets:update"],
  "tickets:pause_ai": ["tickets:execute", "tickets:update"],
  "tickets:update": ["tickets:edit_status", "tickets:assign"],
  "tickets:execute": ["tickets:pause_ai"],
  "diagnostics:view_logs": ["diagnostics:read"],
  "diagnostics:read": ["diagnostics:view_logs"],
  "diagnostics:trigger_manual": ["diagnostics:execute", "diagnostics:create"],
  "diagnostics:execute": ["diagnostics:trigger_manual"],
  "emails:view": ["emails:read"],
  "emails:read": ["emails:view"],
  "emails:send_manual_reply": ["emails:create", "emails:execute"],
  "emails:force_isp_followup": ["emails:execute"],
  "emails:execute": ["emails:send_manual_reply", "emails:force_isp_followup"],
  "replication:view": ["replication:read"],
  "replication:read": ["replication:view"],
  "replication:upload": ["replication:create"],
  "replication:create": ["replication:upload"],
  "replication:trigger_notify": ["replication:execute"],
  "replication:execute": ["replication:trigger_notify"],
  "branches:view": ["branches:read"],
  "branches:read": ["branches:view"],
  "branches:edit": ["branches:update"],
  "branches:update": ["branches:edit"],
  "branches:import_sheet": ["branches:create"],
  "branches:create": ["branches:import_sheet"],
  "isps:manage": ["isps:read", "isps:create", "isps:update", "isps:delete"],
  "isps:read": ["isps:manage"],
  "isps:update": ["isps:manage"],
  "users:view": ["users:read"],
  "users:read": ["users:view"],
  "users:edit_permissions": ["users:update", "roles:manage"],
  "users:update": ["users:edit_permissions"],
  "roles:manage": ["users:edit_permissions", "users:update", "users:create"],
  "settings:manage_mailbox": ["settings:update", "settings:execute"],
  "settings:manage_agent_prompts": ["settings:update"],
  "settings:manage_sla_timers": ["settings:update"],
  "settings:update": [
    "settings:manage_mailbox",
    "settings:manage_agent_prompts",
    "settings:manage_sla_timers",
  ],
};

export interface AuthContextValue {
  user: UserDTO | null;
  token: string | null;
  isLoading: boolean;
  login: (usernameOrEmail: string, password: string, keepSignedIn?: boolean) => Promise<UserDTO>;
  logout: () => void;
  refreshUser: () => Promise<UserDTO | null>;
  hasPermission: (permission: string) => boolean;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserDTO | null>(null);
  const [token, setToken] = useState<string | null>(() => getStoredToken());
  const [isLoading, setIsLoading] = useState<boolean>(() => Boolean(getStoredToken()));

  const logout = useCallback(() => {
    setStoredToken(null);
    setToken(null);
    setUser(null);
  }, []);

  const refreshUser = useCallback(async (): Promise<UserDTO | null> => {
    const activeToken = getStoredToken();
    if (!activeToken) {
      setUser(null);
      setIsLoading(false);
      return null;
    }
    try {
      const me = await authApi.me();
      setUser(me);
      setToken(activeToken);
      return me;
    } catch {
      logout();
      return null;
    } finally {
      setIsLoading(false);
    }
  }, [logout]);

  useEffect(() => {
    void refreshUser();
  }, [refreshUser]);

  const login = useCallback(
    async (
      usernameOrEmail: string,
      password: string,
      keepSignedIn = true,
    ): Promise<UserDTO> => {
      const resp = await authApi.login(usernameOrEmail, password);
      setStoredToken(resp.access_token, keepSignedIn);
      setToken(resp.access_token);
      setUser(resp.user);
      return resp.user;
    },
    [],
  );

  const hasPermission = useCallback(
    (permission: string): boolean => {
      if (!user || !user.is_active) return false;
      if (user.is_super_admin) return true;
      const perms = new Set(user.permissions || []);
      if (perms.has("*") || perms.has(permission)) return true;
      const resource = permission.includes(":") ? permission.split(":")[0] : "";
      if (resource && perms.has(`${resource}:*`)) return true;
      const equivalents = PERMISSION_EQUIVALENTS[permission] || [];
      return equivalents.some((eq) => perms.has(eq));
    },
    [user],
  );

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      token,
      isLoading,
      login,
      logout,
      refreshUser,
      hasPermission,
    }),
    [user, token, isLoading, login, logout, refreshUser, hasPermission],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an <AuthProvider>");
  }
  return ctx;
}

export function getUserInitials(displayName?: string | null, username?: string | null): string {
  const source = (displayName || username || "KZ").trim();
  const parts = source.split(/[\s._-]+/).filter(Boolean);
  if (parts.length >= 2) {
    return `${parts[0].charAt(0)}${parts[1].charAt(0)}`.toUpperCase();
  }
  return source.slice(0, 2).toUpperCase();
}
