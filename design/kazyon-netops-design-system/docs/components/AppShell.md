# AppShell

The authenticated frame around every page: sidebar with the 12-page navigation, topbar with search, live WebSocket indicator, environment badge and avatar.

- `active`: the nav label to highlight.
- `hrefs`: optional map of nav label → link, so the sidebar navigates (used by the console prototype).
- `theme`: `"light" | "dark"`; sets `data-theme` on the shell.
- `onToggleTheme`: when given, a sun/moon button appears in the topbar.
- `env`: `"PROD :8084"` or `"DEV :8085"`.
- `children`: the page content, laid out in `.kz-page` (24px padding, 16px gaps).
