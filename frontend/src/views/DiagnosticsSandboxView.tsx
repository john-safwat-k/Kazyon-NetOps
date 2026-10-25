import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  AppShell,
  Badge,
  BadgeTone,
  Button,
  IspBadge,
  IspName,
  KpiCard,
  StatusPill,
} from "../design-system";
import {
  DiagnosticRunDTO,
  DiagnosticStepDetailDTO,
  DiagnosticSuiteBranchItemDTO,
  DiagnosticSuiteReportDTO,
  SandboxCatalogDTO,
  diagnosticsApi,
} from "../lib/api";
import { ConsoleViewProps } from "./types";

const DEFAULT_BRANCHES = [
  {
    code: "1173",
    name: "1173-Ghmrawy",
    region: "Cairo",
    label: "1173-Ghmrawy · Cairo",
    ip1: "10.11.73.1",
    ip2: "10.11.73.2",
    isp: "ORANGE" as const,
    hub: "10.247.8.1",
    ll_circuit_id: "QUO1-10316406",
    backup_circuit_id: "QUO1-10316407",
    regional_it_email: "CITSupport@kazyon.com",
    default_result: "PASS",
  },
];

type ScenarioType =
  | "LIVE_ICMP"
  | "AUTO"
  | "PASS"
  | "FULL_OUTAGE"
  | "LOCAL_LOOP_DOWN_ON_4G"
  | "INTERNAL_LAN_SWITCH";

interface ResultReferenceItem {
  code: string;
  title: string;
  tone: BadgeTone;
  ip1State: "up" | "down";
  ip2State: "up" | "down" | "skip";
  fourGState: string;
  isps: string;
  whatItMeans: string;
  rootCause: string;
  aiAction: string;
  operatorAction: string;
}

const RESULT_REFERENCE_CATALOG: ResultReferenceItem[] = [
  {
    code: "PASS",
    title: "Healthy Network (Primary WAN & Store LAN Up)",
    tone: "good",
    ip1State: "up",
    ip2State: "up",
    fourGState: "Direct MPLS (No 4G Hub)",
    isps: "NOOR · ORANGE · WE",
    whatItMeans:
      "Both the branch WAN router (IP 1 = 10.<AB>.<CD>.1) and the store server switch (IP 2 = 10.<AB>.<CD>.2) respond with 0% packet loss.",
    rootCause:
      "Primary landline (MPLS / FTTH / VDSL) and internal store switch uplink are both healthy.",
    aiAction:
      "Marks diagnostic check as PASS. If running during recovery verification, confirms link stability with Regional IT and resolves the ticket.",
    operatorAction:
      "No intervention required. If store still reports an issue, check individual POS terminal or application service.",
  },
  {
    code: "FULL_OUTAGE",
    title: "Complete Branch WAN Outage (Router Unreachable)",
    tone: "critical",
    ip1State: "down",
    ip2State: "skip",
    fourGState: "Skipped (Router Down)",
    isps: "NOOR · ORANGE · WE",
    whatItMeans:
      "Router IP 1 (10.<AB>.<CD>.1) has 100% packet loss from HQ. Server switch IP 2 (10.<AB>.<CD>.2) is automatically skipped because it sits behind IP 1.",
    rootCause:
      "Both the primary ISP local loop and any 3G/4G backup path are unreachable, or branch CPE router / store electricity is powered off.",
    aiAction:
      "Requests rack/CPE photo from Regional IT (Gemma 4 Vision check). Once power & cables are verified, escalates to ISP with L.L ID & 3G ID and starts the 2h Welcome SLA timer.",
    operatorAction:
      "Confirm store power/UPS with Regional IT, then track ISP case reference and 2-hour Welcome SLA.",
  },
  {
    code: "LOCAL_LOOP_DOWN_ON_4G",
    title: "Primary Landline Down · Running on 3G/4G Backup Hub",
    tone: "warning",
    ip1State: "up",
    ip2State: "down",
    fourGState: "Hits 10.247.8.1 (ORANGE) or 172.16.70.33 / 172.17.20.33 (WE)",
    isps: "ORANGE · WE",
    whatItMeans:
      "Router IP 1 is reachable (often with higher 150–190 ms cellular latency), Switch IP 2 is unreachable, and traceroute to IP 1 passes through the ISP's 4G backup hub.",
    rootCause:
      "Physical landline (Local Loop) is cut or down at the exchange. The router failed over to its 3G/4G SIM tunnel, which isolates IP 2 by routing policy.",
    aiAction:
      "Escalates primary Local Loop outage to ORANGE or WE support quoting SAP code, L.L Circuit ID, and 4G Hub traceroute hop; starts 2h Welcome SLA timer.",
    operatorAction:
      "Keep store operating on 4G backup while following up with ISP landline team to restore the physical local loop.",
  },
  {
    code: "INTERNAL_LAN_SWITCH",
    title: "Internal Store LAN / Server Switch Issue",
    tone: "warning",
    ip1State: "up",
    ip2State: "down",
    fourGState: "No 4G Hub in path (or NOOR LAN Rule)",
    isps: "NOOR · ORANGE · WE",
    whatItMeans:
      "Router IP 1 is UP on the primary landline (no 4G hub in traceroute, or branch is on NOOR which has no 4G hub), while Server Switch IP 2 is DOWN (100% packet loss).",
    rootCause:
      "ISP WAN link to the branch router is healthy. The failure is inside the store between the router LAN port and the server switch (unplugged RJ45 patch cord, hung switch, or tripped breaker).",
    aiAction:
      "Does NOT escalate to the ISP (prevents false ISP tickets). Routes ticket to Regional IT / Store IT to inspect the internal server switch and LAN cabling.",
    operatorAction:
      "Contact Regional IT engineer to check the store server switch power supply and RJ45 uplink cable connected to the router.",
  },
];

function diagnosisBadgeTone(code: string): BadgeTone {
  if (code === "PASS") return "good";
  if (code === "FULL_OUTAGE") return "critical";
  if (code === "LOCAL_LOOP_DOWN_ON_4G" || code === "INTERNAL_LAN_SWITCH") {
    return "warning";
  }
  return "info";
}

