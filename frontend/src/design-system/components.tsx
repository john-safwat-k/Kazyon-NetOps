import React, { useRef, useState } from "react";
import clsx from "clsx";
import {
  BadgeTone,
  CheckState,
  HealthServiceState,
  IspName,
  KpiTone,
  PRIORITY_TONE,
  ThemeMode,
  TicketPriority,
} from "./tokens";

/* ---------- Icons (24px viewBox, 1.75 stroke) ---------- */
export type IconName =
  | "dashboard"
  | "board"
  | "list"
  | "replication"
  | "alert"
  | "mail"
  | "terminal"
  | "store"
  | "users"
  | "settings"
  | "search"
  | "clock"
  | "ticket"
  | "bot"
  | "pause"
  | "plus"
  | "filter"
  | "download"
  | "play"
  | "bell"
  | "chevron"
  | "sun"
  | "moon"
  | "x";

const ICON_PATHS: Record<IconName, string> = {
  dashboard: "M3 13h8V3H3zM13 21h8V11h-8zM3 21h8v-6H3zM13 3v6h8V3z",
  board: "M4 4h4v16H4zM10 4h4v10h-4zM16 4h4v13h-4z",
  list: "M8 6h13M8 12h13M8 18h13M3.5 6h.01M3.5 12h.01M3.5 18h.01",
  replication: "M21 12a9 9 0 1 1-3-6.7L21 8M21 3v5h-5",
  alert:
    "M12 9v4M12 17h.01M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z",
  mail: "M4 5h16a1 1 0 0 1 1 1v12a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1zM3 7l9 6 9-6",
  terminal: "M4 17l6-6-6-6M12 19h8",
  store: "M3 9l1.5-5h15L21 9M3 9v11h18V9M3 9h18M9 20v-6h6v6",
  users:
    "M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM22 21v-2a4 4 0 0 0-3-3.9M16 3.1a4 4 0 0 1 0 7.8",
  settings:
    "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0-4h-.1a1.7 1.7 0 0 0-1.5 1z",
  search: "M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16zM21 21l-4.3-4.3",
  clock: "M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20zM12 6v6l4 2",
  ticket:
    "M3 7a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v3a2 2 0 0 0 0 4v3a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-3a2 2 0 0 0 0-4zM13 5v2M13 17v2M13 11v2",
  bot: "M12 8V4H8M4 8h16v12H4zM2 14h2M20 14h2M9 13v2M15 13v2",
  pause: "M10 4H6v16h4zM18 4h-4v16h4z",
  plus: "M12 5v14M5 12h14",
  filter: "M22 3H2l8 9.5V19l4 2v-8.5z",
  download: "M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3",
  play: "M6 4l14 8-14 8z",
  bell: "M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9M13.7 21a2 2 0 0 1-3.4 0",
  chevron: "M6 9l6 6 6-6",
  sun: "M12 16a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4",
  moon: "M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z",
  x: "M18 6L6 18M6 6l12 12",
};

export interface IconProps {
  name: IconName;
  size?: number;
  className?: string;
}

export function Icon({ name, size = 20, className }: IconProps) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      width={size}
      height={size}
      className={className}
    >
      <path d={ICON_PATHS[name] || ""} />
    </svg>
  );
}

/* ---------- Atoms ---------- */
export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  /** Visual weight. One primary per view. */
  variant?: "primary" | "secondary" | "ghost" | "danger";
  size?: "md" | "sm";
  icon?: IconName;
}

export function Button({
  variant = "secondary",
  size = "md",
  icon,
  className,
  children,
  ...rest
}: ButtonProps) {
  return (
    <button
      {...rest}
      className={clsx(
        "kz-btn",
        `kz-btn-${variant}`,
        size === "sm" && "kz-btn-sm",
        className,
      )}
    >
      {icon ? <Icon name={icon} /> : null}
      {children}
    </button>
  );
}

