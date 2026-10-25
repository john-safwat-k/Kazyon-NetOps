import React, { useCallback, useEffect, useState } from "react";
import clsx from "clsx";
import { AppShell, Badge, BadgeTone, Button } from "../design-system";
import {
  EmailLoopStatusDTO,
  EmailLoopTriggerResponseDTO,
  KanbanTicketCardDTO,
  MailboxTriageItemDTO,
  SandboxSuggestedNextStepDTO,
  emailsApi,
  settingsApi,
  ticketsApi,
} from "../lib/api";
import { ConsoleViewProps } from "./types";

type MailFilterKey = "ALL" | "IN" | "OUT" | "ISP" | "UNRECOGNIZED";

interface LoopScenarioOption {
  key: string;
  stepBadge: string;
  label: string;
  thread: "BRANCH" | "ISP";
  description: string;
}

const LOOP_SCENARIOS: LoopScenarioOption[] = [
  {
    key: "BRANCH_INCIDENT",
    stepBadge: "Step 1",
    label: "Branch Incident + Router Photo",
    thread: "BRANCH",
    description:
      "Regional IT reports store offline with seated router photo → Vision PASS → Dual-Ping & Traceroute → Escalates to ISP & replies to Branch.",
  },
  {
    key: "CABLE_UNPLUGGED_PHOTO",
    stepBadge: "Step 1B",
    label: "Branch Photo: Cables Unplugged",
    thread: "BRANCH",
    description:
      "Regional IT sends router photo with loose WAN cable → Vision FAIL → Transitions to AWAITING_BRANCH & emails Regional IT to reseat.",
  },
  {
    key: "REGIONAL_IT_CABLE_FIXED",
    stepBadge: "Step 1C",
    label: "Regional IT: Cables Reseated Reply",
    thread: "BRANCH",
    description:
      "Regional IT replies in-thread with fresh seated photo → Vision PASS → Runs Dual-Ping & Traceroute → Escalates to ISP.",
  },
  {
    key: "ISP_WELCOME",
    stepBadge: "Step 2",
    label: "ISP Welcome Mail (Case #)",
    thread: "ISP",
    description:
      "ISP NOC replies in-thread with trouble ticket reference (#244010 / 1-13... / ##RE-...) → Saves Case # & starts 4–6h follow-up SLA loop.",
  },
  {
    key: "ISP_CONTACT_UNREACHABLE",
    stepBadge: "Step 3A",
    label: "ISP Blocker: Contact Unreachable",
    thread: "ISP",
    description:
      "ISP reports site contact phone is switched off/unreachable → Transitions to AWAITING_BRANCH_CONTACT & emails Regional IT for active phone.",
  },
  {
    key: "REGIONAL_IT_NEW_PHONE",
    stepBadge: "Step 3B",
    label: "Regional IT: Active Phone Reply",
    thread: "BRANCH",
    description:
      "Regional IT replies in-thread with new active manager phone (010 9988 7766) → Agent updates ticket & relays phone to ISP on ISP thread.",
  },
  {
    key: "ISP_RESOLVED",
    stepBadge: "Step 4A",
    label: "ISP Closure Claim (Verify PASS)",
    thread: "ISP",
    description:
      "ISP claims link restored → Agent runs Final Verification Dual-Ping (PASS) → Emails closure confirmation to Branch & ISP and closes ticket.",
  },
  {
    key: "ISP_RESOLVED_STILL_DOWN",
    stepBadge: "Step 4B",
    label: "ISP Premature Closure (Verify FAIL)",
    thread: "ISP",
    description:
      "ISP claims link restored, but Final Verification Dual-Ping detects link still DOWN → Agent rejects closure on ISP thread & keeps ticket open.",
  },
  {
    key: "ISP_QUOTA_BLOCKER",
    stepBadge: "Step 5",
    label: "ISP Blocker: 4G Quota Consumed",
    thread: "ISP",
    description:
      "ISP reports 4G backup quota is consumed → Agent pauses AI, moves ticket to NEEDS_HUMAN_REVIEW, and emails on-call engineer.",
  },
  {
    key: "REPLICATION_REPORT",
    stepBadge: "Flow 0",
    label: "Replication Dashboard HTML Report",
    thread: "BRANCH",
    description:
      "Ingests daily Replication Dashboard HTML table → Opens AWAITING_REGIONAL_IT ticket for Not Updated store & emails Regional IT.",
  },
  {
    key: "CUSTOM",
    stepBadge: "Custom",
    label: "Custom Email Message",
    thread: "BRANCH",
    description:
      "Compose a custom inbound email with any From, Subject, In-Reply-To, and Body to test the agent harness loop.",
  },
];

