import React, { useEffect, useState } from "react";
import {
  AppShell,
  Badge,
  Button,
  DashboardScreen,
  HealthServiceItem,
  KanbanBoard,
  useTheme,
} from "./design-system";

interface HealthPayload {
  status: string;
  service: string;
  environment: string;
  env_slug: string;
  version: string;
  vllm_base_url: string;
  vllm_model: string;
}

export default function App() {
  const { theme, toggleTheme } = useTheme();
  const [activeNav, setActiveNav] = useState<string>("Dashboard");
  const [health, setHealth] = useState<HealthPayload | null>(null);

  useEffect(() => {
    fetch("/api/health")
      .then((res) => res.json())
      .then((data: HealthPayload) => setHealth(data))
      .catch(() => setHealth(null));
  }, []);

  const envLabel =
    health?.env_slug?.toUpperCase() === "DEV" ? "DEV :8085" : "PROD :8084";

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

  if (activeNav === "Dashboard") {
    return (
      <DashboardScreen
        theme={theme}
        onToggleTheme={toggleTheme}
        onNavigate={setActiveNav}
        env={envLabel}
        services={healthServices}
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
            Select <b>Dashboard</b> or <b>Kanban Board</b> in the sidebar to
            inspect the live Kazyon NetOps reference screens.
          </p>
        </div>
      </div>
    </AppShell>
  );
}