export interface BadgeProps {
  tone?: BadgeTone;
  children?: React.ReactNode;
  className?: string;
}

export function Badge({ tone = "neutral", children, className }: BadgeProps) {
  return (
    <span className={clsx("kz-badge", `kz-badge-${tone}`, className)}>
      {children}
    </span>
  );
}

export interface IspBadgeProps {
  isp: IspName;
  /** ISP case / request number */
  caseRef?: string;
}

export function IspBadge({ isp = "NOOR", caseRef }: IspBadgeProps) {
  const normalized = isp.toUpperCase() as IspName;
  return (
    <span className={clsx("kz-isp", `kz-isp-${normalized}`)}>
      <i>{normalized.charAt(0)}</i>
      {normalized}
      {caseRef ? (
        <span
          className="kz-mono kz-muted"
          style={{ fontWeight: 500, letterSpacing: 0 }}
        >
          #{caseRef}
        </span>
      ) : null}
    </span>
  );
}

export interface StatusPillProps {
  label: "IP1" | "IP2" | "4G" | string;
  state: CheckState;
  title?: string;
}

const CHECK_STATE_WORDS: Record<CheckState, string> = {
  up: "UP",
  down: "DOWN",
  hub: "BACKUP",
  skip: "SKIPPED",
};

export function StatusPill({ label, state = "up", title }: StatusPillProps) {
  return (
    <span className={clsx("kz-pill", `kz-pill-${state}`)} title={title}>
      <b>{label}</b> {CHECK_STATE_WORDS[state]}
    </span>
  );
}

function formatDurationMinutes(minutes: number): string {
  const m = Math.abs(Math.round(minutes));
  const hh = Math.floor(m / 60);
  const mm = m % 60;
  return `${hh ? `${hh}h ` : ""}${mm < 10 && hh ? "0" : ""}${mm}m`;
}

export interface SlaTimerProps {
  /** negative = overdue */
  minutesLeft: number;
  /** 120 welcome, 300 follow-up */
  totalMinutes?: number;
  label?: string;
}

export function SlaTimer({
  minutesLeft,
  totalMinutes = 120,
  label,
}: SlaTimerProps) {
  const state =
    minutesLeft < 0
      ? "over"
      : minutesLeft / totalMinutes < 0.25
        ? "risk"
        : "ok";
  const pct = Math.max(0, Math.min(100, (1 - minutesLeft / totalMinutes) * 100));
  const text =
    minutesLeft < 0
      ? `Overdue ${formatDurationMinutes(minutesLeft)}`
      : `${formatDurationMinutes(minutesLeft)} left`;

  return (
    <span className={clsx("kz-sla", `kz-sla-${state}`)}>
      <Icon name="clock" size={14} />
      {label ? (
        <span className="kz-muted" style={{ fontWeight: 500 }}>
          {label}
        </span>
      ) : null}
      <span className="kz-sla-track">
        <span
          className="kz-sla-fill"
          style={{ width: `${pct}%`, display: "block" }}
        />
      </span>
      <span className="kz-num">{text}</span>
    </span>
  );
}

/* ---------- Molecules ---------- */
export interface KpiCardProps {
  label: string;
  value: React.ReactNode;
  icon?: IconName;
  delta?: string;
  hint?: string;
  tone?: KpiTone;
}

export function KpiCard({
  label,
  value,
  icon = "ticket",
  delta,
  hint,
  tone = "default",
}: KpiCardProps) {
  return (
    <div
      className={clsx(
        "kz-card",
        "kz-kpi",
        tone !== "default" && `kz-kpi-${tone}`,
      )}
    >
      <div className="kz-kpi-top">
        <span className="kz-kpi-label">{label}</span>
        <span className="kz-kpi-ic">
          <Icon name={icon} />
        </span>
      </div>
      <div className="kz-kpi-val">{value}</div>
      <div className="kz-kpi-ft">
        {delta ? (
          <span
            className={
              delta.charAt(0) === "+" ? "kz-delta-up" : "kz-delta-down"
            }
          >
            {delta}
          </span>
        ) : null}
        {hint}
      </div>
    </div>
  );
}

