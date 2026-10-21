# Kazyon NetOps Design System

Orange-and-white design system for the IT Network Support AI Agent & Ticketing Harness console. Hanken Grotesk, light and dark themes.

## What's inside

| Path | What it is |
| --- | --- |
| `tokens/tokens.css` | CSS custom properties. Light on `:root`, dark on `[data-theme="dark"]`. Load this first. |
| `tokens/tokens.json` | Source tokens (colors per theme, type styles, spacing, radius, shadow) with usage notes. |
| `tokens/tokens.dtcg.json` | Same tokens in W3C Design Tokens (DTCG) format, for Tokens Studio for Figma or Style Dictionary. |
| `tailwind/kazyon-netops.preset.js` | Tailwind 3 preset: `bg-brand-600`, `text-ink-muted`, `rounded-lg`, `shadow-card`, `text-kpi`, and more. |
| `components/bundle.js` | React 18 components on `window.KzNet` (Button, Badge, IspBadge, StatusPill, SlaTimer, KpiCard, TicketCard, HealthBar, BarChart, AppShell, DashboardScreen, KanbanBoard). |
| `components/bundle.css` | Component styles (`kz-` classes). Reads the tokens. |
| `components/index.d.ts` | TypeScript prop types. |
| `docs/brand-book.md` | Principles, color roles, type, layout, status vocabulary, dark mode. |
| `docs/components/*.md` | Usage guidelines per component. |

## Quick start (plain HTML)

```html
<link href="https://fonts.googleapis.com/css2?family=Hanken+Grotesk:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<link rel="stylesheet" href="tokens/tokens.css">
<link rel="stylesheet" href="components/bundle.css">
<script src="https://cdn.jsdelivr.net/npm/react@18.3.1/umd/react.production.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/react-dom@18.3.1/umd/react-dom.production.min.js"></script>
<script src="components/bundle.js"></script>
<div id="app"></div>
<script>
  const h = React.createElement, K = window.KzNet;
  ReactDOM.createRoot(document.getElementById('app')).render(h(K.DashboardScreen));
</script>
```

## React 18 + Tailwind (the BRD stack)

1. Import `tokens/tokens.css` once in your app entry.
2. Add the preset: `presets: [require('./kazyon-netops.preset.js')]` in `tailwind.config.js`.
3. Use token classes: `bg-surface-000 text-ink border-border rounded-lg shadow-card`, primary button `bg-brand-600 text-on-brand hover:bg-brand-700`.
4. Dark mode: set `data-theme="dark"` on `<html>` (or any container). Every token switches; no `dark:` variants needed.

The components in `bundle.js` are a reference implementation. Port them to `.tsx` files using `index.d.ts` for the props.

## Rules worth keeping

- `brand-500` (#f47a20) is for fills only. Orange text uses `brand-text`; the primary button uses `brand-600`.
- Status colors (good, warning, critical, info) mean link and SLA state only, and always come with a label.
- IPs, circuit IDs and case numbers are set in `mono`.
