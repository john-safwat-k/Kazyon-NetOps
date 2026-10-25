import React, { useCallback, useEffect, useState } from "react";
import { AppShell, Badge, Button } from "../design-system";
import {
  BranchDTO,
  ReplicationReportItemDTO,
  branchesApi,
  replicationApi,
} from "../lib/api";
import { ConsoleViewProps } from "./types";

const DEFAULT_HTML_SNIPPET =
  "<tr><td>1450</td><td>Soliman Metwaly</td><td>Assyut</td><td>20/10 21:14</td><td>20/10/2026</td><td>Not Updated</td></tr>";

export function ReplicationMonitorView({
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
  const [reports, setReports] = useState<ReplicationReportItemDTO[]>([]);
  const [directoryBranches, setDirectoryBranches] = useState<BranchDTO[]>([]);
  const [pickedBranchCode, setPickedBranchCode] = useState<string>("");
  const [pickedStatus, setPickedStatus] = useState<"Not Updated" | "Updated">(
    "Not Updated",
  );
  const [selIdx, setSelIdx] = useState(0);
  const [onlyNu, setOnlyNu] = useState(false);

  // Modal state
  const [modalOpen, setModalOpen] = useState(false);
  const [htmlInput, setHtmlInput] = useState(DEFAULT_HTML_SNIPPET);
  const [subjectInput, setSubjectInput] = useState(
    "Replication Dashboard - 21/10/2026",
  );
  const [dryRun, setDryRun] = useState(true);
  const [parseSummary, setParseSummary] = useState<string | null>(null);

  const loadReports = useCallback(() => {
    replicationApi
      .listReports()
      .then((res) => setReports(res))
      .catch(() => {});
  }, []);

  const loadDirectoryBranches = useCallback(() => {
    branchesApi
      .list({ limit: 300, offset: 0 })
      .then((res) => {
        setDirectoryBranches(res.items);
        if (res.items.length > 0 && !pickedBranchCode) {
          setPickedBranchCode(res.items[0].branch_code);
        }
      })
      .catch(() => {});
  }, [pickedBranchCode]);

  useEffect(() => {
    loadReports();
    loadDirectoryBranches();
  }, [loadReports, loadDirectoryBranches]);

  const selected = reports[selIdx] || reports[0];
  const rows = selected
    ? onlyNu
      ? selected.rows.filter((r) => r.status !== "Updated")
      : selected.rows
    : [];

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setSubjectInput(file.name.replace(/\.(eml|html|htm)$/i, ""));
    file.text().then((txt) => setHtmlInput(txt));
  };

  const handleInsertBranchRow = () => {
    const b = directoryBranches.find(
      (item) => item.branch_code === pickedBranchCode,
    );
    if (!b) return;
    const cleanName = b.name.replace(new RegExp(`^${b.branch_code}[-_\\s]*`), "");
    const tr = `<tr><td>${b.branch_code}</td><td>${cleanName || b.name}</td><td>${b.region || "Cairo"}</td><td>21/10 08:30</td><td>21/10/2026</td><td>${pickedStatus}</td></tr>`;
    setHtmlInput((prev) => (prev.trim() ? `${prev.trim()}\n${tr}` : tr));
  };

  const handleGenerateSampleFromDirectory = () => {
    if (directoryBranches.length === 0) return;
    const sampleBranches = directoryBranches.slice(0, 5);
    const lines = sampleBranches.map((b, i) => {
      const cleanName = b.name.replace(
        new RegExp(`^${b.branch_code}[-_\\s]*`),
        "",
      );
      const st = i < 2 ? "Not Updated" : "Updated";
      return `<tr><td>${b.branch_code}</td><td>${cleanName || b.name}</td><td>${b.region || "Cairo"}</td><td>21/10 08:${10 + i * 5}</td><td>21/10/2026</td><td>${st}</td></tr>`;
    });
    setHtmlInput(lines.join("\n"));
  };

  const handleParse = async () => {
    try {
      const res = await replicationApi.parse({
        subject: subjectInput,
        html_content: htmlInput,
        dry_run: dryRun,
      });
      const totalParsed =
        res.total_rows_parsed ??
        (res as unknown as { total_rows?: number }).total_rows ??
        0;
      const ticketsCreated =
        res.tickets_created ??
        (res as unknown as { notified_count?: number }).notified_count ??
        0;
      const emailsSent =
        res.emails_sent ??
        (res as unknown as { notified_count?: number }).notified_count ??
        0;
      setParseSummary(
        `${res.dry_run ? "Dry run:" : "Live run:"} ${totalParsed} row(s) parsed · ${res.not_updated_count} Not Updated · ${
          res.dry_run
            ? "tickets would be created and Regional IT emailed."
            : `${ticketsCreated} ticket(s) created and ${emailsSent} email(s) sent.`
        }`,
      );
      if (!dryRun) {
        loadReports();
        setSelIdx(0);
      }
    } catch {
      setParseSummary("Could not parse replication report.");
    }
  };

  return (
    <AppShell
      active="Replication Monitor"
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
          <h1>Replication Dashboard Monitor</h1>
          <p>
            Every “Replication Dashboard - &lt;Date&gt;” email the agent
            ingested. Not Updated stores get a ticket and a Regional IT email.
          </p>
        </div>
        <Button
          variant="primary"
          onClick={() => {
            setParseSummary(null);
            loadDirectoryBranches();
            setModalOpen(true);
          }}
        >
          + Upload / paste report
        </Button>
      </div>

      {modalOpen ? (
        <div className="kz-modal-scrim">
          <div
            role="dialog"
            aria-modal="true"
            aria-label="Upload replication report"
            className="kz-card"
            style={{
              width: "100%",
              maxWidth: 680,
              boxShadow: "var(--shadow-raised)",
            }}
          >
            <div className="kz-card-hd">
              <div>
                <h2>Upload or paste a Replication Dashboard</h2>
                <p>For testing. Parsed exactly like the 09:00 email.</p>
              </div>
              <button
                type="button"
                className="kz-btn kz-btn-ghost kz-btn-sm"
                aria-label="Close"
                onClick={() => setModalOpen(false)}
              >
                ✕
              </button>
            </div>
            <div
              className="kz-card-bd"
              style={{ display: "flex", flexDirection: "column", gap: 14 }}
            >
              <label className="kz-field">
                Report subject
                <input
                  value={subjectInput}
                  onChange={(e) => setSubjectInput(e.target.value)}
                />
              </label>

              <label className="kz-field">
                Report email (.eml or .html)
                <input
                  type="file"
                  accept=".eml,.html,.htm"
                  onChange={handleFileChange}
                  style={{ paddingTop: 8 }}
                />
              </label>

              {directoryBranches.length > 0 ? (
                <div
                  style={{
                    padding: 12,
                    borderRadius: 10,
                    background: "var(--surface-100)",
                    display: "flex",
                    gap: 8,
                    flexWrap: "wrap",
                    alignItems: "center",
                    fontSize: 13,
                  }}
                >
                  <span style={{ fontWeight: 600 }}>
                    Insert branch from directory:
                  </span>
                  <select
                    value={pickedBranchCode}
                    onChange={(e) => setPickedBranchCode(e.target.value)}
                    style={{
                      flex: "1 1 200px",
                      height: 34,
                      padding: "0 8px",
                      border: "1px solid var(--border-strong)",
                      borderRadius: 8,
                      font: "500 13px var(--font-sans)",
                    }}
                  >
                    {directoryBranches.map((b) => (
                      <option key={b.id} value={b.branch_code}>
                        {b.name} · {b.region || "Cairo"} (
                        {b.regional_it_email || "CITSupport@kazyon.com"})
                      </option>
                    ))}
                  </select>
                  <select
                    value={pickedStatus}
                    onChange={(e) =>
                      setPickedStatus(
                        e.target.value as "Not Updated" | "Updated",
                      )
                    }
                    style={{
                      height: 34,
                      padding: "0 8px",
                      border: "1px solid var(--border-strong)",
                      borderRadius: 8,
                      font: "500 13px var(--font-sans)",
                    }}
                  >
                    <option value="Not Updated">Not Updated</option>
                    <option value="Updated">Updated</option>
                  </select>
                  <button
                    type="button"
                    className="kz-btn kz-btn-secondary kz-btn-sm"
                    onClick={handleInsertBranchRow}
                  >
                    + Add row
                  </button>
                  <button
                    type="button"
                    className="kz-btn kz-btn-ghost kz-btn-sm"
                    onClick={handleGenerateSampleFromDirectory}
                  >
                    Fill 5 directory branches
                  </button>
                </div>
              ) : null}

              <label className="kz-field">
                …or paste the HTML table
                <textarea
                  rows={5}
                  className="kz-mono"
                  value={htmlInput}
                  onChange={(e) => setHtmlInput(e.target.value)}
                />
              </label>
              {parseSummary ? (
                <div
                  style={{
                    padding: 12,
                    borderRadius: 10,
                    background: "var(--info-bg)",
                    color: "var(--info)",
                    fontSize: 13,
                  }}
                >
                  {parseSummary}
                </div>
              ) : null}
              <label
                style={{
                  display: "flex",
                  gap: 8,
                  alignItems: "center",
                  fontSize: 13,
                  fontWeight: 600,
                }}
              >
                <input
                  type="checkbox"
                  checked={dryRun}
                  onChange={(e) => setDryRun(e.target.checked)}
                  style={{
                    accentColor: "var(--brand-600)",
                    width: 16,
                    height: 16,
                  }}
                />
                Dry run only (no tickets, no emails)
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
              <Button variant="primary" onClick={handleParse}>
                Parse report
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
        <section
          className="kz-card"
          style={{ flex: "1 1 280px", maxWidth: 340, overflow: "hidden" }}
        >
          <div className="kz-card-hd" style={{ paddingBottom: 12 }}>
            <h2>Reports</h2>
            <span className="kz-tcard-meta">{reports.length} ingested</span>
          </div>
          {reports.length === 0 ? (
            <div className="kz-card-bd kz-muted" style={{ fontSize: 13 }}>
              No replication reports ingested yet. Click{" "}
              <b>+ Upload / paste report</b> to parse one.
            </div>
          ) : null}
          {reports.map((r, idx) => {
            const isOn = idx === selIdx;
            return (
              <button
                key={r.id}
                type="button"
                onClick={() => setSelIdx(idx)}
                style={{
                  all: "unset",
                  boxSizing: "border-box",
                  cursor: "pointer",
                  width: "100%",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  gap: 10,
                  padding: "12px 16px",
                  borderTop: "1px solid var(--border)",
                  background: isOn ? "var(--brand-100)" : "transparent",
                }}
              >
                <span
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    gap: 2,
                    textAlign: "left",
                  }}
                >
                  <b style={{ fontSize: 13 }}>{r.subject}</b>
                  <span className="kz-tcard-meta">
                    Received {r.received} · {r.total.toLocaleString("en-US")}{" "}
                    stores
                  </span>
                </span>
                <Badge tone={r.tone}>{r.nu} not updated</Badge>
              </button>
            );
          })}
        </section>

        {selected ? (
          <section
            className="kz-card"
            style={{ flex: "999 1 560px", minWidth: 0, overflow: "hidden" }}
          >
            <div
              className="kz-card-hd"
              style={{ paddingBottom: 12, flexWrap: "wrap" }}
            >
              <div>
                <h2>{selected.subject}</h2>
                <p>
                  {selected.total.toLocaleString("en-US")} stores parsed ·{" "}
                  {selected.nu} Not Updated · {selected.notified} Regional IT
                  emails sent · 0 duplicates skipped
                </p>
              </div>
              <label
                style={{
                  display: "flex",
                  gap: 8,
                  alignItems: "center",
                  fontSize: 13,
                  fontWeight: 600,
                }}
              >
                <input
                  type="checkbox"
                  checked={onlyNu}
                  onChange={(e) => setOnlyNu(e.target.checked)}
                  style={{
                    accentColor: "var(--brand-600)",
                    width: 16,
                    height: 16,
                  }}
                />
                Not Updated only
              </label>
            </div>
            <div className="kz-scroll-x">
              <table className="kz-table">
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Store name</th>
                    <th>Region</th>
                    <th>Last trans.</th>
                    <th>Buss. date</th>
                    <th>Status</th>
                    <th>Regional IT</th>
                    <th>Ticket</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((w) => (
                    <tr key={w.id}>
                      <td className="kz-mono">{w.id}</td>
                      <td style={{ fontWeight: 600 }} className="kz-nowrap">
                        {w.name}
                      </td>
                      <td>{w.region}</td>
                      <td className="kz-num kz-nowrap">{w.last}</td>
                      <td className="kz-num kz-nowrap">{w.biz}</td>
                      <td>
                        <Badge tone={w.tone}>{w.status}</Badge>
                      </td>
                      <td className="kz-tcard-meta kz-nowrap">{w.mail}</td>
                      <td>
                        {w.ticket ? (
                          <a
                            href={`#ticket-${w.ticket}`}
                            className="kz-tcard-id"
                            onClick={(e) => {
                              e.preventDefault();
                              onOpenTicket(w.ticket);
                            }}
                          >
                            {w.ticket}
                          </a>
                        ) : null}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        ) : null}
      </div>
    </AppShell>
  );
}
