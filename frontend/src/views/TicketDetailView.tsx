import React, { useCallback, useEffect, useState } from "react";
import {
  AppShell,
  Badge,
  BadgeTone,
  Button,
  IspBadge,
  IspName,
  PRIORITY_TONE,
  SlaTimer,
  StatusPill,
} from "../design-system";
import { TicketDetail360DTO, ticketsApi } from "../lib/api";
import { ConsoleViewProps } from "./types";

export interface TicketDetailViewProps extends ConsoleViewProps {
  ticketNumber: string;
}

export function TicketDetailView({
  ticketNumber,
  theme,
  onToggleTheme,
  onNavigate,
  env,
  initials,
  userDisplayName,
  userRoleLabel,
  onLogout,
  canAccessNav,
}: TicketDetailViewProps) {
  const [ticket, setTicket] = useState<TicketDetail360DTO | null>(null);
  const [activeTab, setActiveTab] = useState<
    "timeline" | "tests" | "branch" | "isp"
  >("timeline");
  const [toast, setToast] = useState<string | null>(null);
  const [noteInput, setNoteInput] = useState("");
  const [replyInput, setReplyInput] = useState("");
  const [ispRefInput, setIspRefInput] = useState("");
  const [sitePhoneInput, setSitePhoneInput] = useState("");

  // Escalate modal state
  const [escOpen, setEscOpen] = useState(false);
  const [escTarget, setEscTarget] = useState("noc-oncall@kazyon.com");
  const [escReason, setEscReason] = useState("OTHER");
  const [escNote, setEscNote] = useState(
    "ISP not responding after chasers; branch manager escalating.",
  );

  const loadDetail = useCallback(() => {
    ticketsApi
      .get360(ticketNumber)
      .then((res) => {
        setTicket(res);
        setIspRefInput(res.isp_reference_number || "");
        setSitePhoneInput(res.site_contact_phone || "");
      })
      .catch(() => {});
  }, [ticketNumber]);

  useEffect(() => {
    loadDetail();
  }, [loadDetail]);

  const handleStatusChange = async (newStatus: string) => {
    if (!ticket) return;
    const updated = await ticketsApi.update(ticket.ticket_number, {
      status: newStatus,
    });
    setTicket(updated);
    setToast(`Status updated to ${newStatus}.`);
  };

  const handlePriorityChange = async (newPriority: string) => {
    if (!ticket) return;
    const updated = await ticketsApi.update(ticket.ticket_number, {
      priority: newPriority,
    });
    setTicket(updated);
    setToast(`Priority updated to ${newPriority}.`);
  };

  const handleToggleAi = async () => {
    if (!ticket) return;
    const nextAi = !ticket.ai_automation_enabled;
    const updated = await ticketsApi.update(ticket.ticket_number, {
      ai_automation_enabled: nextAi,
    });
    setTicket(updated);
    setToast(
      nextAi ? "AI automation resumed." : "AI automation paused on this ticket.",
    );
  };

  const handleRerunDiagnostics = async () => {
    if (!ticket) return;
    setToast("Running dual-ping & 4G hub traceroute diagnostics…");
    const updated = await ticketsApi.rerunDiagnostics(ticket.ticket_number);
    setTicket(updated);
    setActiveTab("tests");
    const latestCode =
      updated.diagnostic_runs[0]?.diagnosis_code || "COMPLETED";
    setToast(`Diagnostics finished: ${latestCode}.`);
  };

  const handleForceFollowup = async () => {
    if (!ticket) return;
    const updated = await ticketsApi.forceFollowup(ticket.ticket_number);
    setTicket(updated);
    setToast(`Follow-up chaser sent to ${updated.isp.support_email}.`);
  };

  const handleContactRegionalIt = () => {
    if (!ticket) return;
    setActiveTab("branch");
    setToast(`Write to ${ticket.branch.regional_it_email} below.`);
  };

  const handleConfirmEscalate = async () => {
    if (!ticket) return;
    const updated = await ticketsApi.escalateHuman(ticket.ticket_number, {
      target_email: escTarget,
      reason: escReason,
      note: escNote,
    });
    setTicket(updated);
    setEscOpen(false);
    setToast(`Escalated. AI paused and report sent to ${escTarget}.`);
  };

  const handleAddNote = async () => {
    if (!ticket || !noteInput.trim()) return;
    const updated = await ticketsApi.addNote(
      ticket.ticket_number,
      noteInput.trim(),
    );
    setTicket(updated);
    setNoteInput("");
    setToast("Internal engineer note added to timeline.");
  };

  const handleSendReply = async () => {
    if (!ticket || !replyInput.trim()) return;
    const threadType = activeTab === "isp" ? "ISP" : "BRANCH";
    const updated = await ticketsApi.replyEmail(ticket.ticket_number, {
      thread_type: threadType,
      body_text: replyInput.trim(),
    });
    setTicket(updated);
    setReplyInput("");
    setToast(
      `Reply sent on ${threadType === "ISP" ? ticket.isp.name : "Regional IT"} thread.`,
    );
  };

  const handleOverrideVision = async () => {
    if (!ticket) return;
    const nextPlugged = !ticket.vision.cables_plugged;
    const updated = await ticketsApi.overrideVision(ticket.ticket_number, {
      cables_plugged: nextPlugged,
      summary: `Manual engineer override: cables ${nextPlugged ? "plugged" : "unplugged"}.`,
    });
    setTicket(updated);
    setToast("Vision verdict overridden.");
  };

  const handleSaveMetaBlur = async () => {
    if (!ticket) return;
    if (
      ispRefInput !== ticket.isp_reference_number ||
      sitePhoneInput !== ticket.site_contact_phone
    ) {
      const updated = await ticketsApi.update(ticket.ticket_number, {
        isp_reference_number: ispRefInput,
        site_contact_phone: sitePhoneInput,
      });
      setTicket(updated);
      setToast("ISP reference / site contact saved.");
    }
  };

  if (!ticket) {
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
        <div className="kz-card">
          <div className="kz-card-bd">
            <span className="kz-live">Loading {ticketNumber}…</span>
          </div>
        </div>
      </AppShell>
    );
  }

  const tabs: Array<["timeline" | "tests" | "branch" | "isp", string]> = [
    ["timeline", "Updates timeline"],
    ["tests", "Test results & vision"],
    ["branch", `Branch emails · ${ticket.branch_emails.length}`],
    ["isp", `ISP emails · ${ticket.isp_emails.length}`],
  ];

  const activeMails =
    activeTab === "isp" ? ticket.isp_emails : ticket.branch_emails;

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
      <nav
        aria-label="Breadcrumb"
        style={{
          fontSize: 13,
          display: "flex",
          gap: 6,
          color: "var(--ink-muted)",
        }}
      >
        <a
          href="#tickets"
          onClick={(e) => {
            e.preventDefault();
            onNavigate("Tickets List");
          }}
        >
          Tickets
        </a>
        <span>/</span>
        <span>{ticket.ticket_number}</span>
      </nav>

      <div className="kz-page-hd" style={{ alignItems: "flex-start" }}>
        <div>
          <div
            style={{
              display: "flex",
              gap: 8,
              alignItems: "center",
              flexWrap: "wrap",
              marginBottom: 4,
            }}
          >
            <span className="kz-tcard-id" style={{ fontSize: 14 }}>
              {ticket.ticket_number}
            </span>
            <Badge tone={PRIORITY_TONE[ticket.priority] || "warning"}>
              {ticket.priority}
            </Badge>
            <Badge
              tone={
                ticket.status === "NEEDS_HUMAN_REVIEW"
                  ? "critical"
                  : ticket.status === "RESOLVED" || ticket.status === "CLOSED"
                    ? "good"
                    : "brand"
              }
            >
              {ticket.stage_label}
            </Badge>
            <Badge tone="outline">{ticket.trigger_source}</Badge>
          </div>
          <h1>{ticket.title}</h1>
          <p>
            Opened {ticket.opened_at} by {ticket.sender_email}
            {ticket.isp_reference_number
              ? ` · ${ticket.isp.name} case ${ticket.isp_reference_number}`
              : ""}
          </p>
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
        <label className="kz-chip">
          Status
          <select
            value={ticket.status}
            onChange={(e) => handleStatusChange(e.target.value)}
            style={{
              border: 0,
              font: "600 12px var(--font-sans)",
              background: "transparent",
              color: "var(--ink)",
            }}
          >
            <option value="AWAITING_REGIONAL_IT">AWAITING_REGIONAL_IT</option>
            <option value="DIAGNOSING">DIAGNOSING</option>
            <option value="AWAITING_BRANCH_PHOTO">AWAITING_BRANCH_PHOTO</option>
            <option value="INTERNAL_LAN_ISSUE">INTERNAL_LAN_ISSUE</option>
            <option value="ESCALATED_TO_ISP">ESCALATED_TO_ISP</option>
            <option value="AWAITING_BRANCH_CONTACT">
              AWAITING_BRANCH_CONTACT
            </option>
            <option value="VERIFYING">VERIFYING</option>
            <option value="NEEDS_HUMAN_REVIEW">NEEDS_HUMAN_REVIEW</option>
            <option value="RESOLVED">RESOLVED</option>
            <option value="CLOSED">CLOSED</option>
          </select>
        </label>

        <label className="kz-chip">
          Priority
          <select
            value={ticket.priority}
            onChange={(e) => handlePriorityChange(e.target.value)}
            style={{
              border: 0,
              font: "600 12px var(--font-sans)",
              background: "transparent",
              color: "var(--ink)",
            }}
          >
            <option value="HIGH">HIGH</option>
            <option value="CRITICAL">CRITICAL</option>
            <option value="MEDIUM">MEDIUM</option>
            <option value="LOW">LOW</option>
          </select>
        </label>

        <button
          type="button"
          className={
            ticket.ai_automation_enabled
              ? "kz-btn kz-btn-secondary"
              : "kz-btn kz-btn-primary"
          }
          aria-pressed={!ticket.ai_automation_enabled}
          onClick={handleToggleAi}
        >
          {ticket.ai_automation_enabled ? "Pause AI" : "Resume AI"}
        </button>

        <span style={{ flex: 1 }} />

        <button
          type="button"
          className="kz-btn kz-btn-secondary"
          onClick={handleRerunDiagnostics}
        >
          ▶ Re-run diagnostics now
        </button>
        <button
          type="button"
          className="kz-btn kz-btn-secondary"
          onClick={handleForceFollowup}
        >
          Force ISP follow-up
        </button>
        <button
          type="button"
          className="kz-btn kz-btn-secondary"
          onClick={handleContactRegionalIt}
        >
          Contact Regional IT
        </button>
        <button
          type="button"
          className="kz-btn kz-btn-danger"
          onClick={() => setEscOpen(true)}
        >
          Escalate to engineer
        </button>
      </div>

      {toast ? (
        <div
          role="status"
          style={{
            padding: "10px 14px",
            borderRadius: 10,
            background: "var(--info-bg)",
            color: "var(--info)",
            fontSize: 13,
            fontWeight: 600,
          }}
        >
          {toast}
        </div>
      ) : null}

      {escOpen ? (
        <div className="kz-modal-scrim">
          <div
            role="dialog"
            aria-modal="true"
            aria-label="Escalate to engineer"
            className="kz-card"
            style={{
              width: "100%",
              maxWidth: 520,
              boxShadow: "var(--shadow-raised)",
            }}
          >
            <div className="kz-card-hd">
              <div>
                <h2>Escalate {ticket.ticket_number} to a human engineer</h2>
                <p>
                  Sets NEEDS_HUMAN_REVIEW, pauses AI and emails the full
                  incident report.
                </p>
              </div>
            </div>
            <div
              className="kz-card-bd"
              style={{ display: "flex", flexDirection: "column", gap: 14 }}
            >
              <label className="kz-field">
                Send report to
                <select
                  value={escTarget}
                  onChange={(e) => setEscTarget(e.target.value)}
                >
                  <option value="noc-oncall@kazyon.com">
                    noc-oncall@kazyon.com
                  </option>
                  <option value="ITInfrastructure@kazyon.com">
                    ITInfrastructure@kazyon.com
                  </option>
                </select>
              </label>
              <label className="kz-field">
                Reason
                <select
                  value={escReason}
                  onChange={(e) => setEscReason(e.target.value)}
                >
                  <option value="OTHER">OTHER</option>
                  <option value="QUOTA_CONSUMED">QUOTA_CONSUMED</option>
                  <option value="INTERNAL_BOX_CABLE">INTERNAL_BOX_CABLE</option>
                  <option value="MSAN_MIGRATION">MSAN_MIGRATION</option>
                  <option value="MAX_RETRIES">MAX_RETRIES</option>
                </select>
              </label>
              <label className="kz-field">
                Note to engineer
                <textarea
                  rows={3}
                  value={escNote}
                  onChange={(e) => setEscNote(e.target.value)}
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
              <Button variant="secondary" onClick={() => setEscOpen(false)}>
                Cancel
              </Button>
              <Button variant="primary" onClick={handleConfirmEscalate}>
                Escalate &amp; email report
              </Button>
            </div>
          </div>
        </div>
      ) : null}

      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: 16,
          alignItems: "flex-start",
        }}
      >
        <aside
          style={{
            flex: "1 1 300px",
            maxWidth: 360,
            display: "flex",
            flexDirection: "column",
            gap: 16,
          }}
        >
          <section className="kz-card">
            <div className="kz-card-hd">
              <h2>SLA</h2>
            </div>
            <div
              className="kz-card-bd"
              style={{ display: "flex", flexDirection: "column", gap: 10 }}
            >
              <SlaTimer
                label={ticket.isp_welcome_received ? "Follow-up" : "Welcome"}
                minutesLeft={ticket.sla_minutes_left}
                totalMinutes={ticket.sla_total_minutes}
              />
              <div className="kz-tcard-meta">{ticket.sla_summary_text}</div>
            </div>
          </section>

          <section className="kz-card">
            <div className="kz-card-hd">
              <h2>Branch</h2>
            </div>
            <dl
              className="kz-card-bd"
              style={{
                margin: 0,
                display: "grid",
                gridTemplateColumns: "120px 1fr",
                gap: "8px 12px",
                fontSize: 13,
              }}
            >
              <dt className="kz-muted">SAP code</dt>
              <dd style={{ margin: 0 }} className="kz-mono">
                {ticket.branch.code}
              </dd>
              <dt className="kz-muted">Store</dt>
              <dd style={{ margin: 0, fontWeight: 600 }}>
                {ticket.branch.name}
              </dd>
              <dt className="kz-muted">IP 1 (router)</dt>
              <dd style={{ margin: 0 }} className="kz-mono">
                {ticket.branch.ip1}
              </dd>
              <dt className="kz-muted">IP 2 (switch)</dt>
              <dd style={{ margin: 0 }} className="kz-mono">
                {ticket.branch.ip2}
              </dd>
              <dt className="kz-muted">Region</dt>
              <dd style={{ margin: 0 }}>{ticket.branch.region}</dd>
              <dt className="kz-muted">Regional IT</dt>
              <dd style={{ margin: 0 }}>
                <a
                  href={`mailto:${ticket.branch.regional_it_email}`}
                  onClick={(e) => {
                    e.preventDefault();
                    handleContactRegionalIt();
                  }}
                >
                  {ticket.branch.regional_it_email}
                </a>
              </dd>
            </dl>
          </section>

          <section className="kz-card">
            <div className="kz-card-hd">
              <h2>ISP</h2>
              <IspBadge isp={ticket.isp.name as IspName} />
            </div>
            <div
              className="kz-card-bd"
              style={{
                display: "flex",
                flexDirection: "column",
                gap: 10,
                fontSize: 13,
              }}
            >
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "120px 1fr",
                  gap: "8px 12px",
                }}
              >
                <span className="kz-muted">Support</span>
                <span>{ticket.isp.support_email}</span>
                <span className="kz-muted">L.L ID</span>
                <span className="kz-mono">{ticket.isp.ll_circuit_id}</span>
                <span className="kz-muted">3G ID</span>
                <span className="kz-mono">{ticket.isp.backup_circuit_id}</span>
                <span className="kz-muted">4G hub IP</span>
                <span className="kz-mono">{ticket.isp.four_g_hub_ip}</span>
              </div>
              <label
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: 4,
                  fontWeight: 600,
                }}
              >
                ISP ticket ref #
                <input
                  value={ispRefInput}
                  onChange={(e) => setIspRefInput(e.target.value)}
                  onBlur={handleSaveMetaBlur}
                  className="kz-mono"
                  style={{
                    height: 36,
                    padding: "0 10px",
                    border: "1px solid var(--border-strong)",
                    borderRadius: 8,
                  }}
                />
              </label>
              <label
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: 4,
                  fontWeight: 600,
                }}
              >
                Site contact phone
                <input
                  value={sitePhoneInput}
                  onChange={(e) => setSitePhoneInput(e.target.value)}
                  onBlur={handleSaveMetaBlur}
                  style={{
                    height: 36,
                    padding: "0 10px",
                    border: "1px solid var(--border-strong)",
                    borderRadius: 8,
                    font: "500 13px var(--font-sans)",
                  }}
                />
              </label>
            </div>
          </section>
        </aside>

        <section
          className="kz-card"
          style={{ flex: "999 1 560px", minWidth: 0 }}
        >
          <div
            role="tablist"
            aria-label="Ticket sections"
            style={{
              display: "flex",
              gap: 4,
              padding: "8px 8px 0",
              borderBottom: "1px solid var(--border)",
              overflowX: "auto",
            }}
          >
            {tabs.map(([key, label]) => {
              const isOn = activeTab === key;
              return (
                <button
                  key={key}
                  type="button"
                  role="tab"
                  aria-selected={isOn}
                  onClick={() => setActiveTab(key)}
                  style={{
                    all: "unset",
                    cursor: "pointer",
                    padding: "10px 14px",
                    font: "600 13px var(--font-sans)",
                    whiteSpace: "nowrap",
                    borderBottom: `2px solid ${
                      isOn ? "var(--brand-600)" : "transparent"
                    }`,
                    color: isOn ? "var(--brand-text)" : "var(--ink-muted)",
                  }}
                >
                  {label}
                </button>
              );
            })}
          </div>

          {activeTab === "timeline" ? (
            <div
              className="kz-card-bd"
              style={{ display: "flex", flexDirection: "column", gap: 0 }}
            >
              {ticket.events.map((e) => (
                <div
                  key={e.id}
                  style={{
                    display: "grid",
                    gridTemplateColumns: "64px 20px 1fr",
                    gap: 10,
                    padding: "10px 0",
                    borderBottom: "1px solid var(--border)",
                  }}
                >
                  <span
                    className="kz-num kz-muted"
                    style={{ fontSize: 12, paddingTop: 2 }}
                  >
                    {e.time}
                  </span>
                  <span
                    style={{
                      width: 10,
                      height: 10,
                      borderRadius: "50%",
                      marginTop: 4,
                      background: `var(--${e.color})`,
                      boxShadow: `0 0 0 3px var(--${e.color}-bg, var(--surface-200))`,
                    }}
                  />
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 600 }}>
                      {e.title}
                    </div>
                    <div className="kz-tcard-meta">
                      {e.actor} · {e.detail}
                    </div>
                  </div>
                </div>
              ))}
              <label
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: 6,
                  fontSize: 13,
                  fontWeight: 600,
                  marginTop: 16,
                }}
              >
                Add internal note
                <textarea
                  rows={3}
                  value={noteInput}
                  onChange={(e) => setNoteInput(e.target.value)}
                  placeholder="Visible to engineers only"
                  style={{
                    padding: "10px 12px",
                    border: "1px solid var(--border-strong)",
                    borderRadius: 10,
                    font: "500 14px var(--font-sans)",
                    resize: "vertical",
                  }}
                />
              </label>
              <div
                style={{
                  display: "flex",
                  justifyContent: "flex-end",
                  marginTop: 8,
                }}
              >
                <Button variant="primary" size="sm" onClick={handleAddNote}>
                  Add note
                </Button>
              </div>
            </div>
          ) : null}

          {activeTab === "tests" ? (
            <div
              className="kz-card-bd"
              style={{ display: "flex", flexDirection: "column", gap: 16 }}
            >
              <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
                <div
                  role="img"
                  aria-label="Router photo placeholder"
                  style={{
                    flex: "1 1 280px",
                    height: 220,
                    borderRadius: 12,
                    background: "var(--surface-200)",
                    border: "1.5px dashed var(--border-strong)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    color: "var(--ink-muted)",
                    fontSize: 13,
                    fontWeight: 600,
                  }}
                >
                  [ROUTER PHOTO — {ticket.vision.photo_filename}]
                </div>
                <div
                  style={{
                    flex: "1 1 260px",
                    display: "flex",
                    flexDirection: "column",
                    gap: 10,
                  }}
                >
                  <h3 style={{ margin: 0, fontSize: 15 }}>
                    Gemma 4 vision verdict
                  </h3>
                  <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                    <Badge
                      tone={ticket.vision.cables_plugged ? "good" : "critical"}
                    >
                      {ticket.vision.cables_plugged
                        ? "Cables plugged"
                        : "Cables unplugged"}
                    </Badge>
                    <Badge
                      tone={ticket.vision.power_led_on ? "good" : "critical"}
                    >
                      {ticket.vision.power_led_on
                        ? "Power LED on"
                        : "Power LED off"}
                    </Badge>
                    <Badge tone={ticket.vision.wan_led_on ? "good" : "warning"}>
                      {ticket.vision.wan_led_on ? "WAN LED on" : "WAN LED off"}
                    </Badge>
                  </div>
                  <p style={{ margin: 0, fontSize: 13, lineHeight: "20px" }}>
                    {ticket.vision.summary} Confidence{" "}
                    {ticket.vision.confidence.toFixed(2)}.
                  </p>
                  <div>
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={handleOverrideVision}
                    >
                      Override verdict
                    </Button>
                  </div>
                </div>
              </div>

              <h3 style={{ margin: 0, fontSize: 15 }}>Diagnostic runs</h3>
              {ticket.diagnostic_runs.map((r, idx) => (
                <details
                  key={r.id || idx}
                  className="kz-card"
                  style={{ padding: "12px 14px" }}
                  open={idx === 0}
                >
                  <summary
                    style={{
                      display: "flex",
                      gap: 8,
                      alignItems: "center",
                      flexWrap: "wrap",
                      cursor: "pointer",
                      fontSize: 13,
                    }}
                  >
                    <b>{r.label}</b>
                    <span className="kz-muted">
                      {r.when} · {r.ms}
                    </span>
                    {r.checks.map((c, cIdx) => (
                      <StatusPill key={cIdx} label={c.label} state={c.state} />
                    ))}
                    <Badge tone={(r.tone as BadgeTone) || "warning"}>
                      {r.result}
                    </Badge>
                  </summary>
                  <pre
                    className="kz-mono"
                    style={{
                      margin: "12px 0 0",
                      padding: 12,
                      background: "var(--term-bg)",
                      color: "var(--term-ink)",
                      border: "1px solid var(--border)",
                      borderRadius: 8,
                      overflowX: "auto",
                      whiteSpace: "pre",
                      lineHeight: "18px",
                    }}
                  >
                    {r.log}
                  </pre>
                </details>
              ))}
            </div>
          ) : null}

          {activeTab === "branch" || activeTab === "isp" ? (
            <div
              className="kz-card-bd"
              style={{ display: "flex", flexDirection: "column", gap: 12 }}
            >
              {activeMails.map((m) => (
                <article
                  key={m.id}
                  style={{
                    padding: "12px 14px",
                    borderRadius: 12,
                    border: "1px solid var(--border)",
                    background: m.outbound
                      ? "var(--brand-50)"
                      : "var(--surface-000)",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      gap: 8,
                      flexWrap: "wrap",
                      fontSize: 12,
                    }}
                  >
                    <div>
                      <b>{m.from_addr}</b>
                      {m.to_addr ? (
                        <span className="kz-muted"> → {m.to_addr}</span>
                      ) : null}
                      {m.cc_addr ? (
                        <span className="kz-muted"> · CC: {m.cc_addr}</span>
                      ) : null}
                    </div>
                    <span className="kz-muted">
                      {m.when} · {m.direction}
                    </span>
                  </div>
                  <div
                    style={{
                      fontSize: 13,
                      fontWeight: 600,
                      marginTop: 4,
                    }}
                  >
                    {m.subject}
                  </div>
                  <p
                    style={{
                      margin: "6px 0 0",
                      fontSize: 13,
                      lineHeight: "20px",
                      whiteSpace: "pre-line",
                    }}
                  >
                    {m.body}
                  </p>
                  {m.thread_replies && m.thread_replies.length > 1 ? (
                    <details
                      style={{
                        marginTop: 8,
                        padding: "8px 10px",
                        borderRadius: 8,
                        background: "var(--surface-100)",
                        border: "1px solid var(--border)",
                        fontSize: 12,
                      }}
                    >
                      <summary style={{ cursor: "pointer", fontWeight: 600 }}>
                        Parsed Full Thread Replies ({m.thread_replies.length})
                      </summary>
                      <div
                        style={{
                          display: "flex",
                          flexDirection: "column",
                          gap: 6,
                          marginTop: 8,
                        }}
                      >
                        {m.thread_replies.map((rep) => (
                          <div
                            key={rep.index}
                            style={{
                              padding: "6px 8px",
                              borderRadius: 6,
                              border: "1px solid var(--border)",
                              background: "var(--surface-000)",
                            }}
                          >
                            <div
                              style={{
                                fontWeight: 600,
                                color: "var(--ink-muted)",
                                marginBottom: 4,
                              }}
                            >
                              {rep.is_latest
                                ? "Reply #1 (Latest)"
                                : `Reply #${rep.index + 1}`}{" "}
                              · {rep.header}
                            </div>
                            <div style={{ whiteSpace: "pre-line" }}>
                              {rep.body}
                            </div>
                          </div>
                        ))}
                      </div>
                    </details>
                  ) : null}
                </article>
              ))}
              <label
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: 6,
                  fontSize: 13,
                  fontWeight: 600,
                }}
              >
                {activeTab === "isp"
                  ? `Reply to ${ticket.isp.name} (ISP thread)`
                  : "Reply to Regional IT (branch thread)"}
                <textarea
                  rows={3}
                  value={replyInput}
                  onChange={(e) => setReplyInput(e.target.value)}
                  style={{
                    padding: "10px 12px",
                    border: "1px solid var(--border-strong)",
                    borderRadius: 10,
                    font: "500 14px var(--font-sans)",
                    resize: "vertical",
                  }}
                />
              </label>
              <div
                style={{
                  display: "flex",
                  justifyContent: "flex-end",
                  gap: 8,
                }}
              >
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => setToast("Draft saved.")}
                >
                  Save draft
                </Button>
                <Button
                  variant="primary"
                  size="sm"
                  icon="mail"
                  onClick={handleSendReply}
                >
                  Send
                </Button>
              </div>
            </div>
          ) : null}
        </section>
      </div>
    </AppShell>
  );
}
