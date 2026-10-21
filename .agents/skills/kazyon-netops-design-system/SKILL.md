---
name: kazyon-netops-design-system
description: >-
  The Kazyon NetOps Design System for the IT Network Support AI Agent & Ticketing Harness web console (React 18 + TypeScript + Tailwind CSS).
  Use this skill whenever the user is building, editing, refactoring, or reviewing any UI page, screen, view, component, modal, drawer, table, chart, or theme in the IT Network Support Agent project (`frontend/`).
  Trigger on requests involving any of the 12 console pages (Login, Executive & SLA Dashboard, Kanban Board, Tickets List & Export, Ticket 360° Detail, Replication Monitor, Human Review Queue, Mailbox & Email Triage, Network Diagnostics Sandbox, Branches & ISP Directory, Users/Roles/RBAC, AI/Mailbox/SLA Settings) or any UI primitives (`AppShell`, `Button`, `Badge`, `IspBadge`, `StatusPill`, `SlaTimer`, `KpiCard`, `TicketCard`, `HealthBar`, `BarChart`, colors, Hanken Grotesk typography, spacing, or dark mode).
---

# Kazyon NetOps — Web Console Design System

This skill is the single source of truth for the look, feel, design tokens, and component library of the **IT Network Support AI Agent & Ticketing Harness** web console (`frontend/`).

The visual language is **white and orange**: quiet white working surfaces, Kazyon orange as the identity and primary action color, and a disciplined set of semantic status colors reserved strictly for network link and SLA state. The typography is **Hanken Grotesk** throughout, paired with system monospace for technical identifiers and raw diagnostic outputs.

When this skill triggers, your job is to build UI that:

1. **Uses the design tokens below** (CSS variables in `src/styles/tokens.css` and Tailwind utilities from `tailwind/kazyon-netops.preset.js` — never hard-code raw hex literals or Tailwind `slate-*`/`indigo-*` colors).
2. **Uses `Hanken Grotesk`** (`font-sans`) for all UI copy and **`font-mono` (`.kz-mono`)** for IPs, circuit IDs, SAP branch codes, ISP case numbers, and raw ping/traceroute logs.
3. **Uses the typed React 18 design system primitives** in `frontend/src/design-system/` (`AppShell`, `Button`, `Badge`, `IspBadge`, `StatusPill`, `SlaTimer`, `KpiCard`, `TicketCard`, `HealthBar`, `BarChart`, `Icon`, `useTheme`).
4. **Follows the component specifications** in [`references/components.md`](./references/components.md).
5. **Follows the 12-screen console blueprints** in [`references/screens.md`](./references/screens.md) whenever implementing or updating any of the 12 console pages.

---

## When to Read the References

- [`references/components.md`](./references/components.md) — Detailed React 18 + TypeScript props, CSS classes (`.kz-*`), and usage rules for every atom, molecule, shell, table, form control, terminal block, and modal. Read this before building or modifying any component.
- [`references/screens.md`](./references/screens.md) — Exact DOM/JSX blueprints and state specifications for all 12 Kazyon NetOps Console screens (Login, Dashboard, Kanban Board, Tickets List, Ticket 360° Detail, Replication Monitor, Human Review Queue, Mailbox & Triage, Diagnostics Sandbox, Branches & ISP Directory, Users & RBAC, AI & SLA Settings). Read the relevant section before building or updating any page.

---

## Project Anatomy

The design system is initialized in `frontend/` and backed by the canonical source in `design/kazyon-netops-design-system/`:

```text
frontend/
├── index.html                                # Loads Hanken Grotesk (400–800) & sets data-theme
├── tailwind.config.js                        # Imports ./tailwind/kazyon-netops.preset.js
├── tailwind/
│   └── kazyon-netops.preset.js               # Tailwind v3 preset mapping CSS vars to utility classes
└── src/
    ├── index.css                             # Imports tokens.css, components.css, and Tailwind layers
    ├── styles/
    │   ├── tokens.css                        # Light (:root) and dark ([data-theme="dark"]) CSS variables
    │   └── components.css                    # Canonical .kz-* component classes
    └── design-system/
        ├── index.ts                          # Barrel export for tokens, theme, and components
        ├── tokens.ts                         # Typed token constants, PRIORITY_TONE, types
        ├── theme.tsx                         # ThemeProvider and useTheme() hook (light/dark)
        └── components.tsx                    # React 18 components (AppShell, Button, Badge, etc.)
```

