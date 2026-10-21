# Kazyon NetOps — Component Recipes & Guidelines

All core components live in `frontend/src/design-system/components.tsx` (re-exported via `frontend/src/design-system/index.ts`) and are styled by `frontend/src/styles/components.css` + `frontend/src/styles/tokens.css`.

Always import from `@/design-system` or `../design-system`:

```tsx
import {
  AppShell,
  Badge,
  BarChart,
  Button,
  HealthBar,
  Icon,
  IspBadge,
  KpiCard,
  PRIORITY_TONE,
  SlaTimer,
  StatusPill,
  TicketCard,
  useTheme,
} from "../design-system";
```

---

## 1. `AppShell`

The authenticated frame around every console page (Pages 2–12):
- **Sidebar (`240px`, `.kz-side`)**: `surface-100` background, Kazyon NetOps brand lockup (`.kz-logo` `K` tile in `brand-500`), and 3 navigation sections (`Operate`, `Tools`, `Admin`) covering all 10 sidebar destinations:
  - **Operate**: `Dashboard`, `Kanban Board`, `Tickets List`, `Human Review` (critical count badge), `Replication Monitor` (neutral count badge), `Mailbox & Triage`
  - **Tools**: `Diagnostics Sandbox`, `Branches & ISPs`
  - **Admin**: `Users & Roles`, `AI & SLA Settings`
- **Topbar (`60px`, `.kz-top`)**: Global search box (`.kz-search`), `Live` WebSocket indicator (`.kz-live`), environment pill (`.kz-env`, e.g. `PROD :8084` or `DEV :8085`), sun/moon theme toggle button, notification bell, and user initials avatar (`.kz-avatar`).
- **Main Canvas (`.kz-page`)**: `24px` padding, `16px` vertical gap between sections.

```tsx
const { theme, toggleTheme } = useTheme();

<AppShell
  active="Tickets List"
  theme={theme}
  onToggleTheme={toggleTheme}
  onNavigate={(label) => navigateTo(label)}
  env="PROD :8084"
  initials="JS"
>
  {/* .kz-page-hd and page sections */}
</AppShell>
```

---

## 2. `Button`

The console's action control.
- **Rule**: Maximum **one** `variant="primary"` button per view (e.g., `New ticket`, `Create manual ticket`, `Run check`, `Save changes`).
- `variant`: `"primary" | "secondary" | "ghost" | "danger"` (defaults to `"secondary"`).
- `size`: `"md"` (`36px` height) or `"sm"` (`28px` height, for table rows and card headers).
- `icon`: Optional `IconName` placed before the label. Icon-only buttons **must** include an `aria-label`.

```tsx
<Button variant="primary" icon="plus">New ticket</Button>
<Button variant="secondary" icon="download">Export CSV</Button>
<Button variant="ghost" size="sm">Open 360°</Button>
<Button variant="danger" size="sm">Escalate</Button>
```

---

## 3. `Badge`

Compact label (`22px` height, `radius-sm`) for ticket priority, lifecycle stage, trigger source, or role status.
- `tone`: `"neutral" | "brand" | "good" | "warning" | "critical" | "info" | "outline"`.
- Priority mapping (`PRIORITY_TONE`):
  - `CRITICAL` → `"critical"`
  - `HIGH` → `"warning"`
  - `MEDIUM` → `"brand"`
  - `LOW` → `"neutral"`
- Stage mapping:
  - `Escalated to ISP`, `With ISP` → `"brand"`
  - `Needs Human Review` → `"critical"`
  - `Diagnosing`, `Verifying` → `"info"`
  - `Internal LAN Issue` → `"warning"`
  - `Awaiting Regional IT` → `"neutral"`
  - `Resolved`, `Closed` → `"good"`

```tsx
<Badge tone={PRIORITY_TONE[ticket.priority]}>{ticket.priority}</Badge>
<Badge tone="outline">DIRECT_EMAIL</Badge>
```

---

## 4. `IspBadge`

Identifies the branch's Network Service Provider (`NOOR`, `ORANGE`, `WE`), optionally paired with the ISP's case/request number in monospace.
- `ORANGE` renders its initial `O` on a `brand-500` tile; `NOOR` (`N`) and `WE` (`W`) render on an `ink` tile.
- Never differentiate ISPs using arbitrary rainbow colors.

```tsx
<IspBadge isp="ORANGE" caseRef="1-1312322942540" />
<IspBadge isp="NOOR" caseRef="244010" />
<IspBadge isp="WE" />
```

---

## 5. `StatusPill`

Displays the result of one diagnostic check from the dual-ping and traceroute harness.
- `label`: `"IP1"` (router `10.x.x.1`), `"IP2"` (switch `10.x.x.2`), or `"4G"` (traceroute backup hub).
- `state`:
  - `"up"` → `IP1 UP` (`good` green dot & tint)
  - `"down"` → `IP1 DOWN` (`critical` red dot & tint)
  - `"hub"` → `4G BACKUP` (`info` blue dot & tint — local loop is down, traffic routed over 4G backup hub)
  - `"skip"` → `IP2 SKIPPED` (`ink-muted` hollow circle — `IP2` is not pinged when `IP1` is down)

```tsx
<StatusPill label="IP1" state="up" />
<StatusPill label="IP2" state="down" />
<StatusPill label="4G" state="hub" />
```

---

## 6. `SlaTimer`

