import React, { useCallback, useEffect, useMemo, useState } from "react";
import clsx from "clsx";
import {
  AppShell,
  Button,
  IspBadge,
  IspName,
  KANBAN_LIFECYCLE_COLUMNS,
  Ticket,
  TicketCard,
} from "../design-system";
import {
  BranchDTO,
  KanbanTicketCardDTO,
  PriorityDTO,
  branchesApi,
  ticketsApi,
} from "../lib/api";
import { ConsoleViewProps } from "./types";

const BASE_REGIONS = ["Behera", "Cairo", "New October", "Assyut", "Giza"];

export function KanbanBoardView({
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
  const [directoryBranches, setDirectoryBranches] = useState<BranchDTO[]>([]);
  const [directoryRegions, setDirectoryRegions] = useState<string[]>(
    BASE_REGIONS,
  );
  const [search, setSearch] = useState("");
  const [isp, setIsp] = useState<string>("ALL");
  const [region, setRegion] = useState<string>("All");
  const [priority, setPriority] = useState<string>("All");
  const [trigger, setTrigger] = useState<string>("All");
  const [pausedOnly, setPausedOnly] = useState<boolean>(false);
  const [dragTicketId, setDragTicketId] = useState<string | null>(null);

  // Create manual ticket modal state
  const [modalOpen, setModalOpen] = useState(false);
  const [formBranchCode, setFormBranchCode] = useState("2009");
  const [formPriority, setFormPriority] = useState<PriorityDTO>("HIGH");
  const [formPhone, setFormPhone] = useState("010 2345 8817");
  const [formTrigger, setFormTrigger] = useState("DIRECT_EMAIL");
  const [formScenario, setFormScenario] = useState<
    | "AUTO"
    | "PASS"
    | "FULL_OUTAGE"
    | "LOCAL_LOOP_DOWN_ON_4G"
    | "INTERNAL_LAN_SWITCH"
  >("AUTO");
  const [formDesc, setFormDesc] = useState(
    "Store not syncing since 08:40. Router photo attached by Regional IT.",
  );
  const [branchPreview, setBranchPreview] = useState<BranchDTO | null>(null);
  const [isCreating, setIsCreating] = useState(false);

  const loadTickets = useCallback(() => {
    ticketsApi
      .list({
        search: search.trim() || undefined,
        isp,
        region,
        priority,
        trigger,
        ai_paused_only: pausedOnly,
      })
      .then((res) => setTickets(res))
      .catch(() => {});
  }, [search, isp, region, priority, trigger, pausedOnly]);

  const loadDirectoryBranches = useCallback(() => {
    branchesApi
      .list({ limit: 500, offset: 0 })
      .then((res) => {
        setDirectoryBranches(res.items);
        const extra = Object.keys(res.regions_count || {}).filter(
          (r) => r && !BASE_REGIONS.includes(r),
        );
        setDirectoryRegions([...BASE_REGIONS, ...extra.sort()]);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    loadTickets();
    loadDirectoryBranches();
  }, [loadTickets, loadDirectoryBranches]);

  useEffect(() => {
    if (!modalOpen) return;
    const code = formBranchCode.trim();
    const localMatch = directoryBranches.find(
      (b) => b.branch_code.toLowerCase() === code.toLowerCase(),
    );
    if (localMatch) {
      setBranchPreview(localMatch);
      return;
    }
    if (code.length >= 2) {
      branchesApi
        .getByCode(code)
        .then((b) => setBranchPreview(b))
        .catch(() => setBranchPreview(null));
    } else {
      setBranchPreview(null);
    }
  }, [modalOpen, formBranchCode, directoryBranches]);

  const allFilterRegions = useMemo(() => {
    const fromTickets = tickets
      .map((t) => t.region)
      .filter((r) => r && !directoryRegions.includes(r));
    return ["All", ...directoryRegions, ...Array.from(new Set(fromTickets))];
  }, [directoryRegions, tickets]);

  const handleDropToColumn = async (targetCol: number) => {
    if (!dragTicketId) return;
    const ticketId = dragTicketId;
    setDragTicketId(null);
    setTickets((prev) =>
      prev.map((t) => (t.id === ticketId ? { ...t, col: targetCol } : t)),
    );
    try {
      await ticketsApi.update(ticketId, { kanban_col: targetCol });
      loadTickets();
    } catch {
      loadTickets();
    }
  };

  const handleOpenCreateModal = () => {
    loadDirectoryBranches();
    if (
      directoryBranches.length > 0 &&
      !directoryBranches.some((b) => b.branch_code === formBranchCode)
    ) {
      setFormBranchCode(directoryBranches[0].branch_code);
    }
    setModalOpen(true);
  };

  const handleCreateManualTicket = async () => {
    if (!formBranchCode.trim()) return;
    setIsCreating(true);
    try {
      const created = await ticketsApi.createManual({
        branch_code: formBranchCode.trim(),
        priority: formPriority,
        site_contact_phone: formPhone.trim() || undefined,
        trigger_source: formTrigger,
        description: formDesc.trim(),
        run_diagnostics: true,
        simulate_scenario: formScenario,
      });
      setModalOpen(false);
      loadTickets();
      onOpenTicket(created.id);
    } catch {
      setModalOpen(false);
    } finally {
      setIsCreating(false);
    }
  };

  return (
    <AppShell
      active="Kanban Board"
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
          <h1>Ticket Board</h1>
          <p>
            Drag a card to change its status. The AI agent keeps working each
            ticket unless it is paused.
          </p>
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <Button
            variant="secondary"
            onClick={() => onNavigate("Tickets List")}
          >
            List view
          </Button>
          <Button variant="primary" onClick={handleOpenCreateModal}>
            + Create manual ticket
          </Button>
        </div>
      </div>

      <div className="kz-filters">
        <label className="kz-search" style={{ maxWidth: 320 }}>
          <span className="kz-muted">Search</span>
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Branch, ticket, circuit ID"
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

        {(["ALL", "NOOR", "ORANGE", "WE"] as const).map((k) => (
          <button
            key={k}
            type="button"
            className={clsx("kz-chip", isp === k && "kz-chip-on")}
            onClick={() => setIsp(k)}
          >
            {k === "ALL" ? "All ISPs" : k}
          </button>
        ))}

        <label className="kz-chip">
          Region
          <select
            value={region}
            onChange={(e) => setRegion(e.target.value)}
            style={{
              border: 0,
              font: "600 12px var(--font-sans)",
              background: "transparent",
              color: "var(--ink)",
            }}
          >
            {allFilterRegions.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>
        </label>

        <label className="kz-chip">
          Priority
          <select
            value={priority}
            onChange={(e) => setPriority(e.target.value)}
            style={{
              border: 0,
              font: "600 12px var(--font-sans)",
              background: "transparent",
              color: "var(--ink)",
            }}
          >
            <option>All</option>
            <option>CRITICAL</option>
            <option>HIGH</option>
            <option>MEDIUM</option>
            <option>LOW</option>
          </select>
        </label>

        <label className="kz-chip">
          Trigger
          <select
            value={trigger}
            onChange={(e) => setTrigger(e.target.value)}
            style={{
              border: 0,
              font: "600 12px var(--font-sans)",
              background: "transparent",
              color: "var(--ink)",
            }}
          >
            <option>All</option>
            <option>DIRECT_EMAIL</option>
            <option>REPLICATION_DASHBOARD</option>
            <option>PROACTIVE_SCAN</option>
          </select>
        </label>

        <button
          type="button"
          className={clsx("kz-chip", pausedOnly && "kz-chip-on")}
          aria-pressed={pausedOnly}
          onClick={() => setPausedOnly((v) => !v)}
        >
          AI paused only
        </button>

        <span className="kz-tcard-meta">{tickets.length} tickets</span>
      </div>

      <div className="kz-board">
        {KANBAN_LIFECYCLE_COLUMNS.map(([colTitle, colTone], colIndex) => {
          const items = tickets.filter((t) => t.col === colIndex);
          return (
            <section
              key={colTitle}
              aria-label={colTitle}
              className={clsx("kz-col", colTone && `kz-col-${colTone}`)}
              onDragOver={(e) => e.preventDefault()}
              onDrop={() => handleDropToColumn(colIndex)}
            >
              <div className="kz-col-hd">
                <span className="kz-col-bar" />
                <b>{colTitle}</b>
                <span>{items.length}</span>
              </div>
              {items.map((item) => {
                const cardModel: Ticket = {
                  id: item.id,
                  priority: item.priority,
                  branch: item.branch,
                  region: item.region,
                  failure: item.failure || undefined,
                  isp: item.isp as IspName,
                  caseRef: item.caseRef || undefined,
                  checks: item.checks || undefined,
                  sla: item.sla || undefined,
                  note: item.note || undefined,
                  aiPaused: item.aiPaused,
                  status: item.status,
                  col: item.col,
                };
                return (
                  <div
                    key={item.id}
                    draggable
                    onDragStart={() => setDragTicketId(item.id)}
                  >
                    <TicketCard
                      ticket={cardModel}
                      onClick={(t) => onOpenTicket(t.id)}
                    />
                  </div>
                );
              })}
              {items.length === 0 ? (
                <div
                  style={{
                    border: "1.5px dashed var(--border-strong)",
                    borderRadius: 10,
                    padding: 16,
                    textAlign: "center",
                    fontSize: 12,
                    color: "var(--ink-muted)",
                  }}
                >
                  No tickets
                </div>
              ) : null}
            </section>
          );
        })}
      </div>

      {modalOpen ? (
        <div className="kz-modal-scrim">
          <div
            role="dialog"
            aria-modal="true"
            aria-label="Create manual ticket"
            className="kz-card"
            style={{
              width: "100%",
              maxWidth: 620,
              boxShadow: "var(--shadow-raised)",
            }}
          >
            <div className="kz-card-hd">
              <div>
                <h2>Create manual ticket</h2>
                <p>
                  Select any branch from the directory. The agent runs
                  diagnostics and escalates to the branch ISP unless AI is
                  paused.
                </p>
              </div>
            </div>
            <div
              className="kz-card-bd"
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
                gap: 14,
              }}
            >
              <label
                style={{
                  gridColumn: "1 / -1",
                  display: "flex",
                  flexDirection: "column",
                  gap: 6,
                  fontSize: 13,
                  fontWeight: 600,
                }}
              >
                Pick branch from directory ({directoryBranches.length} loaded)
                <select
                  value={
                    directoryBranches.some(
                      (b) => b.branch_code === formBranchCode,
                    )
                      ? formBranchCode
                      : ""
                  }
                  onChange={(e) => {
                    if (e.target.value) setFormBranchCode(e.target.value);
                  }}
                  style={{
                    height: 40,
                    padding: "0 10px",
                    border: "1px solid var(--border-strong)",
                    borderRadius: 10,
                    font: "500 14px var(--font-sans)",
                  }}
                >
                  <option value="">-- Choose a branch or type SAP code below --</option>
                  {directoryBranches.map((b) => (
                    <option key={b.id} value={b.branch_code}>
                      {b.name} · {b.region || "Cairo"} ({b.isp_name} ·{" "}
                      {b.ip_1})
                    </option>
                  ))}
                </select>
              </label>

              <label
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: 6,
                  fontSize: 13,
                  fontWeight: 600,
                }}
              >
                Branch SAP code
                <input
                  value={formBranchCode}
                  onChange={(e) => setFormBranchCode(e.target.value)}
                  className="kz-mono"
                  style={{
                    height: 40,
                    padding: "0 12px",
                    border: "1px solid var(--border-strong)",
                    borderRadius: 10,
                  }}
                />
              </label>

              <label
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: 6,
                  fontSize: 13,
                  fontWeight: 600,
                }}
              >
                Priority
                <select
                  value={formPriority}
                  onChange={(e) =>
                    setFormPriority(e.target.value as PriorityDTO)
                  }
                  style={{
                    height: 40,
                    padding: "0 10px",
                    border: "1px solid var(--border-strong)",
                    borderRadius: 10,
                    font: "500 14px var(--font-sans)",
                  }}
                >
                  <option value="HIGH">HIGH</option>
                  <option value="CRITICAL">CRITICAL</option>
                  <option value="MEDIUM">MEDIUM</option>
                  <option value="LOW">LOW</option>
                </select>
              </label>

              <label
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: 6,
                  fontSize: 13,
                  fontWeight: 600,
                }}
              >
                Site contact phone
                <input
                  value={formPhone}
                  onChange={(e) => setFormPhone(e.target.value)}
                  placeholder="010…"
                  style={{
                    height: 40,
                    padding: "0 12px",
                    border: "1px solid var(--border-strong)",
                    borderRadius: 10,
                    font: "500 14px var(--font-sans)",
                  }}
                />
              </label>

              <label
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: 6,
                  fontSize: 13,
                  fontWeight: 600,
                }}
              >
                Trigger
                <select
                  value={formTrigger}
                  onChange={(e) => setFormTrigger(e.target.value)}
                  style={{
                    height: 40,
                    padding: "0 10px",
                    border: "1px solid var(--border-strong)",
                    borderRadius: 10,
                    font: "500 14px var(--font-sans)",
                  }}
                >
                  <option value="DIRECT_EMAIL">DIRECT_EMAIL</option>
                  <option value="REPLICATION_DASHBOARD">
                    REPLICATION_DASHBOARD
                  </option>
                </select>
              </label>

              <label
                style={{
                  gridColumn: "1 / -1",
                  display: "flex",
                  flexDirection: "column",
                  gap: 6,
                  fontSize: 13,
                  fontWeight: 600,
                }}
              >
                Diagnostic scenario (for testing)
                <select
                  value={formScenario}
                  onChange={(e) =>
                    setFormScenario(
                      e.target.value as
                        | "AUTO"
                        | "PASS"
                        | "FULL_OUTAGE"
                        | "LOCAL_LOOP_DOWN_ON_4G"
                        | "INTERNAL_LAN_SWITCH",
                    )
                  }
                  style={{
                    height: 40,
                    padding: "0 10px",
                    border: "1px solid var(--border-strong)",
                    borderRadius: 10,
                    font: "500 14px var(--font-sans)",
                  }}
                >
                  <option value="AUTO">AUTO (Branch default)</option>
                  <option value="FULL_OUTAGE">
                    FULL_OUTAGE (IP1 DOWN → Escalate to ISP)
                  </option>
                  <option value="LOCAL_LOOP_DOWN_ON_4G">
                    LOCAL_LOOP_DOWN_ON_4G (4G Hub → Escalate to ISP)
                  </option>
                  <option value="INTERNAL_LAN_SWITCH">
                    INTERNAL_LAN_SWITCH (IP2 DOWN → Return to Regional IT)
                  </option>
                  <option value="PASS">
                    PASS (IP1 UP + IP2 UP → Auto-Close)
                  </option>
                </select>
              </label>

              <div
                style={{
                  gridColumn: "1 / -1",
                  display: "flex",
                  gap: 10,
                  alignItems: "center",
                  padding: "10px 12px",
                  background: "var(--surface-100)",
                  borderRadius: 10,
                  fontSize: 13,
                  flexWrap: "wrap",
                }}
              >
                <span style={{ fontWeight: 600 }}>
                  {branchPreview
                    ? `${branchPreview.name} (${branchPreview.region || "Cairo"})`
                    : `${formBranchCode}-Store`}
                </span>
                <span className="kz-mono kz-muted">
                  IP1 {branchPreview?.ip_1 ?? "10.20.9.1"} · IP2{" "}
                  {branchPreview?.ip_2 ?? "10.20.9.2"}
                </span>
                <IspBadge
                  isp={(branchPreview?.isp_name as IspName) || "NOOR"}
                />
                {branchPreview?.ll_circuit_id ? (
                  <span className="kz-mono kz-muted">
                    L.L: {branchPreview.ll_circuit_id}
                  </span>
                ) : null}
                {branchPreview?.regional_it_email ? (
                  <span className="kz-tcard-meta">
                    {branchPreview.regional_it_email}
                  </span>
                ) : null}
              </div>

              <label
                style={{
                  gridColumn: "1 / -1",
                  display: "flex",
                  flexDirection: "column",
                  gap: 6,
                  fontSize: 13,
                  fontWeight: 600,
                }}
              >
                Issue details
                <textarea
                  rows={3}
                  value={formDesc}
                  onChange={(e) => setFormDesc(e.target.value)}
                  style={{
                    padding: "10px 12px",
                    border: "1px solid var(--border-strong)",
                    borderRadius: 10,
                    font: "500 14px var(--font-sans)",
                    resize: "vertical",
                  }}
                />
              </label>
            </div>
            <div
              style={{
                display: "flex",
                justifyContent: "flex-end",
                gap: 8,
                padding: "0 16px 16px",
              }}
            >
              <Button variant="secondary" onClick={() => setModalOpen(false)}>
                Cancel
              </Button>
              <Button
                variant="primary"
                disabled={isCreating}
                onClick={handleCreateManualTicket}
              >
                {isCreating ? "Creating…" : "Create & run diagnostics"}
              </Button>
            </div>
          </div>
        </div>
      ) : null}
    </AppShell>
  );
}
