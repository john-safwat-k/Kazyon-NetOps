# Button

The console's action control: one `primary` per view (New ticket, Save), `secondary` for everyday actions, `ghost` for toolbar actions, `danger` for escalate/kill-switch.

- `variant`: `primary | secondary | ghost | danger` (default `secondary`).
- `size`: `md` (36px) or `sm` (28px) for table rows and card headers.
- `icon`: an icon name from `KzNet.Icon` placed before the label. Icon-only buttons need an `aria-label`.
- Primary uses `brand-600` with `on-brand` text, never the lighter `brand-500`.