---

## Core Design Principles

1. **State before decoration.** Every screen answers *"is anything down, and is anyone late?"* first. Status colors (`good`, `warning`, `critical`, `info`) are reserved exclusively for link and SLA state and **always** come with a word or icon — never rely on color alone.
2. **Orange means Kazyon, or "do this".** `brand-500` (`#f47a20`) is for fills only (logo tile, chart bars, SLA progress bar, active markers) — never text on white (2.7:1). Primary buttons use `brand-600` (`#c2410c`) with `on-brand` text. Orange text (links, ticket IDs, active nav label) uses `brand-text` (`#b8480c`). Orange is **never** used to mean "warning"; warning is yellow-amber (`warning`).
3. **White and quiet.** Cards are `surface-000` on `surface-000`, separated by `1px solid var(--border)` hairlines and a subtle `shadow-card`. `surface-100` grounds the sidebar, table headers, and Kanban columns.
4. **Operator language.** Use the exact terminology Kazyon HQ IT engineers use: `SAP code`, `IP1` / `IP2`, `L.L ID`, `3G ID`, `Welcome mail`, `Case #`, `NOOR`, `ORANGE`, `WE`, `GITSupport`, `CITSupport`. Set all technical identifiers (`10.20.9.1`, `QUO1-10316406`, `#244010`, `NET-1058`) in `mono`.

---

## Color Tokens (Light & Dark)

Never write hex literals in components. Use CSS variables (`var(--token)`) or the Tailwind preset classes (`bg-surface-000`, `text-ink`, `border-border`, etc.).

| Role | Token / Tailwind | Light | Dark | Strict Usage Rule |
| :--- | :--- | :--- | :--- | :--- |
| Identity Fill | `brand-500` | `#f47a20` | `#ff8a3d` | Identity fills only: logo tile, chart bars, SLA progress fills, ISP column bar. **Never text on white.** |
| Primary Action | `brand-600` | `#c2410c` | `#ff8a3d` | Primary button & selected segment background. Pair with `on-brand` text. |
| Action Hover | `brand-700` | `#a63f0a` | `#ffb07a` | Primary button hover / pressed state. |
| Orange Text | `brand-text` | `#b8480c` | `#ff9a52` | Links, ticket IDs (`NET-1058`), active nav label, KPI icon accent. |
| Brand Tint | `brand-100` | `#fff1e6` | `#3a2414` | Active nav row background, selected filter chip, `brand` badge ground, KPI icon well. |
| Brand Wash | `brand-50` | `#fff8f2` | `#241a13` | Topbar environment badge background (`PROD :8084`), outbound email bubble background. |
| On-Brand Ink | `on-brand` | `#ffffff` | `#17120e` | Text and icons placed on `brand-600` or alert badges. |
| Surface 000 | `surface-000` | `#ffffff` | `#17120e` | Page background, card background, input background. |
| Surface 100 | `surface-100` | `#fbf8f5` | `#211a15` | Sidebar, table headers (`th`), Kanban column ground, search box well. |
| Surface 200 | `surface-200` | `#f4eee8` | `#2b221c` | Hover rows, chart bar tracks, SLA timer tracks, neutral badges. |
| Primary Ink | `ink` | `#1f1a17` | `#f5efea` | Default primary text on any surface. |
| Muted Ink | `ink-muted` | `#6b625b` | `#a8a29e` | Secondary text, metadata, subtitles, table headers, axis labels. |
| Hairline Border | `border` | `#ede5de` | `#3a302a` | Card outlines, table rules, section dividers. |
| Control Border | `border-strong` | `#a39588` | `#7a6b60` | Form inputs, secondary buttons, filter chips, segmented controls (3:1 contrast). |
| Focus Ring | `focus` | `#c2410c` | `#ff9a52` | 2px outline (`outline-offset: 2px`) on `:focus-visible`. |
| Status: Good | `good` / `good-bg` | `#15803d` / `#ecfdf3` | `#4ade80` / `#13291b` | Link `UP`, ping `PASS`, service `Healthy`, ticket `Resolved`, downward incident delta. |
| Status: Warning | `warning` / `warning-bg` | `#a16207` / `#fefce8` | `#facc15` / `#2b2410` | SLA at risk (`< 25%` left), `DEGRADED`, `HIGH` priority badge. |
| Status: Critical | `critical` / `critical-bg` | `#b91c1c` / `#fef2f2` | `#f87171` / `#2e1515` | Link `DOWN`, SLA overdue, `NEEDS_HUMAN_REVIEW`, `CRITICAL` priority badge. |
| Status: Info | `info` / `info-bg` | `#1d4ed8` / `#eff6ff` | `#93c5fd` / `#14203a` | AI active indicator, `4G BACKUP` hub pill, `Diagnosing` / `Verifying` status. |
| Terminal Block | `term-bg` / `term-ink` | `#1f1a17` / `#f5efea` | `#0d0a08` / `#f5efea` | Raw ping, traceroute, and JSON output blocks (`.kz-term`). |

