import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import clsx from "clsx";
import { AppShell, Badge, Button, IspBadge, IspName } from "../design-system";
import {
  BranchDTO,
  IspDTO,
  SeedResultSummaryDTO,
  branchesApi,
  ispsApi,
} from "../lib/api";
import { ConsoleViewProps } from "./types";

const BASE_REGIONS = ["Behera", "Cairo", "New October", "Assyut", "Giza"];

const REGIONAL_IT_DEFAULTS: Record<string, string> = {
  Behera: "BITSupport@kazyon.com",
  Cairo: "CITSupport@kazyon.com",
  "New October": "newoctregion@kazyon.com",
  Assyut: "assiutregion@kazyon.com",
  Giza: "GITSupport@kazyon.com",
};

const ISP_EMAIL_DEFAULTS: Record<string, string> = {
  NOOR: "noc@noor.net",
  ORANGE: "ccc-eg@orange.com",
  WE: "psupport@te.eg",
};

const ISP_HUB_DEFAULTS: Record<string, string> = {
  NOOR: "",
  ORANGE: "10.247.8.1",
  WE: "172.16.70.33",
};

function deriveIpFromCode(code: string, hostOctet: number): string {
  const digits = code.replace(/\D/g, "").slice(0, 4);
  if (digits.length !== 4) return "";
  const ab = parseInt(digits.slice(0, 2), 10);
  const cd = parseInt(digits.slice(2, 4), 10);
  return `10.${ab}.${cd}.${hostOctet}`;
}