Countdown bar and tabular readout for the **2-hour ISP Welcome SLA** (`totalMinutes={120}`) and the **4–6 hour ISP follow-up loop** (`totalMinutes={300}`).
- `minutesLeft`: Negative values indicate overdue (`Overdue 34m`).
- Automatically transitions visual state:
  - Normal (`>= 25%` time left): `brand-500` progress fill, `ink` text.
  - At risk (`< 25%` time left): `warning` progress fill and text.
  - Overdue (`minutesLeft < 0`): 100% `critical` progress fill and `critical` text.

```tsx
<SlaTimer minutesLeft={-34} totalMinutes={120} label="2h welcome" />
<SlaTimer minutesLeft={52} totalMinutes={300} label="4–6h update" />
```

---

## 7. `KpiCard`

Headline metric card for dashboard KPI rows (`.kz-grid-kpi`).
- `label`: Uppercase eyebrow text (`11px`, `0.06em` tracking).
- `value`: Big tabular metric (`32px/36px` bold).
- `icon`: `IconName` rendered inside a `32x32` tinted well.
- `delta`: Optional string (`"+6"`, `"-3"`). For incident counts, `+` is bad (renders in `.kz-delta-up` `critical`) and `-` is good (renders in `.kz-delta-down` `good`).
- `tone`: `"default" | "warning" | "critical"`. Use `"critical"` only when human action is required immediately (e.g., `Needs human review`).

```tsx
<KpiCard
  label="Needs human review"
  value={4}
  icon="alert"
  tone="critical"
  hint="Quota, MSAN, unknown mail"
/>
```

---

## 8. `TicketCard`

Kanban card molecule (`.kz-tcard`) for one network incident.
- Displays: Ticket ID in `mono` (`brand-text`), priority `Badge`, branch code + name, region + failure summary, `IspBadge` with case reference, `StatusPill` array (`IP1`, `IP2`, `4G`), footer with `SlaTimer` (or muted note) and AI state (`AI active` with `bot` icon in `info`, or `AI paused` with `pause` icon in `ink-muted`).

```tsx
<TicketCard ticket={ticket} onClick={(t) => openTicketDetail(t.id)} />
```

---

## 9. `HealthBar`

Live status strip (`.kz-health`) for platform dependencies (`vLLM · Gemma 4 26B`, `IMAP / SMTP Mailbox`, `PostgreSQL 16`, `Redis 7`).
- Each item shows a glowing status dot (`ok` → `Healthy`, `degraded` → `Degraded`, `down` → `Down`), service name, and monospace connection/latency detail.

```tsx
<HealthBar
  services={[
    { name: "vLLM · Gemma 4 26B", detail: "10.100.109.9:8002 · 412 ms", state: "ok" },
    { name: "IMAP / SMTP Mailbox", detail: "Last poll 14 s ago", state: "ok" },
    { name: "PostgreSQL 16", detail: ":5434 · 18 conn", state: "ok" },
    { name: "Redis 7", detail: ":6384 · queue depth 9", state: "degraded" },
  ]}
/>
```

---

## 10. `BarChart`

Single-series horizontal bar chart (`.kz-bars`) for outage counts and MTTR by ISP, region, or failure type.
- **Rule**: Never put two measures on one chart. Outages and MTTR are always separate cards.
- Bars fill with `brand-500` (`brand-600` on row hover) inside a `surface-200` track, with direct-labeled tabular values on the right and an interactive tooltip (`.kz-tip`) on hover.

```tsx
<BarChart
  unit="h"
  data={[
    { label: "NOOR", value: 5.8, hint: "906 stores" },
    { label: "ORANGE", value: 7.2, hint: "181 stores" },
    { label: "WE", value: 9.4, hint: "63 stores" },
  ]}
/>
```

---

## 11. Tables, Filters, Forms, Terminal Logs & Modals

Use the built-in `.kz-*` utility classes from `src/styles/components.css`:

### Data Tables (`.kz-table`)
```tsx
<div className="kz-card" style={{ overflow: "hidden" }}>
  <table className="kz-table">
    <thead>
      <tr>
        <th>Ticket</th>
        <th>Branch</th>
        <th>Status</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td><span className="kz-tcard-id">NET-1058</span></td>
        <td><b>2009-Kafr Nasar</b></td>
        <td><Badge tone="brand">Escalated to ISP</Badge></td>
      </tr>
    </tbody>
  </table>
</div>
```

### Segmented Control (`.kz-seg`) & Filter Chips (`.kz-filters` / `.kz-chip`)
```tsx
<div className="kz-seg" role="group" aria-label="Time range">
  <button className="on">Today</button>
  <button>7 days</button>
  <button>30 days</button>
</div>

<div className="kz-filters">
  <button className="kz-chip kz-chip-on"><Icon name="filter" /> All ISPs</button>
  <button className="kz-chip">Region <Icon name="chevron" /></button>
</div>
```

### Form Fields (`.kz-field`)
```tsx
<label className="kz-field">
  Branch (SAP code or name)
  <input defaultValue="1173 — Ghmrawy (Cairo)" />
  <small>Matched from Kazyon Store Connections sheet</small>
</label>
```

### Raw Terminal / JSON Logs (`.kz-term`)
```tsx
<pre className="kz-term">{`$ ping -c 4 10.11.73.1
4 packets transmitted, 4 received, 0% packet loss, avg 182 ms
DIAGNOSIS: LOCAL_LOOP_DOWN_ON_4G`}</pre>
```