---

## Dark Mode Rules

- Every color token automatically switches when `data-theme="dark"` is set on `<html>` or on `AppShell`.
- **Do not write `dark:*` Tailwind classes** for colors; use the semantic token classes (`bg-surface-000`, `text-ink`, `border-border`) so light and dark themes work automatically with zero duplication.
- Use the `useTheme()` hook from `src/design-system` (`const { theme, toggleTheme } = useTheme()`) and pass `theme` and `onToggleTheme` to `AppShell`.
- Form inputs, selects, and textareas inside `.kz` automatically inherit `background-color: var(--surface-000)` and `color: var(--ink)` — never hard-code `bg-white` on form controls.
- Raw command/diagnostic logs always use `.kz-term` (`bg-term-bg text-term-ink`).

---

## Typography

Font families:
- `font-sans` (`--font-sans`): `"Hanken Grotesk", system-ui, -apple-system, "Segoe UI", sans-serif`
- `font-mono` (`--font-mono`): `ui-monospace, "SF Mono", Menlo, Consolas, monospace`

| Style Token | Tailwind Class | Size / Line Height | Weight | Letter Spacing | Usage |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `display` | `text-display` | `40px / 44px` | `700` | `-0.02em` | Login hero & empty-state headlines |
| `kpi` | `text-kpi` | `32px / 36px` | `700` | `-0.01em` | KPI card numbers (always with `.kz-num` / `tabular-nums`) |
| `h1` | `text-h1` | `24px / 32px` | `700` | `0` | Page title (`.kz-page-hd h1`), one per page |
| `h2` | `text-h2` | `18px / 26px` | `600` | `0` | Card and panel titles (`.kz-card-hd h2` uses `16px/24px`) |
| `h3` | `text-h3` | `15px / 22px` | `600` | `0` | Ticket card titles, drawer section heads |
| `body` | `text-body` | `14px / 20px` | `400` | `0` | Default console UI text |
| `small` | `text-small` | `12px / 16px` | `500` | `0` | Metadata, table secondary lines, subtitles |
| `label` | `text-label` | `11px / 16px` | `700` | `0.06em` | Uppercase eyebrow labels on KPI cards & table `<th>` |
| `mono` | `text-mono` / `.kz-mono` | `12px / 18px` | `500` | `0` | IPs (`10.20.9.1`), circuit IDs (`QUO1-10316406`), case numbers (`#244010`), ticket IDs (`NET-1058`), ping/traceroute logs |

---

## Spacing, Radius & Shadows

### Spacing Scale (`--space-*`)
- `space-1` (`4px`): Icon-to-label gap, compact pill padding.
- `space-2` (`8px`): Inside badges, compact rows (`.kz-row`), Kanban card internal gap.
- `space-3` (`12px`): Ticket card padding (`.kz-tcard`), Kanban column gap.
- `space-4` (`16px`): Card padding (`.kz-card-bd`), dashboard grid gutter (`.kz-grid-*`), vertical gap between page sections (`.kz-page`).
- `space-6` (`24px`): Page padding (`.kz-page`), topbar horizontal padding (`.kz-top`), modal scrim padding.
- `space-8` (`32px`): Large section spacing, login form padding.

