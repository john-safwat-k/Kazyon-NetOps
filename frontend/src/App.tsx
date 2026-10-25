import React, { useCallback, useEffect, useState } from "react";
import { useTheme } from "./design-system";
import { AuthProvider, getUserInitials, useAuth } from "./lib/auth";
import { DashboardView } from "./views/DashboardView";
import { DiagnosticsSandboxView } from "./views/DiagnosticsSandboxView";
import { DirectoryView } from "./views/DirectoryView";
import { HumanReviewView } from "./views/HumanReviewView";
import { KanbanBoardView } from "./views/KanbanBoardView";
import { LoginView } from "./views/LoginView";
import { MailboxTriageView } from "./views/MailboxTriageView";
import { ReplicationMonitorView } from "./views/ReplicationMonitorView";
import { SettingsView } from "./views/SettingsView";
import { TicketDetailView } from "./views/TicketDetailView";
import { TicketsListView } from "./views/TicketsListView";
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
  const [selectedTicket, setSelectedTicket] = useState<string | null>(null);
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

  const handleNavigate = useCallback((label: string) => {
    setSelectedTicket(null);
    setActiveNav(label);
  }, []);

  const handleOpenTicket = useCallback((ticketNumber: string) => {
    setSelectedTicket(ticketNumber);
  }, []);

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

  const sharedProps = {
    theme,
    onToggleTheme: toggleTheme,
    onNavigate: handleNavigate,
    onOpenTicket: handleOpenTicket,
    env: envLabel,
    initials,
    userDisplayName: user.display_name,
    userRoleLabel: roleLabel,
    onLogout: logout,
    canAccessNav,
  };

  if (selectedTicket) {
    return (
      <TicketDetailView {...sharedProps} ticketNumber={selectedTicket} />
    );
  }

  if (activeNav === "Users & Roles" && canAccessNav("Users & Roles")) {
    return (
      <UsersRbacView
        theme={theme}
        onToggleTheme={toggleTheme}
        onNavigate={handleNavigate}
        env={envLabel}
        canAccessNav={canAccessNav}
      />
    );
  }

  if (activeNav === "Kanban Board") {
    return <KanbanBoardView {...sharedProps} />;
  }

  if (activeNav === "Tickets List") {
    return <TicketsListView {...sharedProps} />;
  }

  if (activeNav === "Replication Monitor") {
    return <ReplicationMonitorView {...sharedProps} />;
  }

  if (activeNav === "Human Review") {
    return <HumanReviewView {...sharedProps} />;
  }

  if (activeNav === "Mailbox & Triage") {
    return <MailboxTriageView {...sharedProps} />;
  }

  if (activeNav === "Diagnostics Sandbox") {
    return <DiagnosticsSandboxView {...sharedProps} />;
  }

  if (activeNav === "Branches & ISPs") {
    return <DirectoryView {...sharedProps} />;
  }

  if (activeNav === "AI & SLA Settings") {
    return <SettingsView {...sharedProps} />;
  }

  return <DashboardView {...sharedProps} />;
}

export default function App() {
  return (
    <AuthProvider>
      <ConsoleRouter />
    </AuthProvider>
  );
}