export interface Ticket {
  id: string;
  priority: TicketPriority;
  branch: string;
  region: string;
  failure?: string;
  isp: IspName;
  caseRef?: string;
  checks?: [string, CheckState][];
  sla?: [number, number];
  note?: string;
  aiPaused?: boolean;
  status?: string;
  col?: number;
}

export interface TicketCardProps {
  ticket: Ticket;
  onClick?: (ticket: Ticket) => void;
}

export function TicketCard({ ticket, onClick }: TicketCardProps) {
  return (
    <div
      className="kz-tcard"
      onClick={onClick ? () => onClick(ticket) : undefined}
    >
      <div className="kz-tcard-top">
        <span className="kz-tcard-id">{ticket.id}</span>
        <Badge tone={PRIORITY_TONE[ticket.priority] || "neutral"}>
          {ticket.priority}
        </Badge>
      </div>
      <p className="kz-tcard-title">{ticket.branch}</p>
      <div className="kz-tcard-meta">
        {ticket.region}
        {ticket.failure ? ` · ${ticket.failure}` : ""}
      </div>
      <div className="kz-row" style={{ gap: 6 }}>
        <IspBadge isp={ticket.isp} caseRef={ticket.caseRef} />
      </div>
      {ticket.checks ? (
        <div className="kz-tcard-pills">
          {ticket.checks.map(([lbl, st], idx) => (
            <StatusPill key={idx} label={lbl} state={st} />
          ))}
        </div>
      ) : null}
      <div className="kz-tcard-ft">
        {ticket.sla ? (
          <SlaTimer
            minutesLeft={ticket.sla[0]}
            totalMinutes={ticket.sla[1]}
          />
        ) : (
          <span className="kz-tcard-meta">{ticket.note || ""}</span>
        )}
        <span className={clsx("kz-ai", ticket.aiPaused && "kz-ai-paused")}>
          <Icon name={ticket.aiPaused ? "pause" : "bot"} size={14} />
          {ticket.aiPaused ? "AI paused" : "AI active"}
        </span>
      </div>
    </div>
  );
}

export interface HealthServiceItem {
  name: string;
  detail?: string;
  state?: HealthServiceState;
}

export interface HealthBarProps {
  services: HealthServiceItem[];
}

const HEALTH_STATE_LABELS: Record<HealthServiceState, string> = {
  ok: "Healthy",
  degraded: "Degraded",
  down: "Down",
};

export function HealthBar({ services }: HealthBarProps) {
  return (
    <div className="kz-health" role="status">
      {services.map((service, idx) => {
        const state = service.state || "ok";
        return (
          <div
            key={idx}
            className={clsx("kz-health-item", `kz-health-${state}`)}
          >
            <span className="kz-health-dot" />
            <div style={{ minWidth: 0 }}>
              <div className="kz-health-name">{service.name}</div>
              <div className="kz-health-detail">{service.detail}</div>
            </div>
            <span className="kz-health-state">
              {HEALTH_STATE_LABELS[state]}
            </span>
          </div>
        );
      })}
    </div>
  );
}

export interface BarChartDatum {
  label: string;
  value: number;
  hint?: string;
}

export interface BarChartProps {
  data: BarChartDatum[];
  unit?: string;
  max?: number;
}

