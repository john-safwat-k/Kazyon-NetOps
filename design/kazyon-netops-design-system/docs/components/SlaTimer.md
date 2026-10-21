# SlaTimer

Countdown for the 2-hour ISP Welcome SLA and the 4–6 hour investigation follow-up loop.

- `minutesLeft`: negative means overdue.
- `totalMinutes`: 120 for the welcome window, 300 for the follow-up window.
- `label`: optional prefix.
- States: normal (brand fill), at risk under 25% left (warning), overdue (critical, full bar, "Overdue 34m").