### Border Radius (`--radius-*`)
- `rounded-sm` (`--radius-sm`: `6px`): Badges (`.kz-badge`), ISP badges (`.kz-isp`), small buttons (`.kz-btn-sm`).
- `rounded-md` (`--radius-md`: `10px`): Standard buttons (`.kz-btn`), ticket cards (`.kz-tcard`), sidebar nav rows (`.kz-nav`), form inputs (`.kz-field input`), terminal blocks (`.kz-term`).
- `rounded-lg` (`--radius-lg`: `14px`): Cards (`.kz-card`), Kanban columns (`.kz-col`), system health bar (`.kz-health`), modals/drawers.
- `rounded-pill` (`--radius-pill`: `999px`): Status pills (`.kz-pill`), SLA timer tracks (`.kz-sla-track`), environment badge (`.kz-env`), nav counters (`.kz-nav-count`), avatars (`.kz-avatar`).

### Shadows
- `shadow-card` (`--shadow-card`): Resting cards and ticket cards.
- `shadow-raised` (`--shadow-raised`): Dragged Kanban cards, hover tooltips (`.kz-tip`), modals, dropdowns.

---

## Status Vocabulary & Priority Mapping

Always use the standardized components and mappings:

| Domain Concept | Component / Prop | Visual Representation |
| :--- | :--- | :--- |
| Priority: `CRITICAL` | `<Badge tone="critical">CRITICAL</Badge>` | Red text on critical-bg |
| Priority: `HIGH` | `<Badge tone="warning">HIGH</Badge>` | Amber text on warning-bg |
| Priority: `MEDIUM` | `<Badge tone="brand">MEDIUM</Badge>` | Brand orange text on brand-100 |
| Priority: `LOW` | `<Badge tone="neutral">LOW</Badge>` | Ink text on surface-200 |
| Ping `IP1` / `IP2` reachable | `<StatusPill label="IP1" state="up" />` | Green dot + `IP1 UP` |
| Ping `IP1` / `IP2` unreachable | `<StatusPill label="IP1" state="down" />` | Red dot + `IP1 DOWN` |
| Traceroute hit 4G backup hub | `<StatusPill label="4G" state="hub" />` | Blue dot + `4G BACKUP` |
| `IP2` skipped because `IP1` is down | `<StatusPill label="IP2" state="skip" />` | Hollow muted ring + `IP2 SKIPPED` |
| 2h Welcome SLA (`120m`) or 4–6h Follow-up (`300m`) | `<SlaTimer minutesLeft={m} totalMinutes={120} />` | Normal: `brand-500` fill; `<25%` left: `warning`; `<0`: `critical` (`Overdue Xm`) |
| ISP Identifier + Case Ref | `<IspBadge isp="ORANGE" caseRef="1-1312322942540" />` | Monogram tile (`O` in `brand-500`, `N`/`W` in `ink`) + ISP name + `#caseRef` in mono |
| AI Automation Active / Paused | `.kz-ai` / `.kz-ai.kz-ai-paused` | `bot` icon in `info` (`AI active`) / `pause` icon in `ink-muted` (`AI paused`) |

---

## Layout & Page Structure Checklist

Every authenticated page in the console follows this structure:

1. Wrap the view in `<AppShell active="<Nav Label>" theme={theme} onToggleTheme={toggleTheme} env={envLabel}>`.
2. Start `.kz-page` with a `.kz-page-hd` header block containing:
   - Left `<div>`: `<h1>Page Title</h1>` + `<p>Muted operational context subtitle</p>`
   - Right `<div className="kz-row">`: Segmented controls (`.kz-seg`), secondary actions (`<Button variant="secondary">`), and **at most one** primary action (`<Button variant="primary">`).
3. Use the layout grids:
   - `.kz-grid-kpi`: 5-up responsive KPI row (`repeat(auto-fit, minmax(180px, 1fr))`).
   - `.kz-grid-3`: 3-up chart/panel row (`repeat(auto-fit, minmax(280px, 1fr))`).
   - `.kz-grid-main`: 2:1 asymmetric content + side panel (`minmax(0, 1fr) 340px`).
   - `.kz-board`: 8-column horizontal Kanban grid (`repeat(8, 260px)`).
4. Validate your changes before finishing:
   ```bash
   cd frontend && npm run build
   ```
