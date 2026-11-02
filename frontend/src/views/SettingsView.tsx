import React, { useCallback, useEffect, useState } from "react";
import { AppShell, Badge, Button } from "../design-system";
import {
  FleetScanRunDTO,
  FleetScanStatusDTO,
  SendTestEmailResult,
  SmtpConnectionTestResult,
  SmtpListenerStatusDTO,
  SmtpSecurity,
  SystemSettingsDTO,
  VllmConnectionTestResult,
  emailsApi,
  settingsApi,
} from "../lib/api";
import { ConsoleViewProps } from "./types";

const DEFAULT_SETTINGS: SystemSettingsDTO = {
  global_ai_kill_switch: false,
  mailbox_account: "noc@kazyon.com",
  smtp_host: "mail.kazyon.com",
  smtp_port: 587,
  smtp_security: "starttls",
  smtp_enabled: true,
  smtp_username: "noc@kazyon.com",
  smtp_credentials_configured: true,
  test_redirect_email: "",
  poll_interval_sec: 30,
  vllm_endpoint: "http://10.100.109.9:8002/v1",
  vllm_temperature: 0.1,
  vllm_max_tokens: 2048,
  confidence_threshold: 80,
  welcome_sla_minutes: 120,
  followup_interval_minutes: 300,
  max_chasers_before_human: 4,
  max_outbound_emails_per_ticket_hour: 6,
  ignore_auto_submitted: true,
  diagnostic_timeout_sec: 20,
  ping_count: 4,
  traceroute_max_hops: 15,
  admin_notification_email: "admin@kazyon.com",
  notify_admin_on_every_action: true,
  require_admin_approval_before_action: false,
  fleet_scan_enabled: false,
  fleet_scan_interval_minutes: 180,
  fleet_scan_window_start: "08:00",
  fleet_scan_window_end: "23:00",
  fleet_scan_mass_outage_pct: 5,
  fallback_contacts: [
    { ini: "NO", email: "noc-oncall@kazyon.com", role: "On-duty engineer" },
    {
      ini: "IT",
      email: "ITInfrastructure@kazyon.com",
      role: "HQ IT Infrastructure team",
    },
  ],
};

const SMTP_DEFAULT_PORTS: Record<SmtpSecurity, number> = {
  starttls: 587,
  ssl: 465,
  none: 25,
};

const SMTP_STAGE_LABELS: Record<SmtpConnectionTestResult["stage"], string> = {
  config: "Host not set",
  connect: "Can't reach server",
  ehlo: "No EHLO reply",
  tls: "TLS failed",
  auth: "Login rejected",
  sender: "Sender refused",
  done: "Connected",
};

type TestState<T> =
  | { kind: "idle" }
  | { kind: "running" }
  | { kind: "done"; result: T }
  | { kind: "request_failed"; message: string };

const fieldStyle: React.CSSProperties = {
  height: 38,
  padding: "0 10px",
  border: "1px solid var(--border-strong)",
  borderRadius: 8,
  font: "500 13px var(--font-sans)",
};

const labelStyle: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: 4,
  fontWeight: 600,
};

const resultTextStyle: React.CSSProperties = {
  gridColumn: "1 / -1",
  margin: 0,
  fontSize: 12,
  color: "var(--ink-muted)",
  overflowWrap: "anywhere",
};