export function DiagnosticsSandboxView({
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
  const [catalog, setCatalog] = useState<SandboxCatalogDTO | null>(null);
  const [branchSearch, setBranchSearch] = useState("");
  const [branchCode, setBranchCode] = useState("1173");
  const [ip1, setIp1] = useState("10.11.73.1");
  const [ip2, setIp2] = useState("10.11.73.2");
  const [scenario, setScenario] = useState<ScenarioType>("LIVE_ICMP");
  const [timeoutSec, setTimeoutSec] = useState(20);
  const [pingCount, setPingCount] = useState(4);
  const [maxHops, setMaxHops] = useState(15);
  const [runCount, setRunCount] = useState(0);
  const [latestRun, setLatestRun] = useState<DiagnosticRunDTO | null>(null);
  const [isRunning, setIsRunning] = useState(false);

  // Full Fleet Test Suite state
  const [suiteIspFilter, setSuiteIspFilter] = useState("ALL");
  const [suiteRegionFilter, setSuiteRegionFilter] = useState("All");
  const [suiteScenario, setSuiteScenario] = useState<ScenarioType>("LIVE_ICMP");
  const [isSuiteRunning, setIsSuiteRunning] = useState(false);
  const [suiteError, setSuiteError] = useState<string | null>(null);
  const [suiteReport, setSuiteReport] =
    useState<DiagnosticSuiteReportDTO | null>(null);
  const [reportDiagFilter, setReportDiagFilter] = useState("ALL");
  const [reportIspFilter, setReportIspFilter] = useState("ALL");
  const [reportRegionFilter, setReportRegionFilter] = useState("All");
  const [reportSearch, setReportSearch] = useState("");
  const [reportPage, setReportPage] = useState(1);
  const [reportPageSize, setReportPageSize] = useState(25);
  const [showReferenceGuide, setShowReferenceGuide] = useState(true);

  const loadCatalog = useCallback(() => {
    diagnosticsApi
      .sandboxCatalog()
      .then((res) => {
        setCatalog(res);
        if (res.branches && res.branches.length > 0) {
          const current =
            res.branches.find((b) => b.code === branchCode) || res.branches[0];
          if (current) {
            setBranchCode(current.code);
            setIp1(current.ip1);
            setIp2(current.ip2);
          }
        }
      })
      .catch(() => {});
  }, [branchCode]);

  useEffect(() => {
    loadCatalog();
  }, [loadCatalog]);

  const branches = catalog?.branches?.length
    ? catalog.branches
    : DEFAULT_BRANCHES;

  const availableRegions = useMemo(() => {
    const s = new Set<string>();
    for (const b of branches) {
      if (b.region) s.add(b.region);
    }
    return Array.from(s).sort();
  }, [branches]);

  const filteredBranches = useMemo(() => {
    const q = branchSearch.trim().toLowerCase();
    if (!q) return branches;
    const matches = branches.filter(
      (b) =>
        b.code.toLowerCase().includes(q) ||
        b.label.toLowerCase().includes(q) ||
        b.ip1.toLowerCase().includes(q) ||
        b.isp.toLowerCase().includes(q),
    );
    return matches.length > 0 ? matches : branches;
  }, [branches, branchSearch]);

  const activeBranch =
    branches.find((b) => b.code === branchCode) ||
    filteredBranches[0] ||
    branches[0];

  const handleSelectBranch = (code: string) => {
    setBranchCode(code);
    const found = branches.find((b) => b.code === code);
    if (found) {
      setIp1(found.ip1);
      setIp2(found.ip2);
      setLatestRun(null);
    }
  };

  const handleSearchChange = (val: string) => {
    setBranchSearch(val);
    const q = val.trim().toLowerCase();
    if (!q) return;
    const exactOrFirst =
      branches.find((b) => b.code.toLowerCase() === q) ||
      branches.find(
        (b) =>
          b.code.toLowerCase().includes(q) ||
          b.label.toLowerCase().includes(q),
      );
    if (exactOrFirst) {
      setBranchCode(exactOrFirst.code);
      setIp1(exactOrFirst.ip1);
      setIp2(exactOrFirst.ip2);
      setLatestRun(null);
    }
  };

  const handleRunCheck = async (
    mode: "full" | "ping_ip1" | "ping_ip2" | "traceroute",
  ) => {
    setIsRunning(true);
    try {
      const res = await diagnosticsApi.run({
        branch_code: branchCode,
        ip_1: ip1,
        ip_2: ip2,
        isp_name: activeBranch.isp,
        four_g_hub_ip:
          activeBranch.hub && activeBranch.hub !== "—"
            ? activeBranch.hub
            : undefined,
        mode,
        simulate_scenario: scenario,
        timeout_sec: timeoutSec,
        ping_count: pingCount,
        traceroute_max_hops: maxHops,
        trigger_source: "SANDBOX",
      });
      setLatestRun(res);
      setRunCount((n) => n + 1);
      diagnosticsApi
        .sandboxCatalog()
        .then((c) => setCatalog(c))
        .catch(() => {});
    } catch {
      // Ignore error
    } finally {
      setIsRunning(false);
    }
  };

  const handleRunFullSuite = async () => {
    setIsSuiteRunning(true);
    setSuiteError(null);
    try {
      const report = await diagnosticsApi.runSuite({
        isp_name: suiteIspFilter !== "ALL" ? suiteIspFilter : undefined,
        region: suiteRegionFilter !== "All" ? suiteRegionFilter : undefined,
        simulate_scenario: suiteScenario,
        ping_count: pingCount,
        traceroute_max_hops: maxHops,
        limit: 5000,
      });
      setSuiteReport(report);
      setReportPage(1);
    } catch (err) {
      setSuiteError(
        err instanceof Error
          ? err.message
          : "Failed to execute full branch diagnostic test suite.",
      );
    } finally {
      setIsSuiteRunning(false);
    }
  };

  const handleInspectSuiteItem = (item: DiagnosticSuiteBranchItemDTO) => {
    setBranchCode(item.branch_code);
    setIp1(item.ip_1);
    setIp2(item.ip_2);
    setLatestRun({
      id: Date.now(),
      ticket_id: null,
      branch_code: item.branch_code,
      branch_label: `${item.branch_name} · ${item.region}`,
      isp_name: item.isp_name,
      ip_1: item.ip_1,
      ip_2: item.ip_2,
      ip_1_up: item.ip_1_up,
      ip_2_up: item.ip_2_up,
      four_g_hub_detected: item.four_g_hub_detected,
      detected_hub_ip: item.detected_hub_ip,
      result_status: item.result_status,
      diagnosis_code: item.diagnosis_code,
      diagnosis_title: item.diagnosis_title,
      meaning: item.meaning,
      root_cause: item.root_cause,
      responsible_team: item.responsible_team,
      ai_workflow_action: item.ai_workflow_action,
      operator_action: item.operator_action,
      checks: item.checks,
      steps: item.steps,
      raw_output: item.raw_output,
      duration_ms: item.duration_ms,
      trigger_source: "SUITE",
      executed_at: suiteReport?.executed_at ?? new Date().toISOString(),
    });
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const filteredSuiteItems = useMemo(() => {
    if (!suiteReport) return [];
    const q = reportSearch.trim().toLowerCase();
    return suiteReport.items.filter((item) => {
      if (
        reportDiagFilter !== "ALL" &&
        item.diagnosis_code !== reportDiagFilter
      ) {
        return false;
      }
      if (reportIspFilter !== "ALL" && item.isp_name !== reportIspFilter) {
        return false;
      }
      if (reportRegionFilter !== "All" && item.region !== reportRegionFilter) {
        return false;
      }
      if (q) {
        const hay =
          `${item.branch_code} ${item.branch_name} ${item.region} ${item.ip_1} ${item.ip_2} ${item.diagnosis_code}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [
    suiteReport,
    reportDiagFilter,
    reportIspFilter,
    reportRegionFilter,
    reportSearch,
  ]);

  const totalReportPages = Math.max(
    1,
    Math.ceil(filteredSuiteItems.length / reportPageSize),
  );
  const paginatedSuiteItems = useMemo(() => {
    const start = (reportPage - 1) * reportPageSize;
    return filteredSuiteItems.slice(start, start + reportPageSize);
  }, [filteredSuiteItems, reportPage, reportPageSize]);

  const handleExportSuiteReport = (format: "csv" | "excel" | "html") => {
    if (!suiteReport) return;
    if (format === "html") {
      const rowsHtml = filteredSuiteItems
        .map(
          (r) => `
          <tr>
            <td style="font-family:monospace;font-weight:700">${r.branch_code}</td>
            <td>${r.branch_name}</td>
            <td>${r.region}</td>
            <td><b>${r.isp_name}</b></td>
            <td style="font-family:monospace">${r.ip_1} (${r.ip_1_up ? "UP" : "DOWN"})</td>
            <td style="font-family:monospace">${r.ip_2} (${
              r.ip_2_skipped ? "SKIPPED" : r.ip_2_up ? "UP" : "DOWN"
            })</td>
            <td style="font-family:monospace">${
              r.four_g_hub_detected ? `4G HUB (${r.detected_hub_ip})` : "—"
            }</td>
            <td><b>${r.diagnosis_code}</b><br/><small>${r.diagnosis_title}</small></td>
            <td>${r.root_cause}</td>
            <td><b>${r.responsible_team}</b><br/><small>${r.operator_action}</small></td>
          </tr>`,
        )
        .join("");

      const htmlDoc = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Kazyon NetOps — Full Branch Diagnostic Report (${suiteReport.suite_id})</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; color: #1f1a17; margin: 24px; }
    h1 { margin: 0 0 4px; color: #c2410c; }
    .meta { color: #6b625b; font-size: 13px; margin-bottom: 20px; }
    .kpis { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 20px; }
    .kpi { border: 1px solid #ede5de; border-radius: 10px; padding: 12px 16px; min-width: 150px; background: #fbf8f5; }
    .kpi .lbl { font-size: 11px; text-transform: uppercase; color: #6b625b; font-weight: 700; }
    .kpi .val { font-size: 24px; font-weight: 700; margin-top: 4px; }
    table { width: 100%; border-collapse: collapse; font-size: 12px; margin-bottom: 24px; }
    th, td { border: 1px solid #ede5de; padding: 8px 10px; text-align: left; vertical-align: top; }
    th { background: #fbf8f5; font-size: 11px; text-transform: uppercase; color: #6b625b; }
  </style>
</head>
<body>
  <h1>Kazyon NetOps — Full Branch Diagnostic Suite Report</h1>
  <div class="meta">
    Suite ID: <b>${suiteReport.suite_id}</b> · Executed: <b>${suiteReport.executed_at}</b> ·
    Scenario Mode: <b>${suiteReport.scenario_mode}</b> · Duration: <b>${suiteReport.duration_ms} ms</b>
  </div>
  <div class="kpis">
    <div class="kpi"><div class="lbl">Total Branches Tested</div><div class="val">${suiteReport.total_branches}</div></div>
    <div class="kpi"><div class="lbl">Healthy (PASS)</div><div class="val" style="color:#15803d">${suiteReport.pass_count} (${suiteReport.health_pct}%)</div></div>
    <div class="kpi"><div class="lbl">Full WAN Outage</div><div class="val" style="color:#b91c1c">${suiteReport.full_outage_count}</div></div>
    <div class="kpi"><div class="lbl">On 4G Backup Hub</div><div class="val" style="color:#a16207">${suiteReport.four_g_count}</div></div>
    <div class="kpi"><div class="lbl">Internal LAN Switch</div><div class="val" style="color:#a16207">${suiteReport.lan_switch_count}</div></div>
  </div>
  <h2>Branch-by-Branch Diagnostic Results (${filteredSuiteItems.length} rows)</h2>
  <table>
    <thead>
      <tr>
        <th>SAP Code</th>
        <th>Branch Name</th>
        <th>Region</th>
        <th>ISP</th>
        <th>IP 1 (Router)</th>
        <th>IP 2 (Switch)</th>
        <th>4G Hub</th>
        <th>Diagnosis Result</th>
        <th>Detailed Root Cause</th>
        <th>Responsible Team &amp; Action</th>
      </tr>
    </thead>
    <tbody>${rowsHtml}</tbody>
  </table>
</body>
</html>`;
      const blob = new Blob([htmlDoc], { type: "text/html;charset=utf-8;" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `kazyon-diagnostic-report-${suiteReport.suite_id}.html`;
      a.click();
      URL.revokeObjectURL(url);
      return;
    }

    const headers = [
      "SAP Code",
      "Branch Name",
      "Region",
      "ISP",
      "IP 1 (Router)",
      "IP 1 Status",
      "IP 2 (Switch)",
      "IP 2 Status",
      "4G Hub Detected",
      "Detected 4G Hub IP",
      "Result Status",
      "Diagnosis Code",
      "Diagnosis Title",
      "Summary Meaning",
      "Detailed Root Cause",
      "Responsible Team",
      "Automated AI Workflow Action",
      "Recommended Operator Action",
      "L.L Circuit ID",
      "3G/4G Backup ID",
      "Regional IT Email",
      "Duration (ms)",
    ];
    const rows = filteredSuiteItems.map((r) => [
      r.branch_code,
      r.branch_name,
      r.region,
      r.isp_name,
      r.ip_1,
      r.ip_1_up ? "UP" : "DOWN",
      r.ip_2,
      r.ip_2_skipped ? "SKIPPED" : r.ip_2_up ? "UP" : "DOWN",
      r.four_g_hub_detected ? "YES" : "NO",
      r.detected_hub_ip || "",
      r.result_status,
      r.diagnosis_code,
      r.diagnosis_title,
      r.meaning,
      r.root_cause,
      r.responsible_team,
      r.ai_workflow_action,
      r.operator_action,
      r.ll_circuit_id || "",
      r.backup_circuit_id || "",
      r.regional_it_email || "",
      String(r.duration_ms),
    ]);
    const csv = [headers, ...rows]
      .map((row) =>
        row.map((v) => `"${String(v).replace(/"/g, '""')}"`).join(","),
      )
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
        ? `kazyon-diagnostic-suite-${suiteReport.suite_id}.xls`
        : `kazyon-diagnostic-suite-${suiteReport.suite_id}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const checks = latestRun?.checks ?? [];
  const diagCode = latestRun?.diagnosis_code ?? "READY";
  const diagTitle =
    latestRun?.diagnosis_title ||
    RESULT_REFERENCE_CATALOG.find((r) => r.code === diagCode)?.title ||
    "Ready for Diagnostic Execution";
  const diagMeaning =
    latestRun?.diagnosis_meaning ??
    latestRun?.meaning ??
    "Select a branch and click 'Run full check' to execute live dual-ping and 4G hub traceroute diagnostics, or run the Full Fleet Test Suite below.";
  const diagTone =
    latestRun?.result_status === "PASS"
      ? "good"
      : latestRun?.result_status === "FAIL"
        ? "critical"
        : latestRun
          ? "warning"
          : "info";
  const rawLog =
    latestRun?.raw_output ??
    `# Ready to run dual-ping & 4G hub traceroute on ${activeBranch.label}\n# IP1 (Router): ${ip1}\n# IP2 (Switch): ${ip2}`;
  const runSteps: DiagnosticStepDetailDTO[] = latestRun?.steps ?? [];
  const activeRefMeta = RESULT_REFERENCE_CATALOG.find(
    (r) => r.code === diagCode,
  );

  return (
    <AppShell
      active="Diagnostics Sandbox"
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
          <h1>Network Diagnostics Sandbox &amp; Fleet Test Suite</h1>
          <p>
            Run dual-ping (`IP 1` Router + `IP 2` Switch) and `ORANGE`/`WE` 4G
            hub traceroute on any single branch or execute the full test suite
            across all {branches.length.toLocaleString("en-US")} directory
            branches with an exportable report.
          </p>
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <Button
            variant="secondary"
            onClick={() => setShowReferenceGuide((v) => !v)}
          >
            {showReferenceGuide
              ? "Hide result reference"
              : "Show result reference"}
          </Button>
          <Button
            variant="primary"
            disabled={isSuiteRunning}
            onClick={handleRunFullSuite}
          >
            {isSuiteRunning
              ? "Running full suite…"
              : `Run full test suite (${branches.length.toLocaleString("en-US")} branches)`}
          </Button>
        </div>
      </div>

      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: 16,
          alignItems: "flex-start",
        }}
      >
        <div
          style={{
            flex: "999 1 560px",
            minWidth: 0,
            display: "flex",
            flexDirection: "column",
            gap: 16,
          }}
        >
          <section className="kz-card">
            <div className="kz-card-hd">
              <h2>Single-Branch Diagnostic Target</h2>
              <span className="kz-tcard-meta">
                {branches.length.toLocaleString("en-US")} branches loaded from
                directory
              </span>
            </div>
            <div
              className="kz-card-bd"
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
                gap: 12,
                alignItems: "end",
              }}
            >
              <label
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: 6,
                  fontSize: 13,
                  fontWeight: 600,
                }}
              >
                Filter branch
                <input
                  type="search"
                  value={branchSearch}
                  onChange={(e) => handleSearchChange(e.target.value)}
                  placeholder="Type SAP code, name, or IP…"
                  style={{
                    height: 40,
                    padding: "0 10px",
                    border: "1px solid var(--border-strong)",
                    borderRadius: 10,
                    font: "500 13px var(--font-sans)",
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
                Branch
                <select
                  value={branchCode}
                  onChange={(e) => handleSelectBranch(e.target.value)}
                  style={{
                    height: 40,
                    padding: "0 10px",
                    border: "1px solid var(--border-strong)",
                    borderRadius: 10,
                    font: "500 14px var(--font-sans)",
                    background: "var(--surface-000)",
                    color: "var(--ink)",
                  }}
                >
                  {filteredBranches.map((b) => (
                    <option key={b.code} value={b.code}>
                      {b.label} ({b.isp})
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
                IP 1 (router)
                <input
                  value={ip1}
                  onChange={(e) => setIp1(e.target.value)}
                  className="kz-mono"
                  style={{
                    height: 40,
                    padding: "0 10px",
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
                IP 2 (switch)
                <input
                  value={ip2}
                  onChange={(e) => setIp2(e.target.value)}
                  className="kz-mono"
                  style={{
                    height: 40,
                    padding: "0 10px",
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
                Test scenario
                <select
                  value={scenario}
                  onChange={(e) => setScenario(e.target.value as ScenarioType)}
                  style={{
                    height: 40,
                    padding: "0 10px",
                    border: "1px solid var(--border-strong)",
                    borderRadius: 10,
                    font: "500 13px var(--font-sans)",
                    background: "var(--surface-000)",
                    color: "var(--ink)",
                  }}
                >
                  <option value="LIVE_ICMP">
                    LIVE_ICMP (Real OS Ping &amp; Traceroute — Matches Live Email Triage)
                  </option>
                  <option value="AUTO">
                    AUTO (Simulated Demo Preset — Does Not Ping Network)
                  </option>
                  <option value="PASS">PASS (Simulated IP1 UP + IP2 UP)</option>
                  <option value="FULL_OUTAGE">
                    FULL_OUTAGE (Simulated IP1 DOWN)
                  </option>
                  <option value="LOCAL_LOOP_DOWN_ON_4G">
                    LOCAL_LOOP_DOWN_ON_4G (Simulated 4G Hub)
                  </option>
                  <option value="INTERNAL_LAN_SWITCH">
                    INTERNAL_LAN_SWITCH (Simulated IP2 DOWN)
                  </option>
                </select>
              </label>

              <div
                style={{
                  display: "flex",
                  gap: 8,
                  alignItems: "center",
                  height: 40,
                }}
              >
                <IspBadge isp={activeBranch.isp as IspName} />
                <span className="kz-tcard-meta">Hub {activeBranch.hub}</span>
              </div>
            </div>

            <div
              style={{
                margin: "0 16px 12px",
                padding: "8px 12px",
                borderRadius: 8,
                background: "var(--surface-100)",
                fontSize: 12,
                display: "flex",
                gap: 16,
                flexWrap: "wrap",
              }}
            >
              <span>
                <span className="kz-muted">SAP:</span>{" "}
                <b className="kz-mono">{activeBranch.code}</b>
              </span>
              <span>
                <span className="kz-muted">Region:</span>{" "}
                <b>{activeBranch.region || "Cairo"}</b>
              </span>
              <span>
                <span className="kz-muted">Regional IT:</span>{" "}
                <b>
                  {activeBranch.regional_it_email || "CITSupport@kazyon.com"}
                </b>
              </span>
              <span>
                <span className="kz-muted">L.L ID:</span>{" "}
                <span className="kz-mono">
                  {activeBranch.ll_circuit_id || "—"}
                </span>
              </span>
              <span>
                <span className="kz-muted">3G ID:</span>{" "}
                <span className="kz-mono">
                  {activeBranch.backup_circuit_id || "—"}
                </span>
              </span>
            </div>

            <div
              style={{
                display: "flex",
                gap: 8,
                flexWrap: "wrap",
                padding: "0 16px 16px",
              }}
            >
              <Button
                variant="primary"
                disabled={isRunning}
                onClick={() => handleRunCheck("full")}
              >
                {isRunning ? "Running…" : "Run full check"}
              </Button>
              <Button
                variant="secondary"
                disabled={isRunning}
                onClick={() => handleRunCheck("ping_ip1")}
              >
                Ping IP 1
              </Button>
              <Button
                variant="secondary"
                disabled={isRunning}
                onClick={() => handleRunCheck("ping_ip2")}
              >
                Ping IP 2
              </Button>
              <Button
                variant="secondary"
                disabled={isRunning}
                onClick={() => handleRunCheck("traceroute")}
              >
                Traceroute (4G hub check)
              </Button>
            </div>
          </section>

          <section className="kz-card">
            <div className="kz-card-hd" style={{ flexWrap: "wrap" }}>
              <div>
                <h2>Detailed Diagnostic Result &amp; Step-by-Step Analysis</h2>
                <p>
                  {latestRun
                    ? `Run #${runCount} · ${
                        latestRun.branch_label || activeBranch.label
                      } · ${(latestRun.duration_ms / 1000).toFixed(2)} s`
                    : `Target: ${activeBranch.label}`}
                </p>
              </div>
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                {checks.map((c, idx) => (
                  <StatusPill key={idx} label={c.label} state={c.state} />
                ))}
              </div>
            </div>
            <div
              className="kz-card-bd"
              style={{ display: "flex", flexDirection: "column", gap: 14 }}
            >
              <div
                style={{
                  padding: "12px 14px",
                  borderRadius: 10,
                  fontSize: 13,
                  background: `var(--${diagTone}-bg)`,
                  color: `var(--${diagTone})`,
                  border: "1px solid var(--border)",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    gap: 8,
                    flexWrap: "wrap",
                    marginBottom: 4,
                  }}
                >
                  <span style={{ fontSize: 15, fontWeight: 700 }}>
                    {diagCode} — {diagTitle}
                  </span>
                  {latestRun && (
                    <Badge tone={diagnosisBadgeTone(diagCode)}>
                      {latestRun.result_status}
                    </Badge>
                  )}
                </div>
                <div>{diagMeaning}</div>
              </div>

              {runSteps.length > 0 && (
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns:
                      "repeat(auto-fit, minmax(220px, 1fr))",
                    gap: 10,
                  }}
                >
                  {runSteps.map((st) => (
                    <div
                      key={st.step_number}
                      style={{
                        padding: 12,
                        borderRadius: 10,
                        border: "1px solid var(--border)",
                        background: "var(--surface-100)",
                        display: "flex",
                        flexDirection: "column",
                        gap: 6,
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
                        <b style={{ fontSize: 12 }}>{st.step_name}</b>
                        <Badge tone={st.tone as BadgeTone}>{st.status}</Badge>
                      </div>
                      <div
                        className="kz-mono"
                        style={{ fontSize: 12, color: "var(--brand-text)" }}
                      >
                        Target: {st.target} · {st.latency_or_hops}
                      </div>
                      <div
                        style={{
                          fontSize: 12,
                          color: "var(--ink-muted)",
                          lineHeight: "17px",
                        }}
                      >
                        {st.explanation}
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {(latestRun || activeRefMeta) && (
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns:
                      "repeat(auto-fit, minmax(240px, 1fr))",
                    gap: 10,
                    padding: 12,
                    borderRadius: 10,
                    border: "1px solid var(--border)",
                    background: "var(--surface-000)",
                    fontSize: 12,
                  }}
                >
                  <div>
                    <div
                      style={{
                        fontWeight: 700,
                        textTransform: "uppercase",
                        fontSize: 11,
                        color: "var(--ink-muted)",
                        marginBottom: 4,
                      }}
                    >
                      Physical Root Cause
                    </div>
                    <div>
                      {latestRun?.root_cause ||
                        activeRefMeta?.rootCause ||
                        "Run a diagnostic check to inspect the physical root cause."}
                    </div>
                  </div>
                  <div>
                    <div
                      style={{
                        fontWeight: 700,
                        textTransform: "uppercase",
                        fontSize: 11,
                        color: "var(--ink-muted)",
                        marginBottom: 4,
                      }}
                    >
                      Responsible Team
                    </div>
                    <div style={{ fontWeight: 600 }}>
                      {latestRun?.responsible_team ||
                        "Run a check to determine ISP vs. Regional IT ownership"}
                    </div>
                  </div>
                  <div>
                    <div
                      style={{
                        fontWeight: 700,
                        textTransform: "uppercase",
                        fontSize: 11,
                        color: "var(--ink-muted)",
                        marginBottom: 4,
                      }}
                    >
                      Automated AI Agent Workflow Action
                    </div>
                    <div>
                      {latestRun?.ai_workflow_action ||
                        activeRefMeta?.aiAction ||
                        "AI Agent executes Dual-Ping + 4G Hub Traceroute before deciding whether to escalate to ISP or Regional IT."}
                    </div>
                  </div>
                  <div>
                    <div
                      style={{
                        fontWeight: 700,
                        textTransform: "uppercase",
                        fontSize: 11,
                        color: "var(--ink-muted)",
                        marginBottom: 4,
                      }}
                    >
                      Recommended Operator Action
                    </div>
                    <div>
                      {latestRun?.operator_action ||
                        activeRefMeta?.operatorAction ||
                        "Select a branch above and click 'Run full check'."}
                    </div>
                  </div>
                </div>
              )}

              <pre
                className="kz-mono"
                style={{
                  margin: 0,
                  padding: 14,
                  minHeight: 190,
                  background: "var(--term-bg)",
                  color: "var(--term-ink)",
                  border: "1px solid var(--border)",
                  borderRadius: 10,
                  overflowX: "auto",
                  lineHeight: "19px",
                }}
              >
                {rawLog}
              </pre>
            </div>
          </section>
        </div>

        <aside
          style={{
            flex: "1 1 300px",
            maxWidth: 400,
            display: "flex",
            flexDirection: "column",
            gap: 16,
          }}
        >
          <section className="kz-card">
            <div className="kz-card-hd">
              <h2>Script settings</h2>
            </div>
            <div
              className="kz-card-bd"
              style={{
                display: "flex",
                flexDirection: "column",
                gap: 12,
                fontSize: 13,
              }}
            >
              <label
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  gap: 8,
                  fontWeight: 600,
                }}
              >
                DIAGNOSTIC_TIMEOUT_SEC
                <input
                  type="number"
                  value={timeoutSec}
                  onChange={(e) => setTimeoutSec(Number(e.target.value) || 20)}
                  style={{
                    width: 80,
                    height: 34,
                    padding: "0 8px",
                    border: "1px solid var(--border-strong)",
                    borderRadius: 8,
                    font: "500 13px var(--font-sans)",
                  }}
                />
              </label>
              <label
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  gap: 8,
                  fontWeight: 600,
                }}
              >
                Ping count
                <input
                  type="number"
                  value={pingCount}
                  onChange={(e) => setPingCount(Number(e.target.value) || 4)}
                  style={{
                    width: 80,
                    height: 34,
                    padding: "0 8px",
                    border: "1px solid var(--border-strong)",
                    borderRadius: 8,
                    font: "500 13px var(--font-sans)",
                  }}
                />
              </label>
              <label
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  gap: 8,
                  fontWeight: 600,
                }}
              >
                Traceroute max hops
                <input
                  type="number"
                  value={maxHops}
                  onChange={(e) => setMaxHops(Number(e.target.value) || 15)}
                  style={{
                    width: 80,
                    height: 34,
                    padding: "0 8px",
                    border: "1px solid var(--border-strong)",
                    borderRadius: 8,
                    font: "500 13px var(--font-sans)",
                  }}
                />
              </label>
            </div>
          </section>

          <section className="kz-card">
            <div className="kz-card-hd">
              <h2>3G / 4G hub IPs</h2>
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
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                }}
              >
                <IspBadge isp="ORANGE" />
                <span className="kz-mono">10.247.8.1</span>
              </div>
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                }}
              >
                <IspBadge isp="WE" />
                <span className="kz-mono">172.16.70.33 · 172.17.20.33</span>
              </div>
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                }}
              >
                <IspBadge isp="NOOR" />
                <span className="kz-muted">No traceroute (LAN rule)</span>
              </div>
              <a
                href="#directory"
                onClick={(e) => {
                  e.preventDefault();
                  onNavigate("Branches & ISPs");
                }}
                style={{ fontWeight: 600 }}
              >
                Edit in ISP directory
              </a>
            </div>
          </section>

          <section className="kz-card">
            <div className="kz-card-hd">
              <h2>Recent sandbox runs</h2>
            </div>
            <ul
              className="kz-card-bd"
              style={{
                margin: 0,
                listStyle: "none",
                display: "flex",
                flexDirection: "column",
                gap: 8,
                fontSize: 13,
              }}
            >
              {(catalog?.recent_runs ?? []).length === 0 ? (
                <li className="kz-muted">No sandbox runs executed yet.</li>
              ) : (
                (catalog?.recent_runs ?? []).map((r) => (
                  <li
                    key={r.id}
                    style={{ display: "flex", justifyContent: "space-between" }}
                  >
                    <span>
                      <b>{r.branch_code}</b> · {r.when}
                    </span>
                    <Badge tone={r.tone}>{r.diagnosis_code}</Badge>
                  </li>
                ))
              )}
            </ul>
          </section>
        </aside>
      </div>

      {showReferenceGuide && (
        <section className="kz-card" style={{ marginTop: 16 }}>
          <div className="kz-card-hd">
            <div>
              <h2>
                Diagnostic Result Reference &amp; Decision Tree Dictionary
              </h2>
              <p>
                Detailed explanation of every diagnostic result code, status
                pill (`IP1`, `IP2`, `4G`), ISP traceroute rule, and automated AI
                Agent action.
              </p>
            </div>
          </div>
          <div
            className="kz-card-bd"
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
              gap: 12,
            }}
          >
            {RESULT_REFERENCE_CATALOG.map((ref) => (
              <div
                key={ref.code}
                style={{
                  border: "1px solid var(--border)",
                  borderRadius: 12,
                  padding: 14,
                  background: "var(--surface-100)",
                  display: "flex",
                  flexDirection: "column",
                  gap: 8,
                  fontSize: 12,
                }}
              >
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    gap: 8,
                    flexWrap: "wrap",
                  }}
                >
                  <Badge tone={ref.tone}>{ref.code}</Badge>
                  <div style={{ display: "flex", gap: 4 }}>
                    <StatusPill label="IP1" state={ref.ip1State} />
                    <StatusPill label="IP2" state={ref.ip2State} />
                    {ref.code === "LOCAL_LOOP_DOWN_ON_4G" && (
                      <StatusPill label="4G" state="hub" />
                    )}
                  </div>
                </div>
                <div style={{ fontSize: 14, fontWeight: 700 }}>{ref.title}</div>
                <div>
                  <span className="kz-muted">Applies to ISPs:</span>{" "}
                  <b>{ref.isps}</b> ·{" "}
                  <span className="kz-muted">Traceroute:</span>{" "}
                  <span className="kz-mono">{ref.fourGState}</span>
                </div>
                <div>
                  <b>What Appears on Branch:</b> {ref.whatItMeans}
                </div>
                <div>
                  <b>Physical Root Cause:</b> {ref.rootCause}
                </div>
                <div>
                  <b>Automated AI Workflow:</b> {ref.aiAction}
                </div>
                <div>
                  <b>Operator Next Step:</b> {ref.operatorAction}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      <section className="kz-card" style={{ marginTop: 16 }}>
        <div className="kz-card-hd" style={{ flexWrap: "wrap", gap: 12 }}>
          <div>
            <h2>Full Branch Diagnostic Test Suite &amp; Report Generator</h2>
            <p>
              Execute the complete Dual-Ping (`IP 1` + `IP 2`) and `ORANGE`/`WE`
              4G Hub Traceroute suite across all active branches and generate a
              comprehensive fleet diagnostic report.
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
            <select
              aria-label="Suite ISP Filter"
              className="kz-chip"
              value={suiteIspFilter}
              onChange={(e) => setSuiteIspFilter(e.target.value)}
            >
              <option value="ALL">Target ISP: All ISPs</option>
              <option value="NOOR">Target ISP: NOOR</option>
              <option value="ORANGE">Target ISP: ORANGE</option>
              <option value="WE">Target ISP: WE</option>
            </select>

            <select
              aria-label="Suite Region Filter"
              className="kz-chip"
              value={suiteRegionFilter}
              onChange={(e) => setSuiteRegionFilter(e.target.value)}
            >
              <option value="All">Target Region: All Regions</option>
              {availableRegions.map((r) => (
                <option key={r} value={r}>
                  Region: {r}
                </option>
              ))}
            </select>

            <select
              aria-label="Suite Scenario Mode"
              className="kz-chip"
              value={suiteScenario}
              onChange={(e) => setSuiteScenario(e.target.value as ScenarioType)}
            >
              <option value="LIVE_ICMP">
                Mode: LIVE_ICMP (Real OS Ping &amp; Traceroute · 64 Workers)
              </option>
              <option value="AUTO">
                Mode: AUTO (Simulated Fleet Distribution · Instant)
              </option>
              <option value="PASS">Mode: PASS (Simulated All Healthy)</option>
              <option value="FULL_OUTAGE">
                Mode: FULL_OUTAGE (Simulated WAN Outage)
              </option>
              <option value="LOCAL_LOOP_DOWN_ON_4G">
                Mode: LOCAL_LOOP_DOWN_ON_4G (Simulated 4G Backup)
              </option>
              <option value="INTERNAL_LAN_SWITCH">
                Mode: INTERNAL_LAN_SWITCH (Simulated LAN Issue)
              </option>
            </select>

            <Button
              variant="primary"
              disabled={isSuiteRunning}
              onClick={handleRunFullSuite}
            >
              {isSuiteRunning
                ? "Running full suite…"
                : "Run full test suite & generate report"}
            </Button>
          </div>
        </div>

        <div className="kz-card-bd">
          {suiteError && (
            <div
              style={{
                marginBottom: 14,
                padding: "10px 14px",
                borderRadius: 10,
                background: "var(--critical-bg)",
                color: "var(--critical)",
                fontSize: 13,
                fontWeight: 600,
              }}
            >
              {suiteError}
            </div>
          )}
          {!suiteReport ? (
            <div
              style={{
                padding: 24,
                textAlign: "center",
                borderRadius: 10,
                background: "var(--surface-100)",
                border: "1px dashed var(--border-strong)",
              }}
            >
              <div style={{ fontSize: 15, fontWeight: 700, marginBottom: 6 }}>
                Ready to Run Full Fleet Diagnostic Test Suite
              </div>
              <p
                className="kz-muted"
                style={{ maxWidth: 640, margin: "0 auto 14px" }}
              >
                Click{" "}
                <b>&ldquo;Run full test suite &amp; generate report&rdquo;</b>{" "}
                to test all {branches.length.toLocaleString("en-US")} active
                branches in the directory and generate an interactive breakdown
                by diagnosis result, ISP, and region with CSV, Excel, and HTML
                report exports.
              </p>
              <Button
                variant="primary"
                disabled={isSuiteRunning}
                onClick={handleRunFullSuite}
              >
                {isSuiteRunning
                  ? "Running full suite…"
                  : `Execute Full Test Suite on ${branches.length.toLocaleString("en-US")} Branches`}
              </Button>
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  flexWrap: "wrap",
                  gap: 10,
                  padding: "10px 14px",
                  borderRadius: 10,
                  background: "var(--surface-100)",
                  border: "1px solid var(--border)",
                  fontSize: 13,
                }}
              >
                <div>
                  Report <b className="kz-mono">{suiteReport.suite_id}</b> ·
                  Executed on{" "}
                  <b>
                    {suiteReport.total_branches.toLocaleString("en-US")}{" "}
                    branches
                  </b>{" "}
                  in <b>{suiteReport.duration_ms} ms</b> · Scenario mode:{" "}
                  <Badge tone="brand">{suiteReport.scenario_mode}</Badge>
                </div>
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                  <Button
                    variant="secondary"
                    icon="download"
                    onClick={() => handleExportSuiteReport("csv")}
                  >
                    Export CSV Report
                  </Button>
                  <Button
                    variant="secondary"
                    icon="download"
                    onClick={() => handleExportSuiteReport("excel")}
                  >
                    Export Excel Report
                  </Button>
                  <Button
                    variant="primary"
                    icon="download"
                    onClick={() => handleExportSuiteReport("html")}
                  >
                    Download HTML Executive Report
                  </Button>
                </div>
              </div>

              <div className="kz-grid-kpi">
                <div
                  role="button"
                  tabIndex={0}
                  onClick={() => {
                    setReportDiagFilter("ALL");
                    setReportPage(1);
                  }}
                  onKeyDown={(e) =>
                    e.key === "Enter" && setReportDiagFilter("ALL")
                  }
                  style={{ cursor: "pointer" }}
                >
                  <KpiCard
                    label="Total branches tested"
                    value={suiteReport.total_branches}
                    icon="store"
                    hint={`Completed in ${suiteReport.duration_ms} ms`}
                  />
                </div>
                <div
                  role="button"
                  tabIndex={0}
                  onClick={() => {
                    setReportDiagFilter("PASS");
                    setReportPage(1);
                  }}
                  onKeyDown={(e) =>
                    e.key === "Enter" && setReportDiagFilter("PASS")
                  }
                  style={{ cursor: "pointer" }}
                >
                  <KpiCard
                    label="Healthy (PASS)"
                    value={suiteReport.pass_count}
                    icon="dashboard"
                    hint={`${suiteReport.health_pct}% of tested fleet`}
                  />
                </div>
                <div
                  role="button"
                  tabIndex={0}
                  onClick={() => {
                    setReportDiagFilter("FULL_OUTAGE");
                    setReportPage(1);
                  }}
                  onKeyDown={(e) =>
                    e.key === "Enter" && setReportDiagFilter("FULL_OUTAGE")
                  }
                  style={{ cursor: "pointer" }}
                >
                  <KpiCard
                    label="Full WAN Outage"
                    value={suiteReport.full_outage_count}
                    icon="alert"
                    tone={
                      suiteReport.full_outage_count > 0 ? "critical" : "default"
                    }
                    hint="IP1 DOWN · Escalate to ISP"
                  />
                </div>
                <div
                  role="button"
                  tabIndex={0}
                  onClick={() => {
                    setReportDiagFilter("LOCAL_LOOP_DOWN_ON_4G");
                    setReportPage(1);
                  }}
                  onKeyDown={(e) =>
                    e.key === "Enter" &&
                    setReportDiagFilter("LOCAL_LOOP_DOWN_ON_4G")
                  }
                  style={{ cursor: "pointer" }}
                >
                  <KpiCard
                    label="On 4G Backup Hub"
                    value={suiteReport.four_g_count}
                    icon="terminal"
                    tone={suiteReport.four_g_count > 0 ? "warning" : "default"}
                    hint="ORANGE / WE landline down"
                  />
                </div>
                <div
                  role="button"
                  tabIndex={0}
                  onClick={() => {
                    setReportDiagFilter("INTERNAL_LAN_SWITCH");
                    setReportPage(1);
                  }}
                  onKeyDown={(e) =>
                    e.key === "Enter" &&
                    setReportDiagFilter("INTERNAL_LAN_SWITCH")
                  }
                  style={{ cursor: "pointer" }}
                >
                  <KpiCard
                    label="Internal LAN Switch"
                    value={suiteReport.lan_switch_count}
                    icon="clock"
                    tone={
                      suiteReport.lan_switch_count > 0 ? "warning" : "default"
                    }
                    hint="IP1 UP, IP2 DOWN · Regional IT"
                  />
                </div>
              </div>

              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fit, minmax(380px, 1fr))",
                  gap: 16,
                }}
              >
                <div
                  style={{
                    border: "1px solid var(--border)",
                    borderRadius: 12,
                    overflow: "hidden",
                  }}
                >
                  <div
                    style={{
                      padding: "10px 14px",
                      background: "var(--surface-100)",
                      borderBottom: "1px solid var(--border)",
                      fontWeight: 700,
                      fontSize: 13,
                    }}
                  >
                    Breakdown by ISP (`NOOR`, `ORANGE`, `WE`)
                  </div>
                  <table className="kz-table">
                    <thead>
                      <tr>
                        <th>ISP</th>
                        <th>Total</th>
                        <th>PASS</th>
                        <th>FULL_OUTAGE</th>
                        <th>4G_BACKUP</th>
                        <th>LAN_SWITCH</th>
                        <th>Health %</th>
                      </tr>
                    </thead>
                    <tbody>
                      {suiteReport.by_isp.map((row) => (
                        <tr key={row.isp_name}>
                          <td>
                            <IspBadge isp={row.isp_name as IspName} />
                          </td>
                          <td className="kz-mono">{row.total}</td>
                          <td
                            className="kz-mono"
                            style={{ color: "var(--good)", fontWeight: 700 }}
                          >
                            {row.pass_count}
                          </td>
                          <td
                            className="kz-mono"
                            style={{
                              color:
                                row.full_outage_count > 0
                                  ? "var(--critical)"
                                  : undefined,
                            }}
                          >
                            {row.full_outage_count}
                          </td>
                          <td
                            className="kz-mono"
                            style={{
                              color:
                                row.four_g_count > 0
                                  ? "var(--warning)"
                                  : undefined,
                            }}
                          >
                            {row.four_g_count}
                          </td>
                          <td
                            className="kz-mono"
                            style={{
                              color:
                                row.lan_switch_count > 0
                                  ? "var(--warning)"
                                  : undefined,
                            }}
                          >
                            {row.lan_switch_count}
                          </td>
                          <td className="kz-mono">
                            <b>{row.health_pct}%</b>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                <div
                  style={{
                    border: "1px solid var(--border)",
                    borderRadius: 12,
                    overflow: "hidden",
                    maxHeight: 260,
                    overflowY: "auto",
                  }}
                >
                  <div
                    style={{
                      padding: "10px 14px",
                      background: "var(--surface-100)",
                      borderBottom: "1px solid var(--border)",
                      fontWeight: 700,
                      fontSize: 13,
                    }}
                  >
                    Breakdown by Region ({suiteReport.by_region.length} regions)
                  </div>
                  <table className="kz-table">
                    <thead>
                      <tr>
                        <th>Region</th>
                        <th>Total</th>
                        <th>PASS</th>
                        <th>Outage</th>
                        <th>4G</th>
                        <th>LAN</th>
                        <th>Health %</th>
                      </tr>
                    </thead>
                    <tbody>
                      {suiteReport.by_region.map((row) => (
                        <tr key={row.region}>
                          <td>
                            <b>{row.region}</b>
                          </td>
                          <td className="kz-mono">{row.total}</td>
                          <td
                            className="kz-mono"
                            style={{ color: "var(--good)", fontWeight: 700 }}
                          >
                            {row.pass_count}
                          </td>
                          <td className="kz-mono">{row.full_outage_count}</td>
                          <td className="kz-mono">{row.four_g_count}</td>
                          <td className="kz-mono">{row.lan_switch_count}</td>
                          <td className="kz-mono">
                            <b>{row.health_pct}%</b>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              <div
                style={{
                  display: "flex",
                  gap: 8,
                  flexWrap: "wrap",
                  alignItems: "center",
                  padding: "10px 12px",
                  borderRadius: 10,
                  background: "var(--surface-100)",
                  border: "1px solid var(--border)",
                }}
              >
                <label className="kz-search" style={{ maxWidth: 280 }}>
                  <span className="kz-muted">Search</span>
                  <input
                    type="search"
                    value={reportSearch}
                    onChange={(e) => {
                      setReportSearch(e.target.value);
                      setReportPage(1);
                    }}
                    placeholder="SAP code, branch name, IP…"
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
                  aria-label="Filter Report by Diagnosis"
                  className="kz-chip"
                  value={reportDiagFilter}
                  onChange={(e) => {
                    setReportDiagFilter(e.target.value);
                    setReportPage(1);
                  }}
                >
                  <option value="ALL">Result: All ({suiteReport.total_branches})</option>
                  <option value="PASS">PASS ({suiteReport.pass_count})</option>
                  <option value="FULL_OUTAGE">
                    FULL_OUTAGE ({suiteReport.full_outage_count})
                  </option>
                  <option value="LOCAL_LOOP_DOWN_ON_4G">
                    LOCAL_LOOP_DOWN_ON_4G ({suiteReport.four_g_count})
                  </option>
                  <option value="INTERNAL_LAN_SWITCH">
                    INTERNAL_LAN_SWITCH ({suiteReport.lan_switch_count})
                  </option>
                </select>

                <select
                  aria-label="Filter Report by ISP"
                  className="kz-chip"
                  value={reportIspFilter}
                  onChange={(e) => {
                    setReportIspFilter(e.target.value);
                    setReportPage(1);
                  }}
                >
                  <option value="ALL">ISP: All</option>
                  <option value="NOOR">NOOR</option>
                  <option value="ORANGE">ORANGE</option>
                  <option value="WE">WE</option>
                </select>

                <select
                  aria-label="Filter Report by Region"
                  className="kz-chip"
                  value={reportRegionFilter}
                  onChange={(e) => {
                    setReportRegionFilter(e.target.value);
                    setReportPage(1);
                  }}
                >
                  <option value="All">Region: All</option>
                  {suiteReport.by_region.map((r) => (
                    <option key={r.region} value={r.region}>
                      {r.region} ({r.total})
                    </option>
                  ))}
                </select>

                <span className="kz-tcard-meta" style={{ marginLeft: "auto" }}>
                  Showing {filteredSuiteItems.length.toLocaleString("en-US")}{" "}
                  matching branches
                </span>
              </div>

              <div
                style={{
                  border: "1px solid var(--border)",
                  borderRadius: 12,
                  overflowX: "auto",
                }}
              >
                <table className="kz-table">
                  <thead>
                    <tr>
                      <th>SAP Code</th>
                      <th>Branch &amp; Region</th>
                      <th>ISP</th>
                      <th>Check Pills (`IP1` / `IP2` / `4G`)</th>
                      <th>Diagnosis Result &amp; Meaning</th>
                      <th>Detailed Root Cause &amp; Responsible Team</th>
                      <th style={{ textAlign: "right" }}>Inspect</th>
                    </tr>
                  </thead>
                  <tbody>
                    {paginatedSuiteItems.map((item) => (
                      <tr key={item.branch_code}>
                        <td className="kz-mono" style={{ fontWeight: 700 }}>
                          {item.branch_code}
                        </td>
                        <td>
                          <b>{item.branch_name}</b>
                          <div className="kz-tcard-meta">
                            {item.region} · L.L: {item.ll_circuit_id || "—"}
                          </div>
                        </td>
                        <td>
                          <IspBadge isp={item.isp_name as IspName} />
                        </td>
                        <td>
                          <div
                            style={{
                              display: "flex",
                              gap: 4,
                              flexWrap: "wrap",
                              marginBottom: 4,
                            }}
                          >
                            {item.checks.map((c, idx) => (
                              <StatusPill
                                key={idx}
                                label={c.label}
                                state={c.state}
                              />
                            ))}
                          </div>
                          <div className="kz-mono kz-muted" style={{ fontSize: 11 }}>
                            IP1: {item.ip_1} · IP2: {item.ip_2}
                          </div>
                        </td>
                        <td style={{ maxWidth: 280 }}>
                          <div style={{ marginBottom: 4 }}>
                            <Badge tone={diagnosisBadgeTone(item.diagnosis_code)}>
                              {item.diagnosis_code}
                            </Badge>
                          </div>
                          <div style={{ fontWeight: 600, fontSize: 12 }}>
                            {item.diagnosis_title}
                          </div>
                          <div className="kz-tcard-meta">{item.meaning}</div>
                        </td>
                        <td style={{ maxWidth: 340, fontSize: 12 }}>
                          <div style={{ marginBottom: 4 }}>
                            {item.root_cause}
                          </div>
                          <div className="kz-tcard-meta">
                            <b>Owner:</b> {item.responsible_team}
                          </div>
                        </td>
                        <td style={{ textAlign: "right" }}>
                          <Button
                            variant="secondary"
                            size="sm"
                            onClick={() => handleInspectSuiteItem(item)}
                          >
                            Inspect
                          </Button>
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
                  flexWrap: "wrap",
                  gap: 10,
                  fontSize: 13,
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span className="kz-muted">Rows per page:</span>
                  <select
                    className="kz-chip"
                    value={reportPageSize}
                    onChange={(e) => {
                      setReportPageSize(Number(e.target.value));
                      setReportPage(1);
                    }}
                  >
                    <option value={25}>25</option>
                    <option value={50}>50</option>
                    <option value={100}>100</option>
                    <option value={250}>250</option>
                  </select>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <Button
                    variant="secondary"
                    size="sm"
                    disabled={reportPage <= 1}
                    onClick={() => setReportPage((p) => Math.max(1, p - 1))}
                  >
                    Previous
                  </Button>
                  <span className="kz-mono">
                    Page {reportPage} of {totalReportPages}
                  </span>
                  <Button
                    variant="secondary"
                    size="sm"
                    disabled={reportPage >= totalReportPages}
                    onClick={() =>
                      setReportPage((p) => Math.min(totalReportPages, p + 1))
                    }
                  >
                    Next
                  </Button>
                </div>
              </div>
            </div>
          )}
        </div>
      </section>
    </AppShell>
  );
}