export function BarChart({ data, unit = "", max }: BarChartProps) {
  const computedMax =
    max || Math.max(...data.map((d) => d.value), 1);
  const [tip, setTip] = useState<{
    x: number;
    y: number;
    d: BarChartDatum;
  } | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);

  return (
    <div
      className="kz-bars"
      ref={containerRef}
      onMouseLeave={() => setTip(null)}
    >
      {data.map((d, idx) => (
        <div
          key={idx}
          className="kz-bar-row"
          tabIndex={0}
          aria-label={`${d.label}: ${d.value}${unit}`}
          onMouseMove={(e) => {
            if (!containerRef.current) return;
            const rect = containerRef.current.getBoundingClientRect();
            setTip({
              x: e.clientX - rect.left,
              y: e.currentTarget.offsetTop - 4,
              d,
            });
          }}
        >
          <span className="kz-bar-label">{d.label}</span>
          <span className="kz-bar-track">
            <span
              className="kz-bar-fill"
              style={{
                width: `${(d.value / computedMax) * 100}%`,
                display: "block",
              }}
            />
          </span>
          <span className="kz-bar-val">
            {d.value}
            {unit}
          </span>
        </div>
      ))}
      {tip ? (
        <div
          className="kz-tip"
          style={{ left: tip.x, top: tip.y }}
        >
          <b>{tip.d.label}</b> · {tip.d.value}
          {unit}
          {tip.d.hint ? ` · ${tip.d.hint}` : ""}
        </div>
      ) : null}
    </div>
  );
}

/* ---------- AppShell ---------- */
export type NavSectionItem = [IconName, string, string?];

export const NAV_SECTIONS: [string, NavSectionItem[]][] = [
  [
    "Operate",
    [
      ["dashboard", "Dashboard"],
      ["board", "Kanban Board"],
      ["list", "Tickets List"],
      ["alert", "Human Review", "4"],
      ["replication", "Replication Monitor", "12"],
      ["mail", "Mailbox & Triage"],
    ],
  ],
  [
    "Tools",
    [
      ["terminal", "Diagnostics Sandbox"],
      ["store", "Branches & ISPs"],
    ],
  ],
  [
    "Admin",
    [
      ["users", "Users & Roles"],
      ["settings", "AI & SLA Settings"],
    ],
  ],
];

export interface AppShellProps {
  active?: string;
  /** nav label → link (e.g. a prototype screen) */
  hrefs?: Record<string, string>;
  onNavigate?: (label: string) => void;
  theme?: ThemeMode;
  onToggleTheme?: () => void;
  env?: string;
  initials?: string;
  userDisplayName?: string;
  userRoleLabel?: string;
  onLogout?: () => void;
  canAccessNav?: (label: string) => boolean;
  children?: React.ReactNode;
  style?: React.CSSProperties;
}

