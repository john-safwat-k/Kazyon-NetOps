# Kazyon NetOps

The design system for the **IT Network Support AI Agent & Ticketing Harness**: the web console HQ IT uses to watch 1,150+ Kazyon branches across NOOR, ORANGE and WE, follow every incident the AI agent is working, and step in when it needs a person.

The look is **white and orange**: white working surfaces, Kazyon orange as the identity and action color, and a small set of status colors that are only used for network and SLA state. The type is **Hanken Grotesk** throughout.

## Principles

1. **State before decoration.** Every screen answers "is anything down, and is anyone late?" first. Status colors (good, warning, critical, info) are reserved for link and SLA state and always come with a word or icon.
2. **Orange means Kazyon, or "do this".** `brand-500` fills identity moments (logo, active nav marker, chart bars). `brand-600` is the primary action. Orange is never used to mean "warning"; that is `warning` (yellow-amber), told apart by lightness.
3. **White and quiet.** Cards are white on white, separated by `border` hairlines and a faint `shadow-card`. `surface-100` grounds the sidebar, table headers and Kanban columns.
4. **Operator language.** Use the words engineers already use: SAP code, IP1/IP2, L.L ID, 3G ID, Welcome mail, Case #. Identifiers (IPs, circuit IDs, case refs) are set in `mono`.

## Color

| Role | Token | Use |
| --- | --- | --- |
| Identity | `brand-500` | Logo tile, chart bars, SLA progress, active markers. Not for text. |
| Action | `brand-600` / `brand-700` | Primary button, selected segment. Text is `on-brand`. |
| Orange text | `brand-text` | Links, ticket numbers, active nav label. |
| Tint | `brand-100`, `brand-50` | Active nav row, brand badges, environment badge. |
| Surfaces | `surface-000`, `surface-100`, `surface-200` | Page and cards, side grounds, hover and tracks. |
| Ink | `ink`, `ink-muted` | Primary and secondary text. |
| Status | `good`, `warning`, `critical`, `info` (+ `-bg`) | UP / at risk / DOWN or overdue / AI and 4G backup. |

## Dark mode

Every color token has a `dark` value; set `data-theme="dark"` on any container (or pass `theme="dark"` to `AppShell`) and everything inside follows.

- Ground goes to a warm near-black (`surface-000` `#17120e`), cards stay one step lighter on `surface-100`.
- Orange lightens to `#ff8a3d`; the primary button flips to dark `on-brand` text on orange (7.9:1).
- Status colors lighten (`good` `#4ade80`, `critical` `#f87171`) and their `-bg` tints darken, so pills keep 4.5:1.
- Form controls get `color-scheme: dark` and themed backgrounds from `bundle.css`; never hard-code `#fff` on inputs.
- Logs use `term-bg` / `term-ink` through the `.kz-term` class.
- `AppShell` shows a sun/moon toggle in the topbar when given `onToggleTheme`.

## Type

Hanken Grotesk from Google Fonts (`wght` 400–800). Load it with:

```html
<link href="https://fonts.googleapis.com/css2?family=Hanken+Grotesk:wght@400;500;600;700;800&display=swap" rel="stylesheet">
```

- `h1` 24/32 bold for the page title; `h2` 18/26 for card titles; `h3` 15/22 for ticket titles.
- `body` 14/20 for UI text, `small` 12/16 for metadata, `label` 11/16 uppercase for KPI eyebrows and column heads.
- `kpi` 32/36 bold with tabular figures for dashboard numbers.
- `mono` for `10.20.9.1`, `QUO1-10316406`, `#244010` and raw ping logs.

## Layout

- App shell: 240px sidebar on `surface-100`, 60px topbar, page padding `space-6` (24px), gaps `space-4` (16px).
- Cards use `radius-lg`; buttons and ticket cards `radius-md`; badges `radius-sm`; status pills and SLA timers `radius-pill`.
- Dashboard grid: a five-up KPI row, three chart cards, then a 2:1 row with the SLA watchlist and outages by region.

## Status vocabulary

| Ticket state | Badge / pill |
| --- | --- |
| IP1 / IP2 reachable | `StatusPill state="up"` |
| IP1 / IP2 unreachable | `StatusPill state="down"` |
| Traceroute hits the 4G hub (local loop down) | `StatusPill state="hub"` |
| 2h welcome or 4–6h follow-up running | `SlaTimer` (brand), under 25% left (warning), overdue (critical) |
| NEEDS_HUMAN_REVIEW | `Badge tone="critical"` and a red count in the nav |
| AI automation on / paused | Bot icon in `info` / pause icon in `ink-muted` |

## Charts

Single-series horizontal bars in `brand-500` on a `surface-200` track, values direct-labeled in ink, a tooltip on hover. One measure per chart: outages and MTTR are separate cards. Region, ISP and failure type share the same mark so they can be compared at a glance.

## Screens

`DashboardScreen` (Page 2, `/dashboard`) and `KanbanBoard` (Page 3, `/tickets/board`) show the components assembled with sample data from the BRD. They are references for the React 18 + Tailwind build: map the tokens to Tailwind theme values and keep the class structure.
