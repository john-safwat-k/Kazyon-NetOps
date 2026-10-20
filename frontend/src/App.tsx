import React, { useEffect, useState } from "react";
import { Activity, Building2, Cpu, Mail, ShieldCheck, Terminal, Ticket } from "lucide-react";

interface HealthPayload {
  status: string;
  service: string;
  environment: string;
  env_slug: string;
  version: string;
  vllm_base_url: string;
  vllm_model: string;
}

const KANBAN_COLUMNS = [
  { id: "NEW", label: "New / Ingested", count: 0 },
  { id: "DIAGNOSING", label: "Diagnosing", count: 0 },
  { id: "ESCALATED_TO_ISP", label: "Escalated to ISP", count: 0 },
  { id: "VERIFYING", label: "Verifying Fix", count: 0 },
  { id: "AWAITING_BRANCH_CONFIRMATION", label: "Awaiting Branch", count: 0 },
  { id: "RESOLVED", label: "Resolved / Closed", count: 0 },
];

export default function App() {
  const [health, setHealth] = useState<HealthPayload | null>(null);

  useEffect(() => {
    fetch("/api/health")
      .then((res) => res.json())
      .then((data: HealthPayload) => setHealth(data))
      .catch(() => setHealth(null));
  }, []);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      <header className="border-b border-slate-800 bg-slate-900/80 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-lg bg-indigo-600/20 border border-indigo-500/40 flex items-center justify-center text-indigo-400">
            <Activity className="h-5 w-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-lg font-semibold tracking-tight text-white">
                IT Network Support AI Agent
              </h1>
              <span className="px-2 py-0.5 text-xs font-mono uppercase rounded bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                {health?.env_slug ?? "dev"}
              </span>
            </div>
            <p className="text-xs text-slate-400">
              Autonomous Branch Troubleshooting, ISP Escalation &amp; Jira-Style Ticketing Harness
            </p>
          </div>
        </div>

        <div className="flex items-center gap-4 text-xs">
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-slate-950 border border-slate-800">
            <Cpu className="h-4 w-4 text-emerald-400" />
            <span className="text-slate-400">vLLM:</span>
            <span className="font-mono text-slate-200">
              {health?.vllm_model ?? "google/gemma-4-26B-A4B-it"}
            </span>
          </div>
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-slate-950 border border-slate-800">
            <span
              className={`h-2 w-2 rounded-full ${
                health?.status === "ok" ? "bg-emerald-400" : "bg-amber-400"
              }`}
            />
            <span className="text-slate-300">
              {health?.status === "ok" ? "API Connected" : "Connecting..."}
            </span>
          </div>
        </div>
      </header>

      <main className="flex-1 p-6 space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 flex items-center gap-3">
            <Ticket className="h-5 w-5 text-indigo-400" />
            <div>
              <div className="text-xs text-slate-400">Jira-Style Ticketing Board</div>
              <div className="text-sm font-medium text-white">Full Lifecycle Tracking</div>
            </div>
          </div>
          <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 flex items-center gap-3">
            <Terminal className="h-5 w-5 text-emerald-400" />
            <div>
              <div className="text-xs text-slate-400">Diagnostic Harness</div>
              <div className="text-sm font-medium text-white">Sandboxed Script Runner</div>
            </div>
          </div>
          <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 flex items-center gap-3">
            <Mail className="h-5 w-5 text-sky-400" />
            <div>
              <div className="text-xs text-slate-400">Dual Email Threads</div>
              <div className="text-sm font-medium text-white">Branch &amp; ISP Chaser Loop</div>
            </div>
          </div>
          <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 flex items-center gap-3">
            <Building2 className="h-5 w-5 text-amber-400" />
            <div>
              <div className="text-xs text-slate-400">Branch &amp; RBAC Directory</div>
              <div className="text-sm font-medium text-white">Sheet Seeding &amp; Permissions</div>
            </div>
          </div>
        </div>

        <section>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-400">
              Network Incident Kanban Board
            </h2>
            <div className="flex items-center gap-2 text-xs text-slate-400">
              <ShieldCheck className="h-4 w-4 text-indigo-400" />
              <span>Permission-Based RBAC Active</span>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-6 gap-4">
            {KANBAN_COLUMNS.map((col) => (
              <div
                key={col.id}
                className="rounded-xl bg-slate-900/50 border border-slate-800/80 p-3 min-h-[360px] flex flex-col"
              >
                <div className="flex items-center justify-between pb-2 mb-3 border-b border-slate-800">
                  <span className="text-xs font-semibold text-slate-200">{col.label}</span>
                  <span className="px-2 py-0.5 text-xs rounded-full bg-slate-800 text-slate-400">
                    {col.count}
                  </span>
                </div>
                <div className="flex-1 flex items-center justify-center text-xs text-slate-600 border border-dashed border-slate-800/60 rounded-lg">
                  No tickets in {col.label}
                </div>
              </div>
            ))}
          </div>
        </section>
      </main>
    </div>
  );
}