export function MailboxTriageView({
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
  const [mails, setMails] = useState<MailboxTriageItemDTO[]>([]);
  const [loopStatus, setLoopStatus] = useState<EmailLoopStatusDTO | null>(null);
  const [openTickets, setOpenTickets] = useState<KanbanTicketCardDTO[]>([]);
  const [samples, setSamples] = useState<string[]>([]);
  const [selectedSample, setSelectedSample] = useState<string>("");
  const [filter, setFilter] = useState<MailFilterKey>("ALL");
  const [selId, setSelId] = useState<number | null>(null);
  const [showRaw, setShowRaw] = useState(false);
  const [simNotice, setSimNotice] = useState<string | null>(null);
  const [lastLoopResult, setLastLoopResult] =
    useState<EmailLoopTriggerResponseDTO | null>(null);

  // Interactive Email Loop Harness state
  const [showLoopPanel, setShowLoopPanel] = useState<boolean>(true);
  const [scenario, setScenario] = useState<string>("BRANCH_INCIDENT");
  const [customRole, setCustomRole] = useState<"BRANCH" | "ISP">("BRANCH");
  const [targetBranchCode, setTargetBranchCode] = useState<string>("2009");
  const [targetTicketNumber, setTargetTicketNumber] = useState<string>("");
  const [customSender, setCustomSender] = useState<string>("");
  const [customSubject, setCustomSubject] = useState<string>("");
  const [customInReplyTo, setCustomInReplyTo] = useState<string>("");
  const [customBody, setCustomBody] = useState<string>("");
  const [diagScenario, setDiagScenario] = useState<string>("AUTO");
  const [busyLoop, setBusyLoop] = useState<boolean>(false);

  const loadData = useCallback(() => {
    emailsApi
      .list()
      .then((res) => {
        setMails(res);
        if (res.length > 0 && selId === null) {
          setSelId(res[0].id);
        }
      })
      .catch(() => {});
    emailsApi
      .loopStatus()
      .then((st) => setLoopStatus(st))
      .catch(() => {});
    ticketsApi
      .list()
      .then((tks) => setOpenTickets(tks))
      .catch(() => {});
    emailsApi
      .listInfoSamples()
      .then((s) => {
        setSamples(s);
        if (s.length > 0 && !selectedSample) {
          setSelectedSample(s[0]);
        }
      })
      .catch(() => {});
  }, [selId, selectedSample]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const filterFn = (m: MailboxTriageItemDTO, f: MailFilterKey): boolean => {
    if (f === "IN") return m.dir === "IN";
    if (f === "OUT") return m.dir === "OUT";
    if (f === "ISP") return /ISP_/.test(m.cls) || m.thread_type === "ISP";
    if (f === "UNRECOGNIZED") return m.cls === "UNRECOGNIZED";
    return true;
  };

  const visibleMails = mails.filter((m) => filterFn(m, filter));
  const selected =
    mails.find((m) => m.id === selId) || visibleMails[0] || mails[0];

  const refreshAfterAction = async (res: EmailLoopTriggerResponseDTO) => {
    setLastLoopResult(res);
    if (res.ticket_number && res.ticket_number.startsWith("NET-")) {
      setTargetTicketNumber(res.ticket_number);
    }
    if (res.branch_code) {
      setTargetBranchCode(res.branch_code);
    }
    const [updatedMails, updatedStatus, updatedTickets] = await Promise.all([
      emailsApi.list(),
      emailsApi.loopStatus().catch(() => null),
      ticketsApi.list().catch(() => []),
    ]);
    setMails(updatedMails);
    if (updatedStatus) setLoopStatus(updatedStatus);
    setOpenTickets(updatedTickets);
    if (updatedMails.length > 0) {
      setSelId(updatedMails[0].id);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setSimNotice(`Triaging ${file.name} with Gemma 4 26B…`);
    try {
      const res = await emailsApi.simulateFile(file);
      setSimNotice(
        `Simulated ${file.name} → Action: ${String(res.action || "TRIAGED")}${
          res.ticket_number && res.ticket_number !== "—"
            ? ` · Ticket ${res.ticket_number}`
            : ""
        }`,
      );
      await refreshAfterAction(res);
    } catch {
      setSimNotice(`Failed to simulate ${file.name}.`);
    }
  };

  const handleSimulateSample = async () => {
    if (!selectedSample) return;
    setSimNotice(`Simulating Info/${selectedSample}…`);
    try {
      const res = await emailsApi.simulateSample(selectedSample);
      setSimNotice(
        `Simulated ${selectedSample} → Action: ${String(res.action || "TRIAGED")}${
          res.ticket_number && res.ticket_number !== "—"
            ? ` · Ticket ${String(res.ticket_number)}`
            : ""
        }`,
      );
      await refreshAfterAction(res);
    } catch {
      setSimNotice(`Could not simulate ${selectedSample}.`);
    }
  };

  const executeScenarioTrigger = async (
    overrideScenario?: string,
    overrideRole?: "BRANCH" | "ISP",
  ) => {
    const activeScen = overrideScenario || scenario;
    if (overrideScenario) setScenario(overrideScenario);
    if (overrideRole) setCustomRole(overrideRole);
    setBusyLoop(true);
    setSimNotice(`Injecting ${activeScen} email into autonomous agent loop…`);
    try {
      const res = await emailsApi.triggerInLoop({
        scenario: activeScen,
        role:
          activeScen === "CUSTOM"
            ? overrideRole || customRole
            : overrideRole,
        branch_code: targetBranchCode.trim() || "2009",
        ticket_number: targetTicketNumber.trim() || undefined,
        sender: customSender.trim() || undefined,
        subject: customSubject.trim() || undefined,
        body_text: customBody.trim() || undefined,
        in_reply_to: customInReplyTo.trim() || undefined,
        diagnostic_scenario:
          diagScenario && diagScenario !== "AUTO" ? diagScenario : undefined,
      });
      const outCount = res.outbound_emails?.length || 0;
      setSimNotice(
        `Loop executed (${res.classification_label} → ${res.action}) · Ticket ${res.ticket_number}${
          outCount > 0 ? ` · ${outCount} autonomous reply email(s) sent` : ""
        }`,
      );
      await refreshAfterAction(res);
    } catch {
      setSimNotice("Failed to trigger email in agent loop.");
    } finally {
      setBusyLoop(false);
    }
  };

  const handleTriggerInLoop = async () => {
    await executeScenarioTrigger();
  };

  const handleRunSuggestedNextStep = async (
    step: SandboxSuggestedNextStepDTO,
  ) => {
    await executeScenarioTrigger(step.scenario, step.role);
  };

  const handleSendLiveGmailTest = async () => {
    setSimNotice("Sending live test email via configured SMTP server…");
    try {
      const res = await settingsApi.sendTestEmail({
        branch_code: targetBranchCode.trim() || "1084",
      });
      if (res.ok) {
        setSimNotice(
          `Sent live test email to ${res.recipient} (${res.latency_ms} ms). Click "Poll & run SLA loop" to fetch it via IMAP!`,
        );
      } else {
        setSimNotice(
          `Live SMTP send failed: ${res.error || "Configure Gmail App Password in AI & SLA Settings first."}`,
        );
      }
    } catch {
      setSimNotice(
        "Could not send live test email. Configure Gmail App Password in AI & SLA Settings.",
      );
    }
  };

  const handlePollNow = async () => {
    setSimNotice("Running IMAP poll & 2h/4–6h SLA chaser cycle…");
    try {
      const res = await emailsApi.pollNow();
      const chased = res.sla_chaser?.chased_count ?? 0;
      setSimNotice(
        `Poll #${res.poll_count} complete · ${res.messages_ingested} new inbound message(s) ingested · ${chased} SLA chaser(s) sent.`,
      );
      loadData();
    } catch {
      setSimNotice("Failed to run poll cycle.");
    }
  };

  const handleReclassify = async (emailItem: MailboxTriageItemDTO) => {
    setSimNotice(`Re-classifying email #${emailItem.id} with Gemma 4 26B…`);
    try {
      const res = await emailsApi.reclassify(emailItem.id);
      setSimNotice(
        `Re-classified "${emailItem.subject}" as ${String(
          res.classification_label || emailItem.cls,
        )} (confidence ${Number(res.confidence || 0.95).toFixed(2)}).`,
      );
      loadData();
    } catch {
      setSimNotice(`Re-classified ${emailItem.subject} as ${emailItem.cls}.`);
    }
  };

  const handlePrepareReplyInLoop = (emailItem: MailboxTriageItemDTO) => {
    setShowLoopPanel(true);
    if (emailItem.ticket && emailItem.ticket.startsWith("NET-")) {
      setTargetTicketNumber(emailItem.ticket);
    }
    if (emailItem.branch_code) {
      setTargetBranchCode(emailItem.branch_code);
    }
    setCustomInReplyTo(emailItem.mid);
    if (emailItem.cls === "CABLE_FIX_REQUEST") {
      setScenario("REGIONAL_IT_CABLE_FIXED");
    } else if (emailItem.cls === "ESCALATION" || emailItem.cls === "CHASER") {
      setScenario("ISP_WELCOME");
    } else if (emailItem.cls === "ISP_WELCOME") {
      setScenario("ISP_RESOLVED");
    } else if (emailItem.cls === "CONTACT_BLOCKER_MEDIATION") {
      setScenario("REGIONAL_IT_NEW_PHONE");
    } else if (emailItem.cls === "REGIONAL_IT_NOTIFY") {
      setScenario("BRANCH_INCIDENT");
    } else {
      setScenario("ISP_WELCOME");
    }
    setSimNotice(
      `Prepared in-thread reply to ${emailItem.mid} (${emailItem.ticket || "new thread"}). Click "Send into Agent Loop" to execute.`,
    );
  };

  const filterMeta: Array<[MailFilterKey, string]> = [
    ["ALL", "All"],
    ["IN", "Inbound"],
    ["OUT", "Outbound"],
    ["ISP", "ISP thread"],
    ["UNRECOGNIZED", "Unrecognized"],
  ];

  const inboundCount =
    loopStatus?.inbound_count ?? mails.filter((m) => m.dir === "IN").length;
  const outboundCount =
    loopStatus?.outbound_count ?? mails.filter((m) => m.dir === "OUT").length;
  const activeScenarioMeta =
    LOOP_SCENARIOS.find((s) => s.key === scenario) || LOOP_SCENARIOS[0];

  const correlatedThreadMails =
    selected && selected.ticket && selected.ticket.startsWith("NET-")
      ? mails.filter((m) => m.ticket === selected.ticket)
      : [];

  return (
    <AppShell
      active="Mailbox & Triage"
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
          <h1>Mailbox &amp; Email Triage</h1>
          <p>
            Interactive Mail Simulation Sandbox &amp; Live Gmail / Exchange
            Harness · {inboundCount} inbound · {outboundCount} outbound ·{" "}
            {loopStatus
              ? `${loopStatus.open_isp_threads_count} ISP threads active · last poll ${loopStatus.seconds_since_last_poll}s ago`
              : "background poller active"}
          </p>
        </div>
        <div className="kz-row">
          <Button variant="secondary" size="sm" onClick={handlePollNow}>
            Poll &amp; run SLA loop
          </Button>
          <Button
            variant="secondary"
            size="sm"
            onClick={handleSendLiveGmailTest}
          >
            Send live SMTP test
          </Button>
          <Button
            variant="primary"
            size="sm"
            onClick={() => setShowLoopPanel((v) => !v)}
          >
            {showLoopPanel
              ? "Hide email loop harness"
              : "Trigger email in loop"}
          </Button>
        </div>
      </div>

      {/* Live Gmail / Exchange Connection & Safe Redirect Status Banner */}
      <section
        className="kz-card"
        style={{
          padding: "12px 16px",
          display: "flex",
          flexWrap: "wrap",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 12,
        }}
      >
        <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 8, fontSize: 13 }}>
          <b>Mailbox Transport:</b>
          <Badge
            tone={
              loopStatus?.provider_preset === "gmail"
                ? "info"
                : loopStatus?.provider_preset === "kazyon"
                  ? "brand"
                  : "neutral"
            }
          >
            {loopStatus?.provider_preset === "gmail"
              ? "Gmail Testing (imap.gmail.com)"
              : loopStatus?.provider_preset === "kazyon"
                ? "Kazyon Exchange (mail.kazyon.com)"
                : loopStatus?.imap_host || "Local Sandbox"}
          </Badge>
          <Badge tone={loopStatus?.imap_credentials_configured ? "good" : "neutral"}>
            {loopStatus?.imap_credentials_configured
              ? "IMAP Login Ready"
              : "IMAP Local Dropbox"}
          </Badge>
          <Badge tone={loopStatus?.smtp_enabled ? "good" : "neutral"}>
            {loopStatus?.smtp_enabled
              ? "Live Outbound SMTP ON"
              : "Outbound SMTP Simulated"}
          </Badge>
          {loopStatus?.test_redirect_email ? (
            <Badge tone="warning">
              Safe Redirect → {loopStatus.test_redirect_email}
            </Badge>
          ) : null}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <button
            type="button"
            className="kz-btn kz-btn-secondary kz-btn-sm"
            onClick={() => onNavigate("AI & SLA Settings")}
          >
            Configure Gmail / App Password →
          </button>
        </div>
      </section>

      {showLoopPanel ? (
        <section
          className="kz-card"
          aria-label="Autonomous Email Loop Trigger & Multi-Turn Harness"
        >
          <div className="kz-card-hd">
            <div>
              <h2>Autonomous Email Loop Trigger &amp; Multi-Turn Harness</h2>
              <p>
                Trigger any stage of the Branch ↔ AI Agent ↔ ISP email loop with
                automatic RFC-5322 In-Reply-To / References correlation
              </p>
            </div>
            <div className="kz-row">
              <Badge
                tone={
                  loopStatus?.global_ai_kill_switch ? "critical" : "good"
                }
              >
                {loopStatus?.global_ai_kill_switch
                  ? "AI Kill-Switch Paused"
                  : "Agent Harness Active"}
              </Badge>
              <Badge tone="info">
                {activeScenarioMeta.thread} Thread
              </Badge>
            </div>
          </div>

          <div
            className="kz-card-bd"
            style={{ display: "flex", flexDirection: "column", gap: 14 }}
          >
            {/* Quick multi-turn loop step chips */}
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
              {LOOP_SCENARIOS.map((sc) => (
                <button
                  key={sc.key}
                  type="button"
                  className={clsx(
                    "kz-chip",
                    scenario === sc.key && "kz-chip-on",
                  )}
                  onClick={() => setScenario(sc.key)}
                >
                  <b>{sc.stepBadge}:</b> {sc.label}
                </button>
              ))}
            </div>

            <div
              style={{
                padding: "10px 12px",
                borderRadius: 10,
                background: "var(--surface-100)",
                border: "1px solid var(--border)",
                fontSize: 13,
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                gap: 12,
                flexWrap: "wrap",
              }}
            >
              <span>{activeScenarioMeta.description}</span>
              {customInReplyTo ? (
                <span className="kz-mono" style={{ fontSize: 12 }}>
                  In-Reply-To: {customInReplyTo}{" "}
                  <button
                    type="button"
                    className="kz-btn kz-btn-ghost kz-btn-sm"
                    onClick={() => setCustomInReplyTo("")}
                  >
                    Clear
                  </button>
                </span>
              ) : null}
            </div>

            <div
              style={{
                display: "grid",
                gridTemplateColumns:
                  "repeat(auto-fit, minmax(min(220px, 100%), 1fr))",
                gap: 12,
                fontSize: 13,
              }}
            >
              <label
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: 4,
                  fontWeight: 600,
                }}
              >
                Store SAP Code (or Preset)
                <div style={{ display: "flex", gap: 6 }}>
                  <input
                    value={targetBranchCode}
                    onChange={(e) => setTargetBranchCode(e.target.value)}
                    placeholder="2009"
                    className="kz-mono"
                    style={{
                      flex: 1,
                      height: 36,
                      padding: "0 10px",
                      border: "1px solid var(--border-strong)",
                      borderRadius: 8,
                    }}
                  />
                  <select
                    aria-label="Quick store preset"
                    value={targetBranchCode}
                    onChange={(e) => setTargetBranchCode(e.target.value)}
                    style={{
                      height: 36,
                      padding: "0 8px",
                      border: "1px solid var(--border-strong)",
                      borderRadius: 8,
                      font: "500 12px var(--font-sans)",
                    }}
                  >
                    <option value="2009">2009 · NOOR (Full Outage)</option>
                    <option value="1173">1173 · ORANGE (4G Backup)</option>
                    <option value="1254">1254 · WE (Full Outage)</option>
                    <option value="1188">1188 · NOOR (Cables Unplugged)</option>
                    <option value="1201">1201 · NOOR (Internal Switch)</option>
                    <option value="1366">1366 · NOOR (Healthy PASS)</option>
                  </select>
                </div>
              </label>

              <label
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: 4,
                  fontWeight: 600,
                }}
              >
                Correlate to Ticket (optional)
                <div style={{ display: "flex", gap: 6 }}>
                  <input
                    value={targetTicketNumber}
                    onChange={(e) => setTargetTicketNumber(e.target.value)}
                    placeholder="Auto-correlate or NET-..."
                    className="kz-mono"
                    style={{
                      flex: 1,
                      height: 36,
                      padding: "0 10px",
                      border: "1px solid var(--border-strong)",
                      borderRadius: 8,
                    }}
                  />
                  {openTickets.length > 0 ? (
                    <select
                      aria-label="Select existing ticket"
                      value={targetTicketNumber}
                      onChange={(e) => {
                        const val = e.target.value;
                        setTargetTicketNumber(val);
                        const tk = openTickets.find((t) => t.id === val);
                        if (tk) setTargetBranchCode(tk.branch_code);
                      }}
                      style={{
                        maxWidth: 150,
                        height: 36,
                        padding: "0 8px",
                        border: "1px solid var(--border-strong)",
                        borderRadius: 8,
                        font: "500 12px var(--font-sans)",
                      }}
                    >
                      <option value="">Auto match</option>
                      {openTickets.slice(0, 20).map((t) => (
                        <option key={t.id} value={t.id}>
                          {t.id} ({t.branch_code} · {t.isp})
                        </option>
                      ))}
                    </select>
                  ) : null}
                </div>
              </label>

              <label
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: 4,
                  fontWeight: 600,
                }}
              >
                Diagnostic Verdict Override
                <select
                  value={diagScenario}
                  onChange={(e) => setDiagScenario(e.target.value)}
                  style={{
                    height: 36,
                    padding: "0 10px",
                    border: "1px solid var(--border-strong)",
                    borderRadius: 8,
                    font: "500 13px var(--font-sans)",
                  }}
                >
                  <option value="AUTO">AUTO (Branch default)</option>
                  <option value="FULL_OUTAGE">FULL_OUTAGE (IP1 DOWN)</option>
                  <option value="LOCAL_LOOP_DOWN_ON_4G">
                    LOCAL_LOOP_DOWN_ON_4G (4G Hub)
                  </option>
                  <option value="INTERNAL_LAN_SWITCH">
                    INTERNAL_LAN_SWITCH (IP1 UP, IP2 DOWN)
                  </option>
                  <option value="PASS">PASS (IP1 UP, IP2 UP)</option>
                </select>
              </label>

              <label
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: 4,
                  fontWeight: 600,
                }}
              >
                Custom Sender (optional)
                <input
                  value={customSender}
                  onChange={(e) => setCustomSender(e.target.value)}
                  placeholder="Auto from store / ISP"
                  className="kz-mono"
                  style={{
                    height: 36,
                    padding: "0 10px",
                    border: "1px solid var(--border-strong)",
                    borderRadius: 8,
                  }}
                />
              </label>
            </div>

            {scenario === "CUSTOM" ? (
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "180px 1fr 2fr",
                  gap: 12,
                  fontSize: 13,
                }}
              >
                <label
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    gap: 4,
                    fontWeight: 600,
                  }}
                >
                  Role-Play Actor
                  <select
                    value={customRole}
                    onChange={(e) =>
                      setCustomRole(e.target.value as "BRANCH" | "ISP")
                    }
                    style={{
                      height: 36,
                      padding: "0 10px",
                      border: "1px solid var(--border-strong)",
                      borderRadius: 8,
                      font: "500 13px var(--font-sans)",
                    }}
                  >
                    <option value="BRANCH">Act as Branch (Regional IT)</option>
                    <option value="ISP">Act as ISP NOC (NOOR/ORANGE/WE)</option>
                  </select>
                </label>
                <label
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    gap: 4,
                    fontWeight: 600,
                  }}
                >
                  Custom Subject
                  <input
                    value={customSubject}
                    onChange={(e) => setCustomSubject(e.target.value)}
                    placeholder="Store 2009 network outage"
                    style={{
                      height: 36,
                      padding: "0 10px",
                      border: "1px solid var(--border-strong)",
                      borderRadius: 8,
                      font: "500 13px var(--font-sans)",
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
                  Custom Email Body
                  <input
                    value={customBody}
                    onChange={(e) => setCustomBody(e.target.value)}
                    placeholder="Dear Network Support, kindly check connection store 2009, site contact 010 2345 8817..."
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
            ) : null}

            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                gap: 12,
                flexWrap: "wrap",
              }}
            >
              <span className="kz-tcard-meta">
                Constructs RFC-5322 MIME message → Correlates thread → Runs
                Gemma 4 classification → Executes diagnostics &amp; dispatches
                outbound replies
              </span>
              <Button
                variant="secondary"
                onClick={handleTriggerInLoop}
                disabled={busyLoop}
              >
                {busyLoop
                  ? "Running Agent Loop…"
                  : `Send "${activeScenarioMeta.stepBadge}" into Agent Loop`}
              </Button>
            </div>

            {lastLoopResult ? (
              <div
                style={{
                  padding: 12,
                  borderRadius: 10,
                  background: "var(--brand-50)",
                  border: "1px solid var(--border)",
                  display: "flex",
                  flexDirection: "column",
                  gap: 8,
                  fontSize: 13,
                }}
              >
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    flexWrap: "wrap",
                    gap: 8,
                  }}
                >
                  <div className="kz-row">
                    <b>Last Loop Execution:</b>
                    <Badge tone="brand">
                      {lastLoopResult.classification_label}
                    </Badge>
                    <span>→</span>
                    <Badge tone="info">{lastLoopResult.action}</Badge>
                    {lastLoopResult.correlation_method ? (
                      <span className="kz-mono kz-muted">
                        ({lastLoopResult.correlation_method})
                      </span>
                    ) : null}
                  </div>
                  {lastLoopResult.ticket_number &&
                  lastLoopResult.ticket_number.startsWith("NET-") ? (
                    <div className="kz-row">
                      <span className="kz-mono">
                        Ticket: <b>{lastLoopResult.ticket_number}</b>
                        {lastLoopResult.ticket_status
                          ? ` (${lastLoopResult.ticket_status})`
                          : ""}
                      </span>
                      <button
                        type="button"
                        className="kz-btn kz-btn-secondary kz-btn-sm"
                        onClick={() =>
                          onOpenTicket(lastLoopResult.ticket_number)
                        }
                      >
                        Open {lastLoopResult.ticket_number} 360°
                      </button>
                    </div>
                  ) : null}
                </div>

                {lastLoopResult.stage_trace &&
                lastLoopResult.stage_trace.length > 0 ? (
                  <div
                    style={{
                      display: "grid",
                      gridTemplateColumns:
                        "repeat(auto-fit, minmax(min(210px, 100%), 1fr))",
                      gap: 8,
                      paddingTop: 4,
                    }}
                  >
                    {lastLoopResult.stage_trace.map((st) => {
                      const tone: BadgeTone =
                        st.status === "PASS"
                          ? "good"
                          : st.status === "FAIL"
                            ? "critical"
                            : st.status === "WARN"
                              ? "warning"
                              : st.status === "INFO"
                                ? "info"
                                : "neutral";
                      return (
                        <div
                          key={st.step}
                          style={{
                            padding: "8px 10px",
                            borderRadius: 8,
                            background: "var(--surface-000)",
                            border: "1px solid var(--border)",
                            display: "flex",
                            flexDirection: "column",
                            gap: 4,
                          }}
                        >
                          <div
                            style={{
                              display: "flex",
                              justifyContent: "space-between",
                              alignItems: "center",
                              gap: 6,
                            }}
                          >
                            <span
                              style={{
                                fontSize: 11,
                                fontWeight: 700,
                                color: "var(--ink-muted)",
                              }}
                            >
                              {st.step}. {st.name}
                            </span>
                            <Badge tone={tone}>{st.status}</Badge>
                          </div>
                          <div style={{ fontSize: 12, fontWeight: 600 }}>
                            {st.summary}
                          </div>
                          <div
                            style={{
                              fontSize: 11,
                              color: "var(--ink-muted)",
                              overflowWrap: "anywhere",
                            }}
                          >
                            {st.detail}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                ) : null}

                {lastLoopResult.actions_taken &&
                lastLoopResult.actions_taken.length > 0 ? (
                  <ul
                    style={{
                      margin: 0,
                      paddingLeft: 18,
                      fontSize: 12,
                      color: "var(--ink)",
                    }}
                  >
                    {lastLoopResult.actions_taken.map((step, idx) => (
                      <li key={idx}>{step}</li>
                    ))}
                  </ul>
                ) : null}

                {lastLoopResult.suggested_next_steps &&
                lastLoopResult.suggested_next_steps.length > 0 ? (
                  <div
                    style={{
                      display: "flex",
                      flexDirection: "column",
                      gap: 6,
                      paddingTop: 4,
                    }}
                  >
                    <span
                      style={{
                        fontSize: 11,
                        fontWeight: 700,
                        textTransform: "uppercase",
                        letterSpacing: ".05em",
                        color: "var(--ink-muted)",
                      }}
                    >
                      Interactive Role-Play — Click Next Turn in Conversation:
                    </span>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                      {lastLoopResult.suggested_next_steps.map((nxt) => (
                        <button
                          key={`${nxt.scenario}-${nxt.role}`}
                          type="button"
                          className="kz-btn kz-btn-primary kz-btn-sm"
                          disabled={busyLoop}
                          onClick={() => handleRunSuggestedNextStep(nxt)}
                          title={nxt.description}
                        >
                          [{nxt.role}] {nxt.label} →
                        </button>
                      ))}
                    </div>
                  </div>
                ) : null}

                {lastLoopResult.outbound_emails &&
                lastLoopResult.outbound_emails.length > 0 ? (
                  <div
                    style={{
                      display: "flex",
                      flexDirection: "column",
                      gap: 6,
                      paddingTop: 4,
                    }}
                  >
                    <span
                      style={{
                        fontSize: 11,
                        fontWeight: 700,
                        textTransform: "uppercase",
                        letterSpacing: ".05em",
                        color: "var(--ink-muted)",
                      }}
                    >
                      Autonomous Outbound Emails Dispatched (
                      {lastLoopResult.outbound_emails.length})
                    </span>
                    {lastLoopResult.outbound_emails.map((out) => (
                      <div
                        key={out.id}
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "center",
                          gap: 8,
                          flexWrap: "wrap",
                          padding: "6px 10px",
                          background: "var(--surface-000)",
                          border: "1px solid var(--border)",
                          borderRadius: 8,
                          fontSize: 12,
                        }}
                      >
                        <div className="kz-row">
                          <Badge tone="outline">OUT · {out.thread_type}</Badge>
                          <Badge tone="good">{out.classification_label}</Badge>
                          <span>
                            To <b>{out.to}</b> — {out.subject}
                          </span>
                        </div>
                        <button
                          type="button"
                          className="kz-btn kz-btn-ghost kz-btn-sm"
                          onClick={() => setSelId(out.id)}
                        >
                          Inspect email
                        </button>
                      </div>
                    ))}
                  </div>
                ) : null}
              </div>
            ) : null}
          </div>
        </section>
      ) : null}

      <div
        style={{
          display: "flex",
          gap: 12,
          flexWrap: "wrap",
          alignItems: "stretch",
        }}
      >
        <label
          style={{
            flex: "2 1 380px",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 12,
            flexWrap: "wrap",
            padding: 18,
            border: "1.5px dashed var(--brand-500)",
            borderRadius: 14,
            background: "var(--brand-50)",
            fontSize: 13,
            cursor: "pointer",
          }}
        >
          <b>Simulate inbound email</b>
          <span className="kz-muted">Drop an .eml file here, or</span>
          <span className="kz-btn kz-btn-secondary kz-btn-sm">Choose file</span>
          <input
            type="file"
            accept=".eml"
            onChange={handleFileUpload}
            style={{
              position: "absolute",
              width: 1,
              height: 1,
              opacity: 0,
            }}
          />
        </label>

        {samples.length > 0 ? (
          <div
            className="kz-card"
            style={{
              flex: "1 1 320px",
              padding: "12px 16px",
              display: "flex",
              alignItems: "center",
              gap: 8,
              flexWrap: "wrap",
            }}
          >
            <select
              aria-label="Info .eml sample"
              value={selectedSample}
              onChange={(e) => setSelectedSample(e.target.value)}
              style={{
                flex: 1,
                minWidth: 160,
                height: 36,
                padding: "0 10px",
                border: "1px solid var(--border-strong)",
                borderRadius: 8,
                font: "500 13px var(--font-sans)",
              }}
            >
              {samples.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
            <Button
              variant="secondary"
              size="sm"
              onClick={handleSimulateSample}
            >
              Simulate sample .eml
            </Button>
          </div>
        ) : null}
      </div>

      {simNotice ? (
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
          {simNotice}
        </div>
      ) : null}

      <div className="kz-filters">
        {filterMeta.map(([key, label]) => (
          <button
            key={key}
            type="button"
            className={clsx("kz-chip", filter === key && "kz-chip-on")}
            onClick={() => setFilter(key)}
          >
            {label} · {mails.filter((m) => filterFn(m, key)).length}
          </button>
        ))}
      </div>

      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: 16,
          alignItems: "flex-start",
        }}
      >
        <section
          className="kz-card"
          style={{ flex: "999 1 560px", minWidth: 0, overflow: "hidden" }}
        >
          <div className="kz-scroll-x">
            <table className="kz-table">
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Dir / Thread</th>
                  <th>From / To</th>
                  <th>Subject</th>
                  <th>Classified as</th>
                  <th>Ticket</th>
                </tr>
              </thead>
              <tbody>
                {visibleMails.map((m) => {
                  const isSel = selected?.id === m.id;
                  return (
                    <tr
                      key={m.id}
                      onClick={() => setSelId(m.id)}
                      style={{
                        cursor: "pointer",
                        background: isSel ? "var(--brand-100)" : undefined,
                      }}
                    >
                      <td className="kz-num kz-nowrap">{m.time}</td>
                      <td className="kz-nowrap">
                        <div className="kz-row">
                          <Badge tone={m.dtone}>{m.dir}</Badge>
                          {m.thread_type ? (
                            <span className="kz-tcard-meta">
                              {m.thread_type}
                            </span>
                          ) : null}
                        </div>
                      </td>
                      <td className="kz-nowrap" style={{ fontWeight: 600 }}>
                        {m.who}
                      </td>
                      <td>
                        <button
                          type="button"
                          onClick={() => setSelId(m.id)}
                          style={{
                            all: "unset",
                            cursor: "pointer",
                            display: "block",
                            maxWidth: 320,
                            overflow: "hidden",
                            textOverflow: "ellipsis",
                            whiteSpace: "nowrap",
                          }}
                        >
                          {m.subject}
                        </button>
                      </td>
                      <td>
                        <Badge tone={(m.ctone as BadgeTone) || "neutral"}>
                          {m.cls}
                        </Badge>
                      </td>
                      <td>
                        {m.ticket && m.ticket.startsWith("NET-") ? (
                          <a
                            href={`#ticket-${m.ticket}`}
                            className="kz-tcard-id"
                            onClick={(e) => {
                              e.preventDefault();
                              e.stopPropagation();
                              onOpenTicket(m.ticket);
                            }}
                          >
                            {m.ticket}
                          </a>
                        ) : (
                          <span className="kz-tcard-meta">{m.ticket}</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>

        {selected ? (
          <aside
            className="kz-card"
            style={{
              flex: "1 1 340px",
              maxWidth: 460,
              display: "flex",
              flexDirection: "column",
            }}
            aria-label="Email details"
          >
            <div className="kz-card-hd">
              <h2>Email details</h2>
              <Badge tone={(selected.ctone as BadgeTone) || "neutral"}>
                {selected.cls}
              </Badge>
            </div>
            <div
              className="kz-card-bd"
              style={{ display: "flex", flexDirection: "column", gap: 12 }}
            >
              <dl
                style={{
                  margin: 0,
                  display: "grid",
                  gridTemplateColumns: "90px 1fr",
                  gap: "6px 10px",
                  fontSize: 12,
                }}
              >
                <dt className="kz-muted">From</dt>
                <dd style={{ margin: 0 }}>{selected.from}</dd>
                <dt className="kz-muted">To</dt>
                <dd style={{ margin: 0 }}>{selected.to}</dd>
                {selected.cc ? (
                  <>
                    <dt className="kz-muted">CC</dt>
                    <dd style={{ margin: 0 }}>{selected.cc}</dd>
                  </>
                ) : null}
                <dt className="kz-muted">Thread</dt>
                <dd style={{ margin: 0 }}>
                  <Badge tone="outline">
                    {selected.thread_type || "BRANCH"}
                  </Badge>
                </dd>
                <dt className="kz-muted">Subject</dt>
                <dd style={{ margin: 0, fontWeight: 600 }}>
                  {selected.subject}
                </dd>
                <dt className="kz-muted">Message-ID</dt>
                <dd style={{ margin: 0 }} className="kz-mono">
                  {selected.mid}
                </dd>
                {selected.in_reply_to ? (
                  <>
                    <dt className="kz-muted">In-Reply-To</dt>
                    <dd style={{ margin: 0 }} className="kz-mono">
                      {selected.in_reply_to}
                    </dd>
                  </>
                ) : null}
                <dt className="kz-muted">Attachments</dt>
                <dd style={{ margin: 0 }}>{selected.att}</dd>
              </dl>
              <p
                style={{
                  margin: 0,
                  padding: 12,
                  background: "var(--surface-100)",
                  borderRadius: 10,
                  fontSize: 13,
                  lineHeight: "20px",
                  whiteSpace: "pre-line",
                }}
              >
                {selected.body}
              </p>

              {selected.thread_replies && selected.thread_replies.length > 1 ? (
                <div
                  style={{ display: "flex", flexDirection: "column", gap: 6 }}
                >
                  <div
                    style={{
                      font: "700 11px/16px var(--font-sans)",
                      letterSpacing: ".06em",
                      textTransform: "uppercase",
                      color: "var(--ink-muted)",
                    }}
                  >
                    Parsed Thread Replies ({selected.thread_replies.length}{" "}
                    replies in email)
                  </div>
                  <div
                    style={{
                      display: "flex",
                      flexDirection: "column",
                      gap: 6,
                      maxHeight: 220,
                      overflowY: "auto",
                    }}
                  >
                    {selected.thread_replies.map((rep) => (
                      <div
                        key={rep.index}
                        style={{
                          padding: "8px 10px",
                          borderRadius: 8,
                          border: "1px solid var(--border)",
                          background: rep.is_latest
                            ? "var(--brand-50)"
                            : "var(--surface-100)",
                          fontSize: 12,
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
                        <div style={{ whiteSpace: "pre-line" }}>{rep.body}</div>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}

              {correlatedThreadMails.length > 1 ? (
                <div
                  style={{ display: "flex", flexDirection: "column", gap: 6 }}
                >
                  <div
                    style={{
                      font: "700 11px/16px var(--font-sans)",
                      letterSpacing: ".06em",
                      textTransform: "uppercase",
                      color: "var(--ink-muted)",
                    }}
                  >
                    Correlated Thread ({selected.ticket} ·{" "}
                    {correlatedThreadMails.length} messages)
                  </div>
                  <div
                    style={{
                      display: "flex",
                      flexDirection: "column",
                      gap: 4,
                      maxHeight: 150,
                      overflowY: "auto",
                    }}
                  >
                    {correlatedThreadMails.map((tm) => (
                      <button
                        key={tm.id}
                        type="button"
                        onClick={() => setSelId(tm.id)}
                        style={{
                          all: "unset",
                          cursor: "pointer",
                          padding: "6px 8px",
                          borderRadius: 6,
                          border: "1px solid var(--border)",
                          background:
                            tm.id === selected.id
                              ? "var(--brand-100)"
                              : "var(--surface-100)",
                          fontSize: 12,
                          display: "flex",
                          justifyContent: "space-between",
                          gap: 8,
                        }}
                      >
                        <span className="kz-nowrap">
                          <b>{tm.dir}</b> · {tm.cls}
                        </span>
                        <span className="kz-mono kz-muted">{tm.time}</span>
                      </button>
                    ))}
                  </div>
                </div>
              ) : null}

              <div
                style={{
                  font: "700 11px/16px var(--font-sans)",
                  letterSpacing: ".06em",
                  textTransform: "uppercase",
                  color: "var(--ink-muted)",
                }}
              >
                Gemma 4 classification
              </div>
              <pre
                className="kz-mono"
                style={{
                  margin: 0,
                  padding: 12,
                  background: "var(--term-bg)",
                  color: "var(--term-ink)",
                  border: "1px solid var(--border)",
                  borderRadius: 10,
                  overflowX: "auto",
                  lineHeight: "18px",
                }}
              >
                {selected.json}
              </pre>
              {showRaw ? (
                <pre
                  className="kz-mono"
                  style={{
                    margin: 0,
                    padding: 12,
                    background: "var(--term-bg)",
                    color: "var(--term-ink)",
                    border: "1px solid var(--border)",
                    borderRadius: 10,
                    overflowX: "auto",
                    lineHeight: "18px",
                  }}
                >
                  {selected.headers}
                </pre>
              ) : null}
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => handlePrepareReplyInLoop(selected)}
                >
                  Reply in loop
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => handleReclassify(selected)}
                >
                  Re-classify
                </Button>
                <button
                  type="button"
                  className="kz-btn kz-btn-ghost kz-btn-sm"
                  aria-pressed={showRaw}
                  onClick={() => setShowRaw((v) => !v)}
                >
                  {showRaw ? "Hide raw headers" : "View raw headers"}
                </button>
                {selected.ticket && selected.ticket.startsWith("NET-") ? (
                  <button
                    type="button"
                    className="kz-btn kz-btn-ghost kz-btn-sm"
                    onClick={() => onOpenTicket(selected.ticket)}
                  >
                    Open ticket
                  </button>
                ) : null}
              </div>
            </div>
          </aside>
        ) : null}
      </div>
    </AppShell>
  );
}
