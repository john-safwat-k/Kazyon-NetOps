import React, { useCallback, useEffect, useMemo, useState } from "react";
import clsx from "clsx";
import {
  AppShell,
  Badge,
  BadgeTone,
  Button,
  Icon,
  IspBadge,
  IspName,
  PRIORITY_TONE,
} from "../design-system";
import { KanbanTicketCardDTO, branchesApi, ticketsApi } from "../lib/api";
import { ConsoleViewProps } from "./types";

const STATUS_TONE: Record<string, BadgeTone> = {
  "Escalated to ISP": "brand",
  "With ISP": "brand",
  "Needs Human Review": "critical",
  Resolved: "good",
  Closed: "good",
  "Awaiting Regional IT": "neutral",
  Diagnosing: "info",
  "Internal LAN Issue": "warning",
  Verifying: "info",
};

type SortKey =
  | "id"
  | "branch"
  | "priority"
  | "status"
  | "isp"
  | "failure"
  | "trigger"
  | "opened"
  | "mttr"
  | "ai";

export function TicketsListView({
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
  const [tickets, setTickets] = useState<KanbanTicketCardDTO[]>([]);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("All");
  const [ispFilter, setIspFilter] = useState("All");
  const [regionFilter, setRegionFilter] = useState("All");
  const [triggerFilter, setTriggerFilter] = useState("All");
  const [failureFilter, setFailureFilter] = useState("All");
  const [sortKey, setSortKey] = useState<SortKey>("opened");
  const [sortDir, setSortDir] = useState<1 | -1>(-1);
  const [directoryRegions, setDirectoryRegions] = useState<string[]>([
    "Behera",
    "Cairo",
    "New October",
    "Assyut",
    "Giza",
  ]);

  const loadTickets = useCallback(() => {
    ticketsApi
      .list({
        search: search.trim() || undefined,
        isp: ispFilter !== "All" ? ispFilter : undefined,
        region: regionFilter !== "All" ? regionFilter : undefined,
        trigger: triggerFilter !== "All" ? triggerFilter : undefined,
        failure_type: failureFilter !== "All" ? failureFilter : undefined,
      })
      .then((res) => setTickets(res))
      .catch(() => {});
  }, [search, ispFilter, regionFilter, triggerFilter, failureFilter]);

  useEffect(() => {
    loadTickets();
  }, [loadTickets]);

  useEffect(() => {
    branchesApi
      .list({ limit: 2000 })
      .then((res) => {
        const regions = Array.from(
          new Set(
            res.items
              .map((b) => b.region)
              .filter((r): r is string => Boolean(r))
          )
        ).sort();
        if (regions.length) {
          setDirectoryRegions(regions);
        }
      })
      .catch(() => {});
  }, []);

  const filteredAndSorted = useMemo(() => {
    const rank: Record<string, number> = {
      CRITICAL: 4,
      HIGH: 3,
      MEDIUM: 2,
      LOW: 1,
    };
    const filtered = tickets.filter((t) => {
      if (statusFilter === "Escalated to ISP") {
        return t.status === "Escalated to ISP" || t.status === "With ISP";
      }
      if (statusFilter === "Needs Human Review") {
        return t.status === "Needs Human Review";
      }
      if (statusFilter === "Resolved / Closed") {
        return t.status === "Resolved" || t.status === "Closed";
      }
      return true;
    });

    return [...filtered].sort((a, b) => {
      let va: string | number = "";
      let vb: string | number = "";
      if (sortKey === "priority") {
        va = rank[a.priority] || 0;
        vb = rank[b.priority] || 0;
      } else if (sortKey === "ai") {
        va = a.aiPaused ? 0 : 1;
        vb = b.aiPaused ? 0 : 1;
      } else if (sortKey === "failure") {
        va = a.failure_code || "—";
        vb = b.failure_code || "—";
      } else {
        va = String(a[sortKey] ?? "");
        vb = String(b[sortKey] ?? "");
      }
      if (va > vb) return sortDir;
      if (va < vb) return -sortDir;
      return 0;
    });
  }, [tickets, statusFilter, sortKey, sortDir]);

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir((d) => (d === 1 ? -1 : 1));
    } else {
      setSortKey(key);
      setSortDir(1);
    }
  };

  const handleClearFilters = () => {
    setSearch("");
    setStatusFilter("All");
    setIspFilter("All");
    setRegionFilter("All");
    setTriggerFilter("All");
    setFailureFilter("All");
  };

  const handleExport = (format: "csv" | "excel") => {
    const headers = [
      "Ticket",
      "Branch",
      "Region",
      "Priority",
      "Status",
      "ISP",
      "Case #",
      "Failure Type",
      "Trigger",
      "Opened",
      "MTTR",
      "AI",
    ];
    const rows = filteredAndSorted.map((t) => [
      t.id,
      t.branch,
      t.region,
      t.priority,
      t.status,
      t.isp,
      t.caseRef || "",
      t.failure_code || "—",
      t.trigger,
      t.opened,
      t.mttr,
      t.aiPaused ? "AI paused" : "AI active",
    ]);
    const csv = [headers, ...rows]
      .map((r) => r.map((v) => `"${String(v).replace(/"/g, '""')}"`).join(","))
      .join("\n");
    const blob = new Blob([csv], {
      type:
        format === "excel"
          ? "application/vnd.ms-excel;charset=utf-8;"
          : "text/csv;charset=utf-8;",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download =
      format === "excel"
        ? "kazyon-tickets-export.xls"
        : "kazyon-tickets-export.csv";
    a.click();
    URL.revokeObjectURL(url);
  };

  const columns: [SortKey, string][] = [
    ["id", "Ticket"],
    ["branch", "Branch"],
    ["priority", "Priority"],
    ["status", "Status"],
    ["isp", "ISP · Case #"],
    ["failure", "Failure type"],
    ["trigger", "Trigger"],
    ["opened", "Opened"],
    ["mttr", "MTTR"],
    ["ai", "AI"],
  ];

  return (
    <AppShell
      active="Tickets List"
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
          <h1>Tickets</h1>
          <p>
            All active and historical incidents · {filteredAndSorted.length}{" "}
            tickets matching current filters
          </p>
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <Button
            variant="secondary"
            icon="download"
            onClick={() => handleExport("csv")}
          >
            Export CSV
          </Button>
          <Button
            variant="primary"
            icon="download"
            onClick={() => handleExport("excel")}
          >
            Export to Excel
          </Button>
        </div>
      </div>

      <div
        className="kz-card"
        style={{
          padding: 12,
          display: "flex",
          gap: 8,
          flexWrap: "wrap",
          alignItems: "center",
        }}
      >
        <label className="kz-search" style={{ maxWidth: 300 }}>
          <span className="kz-muted">Search</span>
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="NET-, SAP code, case #, L.L ID"
            style={{
              border: 0,
              background: "transparent",
              outline: "none",
              font: "500 13px var(--font-sans)",
              color: "var(--ink)",
              flex: 1,
              minWidth: 0,
            }}
          />
        </label>

        <select
          aria-label="Status"
          className="kz-chip"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
        >
          <option value="All">Status: All</option>
          <option value="Escalated to ISP">Escalated to ISP</option>
          <option value="Needs Human Review">Needs Human Review</option>
          <option value="Resolved / Closed">Resolved / Closed</option>
        </select>

        <select
          aria-label="ISP"
          className="kz-chip"
          value={ispFilter}
          onChange={(e) => setIspFilter(e.target.value)}
        >
          <option value="All">ISP: All</option>
          <option value="NOOR">NOOR</option>
          <option value="ORANGE">ORANGE</option>
          <option value="WE">WE</option>
        </select>

        <select
          aria-label="Region"
          className="kz-chip"
          value={regionFilter}
          onChange={(e) => setRegionFilter(e.target.value)}
        >
          <option value="All">Region: All</option>
          {directoryRegions.map((r) => (
            <option key={r} value={r}>
              {r}
            </option>
          ))}
        </select>

        <select
          aria-label="Trigger"
          className="kz-chip"
          value={triggerFilter}
          onChange={(e) => setTriggerFilter(e.target.value)}
        >
          <option value="All">Trigger: All</option>
          <option value="DIRECT_EMAIL">DIRECT_EMAIL</option>
          <option value="REPLICATION_DASHBOARD">REPLICATION_DASHBOARD</option>
          <option value="PROACTIVE_SCAN">PROACTIVE_SCAN</option>
          <option value="UNKNOWN_ESCALATION">UNKNOWN_ESCALATION</option>
        </select>

        <select
          aria-label="Failure type"
          className="kz-chip"
          value={failureFilter}
          onChange={(e) => setFailureFilter(e.target.value)}
        >
          <option value="All">Failure: All</option>
          <option value="FULL_OUTAGE">FULL_OUTAGE</option>
          <option value="LOCAL_LOOP_DOWN_ON_4G">LOCAL_LOOP_DOWN_ON_4G</option>
          <option value="INTERNAL_LAN_SWITCH">INTERNAL_LAN_SWITCH</option>
          <option value="CABLE_UNPLUGGED">CABLE_UNPLUGGED</option>
        </select>

        <span style={{ flex: 1 }} />
        <button
          type="button"
          className="kz-btn kz-btn-ghost kz-btn-sm"
          onClick={handleClearFilters}
        >
          Clear filters
        </button>
      </div>

      <section className="kz-card" style={{ overflow: "hidden" }}>
        <div className="kz-scroll-x">
          <table className="kz-table">
            <thead>
              <tr>
                {columns.map(([key, label]) => (
                  <th key={key}>
                    <button
                      type="button"
                      onClick={() => handleSort(key)}
                      style={{
                        all: "unset",
                        cursor: "pointer",
                        display: "inline-flex",
                        gap: 4,
                      }}
                    >
                      {label}{" "}
                      <span aria-hidden="true">
                        {sortKey === key ? (sortDir > 0 ? "↑" : "↓") : ""}
                      </span>
                    </button>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filteredAndSorted.map((t) => (
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
                    <div className="kz-tcard-meta">{t.region}</div>
                  </td>
                  <td>
                    <Badge tone={PRIORITY_TONE[t.priority] || "neutral"}>
                      {t.priority}
                    </Badge>
                  </td>
                  <td>
                    <Badge tone={STATUS_TONE[t.status] || "neutral"}>
                      {t.status}
                    </Badge>
                  </td>
                  <td>
                    <IspBadge
                      isp={t.isp as IspName}
                      caseRef={t.caseRef || undefined}
                    />
                  </td>
                  <td className="kz-mono kz-nowrap">{t.failure_code || "—"}</td>
                  <td className="kz-tcard-meta kz-nowrap">{t.trigger}</td>
                  <td className="kz-num kz-nowrap">{t.opened}</td>
                  <td className="kz-num kz-nowrap">{t.mttr}</td>
                  <td>
                    <span
                      className={clsx("kz-ai", t.aiPaused && "kz-ai-paused")}
                    >
                      <Icon name={t.aiPaused ? "pause" : "bot"} size={14} />
                      {t.aiPaused ? "AI paused" : "AI active"}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            gap: 12,
            padding: "12px 16px",
            borderTop: "1px solid var(--border)",
            flexWrap: "wrap",
            fontSize: 13,
          }}
        >
          <span className="kz-muted">
            Showing 1–{filteredAndSorted.length} of {filteredAndSorted.length}
          </span>
          <div style={{ display: "flex", gap: 4 }}>
            <button
              type="button"
              className="kz-btn kz-btn-secondary kz-btn-sm"
              disabled
            >
              Previous
            </button>
            <button type="button" className="kz-btn kz-btn-primary kz-btn-sm">
              1
            </button>
            <button
              type="button"
              className="kz-btn kz-btn-secondary kz-btn-sm"
              disabled
            >
              Next
            </button>
          </div>
        </div>
      </section>
    </AppShell>
  );
}