export function AppShell({
  active = "Dashboard",
  hrefs,
  onNavigate,
  theme,
  onToggleTheme,
  env = "PROD :8084",
  initials = "JS",
  userDisplayName,
  userRoleLabel,
  onLogout,
  canAccessNav,
  children,
  style,
}: AppShellProps) {
  const isDark = theme === "dark";

  return (
    <div
      className="kz kz-shell"
      style={style}
      data-theme={theme || undefined}
    >
      <aside className="kz-side">
        <div className="kz-brand">
          <span className="kz-logo">K</span>
          <div>
            <b>Kazyon NetOps</b>
            <span>IT Network Support Agent</span>
          </div>
        </div>
        {NAV_SECTIONS.map(([sectionTitle, items]) => {
          const visibleItems = canAccessNav
            ? items.filter(([, label]) => canAccessNav(label))
            : items;
          if (visibleItems.length === 0) return null;
          return (
            <React.Fragment key={sectionTitle}>
              <div className="kz-nav-sec">{sectionTitle}</div>
              {visibleItems.map(([iconName, label, badgeCount]) => {
                const href = hrefs?.[label];
                const isActive = label === active;
                return (
                  <a
                    key={label}
                    href={href || "#"}
                    aria-current={isActive ? "page" : undefined}
                    className={clsx("kz-nav", isActive && "kz-nav-on")}
                    onClick={(e) => {
                      if (onNavigate) {
                        e.preventDefault();
                        onNavigate(label);
                      } else if (!href) {
                        e.preventDefault();
                      }
                    }}
                  >
                    <Icon name={iconName} />
                    {label}
                    {badgeCount ? (
                      <span
                        className={clsx(
                          "kz-nav-count",
                          iconName === "alert" && "kz-nav-count-alert",
                        )}
                      >
                        {badgeCount}
                      </span>
                    ) : null}
                  </a>
                );
              })}
            </React.Fragment>
          );
        })}
      </aside>
      <div className="kz-main">
        <header className="kz-top">
          <div className="kz-search">
            <Icon name="search" />
            Search branch, ticket, circuit ID…
          </div>
          <span style={{ flex: 1 }} />
          <span className="kz-live">Live</span>
          <span className="kz-env">{env}</span>
          {onToggleTheme ? (
            <Button
              variant="ghost"
              icon={isDark ? "sun" : "moon"}
              aria-label={
                isDark ? "Switch to light mode" : "Switch to dark mode"
              }
              aria-pressed={isDark}
              onClick={onToggleTheme}
            />
          ) : null}
          <Button variant="ghost" icon="bell" aria-label="Notifications" />
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
            }}
          >
            <span className="kz-avatar" title={userDisplayName || undefined}>
              {initials}
            </span>
            {userDisplayName ? (
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  lineHeight: "14px",
                  fontSize: 12,
                }}
              >
                <b style={{ fontWeight: 600 }}>{userDisplayName}</b>
                {userRoleLabel ? (
                  <span className="kz-muted" style={{ fontSize: 11 }}>
                    {userRoleLabel}
                  </span>
                ) : null}
              </div>
            ) : null}
            {onLogout ? (
              <Button
                variant="ghost"
                size="sm"
                onClick={onLogout}
                aria-label="Sign out"
              >
                Sign out
              </Button>
            ) : null}
          </div>
        </header>
        <main className="kz-page">{children}</main>
      </div>
    </div>
  );
}

/* ---------- Sample Tickets & Reference Screens ---------- */
export const SAMPLE_TICKETS: Ticket[] = [
  {
    id: "NET-1058",
    priority: "CRITICAL",
    branch: "2009-Kafr Nasar",
    region: "Giza",
    failure: "Full outage",
    isp: "NOOR",
    caseRef: "244010",
    checks: [
      ["IP1", "down"],
      ["IP2", "skip"],
    ],
    sla: [-34, 120],
    status: "Escalated · Welcome",
    col: 3,
  },
  {
    id: "NET-1057",
    priority: "HIGH",
    branch: "1173-Ghmrawy",
    region: "Cairo",
    failure: "Local loop down (4G)",
    isp: "ORANGE",
    caseRef: "1-1312322942540",
    checks: [
      ["IP1", "up"],
      ["IP2", "down"],
      ["4G", "hub"],
    ],
    sla: [52, 300],
    status: "With ISP",
    col: 4,
  },
  {
    id: "NET-1055",
    priority: "HIGH",
    branch: "1254-El Mansheya",
    region: "Behera",
    failure: "Full outage",
    isp: "WE",
    caseRef: "8407532",
    checks: [
      ["IP1", "down"],
      ["IP2", "skip"],
    ],
    sla: [18, 120],
    status: "Escalated · Welcome",
    col: 3,
  },
  {
    id: "NET-1054",
    priority: "MEDIUM",
    branch: "1450-Soliman Metwaly",
    region: "Assyut",
    note: "Replication: Not Updated",
    isp: "NOOR",
    status: "Awaiting Regional IT",
    col: 0,
  },
  {
    id: "NET-1053",
    priority: "MEDIUM",
    branch: "1088-Gamal Salem",
    region: "New October",
    note: "Replication: Not Updated",
    isp: "ORANGE",
    status: "Awaiting Regional IT",
    col: 0,
  },
  {
    id: "NET-1052",
    priority: "HIGH",
    branch: "1312-Damanhour 3",
    region: "Behera",
    failure: "Router photo check",
    isp: "NOOR",
    note: "Vision: analysing photo",
    status: "Diagnosing",
    col: 1,
  },
  {
    id: "NET-1051",
    priority: "LOW",
    branch: "1201-Hadayek El Ahram",
    region: "Giza",
    failure: "Internal switch",
    isp: "NOOR",
    checks: [
      ["IP1", "up"],
      ["IP2", "down"],
    ],
    note: "Returned to GITSupport",
    status: "Internal LAN",
    col: 2,
  },
  {
    id: "NET-1049",
    priority: "CRITICAL",
    branch: "1005-Tosson",
    region: "Behera",
    failure: "Quota consumed",
    isp: "WE",
    caseRef: "8400809",
    aiPaused: true,
    note: "Engineer notified",
    status: "Needs review",
    col: 6,
  },
  {
    id: "NET-1047",
    priority: "MEDIUM",
    branch: "1366-Nasr City 7",
    region: "Cairo",
    failure: "Full outage",
    isp: "NOOR",
    caseRef: "243881",
    checks: [
      ["IP1", "up"],
      ["IP2", "up"],
    ],
    note: "Re-pinging after ISP closure",
    status: "Verifying",
    col: 5,
  },
  {
    id: "NET-1046",
    priority: "HIGH",
    branch: "1420-Sheikh Zayed 2",
    region: "New October",
    failure: "Site contact unreachable",
    isp: "NOOR",
    caseRef: "243860",
    sla: [210, 300],
    status: "With ISP",
    col: 4,
  },
  {
    id: "NET-1044",
    priority: "LOW",
    branch: "1099-Kafr El Dawar",
    region: "Behera",
    failure: "Cables",
    isp: "NOOR",
    checks: [
      ["IP1", "up"],
      ["IP2", "up"],
    ],
    note: "Closed 08:14",
    status: "Resolved",
    col: 7,
  },
  {
    id: "NET-1041",
    priority: "HIGH",
    branch: "1510-Abnoub",
    region: "Assyut",
    failure: "MSAN migration",
    isp: "WE",
    aiPaused: true,
    note: "Engineer notified",
    status: "Needs review",
    col: 6,
  },
];