export function DirectoryView({
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
  const [tab, setTab] = useState<"branches" | "isps">("branches");
  const [branches, setBranches] = useState<BranchDTO[]>([]);
  const [totalBranches, setTotalBranches] = useState(1150);
  const [regionsCount, setRegionsCount] = useState<Record<string, number>>({});
  const [ispsCount, setIspsCount] = useState<Record<string, number>>({});
  const [search, setSearch] = useState("");
  const [region, setRegion] = useState("All");
  const [ispFilter, setIspFilter] = useState("ALL");
  const [pageSize, setPageSize] = useState(100);
  const [pageOffset, setPageOffset] = useState(0);
  const [isps, setIsps] = useState<IspDTO[]>([]);

  // Bulk CSV / Excel upload & seeder state
  const [seedOpen, setSeedOpen] = useState(false);
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [replaceExisting, setReplaceExisting] = useState(false);
  const [seedSummary, setSeedSummary] = useState<SeedResultSummaryDTO | null>(
    null,
  );
  const [isSeeding, setIsSeeding] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // Add/Edit branch modal state
  const [editMode, setEditMode] = useState<"add" | "edit" | null>(null);
  const [editBranchId, setEditBranchId] = useState<number | null>(null);
  const [formCode, setFormCode] = useState("");
  const [formName, setFormName] = useState("");
  const [formRegion, setFormRegion] = useState("Cairo");
  const [formIp1, setFormIp1] = useState("");
  const [formIp2, setFormIp2] = useState("");
  const [formRit, setFormRit] = useState("CITSupport@kazyon.com");
  const [formIsp, setFormIsp] = useState("NOOR");
  const [formMail, setFormMail] = useState("noc@noor.net");
  const [formHub, setFormHub] = useState("");
  const [formLl, setFormLl] = useState("");
  const [formG3, setFormG3] = useState("");
  const [formActive, setFormActive] = useState(true);
  const [modalError, setModalError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const loadBranches = useCallback(() => {
    branchesApi
      .list({
        search: search.trim() || undefined,
        region: region !== "All" ? region : undefined,
        isp_name: ispFilter !== "ALL" ? ispFilter : undefined,
        limit: pageSize,
        offset: pageOffset,
      })
      .then((res) => {
        setBranches(res.items);
        setTotalBranches(res.total);
        setRegionsCount(res.regions_count || {});
        setIspsCount(res.isps_count || {});
      })
      .catch(() => {});
  }, [search, region, ispFilter, pageSize, pageOffset]);

  const loadIsps = useCallback(() => {
    ispsApi
      .list()
      .then((res) => setIsps(res))
      .catch(() => {});
  }, []);

  useEffect(() => {
    loadBranches();
    loadIsps();
  }, [loadBranches, loadIsps]);

  const allRegions = useMemo(() => {
    const dynamic = Object.keys(regionsCount).filter(
      (r) => r && !BASE_REGIONS.includes(r),
    );
    return ["All", ...BASE_REGIONS, ...dynamic.sort()];
  }, [regionsCount]);

  const totalDirectoryCount = useMemo(() => {
    const sum = Object.values(ispsCount).reduce((acc, v) => acc + v, 0);
    return sum > 0 ? sum : totalBranches;
  }, [ispsCount, totalBranches]);

  const runDryRunPreview = useCallback(
    async (file: File | null, replace: boolean) => {
      setIsSeeding(true);
      try {
        const res = await branchesApi.seedExcel({
          dry_run: true,
          replace_existing: replace,
          file,
        });
        setSeedSummary(res);
      } catch (err) {
        setToast(
          err instanceof Error
            ? err.message
            : "Could not preview the selected sheet.",
        );
      } finally {
        setIsSeeding(false);
      }
    },
    [],
  );

  const handleToggleSeedPreview = async () => {
    if (seedOpen) {
      setSeedOpen(false);
      return;
    }
    setSeedOpen(true);
    await runDryRunPreview(uploadedFile, replaceExisting);
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0] || null;
    if (!file) return;
    setUploadedFile(file);
    setSeedOpen(true);
    await runDryRunPreview(file, replaceExisting);
  };

  const handleDropFile = async (e: React.DragEvent<HTMLElement>) => {
    e.preventDefault();
    const file = e.dataTransfer.files?.[0] || null;
    if (!file) return;
    setUploadedFile(file);
    setSeedOpen(true);
    await runDryRunPreview(file, replaceExisting);
  };

  const handleToggleReplaceExisting = async (nextReplace: boolean) => {
    setReplaceExisting(nextReplace);
    if (seedOpen) {
      await runDryRunPreview(uploadedFile, nextReplace);
    }
  };

  const handleClearUploadedFile = async () => {
    setUploadedFile(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
    await runDryRunPreview(null, replaceExisting);
  };

  const handleApplySeed = async () => {
    setIsSeeding(true);
    try {
      const res = await branchesApi.seedExcel({
        dry_run: false,
        replace_existing: replaceExisting,
        file: uploadedFile,
      });
      setSeedSummary(res);
      setSeedOpen(false);
      setPageOffset(0);
      setToast(
        `Applied ${res.total_rows_parsed.toLocaleString("en-US")} rows from ${res.source_filename} (${res.created_count} new, ${res.updated_count} updated, ${res.unchanged_count} unchanged${
          res.deleted_count ? `, ${res.deleted_count} removed` : ""
        }).`,
      );
      loadBranches();
      loadIsps();
    } catch (err) {
      setToast(
        err instanceof Error ? err.message : "Failed to apply bulk branch sheet.",
      );
    } finally {
      setIsSeeding(false);
    }
  };

  const openAddModal = () => {
    setEditMode("add");
    setEditBranchId(null);
    setModalError(null);
    setFormCode("");
    setFormName("");
    setFormRegion("Cairo");
    setFormIp1("");
    setFormIp2("");
    setFormRit("CITSupport@kazyon.com");
    setFormIsp("NOOR");
    setFormMail("noc@noor.net");
    setFormHub("");
    setFormLl("");
    setFormG3("");
    setFormActive(true);
  };

  const openEditModal = (b: BranchDTO) => {
    setEditMode("edit");
    setEditBranchId(b.id);
    setModalError(null);
    setFormCode(b.branch_code);
    setFormName(b.name);
    setFormRegion(b.region || "Cairo");
    setFormIp1(b.ip_1);
    setFormIp2(b.ip_2);
    setFormRit(b.regional_it_email || "");
    setFormIsp(b.isp_name);
    setFormMail(b.isp_contact_mail);
    setFormHub(b.four_g_hub_ip || "");
    setFormLl(b.ll_circuit_id || "");
    setFormG3(b.backup_circuit_id || "");
    setFormActive(b.is_active);
  };

  const handleCodeChange = (val: string) => {
    const clean = val.trim().slice(0, 16);
    setFormCode(clean);
    const digits = clean.replace(/\D/g, "");
    if (digits.length >= 4) {
      setFormIp1(deriveIpFromCode(digits, 1));
      setFormIp2(deriveIpFromCode(digits, 2));
    }
  };

  const handleRegionChangeInForm = (nextRegion: string) => {
    setFormRegion(nextRegion);
    if (REGIONAL_IT_DEFAULTS[nextRegion]) {
      setFormRit(REGIONAL_IT_DEFAULTS[nextRegion]);
    }
  };

  const handleIspChangeInForm = (nextIsp: string) => {
    setFormIsp(nextIsp);
    if (ISP_EMAIL_DEFAULTS[nextIsp]) {
      setFormMail(ISP_EMAIL_DEFAULTS[nextIsp]);
    }
    if (ISP_HUB_DEFAULTS[nextIsp] !== undefined) {
      setFormHub(ISP_HUB_DEFAULTS[nextIsp]);
    }
  };

  const handleSaveBranch = async () => {
    if (!formCode.trim()) {
      setModalError("SAP code is required.");
      return;
    }
    setModalError(null);
    try {
      if (editMode === "add") {
        await branchesApi.create({
          branch_code: formCode.trim(),
          name: formName.trim() || `${formCode.trim()}-Store`,
          region: formRegion.trim() || "Cairo",
          ip_1: formIp1.trim() || undefined,
          ip_2: formIp2.trim() || undefined,
          regional_it_email: formRit.trim() || undefined,
          isp_name: formIsp,
          isp_contact_mail: formMail.trim() || undefined,
          four_g_hub_ip: formHub.trim() || undefined,
          ll_circuit_id: formLl.trim() || undefined,
          backup_circuit_id: formG3.trim() || undefined,
          is_active: formActive,
        });
        setToast(`Created branch ${formCode.trim()} and added to directory.`);
      } else if (editMode === "edit" && editBranchId !== null) {
        await branchesApi.update(editBranchId, {
          branch_code: formCode.trim(),
          name: formName.trim(),
          region: formRegion.trim(),
          ip_1: formIp1.trim(),
          ip_2: formIp2.trim(),
          regional_it_email: formRit.trim(),
          isp_name: formIsp,
          isp_contact_mail: formMail.trim(),
          four_g_hub_ip: formHub.trim(),
          ll_circuit_id: formLl.trim(),
          backup_circuit_id: formG3.trim(),
          is_active: formActive,
        });
        setToast(`Saved branch ${formCode.trim()}.`);
      }
      setEditMode(null);
      loadBranches();
      loadIsps();
    } catch (err) {
      setModalError(
        err instanceof Error ? err.message : "Could not save branch.",
      );
    }
  };

  const handleDeleteBranch = async (b: BranchDTO) => {
    try {
      await branchesApi.delete(b.id);
      setToast(`Deleted branch ${b.branch_code} (${b.name}).`);
      loadBranches();
      loadIsps();
    } catch (err) {
      setToast(
        err instanceof Error ? err.message : `Could not delete ${b.branch_code}.`,
      );
    }
  };

  const handleSaveIsp = async (isp: IspDTO) => {
    try {
      await ispsApi.update(isp.name, {
        support_email: isp.support_email,
        cc_emails: isp.cc_emails,
        four_g_hub_ip: isp.four_g_hub_ip || undefined,
        welcome_sla_minutes: isp.welcome_sla_minutes,
        followup_sla_minutes: isp.followup_sla_minutes,
        escalation_template: isp.escalation_template || undefined,
      });
      setToast(`Saved ${isp.name} configuration.`);
      loadIsps();
    } catch {
      setToast(`Failed to save ${isp.name}.`);
    }
  };

  const currentPage = Math.floor(pageOffset / pageSize) + 1;
  const totalPages = Math.max(1, Math.ceil(totalBranches / pageSize));

  return (
    <AppShell
      active="Branches & ISPs"
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
          <h1>Branches &amp; ISP Directory</h1>
          <p>
            {totalDirectoryCount.toLocaleString("en-US")} stores ·{" "}
            {Math.max(5, Object.keys(regionsCount).length)} regions · 3 ISPs ·
            bulk upload CSV or Excel (.xlsx)
          </p>
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <Button
            variant="secondary"
            icon="download"
            onClick={() =>
              branchesApi.exportSheet({
                format: "csv",
                search: search.trim() || undefined,
                region,
                isp_name: ispFilter,
              })
            }
          >
            Export CSV
          </Button>
          <Button
            variant="secondary"
            icon="download"
            onClick={() =>
              branchesApi.exportSheet({
                format: "xlsx",
                search: search.trim() || undefined,
                region,
                isp_name: ispFilter,
              })
            }
          >
            Export Excel
          </Button>
          <Button variant="secondary" onClick={handleToggleSeedPreview}>
            Import CSV / Excel sheet
          </Button>
          <Button variant="primary" onClick={openAddModal}>
            + Add branch
          </Button>
        </div>
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
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            gap: 8,
          }}
        >
          <span>{toast}</span>
          <button
            type="button"
            className="kz-btn kz-btn-ghost kz-btn-sm"
            onClick={() => setToast(null)}
          >
            ✕
          </button>
        </div>
      ) : null}

      {editMode ? (
        <div className="kz-modal-scrim">
          <div
            role="dialog"
            aria-modal="true"
            aria-label={
              editMode === "edit" ? `Edit branch ${formCode}` : "Add branch"
            }
            className="kz-card"
            style={{
              width: "100%",
              maxWidth: 720,
              boxShadow: "var(--shadow-raised)",
              maxHeight: "92%",
              overflowY: "auto",
            }}
          >
            <div className="kz-card-hd">
              <div>
                <h2>
                  {editMode === "edit"
                    ? `Edit branch ${formCode}`
                    : "Add branch"}
                </h2>
                <p>
                  Columns A–K of the store sheet. IPs fill in from the SAP
                  code; override if the branch differs.
                </p>
              </div>
              <button
                type="button"
                className="kz-btn kz-btn-ghost kz-btn-sm"
                aria-label="Close"
                onClick={() => setEditMode(null)}
              >
                ✕
              </button>
            </div>
            {modalError ? (
              <div
                role="alert"
                style={{
                  margin: "12px 16px 0",
                  padding: "10px 12px",
                  borderRadius: 10,
                  background: "var(--critical-bg)",
                  color: "var(--critical)",
                  fontSize: 13,
                  fontWeight: 600,
                }}
              >
                {modalError}
              </div>
            ) : null}
            <div
              className="kz-card-bd"
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
                gap: 14,
              }}
            >
              <label className="kz-field">
                SAP code (A)
                <input
                  value={formCode}
                  onChange={(e) => handleCodeChange(e.target.value)}
                  placeholder="e.g. 2009"
                  className="kz-mono"
                />
              </label>
              <label className="kz-field">
                Store name (B)
                <input
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                  placeholder="e.g. 2009-Kafr Nasar"
                />
              </label>
              <label className="kz-field">
                Region (E)
                <input
                  list="kz-region-options"
                  value={formRegion}
                  onChange={(e) => handleRegionChangeInForm(e.target.value)}
                />
                <datalist id="kz-region-options">
                  {allRegions
                    .filter((r) => r !== "All")
                    .map((r) => (
                      <option key={r} value={r} />
                    ))}
                </datalist>
              </label>
              <label className="kz-field">
                IP router (C)
                <input
                  value={formIp1}
                  onChange={(e) => setFormIp1(e.target.value)}
                  className="kz-mono"
                />
                <small>Derived: 10.&lt;AB&gt;.&lt;CD&gt;.1</small>
              </label>
              <label className="kz-field">
                IP server switch (D)
                <input
                  value={formIp2}
                  onChange={(e) => setFormIp2(e.target.value)}
                  className="kz-mono"
                />
                <small>Derived: 10.&lt;AB&gt;.&lt;CD&gt;.2</small>
              </label>
              <label className="kz-field">
                Regional IT email (G)
                <input
                  value={formRit}
                  onChange={(e) => setFormRit(e.target.value)}
                />
              </label>
              <label className="kz-field">
                ISP (H)
                <select
                  value={formIsp}
                  onChange={(e) => handleIspChangeInForm(e.target.value)}
                >
                  <option value="NOOR">NOOR</option>
                  <option value="ORANGE">ORANGE</option>
                  <option value="WE">WE</option>
                </select>
              </label>
              <label className="kz-field">
                ISP email (F)
                <input
                  value={formMail}
                  onChange={(e) => setFormMail(e.target.value)}
                />
              </label>
              <label className="kz-field">
                3G / 4G hub IP (I)
                <input
                  value={formHub}
                  onChange={(e) => setFormHub(e.target.value)}
                  className="kz-mono"
                />
              </label>
              <label className="kz-field">
                L.L ID (J)
                <input
                  value={formLl}
                  onChange={(e) => setFormLl(e.target.value)}
                  className="kz-mono"
                />
              </label>
              <label className="kz-field">
                3G ID (K)
                <input
                  value={formG3}
                  onChange={(e) => setFormG3(e.target.value)}
                  className="kz-mono"
                />
              </label>
              <label
                style={{
                  display: "flex",
                  gap: 8,
                  alignItems: "center",
                  fontSize: 13,
                  fontWeight: 600,
                  alignSelf: "end",
                  height: 40,
                }}
              >
                <input
                  type="checkbox"
                  checked={formActive}
                  onChange={(e) => setFormActive(e.target.checked)}
                  style={{
                    accentColor: "var(--brand-600)",
                    width: 16,
                    height: 16,
                  }}
                />
                Branch active
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
              <Button variant="secondary" onClick={() => setEditMode(null)}>
                Cancel
              </Button>
              <Button variant="primary" onClick={handleSaveBranch}>
                Save branch
              </Button>
            </div>
          </div>
        </div>
      ) : null}

      <div
        className="kz-seg"
        role="tablist"
        aria-label="Directory"
        style={{ alignSelf: "flex-start" }}
      >
        <button
          type="button"
          role="tab"
          aria-selected={tab === "branches"}
          className={tab === "branches" ? "on" : ""}
          onClick={() => setTab("branches")}
        >
          Branches · {totalDirectoryCount.toLocaleString("en-US")}
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === "isps"}
          className={tab === "isps" ? "on" : ""}
          onClick={() => setTab("isps")}
        >
          ISPs · {isps.length || 3}
        </button>
      </div>

      {seedOpen ? (
        <section
          className="kz-card"
          style={{ borderColor: "var(--brand-500)" }}
        >
          <div className="kz-card-hd" style={{ flexWrap: "wrap", gap: 12 }}>
            <div>
              <h2>Bulk Branches Import (CSV / Excel) · dry run preview</h2>
              <p>
                {seedSummary?.source_filename ||
                  (uploadedFile
                    ? uploadedFile.name
                    : "Copy of All store ISP (2).xlsx")}{" "}
                · columns A–K (or header-mapped) · nothing is written until you
                apply
              </p>
            </div>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <button
                type="button"
                className="kz-btn kz-btn-secondary kz-btn-sm"
                onClick={() => branchesApi.downloadTemplate("csv")}
              >
                Download CSV template
              </button>
              <button
                type="button"
                className="kz-btn kz-btn-secondary kz-btn-sm"
                onClick={() => branchesApi.downloadTemplate("xlsx")}
              >
                Download Excel template
              </button>
              <button
                type="button"
                className="kz-btn kz-btn-secondary kz-btn-sm"
                onClick={() => setSeedOpen(false)}
              >
                Cancel
              </button>
              <button
                type="button"
                className="kz-btn kz-btn-primary kz-btn-sm"
                disabled={isSeeding}
                onClick={handleApplySeed}
              >
                {isSeeding
                  ? "Applying…"
                  : `Apply ${(
                      seedSummary?.total_rows_parsed ?? 0
                    ).toLocaleString("en-US")} rows`}
              </button>
            </div>
          </div>

          <div
            className="kz-card-bd"
            style={{ display: "flex", flexDirection: "column", gap: 14 }}
          >
            <div
              style={{
                display: "flex",
                gap: 12,
                flexWrap: "wrap",
                alignItems: "center",
              }}
            >
              <label
                onDragOver={(e) => e.preventDefault()}
                onDrop={handleDropFile}
                style={{
                  flex: "2 1 360px",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  gap: 12,
                  flexWrap: "wrap",
                  padding: "12px 16px",
                  border: "1.5px dashed var(--brand-500)",
                  borderRadius: 12,
                  background: "var(--brand-50)",
                  fontSize: 13,
                  cursor: "pointer",
                }}
              >
                <div>
                  <b>
                    {uploadedFile
                      ? `Selected file: ${uploadedFile.name}`
                      : "Upload a CSV (.csv) or Excel (.xlsx) branches sheet"}
                  </b>
                  <div className="kz-muted" style={{ fontSize: 12 }}>
                    Supports Columns A–K (`SAP Code`, `Store Name`, `IP Router`,
                    `server`, `Region`, `E-Mail`, `Regional IT Mail`, `ISP`,
                    `3G`, `L.L ID`, `3G ID`)
                  </div>
                </div>
                <span className="kz-btn kz-btn-secondary kz-btn-sm">
                  Choose CSV / Excel file
                </span>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".csv,.xlsx,.xls,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                  onChange={handleFileChange}
                  style={{
                    position: "absolute",
                    width: 1,
                    height: 1,
                    opacity: 0,
                  }}
                />
              </label>

              {uploadedFile ? (
                <button
                  type="button"
                  className="kz-btn kz-btn-ghost kz-btn-sm"
                  onClick={handleClearUploadedFile}
                >
                  Use default 1,150-store sheet instead
                </button>
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
                  checked={replaceExisting}
                  onChange={(e) =>
                    handleToggleReplaceExisting(e.target.checked)
                  }
                  style={{
                    accentColor: "var(--brand-600)",
                    width: 16,
                    height: 16,
                  }}
                />
                Replace existing branches with uploaded sheet
              </label>
            </div>

            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))",
                gap: 12,
              }}
            >
              <div className="kz-card" style={{ padding: 12 }}>
                <div className="kz-kpi-label">Rows parsed</div>
                <div className="kz-kpi-val" style={{ fontSize: 24 }}>
                  {(seedSummary?.total_rows_parsed ?? 0).toLocaleString("en-US")}
                </div>
                <div className="kz-tcard-meta">
                  {Object.entries(seedSummary?.by_isp || {})
                    .filter(([, cnt]) => cnt > 0)
                    .map(([k, cnt]) => `${k}: ${cnt}`)
                    .join(" · ") || "NOOR / ORANGE / WE"}
                </div>
              </div>
              <div className="kz-card" style={{ padding: 12 }}>
                <div className="kz-kpi-label">New</div>
                <div className="kz-kpi-val" style={{ fontSize: 24 }}>
                  {(seedSummary?.created_count ?? 0).toLocaleString("en-US")}
                </div>
                <div className="kz-tcard-meta">Will be created</div>
              </div>
              <div className="kz-card" style={{ padding: 12 }}>
                <div className="kz-kpi-label">Updated</div>
                <div className="kz-kpi-val" style={{ fontSize: 24 }}>
                  {(seedSummary?.updated_count ?? 0).toLocaleString("en-US")}
                </div>
                <div className="kz-tcard-meta">Changed fields</div>
              </div>
              <div className="kz-card" style={{ padding: 12 }}>
                <div className="kz-kpi-label">Unchanged</div>
                <div className="kz-kpi-val" style={{ fontSize: 24 }}>
                  {(seedSummary?.unchanged_count ?? 0).toLocaleString("en-US")}
                </div>
                <div className="kz-tcard-meta">Already in sync</div>
              </div>
              {replaceExisting ? (
                <div className="kz-card" style={{ padding: 12 }}>
                  <div className="kz-kpi-label">To remove</div>
                  <div className="kz-kpi-val" style={{ fontSize: 24 }}>
                    {(seedSummary?.deleted_count ?? 0).toLocaleString("en-US")}
                  </div>
                  <div className="kz-tcard-meta">Not in uploaded sheet</div>
                </div>
              ) : null}
              <div
                className="kz-card"
                style={{
                  padding: 12,
                  background: "var(--warning-bg)",
                  borderColor: "var(--warning)",
                }}
              >
                <div
                  className="kz-kpi-label"
                  style={{ color: "var(--warning)" }}
                >
                  Warnings
                </div>
                <div className="kz-kpi-val" style={{ fontSize: 24 }}>
                  {seedSummary?.warnings_count ?? 0}
                </div>
                <div className="kz-tcard-meta">
                  {seedSummary?.warnings?.[0] || "“Orang” normalised to ORANGE"}
                </div>
              </div>
            </div>

            {seedSummary?.preview_rows &&
            seedSummary.preview_rows.length > 0 ? (
              <div
                className="kz-card"
                style={{ overflow: "hidden", maxHeight: 280, overflowY: "auto" }}
              >
                <div className="kz-scroll-x">
                  <table className="kz-table">
                    <thead>
                      <tr>
                        <th>Action</th>
                        <th>SAP</th>
                        <th>Store name</th>
                        <th>IP 1</th>
                        <th>IP 2</th>
                        <th>Region</th>
                        <th>Regional IT</th>
                        <th>ISP</th>
                        <th>3G hub</th>
                        <th>L.L ID</th>
                        <th>3G ID</th>
                      </tr>
                    </thead>
                    <tbody>
                      {seedSummary.preview_rows.slice(0, 25).map((r, i) => (
                        <tr key={`${r.branch_code}-${i}`}>
                          <td>
                            <Badge
                              tone={
                                r.action === "CREATED"
                                  ? "good"
                                  : r.action === "UPDATED"
                                    ? "brand"
                                    : "neutral"
                              }
                            >
                              {r.action}
                            </Badge>
                          </td>
                          <td className="kz-mono" style={{ fontWeight: 700 }}>
                            {r.branch_code}
                          </td>
                          <td className="kz-nowrap" style={{ fontWeight: 600 }}>
                            {r.name}
                          </td>
                          <td className="kz-mono">{r.ip_1}</td>
                          <td className="kz-mono">{r.ip_2}</td>
                          <td>{r.region}</td>
                          <td className="kz-tcard-meta kz-nowrap">
                            {r.regional_it_email}
                          </td>
                          <td>
                            <IspBadge isp={r.isp_name as IspName} />
                          </td>
                          <td className="kz-mono">{r.four_g_hub_ip || "—"}</td>
                          <td className="kz-mono">{r.ll_circuit_id || "—"}</td>
                          <td className="kz-mono">
                            {r.backup_circuit_id || "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : null}
          </div>
        </section>
      ) : null}

      {tab === "branches" ? (
        <>
          <div
            style={{
              display: "flex",
              gap: 8,
              flexWrap: "wrap",
              alignItems: "center",
            }}
          >
            <label className="kz-search" style={{ maxWidth: 320 }}>
              <span className="kz-muted">Search</span>
              <input
                type="search"
                value={search}
                onChange={(e) => {
                  setSearch(e.target.value);
                  setPageOffset(0);
                }}
                placeholder="SAP code, store, IP, L.L ID"
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
                className={clsx("kz-chip", ispFilter === k && "kz-chip-on")}
                onClick={() => {
                  setIspFilter(k);
                  setPageOffset(0);
                }}
              >
                {k === "ALL"
                  ? "All ISPs"
                  : `${k}${ispsCount[k] !== undefined ? ` · ${ispsCount[k]}` : ""}`}
              </button>
            ))}

            {allRegions.map((r) => (
              <button
                key={r}
                type="button"
                className={clsx("kz-chip", region === r && "kz-chip-on")}
                onClick={() => {
                  setRegion(r);
                  setPageOffset(0);
                }}
              >
                {r}
                {r !== "All" && regionsCount[r] !== undefined
                  ? ` · ${regionsCount[r]}`
                  : ""}
              </button>
            ))}
          </div>

          <section className="kz-card" style={{ overflow: "hidden" }}>
            <div className="kz-scroll-x">
              <table className="kz-table">
                <thead>
                  <tr>
                    <th>SAP</th>
                    <th>Store name</th>
                    <th>IP 1</th>
                    <th>IP 2</th>
                    <th>Region</th>
                    <th>Regional IT</th>
                    <th>ISP</th>
                    <th>ISP email</th>
                    <th>3G hub</th>
                    <th>L.L ID</th>
                    <th>3G ID</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {branches.map((b) => (
                    <tr key={b.id}>
                      <td className="kz-mono" style={{ fontWeight: 700 }}>
                        {b.branch_code}
                      </td>
                      <td className="kz-nowrap" style={{ fontWeight: 600 }}>
                        {b.name}
                      </td>
                      <td className="kz-mono">{b.ip_1}</td>
                      <td className="kz-mono">{b.ip_2}</td>
                      <td>{b.region || "—"}</td>
                      <td className="kz-tcard-meta kz-nowrap">
                        {b.regional_it_email || "—"}
                      </td>
                      <td>
                        <IspBadge isp={b.isp_name as IspName} />
                      </td>
                      <td className="kz-tcard-meta kz-nowrap">
                        {b.isp_contact_mail}
                      </td>
                      <td className="kz-mono">{b.four_g_hub_ip || "—"}</td>
                      <td className="kz-mono kz-nowrap">
                        {b.ll_circuit_id || "—"}
                      </td>
                      <td className="kz-mono kz-nowrap">
                        {b.backup_circuit_id || "—"}
                      </td>
                      <td>
                        <div
                          style={{
                            display: "flex",
                            gap: 4,
                            justifyContent: "flex-end",
                          }}
                        >
                          <button
                            type="button"
                            className="kz-btn kz-btn-ghost kz-btn-sm"
                            aria-label={`Edit ${b.name}`}
                            onClick={() => openEditModal(b)}
                          >
                            Edit
                          </button>
                          <button
                            type="button"
                            className="kz-btn kz-btn-ghost kz-btn-sm"
                            aria-label={`Delete ${b.name}`}
                            onClick={() => handleDeleteBranch(b)}
                          >
                            Delete
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                  {branches.length === 0 ? (
                    <tr>
                      <td
                        colSpan={12}
                        className="kz-muted"
                        style={{ textAlign: "center", padding: 24 }}
                      >
                        No branches match the current filter. Click{" "}
                        <b>Import CSV / Excel sheet</b> or <b>+ Add branch</b>{" "}
                        to add branches.
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                gap: 12,
                flexWrap: "wrap",
                padding: "12px 16px",
                borderTop: "1px solid var(--border)",
                fontSize: 13,
              }}
              className="kz-muted"
            >
              <span>
                Showing{" "}
                {branches.length > 0
                  ? `${pageOffset + 1}–${pageOffset + branches.length}`
                  : "0"}{" "}
                of {totalBranches.toLocaleString("en-US")} · IPs derive from SAP
                code (10.&lt;AB&gt;.&lt;CD&gt;.1 / .2) unless overridden
              </span>
              <div
                style={{
                  display: "flex",
                  gap: 8,
                  alignItems: "center",
                  flexWrap: "wrap",
                }}
              >
                <label className="kz-chip">
                  Rows
                  <select
                    value={pageSize}
                    onChange={(e) => {
                      setPageSize(Number(e.target.value) || 100);
                      setPageOffset(0);
                    }}
                    style={{
                      border: 0,
                      font: "600 12px var(--font-sans)",
                      background: "transparent",
                      color: "var(--ink)",
                    }}
                  >
                    <option value={50}>50</option>
                    <option value={100}>100</option>
                    <option value={250}>250</option>
                    <option value={500}>500</option>
                  </select>
                </label>
                <button
                  type="button"
                  className="kz-btn kz-btn-secondary kz-btn-sm"
                  disabled={pageOffset === 0}
                  onClick={() =>
                    setPageOffset((prev) => Math.max(0, prev - pageSize))
                  }
                >
                  Previous
                </button>
                <span className="kz-num" style={{ fontWeight: 600 }}>
                  Page {currentPage} of {totalPages}
                </span>
                <button
                  type="button"
                  className="kz-btn kz-btn-secondary kz-btn-sm"
                  disabled={pageOffset + pageSize >= totalBranches}
                  onClick={() => setPageOffset((prev) => prev + pageSize)}
                >
                  Next
                </button>
              </div>
            </div>
          </section>
        </>
      ) : (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
            gap: 16,
          }}
        >
          {isps.map((p, idx) => (
            <section key={p.id} className="kz-card">
              <div className="kz-card-hd">
                <IspBadge isp={p.name as IspName} />
                <span className="kz-tcard-meta">
                  {p.store_count.toLocaleString("en-US")} stores
                </span>
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
                <label
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    gap: 4,
                    fontWeight: 600,
                  }}
                >
                  Support email
                  <input
                    value={p.support_email}
                    onChange={(e) => {
                      const val = e.target.value;
                      setIsps((prev) =>
                        prev.map((it, i) =>
                          i === idx ? { ...it, support_email: val } : it,
                        ),
                      );
                    }}
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
                  CC
                  <input
                    value={(p.cc_emails || []).join(", ")}
                    onChange={(e) => {
                      const val = e.target.value
                        .split(",")
                        .map((s) => s.trim())
                        .filter(Boolean);
                      setIsps((prev) =>
                        prev.map((it, i) =>
                          i === idx ? { ...it, cc_emails: val } : it,
                        ),
                      );
                    }}
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
                  4G hub IP(s)
                  <input
                    value={p.four_g_hub_ip || "—"}
                    onChange={(e) => {
                      const val = e.target.value;
                      setIsps((prev) =>
                        prev.map((it, i) =>
                          i === idx ? { ...it, four_g_hub_ip: val } : it,
                        ),
                      );
                    }}
                    className="kz-mono"
                    style={{
                      height: 36,
                      padding: "0 10px",
                      border: "1px solid var(--border-strong)",
                      borderRadius: 8,
                    }}
                  />
                </label>

                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
                    gap: 10,
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
                    Welcome SLA (min)
                    <input
                      type="number"
                      value={p.welcome_sla_minutes}
                      onChange={(e) => {
                        const val = Number(e.target.value) || 120;
                        setIsps((prev) =>
                          prev.map((it, i) =>
                            i === idx
                              ? { ...it, welcome_sla_minutes: val }
                              : it,
                          ),
                        );
                      }}
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
                    Follow-up SLA (min)
                    <input
                      type="number"
                      value={p.followup_sla_minutes}
                      onChange={(e) => {
                        const val = Number(e.target.value) || 300;
                        setIsps((prev) =>
                          prev.map((it, i) =>
                            i === idx
                              ? { ...it, followup_sla_minutes: val }
                              : it,
                          ),
                        );
                      }}
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

                <div style={{ fontWeight: 600 }}>Escalation template</div>
                <pre
                  className="kz-mono"
                  style={{
                    margin: 0,
                    padding: "10px 12px",
                    background: "var(--surface-100)",
                    border: "1px solid var(--border)",
                    borderRadius: 8,
                    whiteSpace: "pre-wrap",
                    lineHeight: "18px",
                  }}
                >
                  {p.escalation_template}
                </pre>
                <div style={{ display: "flex", justifyContent: "flex-end" }}>
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={() => handleSaveIsp(p)}
                  >
                    Save
                  </Button>
                </div>
              </div>
            </section>
          ))}
        </div>
      )}
    </AppShell>
  );
}
