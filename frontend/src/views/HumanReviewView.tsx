import React, { useCallback, useEffect, useState } from "react";
import clsx from "clsx";
import { AppShell, Badge, IspBadge, IspName } from "../design-system";
import { EscalationItemDTO, escalationsApi, ticketsApi } from "../lib/api";
import { ConsoleViewProps } from "./types";

const ESCALATION_REASONS = [
  "ALL",
  "ADMIN_APPROVAL_REQUIRED",
  "QUOTA_CONSUMED",
  "MSAN_MIGRATION",
  "INTERNAL_BOX_CABLE",
  "UNRECOGNIZED_EMAIL",
  "MAX_RETRIES",
] as const;

export function HumanReviewView({
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
  const [items, setItems] = useState<EscalationItemDTO[]>([]);
  const [reason, setReason] = useState<string>("ALL");
  const [doneKeys, setDoneKeys] = useState<Record<string, boolean>>({});
  const [toast, setToast] = useState<string | null>(null);

  const loadItems = useCallback(() => {
    escalationsApi
      .list()
      .then((res) => setItems(res))
      .catch(() => {});
  }, []);

  useEffect(() => {
    loadItems();
  }, [loadItems]);

  const openItems = items.filter((a) => !doneKeys[a.key]);
  const visibleItems = openItems.filter(
    (a) => reason === "ALL" || a.reason === reason,
  );

  const handleApproveAction = async (item: EscalationItemDTO) => {
    if (!item.ticket_number) return;
    setDoneKeys((prev) => ({ ...prev, [item.key]: true }));
    try {
      await ticketsApi.approveAction(item.ticket_number);
      setToast(
        `Approved & executed ${
          item.pending_admin_action?.action_label || "action"
        } on ${item.ticket_number}.`,
      );
      loadItems();
    } catch {
      setToast(`Failed to approve action on ${item.ticket_number}.`);
    }
  };

  const handleRejectAction = async (item: EscalationItemDTO) => {
    if (!item.ticket_number) return;
    setDoneKeys((prev) => ({ ...prev, [item.key]: true }));
    try {
      await ticketsApi.rejectAction(item.ticket_number);
      setToast(
        `Rejected proposed action on ${item.ticket_number}; AI paused for manual control.`,
      );
      loadItems();
    } catch {
      setToast(`Failed to reject action on ${item.ticket_number}.`);
    }
  };

  const handleMarkDone = async (item: EscalationItemDTO, resumeAi = false) => {
    if (
      !resumeAi &&
      item.reason === "ADMIN_APPROVAL_REQUIRED" &&
      item.pending_admin_action &&
      item.ticket_number
    ) {
      await handleApproveAction(item);
      return;
    }
    setDoneKeys((prev) => ({ ...prev, [item.key]: true }));
    if (item.ticket_number) {
      try {
        await ticketsApi.update(item.ticket_number, {
          status: resumeAi ? "ESCALATED_TO_ISP" : "RESOLVED",
          ai_automation_enabled: resumeAi ? true : undefined,
        });
      } catch {
        // Ignore if sample fallback key
      }
    } else if (item.email_id) {
      try {
        const res = await escalationsApi.convertEmailToTicket(item.email_id);
        if (res.ticket_number) {
          onOpenTicket(res.ticket_number);
        }
      } catch {
        // Ignore if sample fallback key
      }
    }
  };

  return (
    <AppShell
      active="Human Review"
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
          <h1>Human Review &amp; Escalations</h1>
          <p>
            Items the agent could not handle alone. Each one was emailed to the
            on-duty engineer with the full incident report.
          </p>
        </div>
        <span className="kz-tcard-meta">
          On duty: <b style={{ color: "var(--ink)" }}>noc-oncall@kazyon.com</b>
        </span>
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

      <div className="kz-filters">
        {ESCALATION_REASONS.map((r) => {
          const count =
            r === "ALL"
              ? openItems.length
              : openItems.filter((a) => a.reason === r).length;
          return (
            <button
              key={r}
              type="button"
              className={clsx("kz-chip", reason === r && "kz-chip-on")}
              onClick={() => setReason(r)}
            >
              {r === "ALL" ? "All" : r} · {count}
            </button>
          );
        })}
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        {visibleItems.map((it) => (
          <article
            key={it.key}
            className="kz-card"
            style={{
              padding: 16,
              display: "flex",
              flexWrap: "wrap",
              gap: 16,
              alignItems: "flex-start",
            }}
          >
            <div
              style={{
                flex: "999 1 520px",
                minWidth: 0,
                display: "flex",
                flexDirection: "column",
                gap: 8,
              }}
            >
              <div
                style={{
                  display: "flex",
                  gap: 8,
                  alignItems: "center",
                  flexWrap: "wrap",
                }}
              >
                <Badge
                  tone={
                    it.reason === "ADMIN_APPROVAL_REQUIRED"
                      ? "warning"
                      : "critical"
                  }
                >
                  {it.reason}
                </Badge>
                {it.ticket_number ? (
                  <a
                    href={`#ticket-${it.ticket_number}`}
                    className="kz-tcard-id"
                    onClick={(e) => {
                      e.preventDefault();
                      if (it.ticket_number) onOpenTicket(it.ticket_number);
                    }}
                  >
                    {it.ticket_number}
                  </a>
                ) : null}
                {it.isp ? (
                  <IspBadge
                    isp={it.isp as IspName}
                    caseRef={it.case_ref || undefined}
                  />
                ) : null}
                <span className="kz-tcard-meta">{it.when}</span>
              </div>
              <h3 style={{ margin: 0, fontSize: 16, lineHeight: "22px" }}>
                {it.title}
              </h3>
              <blockquote
                style={{
                  margin: 0,
                  padding: "10px 12px",
                  background: "var(--surface-100)",
                  borderRadius: 10,
                  fontSize: 13,
                  lineHeight: "20px",
                  color: "var(--ink)",
                }}
              >
                “{it.quote}”
                <div className="kz-tcard-meta" style={{ marginTop: 4 }}>
                  — {it.from_addr}
                </div>
              </blockquote>
              <p style={{ margin: 0, fontSize: 13, lineHeight: "20px" }}>
                <b>Agent summary:</b> {it.summary}
              </p>
              {it.pending_admin_action ? (
                <div
                  style={{
                    padding: "10px 12px",
                    borderRadius: 10,
                    border: "1px solid var(--warning)",
                    background: "var(--warning-bg)",
                    fontSize: 12.5,
                    display: "flex",
                    flexDirection: "column",
                    gap: 6,
                  }}
                >
                  <div style={{ fontWeight: 700, color: "var(--ink)" }}>
                    Proposed Action:{" "}
                    <span className="kz-mono">
                      {it.pending_admin_action.action_label}
                    </span>
                    {it.pending_admin_action.target_status ? (
                      <span>
                        {" "}
                        → Target Status:{" "}
                        <span className="kz-mono">
                          {it.pending_admin_action.target_status}
                        </span>
                      </span>
                    ) : null}
                  </div>
                  {(it.pending_admin_action.proposed_emails || []).length >
                  0 ? (
                    <div
                      style={{
                        display: "flex",
                        flexDirection: "column",
                        gap: 4,
                      }}
                    >
                      <div style={{ fontWeight: 600 }}>
                        Draft Outbound Emails (
                        {it.pending_admin_action.proposed_emails?.length}):
                      </div>
                      {it.pending_admin_action.proposed_emails?.map(
                        (em, idx) => (
                          <div
                            key={idx}
                            style={{
                              padding: "6px 8px",
                              borderRadius: 6,
                              background: "var(--surface-000)",
                              border: "1px solid var(--border)",
                            }}
                          >
                            <div className="kz-mono" style={{ fontSize: 11.5 }}>
                              [{em.thread_type}] To:{" "}
                              {(em.recipients || []).join(", ")} · Subject:{" "}
                              {em.subject}
                            </div>
                          </div>
                        ),
                      )}
                    </div>
                  ) : null}
                </div>
              ) : null}
              <div className="kz-tcard-meta">
                Report emailed to {it.engineer_email} · AI automation paused on
                this item
              </div>
            </div>
            <div
              style={{
                flex: "1 1 200px",
                display: "flex",
                flexDirection: "column",
                gap: 8,
              }}
            >
              {it.reason === "ADMIN_APPROVAL_REQUIRED" &&
              it.pending_admin_action &&
              it.ticket_number ? (
                <>
                  <button
                    type="button"
                    className="kz-btn kz-btn-primary"
                    onClick={() => handleApproveAction(it)}
                  >
                    Approve &amp; Execute
                  </button>
                  <button
                    type="button"
                    className="kz-btn kz-btn-danger"
                    onClick={() => handleRejectAction(it)}
                  >
                    Reject Action
                  </button>
                  <button
                    type="button"
                    className="kz-btn kz-btn-secondary"
                    onClick={() => {
                      if (it.ticket_number) onOpenTicket(it.ticket_number);
                    }}
                  >
                    Inspect Ticket 360°
                  </button>
                </>
              ) : (
                <>
                  <button
                    type="button"
                    className="kz-btn kz-btn-primary"
                    onClick={() => handleMarkDone(it, false)}
                  >
                    {it.primary_action}
                  </button>
                  <button
                    type="button"
                    className="kz-btn kz-btn-secondary"
                    onClick={() => {
                      if (it.ticket_number) {
                        onOpenTicket(it.ticket_number);
                      } else {
                        onNavigate("Mailbox & Triage");
                      }
                    }}
                  >
                    Reply manually
                  </button>
                  <button
                    type="button"
                    className="kz-btn kz-btn-ghost"
                    onClick={() => handleMarkDone(it, true)}
                  >
                    Resume AI automation
                  </button>
                </>
              )}
            </div>
          </article>
        ))}

        {visibleItems.length === 0 ? (
          <div className="kz-card" style={{ padding: 40, textAlign: "center" }}>
            <h2 style={{ margin: "0 0 4px", fontSize: 18 }}>Queue clear</h2>
            <p className="kz-muted" style={{ margin: 0, fontSize: 13 }}>
              Nothing needs a person right now.
            </p>
          </div>
        ) : null}
      </div>
    </AppShell>
  );
}