export interface DashboardScreenProps {
  style?: React.CSSProperties;
  theme?: ThemeMode;
  onToggleTheme?: () => void;
  onNavigate?: (label: string) => void;
  env?: string;
  services?: HealthServiceItem[];
  initials?: string;
  userDisplayName?: string;
  userRoleLabel?: string;
  onLogout?: () => void;
  canAccessNav?: (label: string) => boolean;
}

export function DashboardScreen({
  style,
  theme,
  onToggleTheme,
  onNavigate,
  env,
  services,
  initials,
  userDisplayName,
  userRoleLabel,
  onLogout,
  canAccessNav,
}: DashboardScreenProps) {
  const [range, setRange] = useState<"24h" | "7d" | "30d">("7d");
  const watchlist = SAMPLE_TICKETS.filter((t) => t.sla).sort(
    (a, b) => (a.sla?.[0] ?? 0) - (b.sla?.[0] ?? 0),
  );

  const defaultServices: HealthServiceItem[] = services ?? [
    {
      name: "vLLM · Gemma 4 26B",
      detail: "10.100.109.9:8002 · 412 ms",
      state: "ok",
    },
    {
      name: "IMAP / SMTP Mailbox",
      detail: "Last poll 14 s ago",
      state: "ok",
    },
    { name: "PostgreSQL 16", detail: ":5434 · 18 conn", state: "ok" },
    { name: "Redis 7", detail: ":6384 · queue depth 9", state: "degraded" },
  ];

  return (
    <AppShell
      active="Dashboard"
      style={style}
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
          <h1>Executive &amp; SLA Dashboard</h1>
          <p>
            1,150 branches · NOOR, ORANGE, WE · Updated 11:24 Cairo time
          </p>
        </div>
        <div className="kz-row">
          <div className="kz-seg" role="group" aria-label="Time range">
            <button
              className={range === "24h" ? "on" : ""}
              onClick={() => setRange("24h")}
            >
              Today
            </button>
            <button
              className={range === "7d" ? "on" : ""}
              onClick={() => setRange("7d")}
            >
              7 days
            </button>
            <button
              className={range === "30d" ? "on" : ""}
              onClick={() => setRange("30d")}
            >
              30 days
            </button>
          </div>
          <Button variant="secondary" icon="download">
            Export
          </Button>
          <Button variant="primary" icon="plus">
            New ticket
          </Button>
        </div>
      </div>

      <HealthBar services={defaultServices} />

      <div className="kz-grid-kpi">
        <KpiCard
          label="Open tickets"
          value={37}
          icon="ticket"
          delta="+6"
          hint="vs. yesterday"
        />
        <KpiCard
          label="Needs human review"
          value={4}
          icon="alert"
          tone="critical"
          hint="Quota, MSAN, unknown mail"
        />
        <KpiCard
          label="Overdue 2h welcome"
          value={3}
          icon="mail"
          tone="warning"
          hint="ISP has not opened a case"
        />
        <KpiCard
          label="Overdue 4–6h update"
          value={5}
          icon="clock"
          tone="warning"
          hint="Chasers sent automatically"
        />
        <KpiCard
          label="Not updated today"
          value={12}
          icon="replication"
          delta="-3"
          hint="Replication Dashboard 09:00"
        />
      </div>

      <div className="kz-grid-3">
        <div className="kz-card">
          <div className="kz-card-hd">
            <div>
              <h2>Outages by ISP</h2>
              <p>Tickets opened, last 7 days</p>
            </div>
          </div>
          <div className="kz-card-bd">
            <BarChart
              data={[
                { label: "NOOR", value: 64, hint: "906 stores" },
                { label: "ORANGE", value: 21, hint: "181 stores" },
                { label: "WE", value: 9, hint: "63 stores" },
              ]}
            />
          </div>
        </div>
        <div className="kz-card">
          <div className="kz-card-hd">
            <div>
              <h2>MTTR by ISP</h2>
              <p>Mean hours, escalation → verified fix</p>
            </div>
          </div>
          <div className="kz-card-bd">
            <BarChart
              unit="h"
              data={[
                { label: "NOOR", value: 5.8 },
                { label: "ORANGE", value: 7.2 },
                { label: "WE", value: 9.4 },
              ]}
            />
          </div>
        </div>
        <div className="kz-card">
          <div className="kz-card-hd">
            <div>
              <h2>Outages by failure type</h2>
              <p>Diagnosis from dual-ping &amp; traceroute</p>
            </div>
          </div>
          <div className="kz-card-bd">
            <BarChart
              data={[
                { label: "Full outage", value: 41 },
                { label: "4G / LL down", value: 23 },
                { label: "Internal switch", value: 19 },
                { label: "Cables", value: 11 },
              ]}
            />
          </div>
        </div>
      </div>

      <div className="kz-grid-main">
        <div className="kz-card" style={{ overflow: "hidden" }}>
          <div className="kz-card-hd" style={{ paddingBottom: 12 }}>
            <div>
              <h2>SLA watchlist</h2>
              <p>Tickets waiting on an ISP, most urgent first</p>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onNavigate?.("Kanban Board")}
            >
              Open board
            </Button>
          </div>
          <table className="kz-table">
            <thead>
              <tr>
                {["Ticket", "Branch", "ISP", "Checks", "Stage", "SLA"].map(
                  (col) => (
                    <th key={col}>{col}</th>
                  ),
                )}
              </tr>
            </thead>
            <tbody>
              {watchlist.map((t) => (
                <tr key={t.id}>
                  <td>
                    <span className="kz-tcard-id">{t.id}</span>
                  </td>
                  <td>
                    <div className="kz-nowrap" style={{ fontWeight: 600 }}>
                      {t.branch}
                    </div>
                    <div className="kz-tcard-meta">
                      {t.region} · {t.failure}
                    </div>
                  </td>
                  <td>
                    <IspBadge isp={t.isp} />
                  </td>
                  <td>
                    <div className="kz-tcard-pills">
                      {(t.checks || []).map(([lbl, st], idx) => (
                        <StatusPill key={idx} label={lbl} state={st} />
                      ))}
                    </div>
                  </td>
                  <td>
                    <Badge tone={(t.sla?.[0] ?? 0) < 0 ? "critical" : "brand"}>
                      {t.status}
                    </Badge>
                  </td>
                  <td className="kz-nowrap">
                    {t.sla ? (
                      <SlaTimer
                        minutesLeft={t.sla[0]}
                        totalMinutes={t.sla[1]}
                      />
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="kz-card">
          <div className="kz-card-hd">
            <div>
              <h2>Outages by region</h2>
              <p>Open + resolved, last 7 days</p>
            </div>
          </div>
          <div className="kz-card-bd">
            <BarChart
              data={[
                { label: "Behera", value: 31, hint: "350 stores" },
                { label: "Cairo", value: 22, hint: "223 stores" },
                { label: "New October", value: 18, hint: "212 stores" },
                { label: "Assyut", value: 15, hint: "209 stores" },
                { label: "Giza", value: 8, hint: "156 stores" },
              ]}
            />
          </div>
        </div>
      </div>
    </AppShell>
  );
}

export const KANBAN_LIFECYCLE_COLUMNS: [string, string][] = [
  ["Awaiting Regional IT", ""],
  ["New & Diagnosing", ""],
  ["Branch / Internal Action", ""],
  ["Escalated to ISP · 2h", "isp"],
  ["With ISP · 4–6h loop", "isp"],
  ["Verifying Fix", ""],
  ["Needs Human Review", "human"],
  ["Resolved / Closed", "done"],
];

export interface KanbanBoardProps {
  style?: React.CSSProperties;
  theme?: ThemeMode;
  onToggleTheme?: () => void;
  onNavigate?: (label: string) => void;
  env?: string;
  initials?: string;
  userDisplayName?: string;
  userRoleLabel?: string;
  onLogout?: () => void;
  canAccessNav?: (label: string) => boolean;
}

export function KanbanBoard({
  style,
  theme,
  onToggleTheme,
  onNavigate,
  env,
  initials,
  userDisplayName,
  userRoleLabel,
  onLogout,
  canAccessNav,
}: KanbanBoardProps) {
  return (
    <AppShell
      active="Kanban Board"
      style={style}
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
            Drag a card to change its status. The AI agent keeps working unless
            paused.
          </p>
        </div>
        <div className="kz-row">
          <Button variant="secondary" icon="download">
            Export
          </Button>
          <Button variant="primary" icon="plus">
            Create manual ticket
          </Button>
        </div>
      </div>
      <div className="kz-filters">
        <span className="kz-chip kz-chip-on">
          <Icon name="filter" />
          All ISPs
        </span>
        <span className="kz-chip">
          Region <Icon name="chevron" />
        </span>
        <span className="kz-chip">
          Trigger <Icon name="chevron" />
        </span>
        <span className="kz-chip">
          Priority <Icon name="chevron" />
        </span>
        <span className="kz-chip">AI paused only</span>
      </div>
      <div className="kz-board">
        {KANBAN_LIFECYCLE_COLUMNS.map(([title, colTone], idx) => {
          const items = SAMPLE_TICKETS.filter((t) => t.col === idx);
          return (
            <section
              key={idx}
              className={clsx("kz-col", colTone && `kz-col-${colTone}`)}
            >
              <div className="kz-col-hd">
                <span className="kz-col-bar" />
                <b>{title}</b>
                <span>{items.length}</span>
              </div>
              {items.map((ticket) => (
                <TicketCard key={ticket.id} ticket={ticket} />
              ))}
            </section>
          );
        })}
      </div>
    </AppShell>
  );
}
