import React, { useCallback, useEffect, useState } from "react";
import {
  AppShell,
  Badge,
  BadgeTone,
  BarChart,
  Button,
  HealthBar,
  HealthServiceItem,
  IspBadge,
  KpiCard,
  SlaTimer,
  StatusPill,
} from "../design-system";
import { DashboardSummaryDTO, dashboardApi } from "../lib/api";
import { ConsoleViewProps } from "./types";

export function DashboardView({
  theme,
  onToggleTheme,
  onNavigate,
  onOpenTicket,
  env,
  initials,
  userDisplayName,
  userRoleLabel,
  onLogout,
  canAccessNav,
}: ConsoleViewProps) {
  const [range, setRange] = useState<"24h" | "7d" | "30d">("7d");
  const [data, setData] = useState<DashboardSummaryDTO | null>(null);

  const loadSummary = useCallback((r: "24h" | "7d" | "30d") => {
    dashboardApi
      .summary(r)
      .then((res) => setData(res))
      .catch(() => {});
  }, []);

  useEffect(() => {
    loadSummary(range);
  }, [range, loadSummary]);

  const kpis = data?.kpis ?? {
    open: 0,
    review: 0,
    welcome: 0,
    followup: 0,
    repl: 0,
  };

  const services: HealthServiceItem[] = (data?.services as HealthServiceItem[]) ?? [
    {
      name: "vLLM · Gemma 4 26B",
      detail: "10.100.109.9:8002 · Ready",
      state: "ok",
    },
    {
      name: "SMTP Mailbox (noc@kazyon.com)",
      detail: "Service account active",
      state: "ok",
    },
    { name: "PostgreSQL 16", detail: "Connected", state: "ok" },
    { name: "Redis 7", detail: "Loop guard active", state: "ok" },
  ];

  const rangeLabel =
    data?.range_label ??
    (range === "24h"
      ? "today"
      : range === "30d"
        ? "last 30 days"
        : "last 7 days");

  const handleExportCsv = () => {
    if (!data) return;
    const rows = [
      [
        "Ticket",
        "Branch",
        "Region",
        "Failure",
        "ISP",
        "Stage",
        "SLA Minutes Left",
      ],
      ...data.watchlist.map((w) => [
        w.id,
        w.branch,
        w.region,
        w.failure,
        w.isp,
        w.stage,
        String(w.left),
      ]),
    ];
    const csv = rows
      .map((r) => r.map((v) => `"${v.replace(/"/g, '""')}"`).join(","))
      .join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `kazyon-sla-dashboard-${range}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <AppShell
      active="Dashboard"
      theme={theme}
      onToggleTheme={onToggleTheme}
      onNavigate={onNavigate}
      env={env}
      initials={initials}
      userDisplayName={userDisplayName}
      userRoleLabel={userRoleLabel}
      onLogout={onLogout}
      canAccessNav={canAccessNav}
    >
      <div className="kz-page-hd">
        <div>
          <h1>Executive &amp; SLA Dashboard</h1>
          <p>
            {(data?.total_branches ?? 1150).toLocaleString()} branches · NOOR,
            ORANGE, WE · Live database metrics
          </p>
        </div>
        <div
          style={{
            display: "flex",
            gap: 8,
            alignItems: "center",
            flexWrap: "wrap",
          }}
        >
          <div className="kz-seg" role="group" aria-label="Time range">
            {(
              [
                ["24h", "Today"],
                ["7d", "7 days"],
                ["30d", "30 days"],
              ] as const
            ).map(([key, label]) => (
              <button
                key={key}
                type="button"
                className={range === key ? "on" : ""}
                onClick={() => setRange(key)}
              >
                {label}
              </button>
            ))}
          </div>
          <Button variant="secondary" icon="download" onClick={handleExportCsv}>
            Export
          </Button>
          <Button
            variant="primary"
            icon="plus"
            onClick={() => onNavigate("Kanban Board")}
          >
            New ticket
          </Button>
        </div>
      </div>

      <HealthBar services={services} />

      <div className="kz-grid-kpi">
        <div
          role="button"
          tabIndex={0}
          onClick={() => onNavigate("Tickets List")}
          onKeyDown={(e) => e.key === "Enter" && onNavigate("Tickets List")}
          style={{ cursor: "pointer" }}
        >
          <KpiCard
            label="Open tickets"
            value={kpis.open}
            icon="ticket"
            hint="Active in workflow"
          />
        </div>
        <div
          role="button"
          tabIndex={0}
          onClick={() => onNavigate("Human Review")}
          onKeyDown={(e) => e.key === "Enter" && onNavigate("Human Review")}
          style={{ cursor: "pointer" }}
        >
          <KpiCard
            label="Needs human review"
            value={kpis.review}
            icon="alert"
            tone={kpis.review > 0 ? "critical" : "default"}
            hint="Quota, MSAN, unknown mail"
          />
        </div>
        <div
          role="button"
          tabIndex={0}
          onClick={() => onNavigate("Kanban Board")}
          onKeyDown={(e) => e.key === "Enter" && onNavigate("Kanban Board")}
          style={{ cursor: "pointer" }}
        >
          <KpiCard
            label="Overdue 2h welcome"
            value={kpis.welcome}
            icon="mail"
            tone={kpis.welcome > 0 ? "warning" : "default"}
            hint="ISP has not opened a case"
          />
        </div>
        <div
          role="button"
          tabIndex={0}
          onClick={() => onNavigate("Kanban Board")}
          onKeyDown={(e) => e.key === "Enter" && onNavigate("Kanban Board")}
          style={{ cursor: "pointer" }}
        >
          <KpiCard
            label="Overdue 4–6h update"
            value={kpis.followup}
            icon="clock"
            tone={kpis.followup > 0 ? "warning" : "default"}
            hint="Chasers sent automatically"
          />
        </div>
        <div
          role="button"
          tabIndex={0}
          onClick={() => onNavigate("Replication Monitor")}
          onKeyDown={(e) =>
            e.key === "Enter" && onNavigate("Replication Monitor")
          }
          style={{ cursor: "pointer" }}
        >
          <KpiCard
            label="Not updated today"
            value={kpis.repl}
            icon="replication"
            hint="Latest Replication report"
          />
        </div>
      </div>

      <div className="kz-grid-3">
        <section className="kz-card">
          <div className="kz-card-hd">
            <div>
              <h2>Outages by ISP</h2>
              <p>Tickets opened, {rangeLabel}</p>
            </div>
          </div>
          <div className="kz-card-bd">
            <BarChart
              data={
                data?.by_isp ?? [
                  { label: "NOOR", value: 0, hint: "906 stores" },
                  { label: "ORANGE", value: 0, hint: "181 stores" },
                  { label: "WE", value: 0, hint: "63 stores" },
                ]
              }
            />
          </div>
        </section>

        <section className="kz-card">
          <div className="kz-card-hd">
            <div>
              <h2>MTTR by ISP</h2>
              <p>Mean hours, escalation → verified fix</p>
            </div>
          </div>
          <div className="kz-card-bd">
            <BarChart
              unit="h"
              data={
                data?.mttr_by_isp ?? [
                  { label: "NOOR", value: 0 },
                  { label: "ORANGE", value: 0 },
                  { label: "WE", value: 0 },
                ]
              }
            />
          </div>
        </section>

        <section className="kz-card">
          <div className="kz-card-hd">
            <div>
              <h2>Outages by failure type</h2>
              <p>Diagnosis from dual-ping &amp; traceroute</p>
            </div>
          </div>
          <div className="kz-card-bd">
            <BarChart
              data={
                data?.by_type ?? [
                  { label: "Full outage", value: 0 },
                  { label: "4G / LL down", value: 0 },
                  { label: "Internal switch", value: 0 },
                  { label: "Cables", value: 0 },
                ]
              }
            />
          </div>
        </section>
      </div>

      <div className="kz-grid-main">
        <section className="kz-card" style={{ overflow: "hidden" }}>
          <div className="kz-card-hd" style={{ paddingBottom: 12 }}>
            <div>
              <h2>SLA watchlist</h2>
              <p>Tickets waiting on an ISP, most urgent first</p>
            </div>
            <a
              href="#board"
              onClick={(e) => {
                e.preventDefault();
                onNavigate("Kanban Board");
              }}
              style={{ fontSize: 13, fontWeight: 600 }}
            >
              Open board
            </a>
          </div>
          <div className="kz-scroll-x">
            <table className="kz-table">
              <thead>
                <tr>
                  <th>Ticket</th>
                  <th>Branch</th>
                  <th>ISP</th>
                  <th>Checks</th>
                  <th>Stage</th>
                  <th>SLA</th>
                </tr>
              </thead>
              <tbody>
                {(data?.watchlist ?? []).length === 0 ? (
                  <tr>
                    <td
                      colSpan={6}
                      className="kz-muted"
                      style={{ textAlign: "center", padding: 24 }}
                    >
                      No tickets currently waiting on an ISP SLA timer.
                    </td>
                  </tr>
                ) : (
                  (data?.watchlist ?? []).map((t) => (
                    <tr key={t.id}>
                      <td>
                        <a
                          href={`#ticket-${t.id}`}
                          className="kz-tcard-id"
                          onClick={(e) => {
                            e.preventDefault();
                            onOpenTicket(t.id);
                          }}
                        >
                          {t.id}
                        </a>
                      </td>
                      <td>
                        <div className="kz-nowrap" style={{ fontWeight: 600 }}>
                          {t.branch}
                        </div>
                        <div className="kz-tcard-meta">
                          {t.region} · {t.failure}
                        </div>
                      </td>
                      <td>
                        <IspBadge isp={t.isp} />
                      </td>
                      <td>
                        <div className="kz-tcard-pills">
                          {t.checks.map((c, idx) => (
                            <StatusPill
                              key={idx}
                              label={c.label}
                              state={c.state}
                            />
                          ))}
                        </div>
                      </td>
                      <td>
                        <Badge tone={(t.tone as BadgeTone) || "brand"}>
                          {t.stage}
                        </Badge>
                      </td>
                      <td className="kz-nowrap">
                        <SlaTimer minutesLeft={t.left} totalMinutes={t.total} />
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </section>

        <section className="kz-card">
          <div className="kz-card-hd">
            <div>
              <h2>Outages by region</h2>
              <p>Open + resolved, {rangeLabel}</p>
            </div>
          </div>
          <div className="kz-card-bd">
            <BarChart
              data={
                data?.by_region ?? [
                  { label: "Behera", value: 0, hint: "350 stores" },
                  { label: "Cairo", value: 0, hint: "223 stores" },
                  { label: "New October", value: 0, hint: "212 stores" },
                  { label: "Assyut", value: 0, hint: "209 stores" },
                  { label: "Giza", value: 0, hint: "156 stores" },
                ]
              }
            />
          </div>
        </section>
      </div>
    </AppShell>
  );
}
