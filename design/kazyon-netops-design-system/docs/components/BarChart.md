# BarChart

A single-series horizontal bar chart for outage counts and MTTR by ISP, region or failure type.

- `data`: `[{label, value, hint?}]`, `unit?` (e.g. `"h"`), `max?`.
- One series, one color (`brand-500`), values direct-labeled in ink. Hover or focus a row for a tooltip.
- Never put two measures on one chart: outages and MTTR are separate cards.
