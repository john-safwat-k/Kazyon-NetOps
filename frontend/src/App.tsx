import React, { useCallback, useEffect, useState } from "react";
import {
  AppShell,
  Badge,
  Button,
  DashboardScreen,
  HealthServiceItem,
  KanbanBoard,
  useTheme,
} from "./design-system";
import { AuthProvider, getUserInitials, useAuth } from "./lib/auth";
import { LoginView } from "./views/LoginView";
import { UsersRbacView } from "./views/UsersRbacView";

interface HealthPayload {
  status: string;
  service: string;
  environment: string;
  env_slug: string;
  version: string;
  vllm_base_url: string;
  vllm_model: string;
}

const NAV_REQUIRED_PERMISSIONS: Record<string, string> = {
  Dashboard: "tickets:view",
  "Kanban Board": "tickets:view",
  "Tickets List": "tickets:view",
  "Human Review": "tickets:view",
  "Replication Monitor": "replication:view",
  "Mailbox & Triage": "emails:view",
  "Diagnostics Sandbox": "diagnostics:view_logs",
  "Branches & ISPs": "branches:view",
  "Users & Roles": "users:view",
  "AI & SLA Settings": "settings:read",
};

function ConsoleRouter() {
  const { theme, toggleTheme } = useTheme();
  const { user, isLoading, logout, hasPermission } = useAuth();
  const [activeNav, setActiveNav] = useState<string>("Dashboard");
  const [health, setHealth] = useState<HealthPayload | null>(null);

  useEffect(() => {
    fetch("/api/health")
      .then((res) => res.json())
      .then((data: HealthPayload) => setHealth(data))
      .catch(() => setHealth(null));
  }, []);

  const canAccessNav = useCallback(
    (label: string): boolean => {
      const reqPerm = NAV_REQUIRED_PERMISSIONS[label];
      if (!reqPerm) return true;
      return hasPermission(reqPerm);
    },
    [hasPermission],
  );

  const envLabel =
    health?.env_slug?.toUpperCase() === "DEV" ? "DEV :8085" : "PROD :8084";

  if (isLoading) {
    return (
      <div
        className="kz"
        data-theme={theme}
        style={{
          minHeight: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "var(--surface-000)",
          color: "var(--ink)",
        }}
      >
        <span className="kz-live">Verifying Kazyon NetOps session…</span>
      </div>
    );
  }

  if (!user) {
    return (
      <LoginView
        theme={theme}
        onToggleTheme={toggleTheme}
        envSlug={health?.env_slug || "dev"}
        apiReachable={Boolean(health)}
      />
    );
  }

  const initials = getUserInitials(user.display_name, user.username);
  const roleLabel = user.is_super_admin
    ? "Super Admin"
    : user.role_name === "support_engineer"
      ? "HQ Network Engineer"
      : user.role_name === "viewer"
        ? "Viewer / Auditor"
        : user.role_name;

  const healthServices: HealthServiceItem[] = [
    {
      name: "vLLM · Gemma 4 26B",
      detail: `${health?.vllm_base_url?.replace(/^https?:\/\//, "").replace(/\/v1$/, "") ?? "10.100.109.9:8002"} · 412 ms`,
      state: "ok",
    },
    {
      name: "IMAP / SMTP Mailbox",
      detail: "Last poll 14 s ago",
      state: "ok",
    },
    {
      name: "PostgreSQL 16",
      detail: ":5434 · 18 conn",
      state: health?.status === "ok" || !health ? "ok" : "degraded",
    },
    {
      name: "Redis 7",
      detail: ":6384 · queue depth 9",
      state: "degraded",
    },
  ];

  if (activeNav === "Users & Roles" && canAccessNav("Users & Roles")) {
    return (
      <UsersRbacView
        theme={theme}
        onToggleTheme={toggleTheme}
        onNavigate={setActiveNav}
        env={envLabel}
        canAccessNav={canAccessNav}
      />
    );
  }

  if (activeNav === "Dashboard") {
    return (
      <DashboardScreen
        theme={theme}
        onToggleTheme={toggleTheme}
        onNavigate={setActiveNav}
        env={envLabel}
        services={healthServices}
        initials={initials}
        userDisplayName={user.display_name}
        userRoleLabel={roleLabel}
        onLogout={logout}
        canAccessNav={canAccessNav}
      />
    );
  }

  if (activeNav === "Kanban Board") {
    return (
      <KanbanBoard
        theme={theme}
        onToggleTheme={toggleTheme}
        onNavigate={setActiveNav}
        env={envLabel}
        initials={initials}
        userDisplayName={user.display_name}
        userRoleLabel={roleLabel}
        onLogout={logout}
        canAccessNav={canAccessNav}
      />
    );
  }

  return (
    <AppShell
      active={activeNav}
      theme={theme}
      onToggleTheme={toggleTheme}
      onNavigate={setActiveNav}
      env={envLabel}
      initials={initials}
      userDisplayName={user.display_name}
      userRoleLabel={roleLabel}
      onLogout={logout}
      canAccessNav={canAccessNav}
    >
      <div className="kz-page-hd">
        <div>
          <h1>{activeNav}</h1>
          <p>
            Kazyon NetOps Console · Follow the Kazyon NetOps Design System skill
            to build this screen.
          </p>
        </div>
        <div className="kz-row">
          <Badge tone="brand">Kazyon NetOps v1</Badge>
          <Button
            variant="primary"
            onClick={() => setActiveNav("Dashboard")}
          >
            Back to Dashboard
          </Button>
        </div>
      </div>
      <div className="kz-card">
        <div className="kz-card-bd">
          <p className="kz-muted" style={{ margin: 0 }}>
            Select <b>Dashboard</b>, <b>Kanban Board</b>, or{" "}
            <b>Users &amp; Roles</b> in the sidebar to inspect the live Kazyon
            NetOps screens.
          </p>
        </div>
      </div>
    </AppShell>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <ConsoleRouter />
    </AuthProvider>
  );
}