export function SettingsView({
  theme,
  onToggleTheme,
  onNavigate,
  env,
  initials,
  userDisplayName,
  userRoleLabel,
  onLogout,
  canAccessNav,
}: ConsoleViewProps) {
  const [settings, setSettings] =
    useState<SystemSettingsDTO>(DEFAULT_SETTINGS);
  const [smtpPasswordInput, setSmtpPasswordInput] = useState("");
  const [smtpTest, setSmtpTest] = useState<
    TestState<SmtpConnectionTestResult>
  >({ kind: "idle" });
  const [roundTripTest, setRoundTripTest] = useState<
    TestState<SendTestEmailResult>
  >({ kind: "idle" });
  const [vllmTest, setVllmTest] = useState<
    TestState<VllmConnectionTestResult>
  >({ kind: "idle" });
  const [newFallbackEmail, setNewFallbackEmail] = useState("");
  const [toast, setToast] = useState<string | null>(null);

  const loadSettings = useCallback(() => {
    settingsApi
      .get()
      .then((res) => setSettings(res))
      .catch(() => {});
  }, []);

  const [listener, setListener] = useState<SmtpListenerStatusDTO | null>(
    null,
  );
  const [fleetScanStatus, setFleetScanStatus] =
    useState<FleetScanStatusDTO | null>(null);
  const [fleetScanRunState, setFleetScanRunState] = useState<
    TestState<FleetScanRunDTO>
  >({ kind: "idle" });

  const loadListenerStatus = useCallback(() => {
    emailsApi
      .loopStatus()
      .then((res) => setListener(res.smtp_listener))
      .catch(() => setListener(null));
  }, []);

  const loadFleetScanStatus = useCallback(() => {
    settingsApi
      .getFleetScans(10)
      .then((res) => setFleetScanStatus(res))
      .catch(() => setFleetScanStatus(null));
  }, []);

  useEffect(() => {
    loadSettings();
    loadListenerStatus();
    loadFleetScanStatus();
  }, [loadSettings, loadListenerStatus, loadFleetScanStatus]);

  const handleSaveAll = async () => {
    try {
      const payload: Partial<SystemSettingsDTO> = { ...settings };
      if (smtpPasswordInput.trim()) {
        payload.smtp_password = smtpPasswordInput.trim();
      }
      const updated = await settingsApi.update(payload);
      setSettings(updated);
      setSmtpPasswordInput("");
      setToast("All settings saved (encrypted SMTP credentials stored) and recorded in the audit log.");
    } catch {
      setToast("Failed to save settings.");
    }
  };

  const handleToggleKillSwitch = async () => {
    const nextKilled = !settings.global_ai_kill_switch;
    setSettings((prev) => ({ ...prev, global_ai_kill_switch: nextKilled }));
    try {
      const updated = await settingsApi.update({
        global_ai_kill_switch: nextKilled,
      });
      setSettings(updated);
      setToast(
        nextKilled
          ? "Global AI master kill-switch activated. All autonomous actions paused."
          : "Global AI master kill-switch deactivated. Autonomous actions resumed.",
      );
    } catch {
      // Keep local toggle
    }
  };

  const handleSetExecutionMode = async (requireApproval: boolean) => {
    setSettings((prev) => ({
      ...prev,
      require_admin_approval_before_action: requireApproval,
    }));
    try {
      const updated = await settingsApi.update({
        require_admin_approval_before_action: requireApproval,
        admin_notification_email: settings.admin_notification_email,
        notify_admin_on_every_action: settings.notify_admin_on_every_action,
      });
      setSettings(updated);
      setToast(
        requireApproval
          ? "Agent Execution Mode set to ASK BEFORE ACTING: Agent will run triage & diagnostics first, email the Admin, and pause for approval before sending outbound emails or finalizing ticket status."
          : "Agent Execution Mode set to PROCEED WITHOUT ASKING: Agent will execute actions autonomously and email a report of every action to the Admin.",
      );
    } catch {
      // Keep local toggle
    }
  };

  const handleToggleNotifyEveryAction = async (enabled: boolean) => {
    setSettings((prev) => ({
      ...prev,
      notify_admin_on_every_action: enabled,
    }));
    try {
      const updated = await settingsApi.update({
        notify_admin_on_every_action: enabled,
        admin_notification_email: settings.admin_notification_email,
      });
      setSettings(updated);
      setToast(
        enabled
          ? `Admin action email notifications enabled (${updated.admin_notification_email}).`
          : "Admin action email notifications disabled for autonomous actions (Approval Mode requests are still emailed).",
      );
    } catch {
      // Keep local toggle
    }
  };

  const handleToggleFleetScan = async (enabled: boolean) => {
    setSettings((prev) => ({
      ...prev,
      fleet_scan_enabled: enabled,
    }));
    try {
      const updated = await settingsApi.update({
        fleet_scan_enabled: enabled,
        fleet_scan_interval_minutes: settings.fleet_scan_interval_minutes,
        fleet_scan_window_start: settings.fleet_scan_window_start,
        fleet_scan_window_end: settings.fleet_scan_window_end,
        fleet_scan_mass_outage_pct: settings.fleet_scan_mass_outage_pct,
      });
      setSettings(updated);
      loadFleetScanStatus();
      setToast(
        enabled
          ? `Proactive Fleet Scan enabled: Agent will run the full test suite every ${updated.fleet_scan_interval_minutes} min (${updated.fleet_scan_window_start}–${updated.fleet_scan_window_end} Cairo time) and start the flow for failing sites.`
          : "Proactive Fleet Scan stopped. Scheduled 3-hour branch scans are disabled.",
      );
    } catch {
      setToast("Failed to update Proactive Fleet Scan setting.");
    }
  };

  const handleRunFleetScanNow = async (dryRun: boolean) => {
    setFleetScanRunState({ kind: "running" });
    try {
      const result = await settingsApi.runFleetScanNow({ dry_run: dryRun });
      setFleetScanRunState({ kind: "done", result });
      loadFleetScanStatus();
      setToast(result.summary);
    } catch (err) {
      setFleetScanRunState({
        kind: "request_failed",
        message: err instanceof Error ? err.message : "Fleet scan failed",
      });
    }
  };

  // Both tests use the values currently in the form, so they can be checked before saving.
  const handleTestSmtp = async () => {
    setSmtpTest({ kind: "running" });
    try {
      const result = await settingsApi.testSmtp({
        smtp_host: settings.smtp_host,
        smtp_port: settings.smtp_port,
        smtp_security: settings.smtp_security,
        smtp_username: settings.smtp_username || undefined,
        smtp_password: smtpPasswordInput.trim() || undefined,
        mailbox_account: settings.mailbox_account || undefined,
      });
      setSmtpTest({ kind: "done", result });
    } catch (err) {
      setSmtpTest({
        kind: "request_failed",
        message: err instanceof Error ? err.message : "Request failed",
      });
    }
  };

  const handleSendTestEmail = async () => {
    setRoundTripTest({ kind: "running" });
    try {
      const result = await settingsApi.sendTestEmail({
        recipient: settings.test_redirect_email || settings.mailbox_account,
        branch_code: "1084",
        smtp_host: settings.smtp_host,
        smtp_port: settings.smtp_port,
        smtp_security: settings.smtp_security,
        smtp_username: settings.smtp_username || undefined,
        smtp_password: smtpPasswordInput.trim() || undefined,
        mailbox_account: settings.mailbox_account || undefined,
      });
      setRoundTripTest({ kind: "done", result });
    } catch (err) {
      setRoundTripTest({
        kind: "request_failed",
        message: err instanceof Error ? err.message : "Request failed",
      });
    }
  };

  const handleTestVllm = async () => {
    setVllmTest({ kind: "running" });
    try {
      const result = await settingsApi.testVllm({
        vllm_endpoint: settings.vllm_endpoint,
      });
      setVllmTest({ kind: "done", result });
    } catch (err) {
      setVllmTest({
        kind: "request_failed",
        message: err instanceof Error ? err.message : "Request failed",
      });
    }
  };

  const handleSmtpSecurityChange = (security: SmtpSecurity) => {
    setSettings((s) => ({
      ...s,
      smtp_security: security,
      // Follow the standard port for the mode unless a custom port was entered
      smtp_port: Object.values(SMTP_DEFAULT_PORTS).includes(s.smtp_port)
        ? SMTP_DEFAULT_PORTS[security]
        : s.smtp_port,
    }));
    setSmtpTest({ kind: "idle" });
  };

  const handleAddFallback = () => {
    const email = newFallbackEmail.trim();
    if (!email) return;
    const ini = email.slice(0, 2).toUpperCase();
    setSettings((prev) => ({
      ...prev,
      fallback_contacts: [
        ...prev.fallback_contacts,
        { ini, email, role: "Fallback engineer" },
      ],
    }));
    setNewFallbackEmail("");
  };

  const handleRemoveFallback = (email: string) => {
    setSettings((prev) => ({
      ...prev,
      fallback_contacts: prev.fallback_contacts.filter(
        (c) => c.email !== email,
      ),
    }));
  };

  const killed = settings.global_ai_kill_switch;

  return (
    <AppShell
      active="AI & SLA Settings"
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
          <h1>AI Agent, Mailbox &amp; SLA Settings</h1>
          <p>{env} · changes are logged to the audit trail</p>
        </div>
        <Button variant="primary" onClick={handleSaveAll}>
          Save all changes
        </Button>
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

      <section
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: 16,
          alignItems: "center",
          padding: 18,
          borderRadius: 14,
          border: `1.5px solid ${
            killed ? "var(--critical)" : "var(--border)"
          }`,
          background: killed ? "var(--critical-bg)" : "var(--surface-000)",
        }}
      >
        <div style={{ flex: "999 1 420px" }}>
          <h2 style={{ margin: 0, fontSize: 18, lineHeight: "26px" }}>
            Global AI master kill-switch
          </h2>
          <p style={{ margin: "4px 0 0", fontSize: 13, lineHeight: "20px" }}>
            {killed
              ? "AI automation is PAUSED across the entire console. Emails are still logged, but no outbound emails or automated actions will run."
              : "Stops all autonomous outbound emails, SLA chasers, and ticket transitions immediately across all 1,150 branches."}
          </p>
        </div>
        <button
          type="button"
          className={
            killed ? "kz-btn kz-btn-primary" : "kz-btn kz-btn-danger"
          }
          aria-pressed={killed}
          onClick={handleToggleKillSwitch}
        >
          {killed
            ? "Resume global AI automation"
            : "Pause all AI automation"}
        </button>
      </section>

      <section
        className="kz-card"
        style={{
          border: `1.5px solid ${
            settings.require_admin_approval_before_action
              ? "var(--warning)"
              : "var(--brand-500)"
          }`,
        }}
      >
        <div className="kz-card-hd">
          <div>
            <h3>Admin Action Email Notifications &amp; Execution Mode</h3>
            <p>
              Email the Admin on every action the AI agent performs, and choose
              whether the agent proceeds autonomously or asks for Admin approval
              before acting.
            </p>
          </div>
          <Badge
            tone={
              settings.require_admin_approval_before_action ? "warning" : "good"
            }
          >
            {settings.require_admin_approval_before_action
              ? "Ask Admin Before Acting"
              : "Proceed Without Asking"}
          </Badge>
        </div>

        <div
          className="kz-card-bd"
          style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}
        >
          <div style={{ gridColumn: "1 / -1" }}>
            <div
              style={{
                fontWeight: 600,
                fontSize: 13,
                marginBottom: 6,
                color: "var(--ink)",
              }}
            >
              Agent Execution Mode
            </div>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
                gap: 10,
              }}
            >
              <button
                type="button"
                onClick={() => handleSetExecutionMode(false)}
                style={{
                  textAlign: "left",
                  padding: "12px 14px",
                  borderRadius: 10,
                  cursor: "pointer",
                  border: `1.5px solid ${
                    !settings.require_admin_approval_before_action
                      ? "var(--brand-600)"
                      : "var(--border-strong)"
                  }`,
                  background: !settings.require_admin_approval_before_action
                    ? "var(--brand-50)"
                    : "var(--surface-000)",
                  color: "var(--ink)",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    fontWeight: 700,
                    fontSize: 13.5,
                  }}
                >
                  <span>Proceed Without Asking (Autonomous)</span>
                  {!settings.require_admin_approval_before_action ? (
                    <Badge tone="good">Active</Badge>
                  ) : null}
                </div>
                <p
                  style={{
                    margin: "6px 0 0",
                    fontSize: 12,
                    lineHeight: "18px",
                    color: "var(--ink-muted)",
                  }}
                >
                  Agent runs triage, vision check, and ICMP diagnostics,
                  executes outbound Branch/ISP emails &amp; ticket transitions
                  immediately, and emails an action report to the Admin.
                </p>
              </button>

              <button
                type="button"
                onClick={() => handleSetExecutionMode(true)}
                style={{
                  textAlign: "left",
                  padding: "12px 14px",
                  borderRadius: 10,
                  cursor: "pointer",
                  border: `1.5px solid ${
                    settings.require_admin_approval_before_action
                      ? "var(--warning)"
                      : "var(--border-strong)"
                  }`,
                  background: settings.require_admin_approval_before_action
                    ? "var(--warning-bg)"
                    : "var(--surface-000)",
                  color: "var(--ink)",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    fontWeight: 700,
                    fontSize: 13.5,
                  }}
                >
                  <span>Ask Admin Before Acting (Approval Mode)</span>
                  {settings.require_admin_approval_before_action ? (
                    <Badge tone="warning">Active</Badge>
                  ) : null}
                </div>
                <p
                  style={{
                    margin: "6px 0 0",
                    fontSize: 12,
                    lineHeight: "18px",
                    color: "var(--ink-muted)",
                  }}
                >
                  Agent runs read-only triage, vision &amp; ICMP diagnostics
                  first, then pauses in the Human Review Queue and emails the
                  Admin with full context &amp; draft emails for Web Console
                  approval.
                </p>
              </button>
            </div>
          </div>

          <label style={labelStyle}>
            <span>Admin notification email</span>
            <input
              type="email"
              className="kz-mono"
              value={settings.admin_notification_email}
              placeholder="admin@kazyon.com"
              onChange={(e) =>
                setSettings((s) => ({
                  ...s,
                  admin_notification_email: e.target.value,
                }))
              }
              style={fieldStyle}
            />
          </label>

          <label
            style={{
              display: "flex",
              alignItems: "center",
              gap: 10,
              fontWeight: 600,
              fontSize: 13,
              paddingTop: 18,
            }}
          >
            <input
              type="checkbox"
              checked={settings.notify_admin_on_every_action}
              onChange={(e) =>
                handleToggleNotifyEveryAction(e.target.checked)
              }
            />
            <span>
              Send email to Admin on every agent action (Autonomous &amp;
              Approval modes)
            </span>
          </label>
        </div>
      </section>

      <section
        className="kz-card"
        style={{
          border: `1.5px solid ${
            settings.fleet_scan_enabled && !killed
              ? "var(--good)"
              : "var(--border)"
          }`,
        }}
      >
        <div className="kz-card-hd">
          <div>
            <h3>Proactive 3-Hour Full Fleet Diagnostic Scan</h3>
            <p>
              Automatically run the full Dual-Ping + 4G Hub Traceroute test
              suite across all active branches every 3 hours (180 min) and start
              the autonomous ticket flow for sites that fail the test.
            </p>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <Badge
              tone={
                settings.fleet_scan_enabled && !killed ? "good" : "neutral"
              }
            >
              {settings.fleet_scan_enabled && !killed
                ? `Active · Every ${settings.fleet_scan_interval_minutes}m (${settings.fleet_scan_window_start}–${settings.fleet_scan_window_end})`
                : "Stopped"}
            </Badge>
            <button
              type="button"
              className={
                settings.fleet_scan_enabled
                  ? "kz-btn kz-btn-danger kz-btn-sm"
                  : "kz-btn kz-btn-primary kz-btn-sm"
              }
              aria-pressed={settings.fleet_scan_enabled}
              onClick={() => handleToggleFleetScan(!settings.fleet_scan_enabled)}
            >
              {settings.fleet_scan_enabled
                ? "Stop Proactive Fleet Scan"
                : "Enable 3h Proactive Scan"}
            </button>
          </div>
        </div>

        <div
          className="kz-card-bd"
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
            gap: 14,
            fontSize: 13,
          }}
        >
          <label
            style={{
              gridColumn: "1 / -1",
              display: "flex",
              alignItems: "center",
              gap: 10,
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            <input
              type="checkbox"
              {...({ switch: "" } as React.InputHTMLAttributes<HTMLInputElement>)}
              checked={settings.fleet_scan_enabled}
              onChange={(e) => handleToggleFleetScan(e.target.checked)}
              style={{
                accentColor: "var(--brand-600)",
                width: 16,
                height: 16,
                margin: 0,
                cursor: "pointer",
              }}
            />
            <span>
              Run scheduled Full Fleet Test Suite and auto-open incident tickets
              for confirmed failing branches
            </span>
          </label>

          <label style={labelStyle}>
            <span>Scan interval (minutes · 180 = 3 hours)</span>
            <input
              type="number"
              min={15}
              max={1440}
              value={settings.fleet_scan_interval_minutes}
              onChange={(e) =>
                setSettings((s) => ({
                  ...s,
                  fleet_scan_interval_minutes: Math.max(
                    15,
                    Number(e.target.value) || 180,
                  ),
                }))
              }
              style={fieldStyle}
            />
          </label>

          <label style={labelStyle}>
            <span>Store window start (Africa/Cairo)</span>
            <input
              type="text"
              className="kz-mono"
              placeholder="08:00"
              value={settings.fleet_scan_window_start}
              onChange={(e) =>
                setSettings((s) => ({
                  ...s,
                  fleet_scan_window_start: e.target.value,
                }))
              }
              style={fieldStyle}
            />
          </label>

          <label style={labelStyle}>
            <span>Store window end (Africa/Cairo)</span>
            <input
              type="text"
              className="kz-mono"
              placeholder="23:00"
              value={settings.fleet_scan_window_end}
              onChange={(e) =>
                setSettings((s) => ({
                  ...s,
                  fleet_scan_window_end: e.target.value,
                }))
              }
              style={fieldStyle}
            />
          </label>

          <label style={labelStyle}>
            <span>Mass-outage safety threshold (% of fleet)</span>
            <input
              type="number"
              min={1}
              max={100}
              value={settings.fleet_scan_mass_outage_pct}
              onChange={(e) =>
                setSettings((s) => ({
                  ...s,
                  fleet_scan_mass_outage_pct: Math.max(
                    1,
                    Math.min(100, Number(e.target.value) || 5),
                  ),
                }))
              }
              style={fieldStyle}
            />
          </label>

          <div
            style={{
              gridColumn: "1 / -1",
              display: "flex",
              flexWrap: "wrap",
              alignItems: "center",
              justifyContent: "space-between",
              gap: 10,
              paddingTop: 4,
            }}
          >
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
              <button
                type="button"
                className="kz-btn kz-btn-secondary kz-btn-sm"
                disabled={fleetScanRunState.kind === "running"}
                onClick={() => handleRunFleetScanNow(false)}
              >
                {fleetScanRunState.kind === "running"
                  ? "Running fleet scan…"
                  : "Run full scan & start flows now"}
              </button>
              <button
                type="button"
                className="kz-btn kz-btn-secondary kz-btn-sm"
                disabled={fleetScanRunState.kind === "running"}
                onClick={() => handleRunFleetScanNow(true)}
              >
                Dry run (preview without opening tickets)
              </button>
              <button
                type="button"
                className="kz-btn kz-btn-ghost kz-btn-sm"
                onClick={loadFleetScanStatus}
              >
                Refresh history
              </button>
            </div>
            <span style={{ fontSize: 12, color: "var(--ink-muted)" }}>
              Two-strike re-test confirmation · Skips branches with open tickets ·
              Aborts above {settings.fleet_scan_mass_outage_pct}% fleet outage
            </span>
          </div>

          {fleetScanRunState.kind === "request_failed" && (
            <p style={resultTextStyle} role="alert">
              Fleet scan failed: {fleetScanRunState.message}
            </p>
          )}
          {fleetScanRunState.kind === "done" && (
            <p style={resultTextStyle} className="kz-mono">
              {fleetScanRunState.result.summary}
            </p>
          )}

          {fleetScanStatus && fleetScanStatus.recent_runs.length > 0 && (
            <div
              style={{
                gridColumn: "1 / -1",
                overflowX: "auto",
                border: "1px solid var(--border)",
                borderRadius: 10,
              }}
            >
              <table className="kz-table" style={{ fontSize: 12 }}>
                <thead>
                  <tr>
                    <th>Suite / Time</th>
                    <th>Trigger</th>
                    <th>Status</th>
                    <th>Scanned</th>
                    <th>Confirmed Down</th>
                    <th>Recovered (Re-test)</th>
                    <th>Dupes Skipped</th>
                    <th>Tickets Opened</th>
                  </tr>
                </thead>
                <tbody>
                  {fleetScanStatus.recent_runs.slice(0, 5).map((r) => (
                    <tr key={r.id}>
                      <td className="kz-mono">
                        {r.suite_id || `#${r.id}`} ·{" "}
                        {new Date(r.started_at).toLocaleTimeString(undefined, {
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </td>
                      <td className="kz-mono">{r.triggered_by}</td>
                      <td>
                        <Badge
                          tone={
                            r.status === "COMPLETED"
                              ? "good"
                              : r.status === "MASS_OUTAGE_GUARD"
                                ? "critical"
                                : "info"
                          }
                        >
                          {r.status}
                        </Badge>
                      </td>
                      <td className="kz-num">{r.total_branches}</td>
                      <td className="kz-num">{r.confirmed_down}</td>
                      <td className="kz-num">{r.recovered_on_retest}</td>
                      <td className="kz-num">{r.duplicates_skipped}</td>
                      <td className="kz-mono">
                        {r.created_ticket_numbers.length > 0
                          ? r.created_ticket_numbers.slice(0, 6).join(", ") +
                            (r.created_ticket_numbers.length > 6
                              ? ` +${r.created_ticket_numbers.length - 6}`
                              : "")
                          : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </section>

      <div
        style={{
          display: "grid",
          gridTemplateColumns:
            "repeat(auto-fit, minmax(min(420px, 100%), 1fr))",
          gap: 16,
        }}
      >
        <section className="kz-card">
          <div className="kz-card-hd">
            <div>
              <h2>Outbound email (SMTP)</h2>
              <p>Escalations, chasers, and branch replies via Kazyon SMTP</p>
            </div>
            {smtpTest.kind === "idle" && (
              <Badge
                tone={settings.smtp_credentials_configured ? "info" : "neutral"}
              >
                {settings.smtp_credentials_configured
                  ? "Credentials saved"
                  : "Not tested"}
              </Badge>
            )}
            {smtpTest.kind === "running" && <Badge tone="neutral">Testing…</Badge>}
            {smtpTest.kind === "request_failed" && (
              <Badge tone="critical">Test failed</Badge>
            )}
            {smtpTest.kind === "done" && (
              <Badge tone={smtpTest.result.ok ? "good" : "critical"}>
                {smtpTest.result.ok
                  ? `SMTP ✓ · ${smtpTest.result.latency_ms} ms`
                  : `SMTP ✗ · ${SMTP_STAGE_LABELS[smtpTest.result.stage]}`}
              </Badge>
            )}
          </div>
          <div
            className="kz-card-bd"
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
              gap: 12,
              fontSize: 13,
            }}
          >
            <label
              style={{
                gridColumn: "1 / -1",
                display: "flex",
                alignItems: "center",
                gap: 8,
                fontWeight: 600,
              }}
            >
              <input
                type="checkbox"
                checked={settings.smtp_enabled}
                onChange={(e) =>
                  setSettings((s) => ({ ...s, smtp_enabled: e.target.checked }))
                }
              />
              Send real email
              {!settings.smtp_enabled && (
                <span style={{ fontWeight: 500, color: "var(--ink-muted)" }}>
                  — off: emails are recorded on tickets but not sent
                </span>
              )}
            </label>
            <label style={{ ...labelStyle, gridColumn: "1 / -1" }}>
              Sender address (From)
              <input
                value={settings.mailbox_account}
                placeholder="noc@kazyon.com"
                onChange={(e) =>
                  setSettings((s) => ({
                    ...s,
                    mailbox_account: e.target.value,
                  }))
                }
                className="kz-mono"
                style={fieldStyle}
              />
            </label>
            <label style={labelStyle}>
              SMTP host
              <input
                value={settings.smtp_host}
                placeholder="mail.kazyon.com"
                onChange={(e) => {
                  setSettings((s) => ({ ...s, smtp_host: e.target.value }));
                  setSmtpTest({ kind: "idle" });
                }}
                className="kz-mono"
                style={fieldStyle}
              />
            </label>
            <label style={labelStyle}>
              SMTP port
              <input
                type="number"
                value={settings.smtp_port}
                onChange={(e) => {
                  setSettings((s) => ({
                    ...s,
                    smtp_port: Number(e.target.value) || 587,
                  }));
                  setSmtpTest({ kind: "idle" });
                }}
                style={fieldStyle}
              />
            </label>
            <label style={labelStyle}>
              Security
              <select
                value={settings.smtp_security}
                onChange={(e) =>
                  handleSmtpSecurityChange(e.target.value as SmtpSecurity)
                }
                style={fieldStyle}
              >
                <option value="starttls">STARTTLS (587)</option>
                <option value="ssl">SSL/TLS (465)</option>
                <option value="none">None — internal relay (25)</option>
              </select>
            </label>
            <label style={labelStyle}>
              SMTP Username
              <input
                value={settings.smtp_username}
                placeholder="noc@kazyon.com"
                onChange={(e) =>
                  setSettings((s) => ({ ...s, smtp_username: e.target.value }))
                }
                className="kz-mono"
                style={fieldStyle}
              />
            </label>
            <label style={{ ...labelStyle, gridColumn: "1 / -1" }}>
              SMTP Password
              <input
                type="password"
                value={smtpPasswordInput}
                placeholder={
                  settings.smtp_credentials_configured
                    ? "•••••••••••••••• (saved encrypted — enter new to replace)"
                    : "Enter service account password"
                }
                onChange={(e) => setSmtpPasswordInput(e.target.value)}
                className="kz-mono"
                style={fieldStyle}
              />
            </label>
            <label style={{ ...labelStyle, gridColumn: "1 / -1" }}>
              Safe Test Redirect Email (Optional — protects real ISPs during testing)
              <input
                value={settings.test_redirect_email}
                placeholder="Leave empty in production to email real Branches & ISPs"
                onChange={(e) =>
                  setSettings((s) => ({
                    ...s,
                    test_redirect_email: e.target.value,
                  }))
                }
                className="kz-mono"
                style={fieldStyle}
              />
              <span
                style={{
                  fontSize: 11,
                  fontWeight: 500,
                  color: "var(--ink-muted)",
                }}
              >
                When set, all outbound Branch, ISP (NOOR/ORANGE/WE), and Human
                Escalation emails are redirected to this address with a role-play
                banner.
              </span>
            </label>
            <div
              style={{
                gridColumn: "1 / -1",
                display: "flex",
                flexWrap: "wrap",
                alignItems: "center",
                gap: 10,
              }}
            >
              <button
                type="button"
                className="kz-btn kz-btn-secondary kz-btn-sm"
                onClick={handleTestSmtp}
                disabled={smtpTest.kind === "running"}
              >
                {smtpTest.kind === "running" ? "Testing…" : "Test SMTP connection"}
              </button>
              <button
                type="button"
                className="kz-btn kz-btn-secondary kz-btn-sm"
                onClick={handleSendTestEmail}
                disabled={roundTripTest.kind === "running"}
              >
                {roundTripTest.kind === "running"
                  ? "Sending…"
                  : "Send live test email"}
              </button>
            </div>
            {smtpTest.kind === "request_failed" && (
              <p style={resultTextStyle} role="alert">
                Could not run the test: {smtpTest.message}
              </p>
            )}
            {smtpTest.kind === "done" && (
              <p
                style={resultTextStyle}
                className="kz-mono"
                role={smtpTest.result.ok ? undefined : "alert"}
              >
                {smtpTest.result.host}:{smtpTest.result.port} ·{" "}
                {smtpTest.result.security} ·{" "}
                {smtpTest.result.ok
                  ? smtpTest.result.authenticated
                    ? "logged in"
                    : "no login"
                  : smtpTest.result.error}
                {smtpTest.result.ok && smtpTest.result.server_banner
                  ? ` · ${smtpTest.result.server_banner}`
                  : ""}
              </p>
            )}
            {roundTripTest.kind === "done" && (
              <p
                style={resultTextStyle}
                className="kz-mono"
                role={roundTripTest.result.ok ? undefined : "alert"}
              >
                {roundTripTest.result.ok
                  ? `Sent test email to ${roundTripTest.result.recipient} in ${roundTripTest.result.latency_ms} ms (${roundTripTest.result.message_id}).`
                  : `Send failed: ${roundTripTest.result.error}`}
              </p>
            )}
          </div>
        </section>

        <section className="kz-card">
          <div className="kz-card-hd">
            <div>
              <h2>Inbound email (SMTP listener &amp; dropbox poller)</h2>
              <p>Your mail server forwards branch and ISP mail here</p>
            </div>
            {listener === null && <Badge tone="neutral">Unknown</Badge>}
            {listener && !listener.enabled && <Badge tone="neutral">Off</Badge>}
            {listener?.enabled && listener.running && (
              <Badge tone="good">Listening · :{listener.port}</Badge>
            )}
            {listener?.enabled && !listener.running && (
              <Badge tone="critical">Not running</Badge>
            )}
          </div>
          <div
            className="kz-card-bd"
            style={{ display: "grid", gap: 10, fontSize: 13 }}
          >
            <label style={labelStyle}>
              Dropbox &amp; SLA poll interval (sec)
              <input
                type="number"
                value={settings.poll_interval_sec}
                onChange={(e) =>
                  setSettings((s) => ({
                    ...s,
                    poll_interval_sec: Number(e.target.value) || 30,
                  }))
                }
                style={fieldStyle}
              />
            </label>
            {listener === null && (
              <p style={{ margin: 0, color: "var(--ink-muted)" }}>
                Could not load the listener status.
              </p>
            )}
            {listener && !listener.enabled && (
              <p style={{ margin: 0, color: "var(--ink-muted)" }}>
                Off. To receive mail, set <code>SMTP_LISTENER_ENABLED=true</code>{" "}
                and <code>SMTP_LISTENER_ALLOWED_CLIENTS</code> (your mail
                server&apos;s IP) on the server, redeploy, then forward branch and
                ISP mail to this host on the published listener port.
              </p>
            )}
            {listener?.enabled && (
              <dl
                style={{
                  margin: 0,
                  display: "grid",
                  gridTemplateColumns: "max-content 1fr",
                  gap: "6px 14px",
                }}
              >
                <dt style={{ fontWeight: 600 }}>Accepts from</dt>
                <dd style={{ margin: 0 }} className="kz-mono">
                  {(listener.allowed_clients ?? []).join(", ") || "—"}
                </dd>
                <dt style={{ fontWeight: 600 }}>Messages</dt>
                <dd style={{ margin: 0 }}>
                  {listener.messages_accepted ?? 0} accepted ·{" "}
                  {listener.messages_rejected ?? 0} rejected ·{" "}
                  {listener.connections_refused ?? 0} connections refused
                </dd>
                <dt style={{ fontWeight: 600 }}>Last message</dt>
                <dd style={{ margin: 0 }}>
                  {listener.last_received_at
                    ? new Date(listener.last_received_at).toLocaleString(
                        undefined,
                        { timeZone: "Africa/Cairo" },
                      )
                    : "None yet"}
                </dd>
                {listener.last_error && (
                  <>
                    <dt style={{ fontWeight: 600 }}>Error</dt>
                    <dd
                      style={{ margin: 0, color: "var(--critical)" }}
                      role="alert"
                    >
                      {listener.last_error}
                    </dd>
                  </>
                )}
              </dl>
            )}
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <button
                type="button"
                className="kz-btn kz-btn-secondary kz-btn-sm"
                onClick={loadListenerStatus}
              >
                Refresh
              </button>
              <button
                type="button"
                className="kz-btn kz-btn-secondary kz-btn-sm"
                onClick={() => onNavigate("Mailbox & Triage")}
              >
                Open Mail Simulation Sandbox →
              </button>
            </div>
          </div>
        </section>

        <section className="kz-card">
          <div className="kz-card-hd">
            <div>
              <h2>vLLM model endpoint</h2>
              <p>Gemma 4 26B A4B NVFP4 · multimodal</p>
            </div>
            {vllmTest.kind === "idle" && <Badge tone="neutral">Not tested</Badge>}
            {vllmTest.kind === "running" && <Badge tone="neutral">Testing…</Badge>}
            {vllmTest.kind === "request_failed" && (
              <Badge tone="critical">Test failed</Badge>
            )}
            {vllmTest.kind === "done" && (
              <Badge tone={vllmTest.result.ok ? "good" : "critical"}>
                {vllmTest.result.ok
                  ? `Model ✓ · ${vllmTest.result.latency_ms} ms`
                  : "Model ✗"}
              </Badge>
            )}
          </div>
          <div
            className="kz-card-bd"
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
              gap: 12,
              fontSize: 13,
            }}
          >
            <label
              style={{
                gridColumn: "1 / -1",
                display: "flex",
                flexDirection: "column",
                gap: 4,
                fontWeight: 600,
              }}
            >
              Endpoint
              <input
                value={settings.vllm_endpoint}
                onChange={(e) => {
                  setSettings((s) => ({ ...s, vllm_endpoint: e.target.value }));
                  setVllmTest({ kind: "idle" });
                }}
                className="kz-mono"
                style={{
                  height: 38,
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
              Temperature
              <input
                type="number"
                step="0.1"
                value={settings.vllm_temperature}
                onChange={(e) =>
                  setSettings((s) => ({
                    ...s,
                    vllm_temperature: Number(e.target.value) || 0.1,
                  }))
                }
                style={{
                  height: 38,
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
              Max tokens
              <input
                type="number"
                value={settings.vllm_max_tokens}
                onChange={(e) =>
                  setSettings((s) => ({
                    ...s,
                    vllm_max_tokens: Number(e.target.value) || 2048,
                  }))
                }
                style={{
                  height: 38,
                  padding: "0 10px",
                  border: "1px solid var(--border-strong)",
                  borderRadius: 8,
                  font: "500 13px var(--font-sans)",
                }}
              />
            </label>
            <div
              style={{
                gridColumn: "1 / -1",
                display: "flex",
                alignItems: "center",
                gap: 10,
              }}
            >
              <button
                type="button"
                className="kz-btn kz-btn-secondary kz-btn-sm"
                onClick={handleTestVllm}
                disabled={vllmTest.kind === "running"}
              >
                {vllmTest.kind === "running" ? "Testing…" : "Test vLLM"}
              </button>
              <span style={{ fontSize: 12, color: "var(--ink-muted)" }}>
                Calls /v1/models and checks the model is served.
              </span>
            </div>
            {vllmTest.kind === "request_failed" && (
              <p style={resultTextStyle} role="alert">
                Could not run the test: {vllmTest.message}
              </p>
            )}
            {vllmTest.kind === "done" && (
              <p
                style={resultTextStyle}
                className="kz-mono"
                role={vllmTest.result.ok ? undefined : "alert"}
              >
                {vllmTest.result.endpoint} ·{" "}
                {vllmTest.result.ok
                  ? `${vllmTest.result.configured_model} is served`
                  : vllmTest.result.error}
              </p>
            )}
            <label
              style={{
                gridColumn: "1 / -1",
                display: "flex",
                flexDirection: "column",
                gap: 6,
                fontWeight: 600,
              }}
            >
              <span style={{ display: "flex", justifyContent: "space-between" }}>
                Confidence threshold for auto-action
                <span className="kz-num" style={{ color: "var(--brand-text)" }}>
                  {(settings.confidence_threshold / 100).toFixed(2)}
                </span>
              </span>
              <input
                type="range"
                min={50}
                max={99}
                value={settings.confidence_threshold}
                onChange={(e) =>
                  setSettings((s) => ({
                    ...s,
                    confidence_threshold: Number(e.target.value) || 80,
                  }))
                }
                style={{ accentColor: "var(--brand-600)" }}
              />
              <span className="kz-tcard-meta" style={{ fontWeight: 500 }}>
                Below this, the email goes to Human Review instead of being
                acted on.
              </span>
            </label>
          </div>
        </section>

        <section className="kz-card">
          <div className="kz-card-hd">
            <div>
              <h2>SLA timers &amp; loop guard</h2>
              <p>Defaults; ISPs can override in the directory</p>
            </div>
          </div>
          <div
            className="kz-card-bd"
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
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
              ISP Welcome SLA (min)
              <input
                type="number"
                value={settings.welcome_sla_minutes}
                onChange={(e) =>
                  setSettings((s) => ({
                    ...s,
                    welcome_sla_minutes: Number(e.target.value) || 120,
                  }))
                }
                style={{
                  height: 38,
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
              Follow-up interval (min)
              <input
                type="number"
                value={settings.followup_interval_minutes}
                onChange={(e) =>
                  setSettings((s) => ({
                    ...s,
                    followup_interval_minutes: Number(e.target.value) || 300,
                  }))
                }
                style={{
                  height: 38,
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
              Max chasers before human
              <input
                type="number"
                value={settings.max_chasers_before_human}
                onChange={(e) =>
                  setSettings((s) => ({
                    ...s,
                    max_chasers_before_human: Number(e.target.value) || 4,
                  }))
                }
                style={{
                  height: 38,
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
              MAX_OUTBOUND_EMAILS_PER_TICKET_HOUR
              <input
                type="number"
                value={settings.max_outbound_emails_per_ticket_hour}
                onChange={(e) =>
                  setSettings((s) => ({
                    ...s,
                    max_outbound_emails_per_ticket_hour:
                      Number(e.target.value) || 6,
                  }))
                }
                style={{
                  height: 38,
                  padding: "0 10px",
                  border: "1px solid var(--border-strong)",
                  borderRadius: 8,
                  font: "500 13px var(--font-sans)",
                }}
              />
            </label>
            <label
              style={{
                gridColumn: "1 / -1",
                display: "flex",
                gap: 8,
                alignItems: "center",
                fontWeight: 600,
              }}
            >
              <input
                type="checkbox"
                checked={settings.ignore_auto_submitted}
                onChange={(e) =>
                  setSettings((s) => ({
                    ...s,
                    ignore_auto_submitted: e.target.checked,
                  }))
                }
                style={{
                  accentColor: "var(--brand-600)",
                  width: 16,
                  height: 16,
                }}
              />
              Ignore auto-reply and Auto-Submitted emails
            </label>
          </div>
        </section>

        <section className="kz-card">
          <div className="kz-card-hd">
            <div>
              <h2>Human fallback escalation</h2>
              <p>Who receives the full incident report</p>
            </div>
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
            {settings.fallback_contacts.map((f) => (
              <div
                key={f.email}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                  padding: "10px 12px",
                  border: "1px solid var(--border)",
                  borderRadius: 10,
                }}
              >
                <span
                  className="kz-avatar"
                  style={{ width: 28, height: 28, fontSize: 11 }}
                >
                  {f.ini}
                </span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <b>{f.email}</b>
                  <div className="kz-tcard-meta">{f.role}</div>
                </div>
                <button
                  type="button"
                  className="kz-btn kz-btn-ghost kz-btn-sm"
                  onClick={() => handleRemoveFallback(f.email)}
                >
                  Remove
                </button>
              </div>
            ))}
            <div style={{ display: "flex", gap: 8 }}>
              <label style={{ flex: 1, display: "flex" }}>
                <span
                  style={{
                    position: "absolute",
                    width: 1,
                    height: 1,
                    overflow: "hidden",
                  }}
                >
                  New fallback email
                </span>
                <input
                  value={newFallbackEmail}
                  onChange={(e) => setNewFallbackEmail(e.target.value)}
                  placeholder="engineer@kazyon.com"
                  style={{
                    flex: 1,
                    height: 36,
                    padding: "0 10px",
                    border: "1px solid var(--border-strong)",
                    borderRadius: 8,
                    font: "500 13px var(--font-sans)",
                  }}
                />
              </label>
              <button
                type="button"
                className="kz-btn kz-btn-secondary kz-btn-sm"
                style={{ height: 36 }}
                onClick={handleAddFallback}
              >
                Add
              </button>
            </div>
          </div>
        </section>
      </div>
    </AppShell>
  );
}
