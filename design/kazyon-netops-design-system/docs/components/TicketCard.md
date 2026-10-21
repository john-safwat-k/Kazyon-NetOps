# TicketCard

The Kanban card for one network incident.

- `ticket`: `{id, priority, branch, region, failure?, isp, caseRef?, checks?: [[label, state]], sla?: [minutesLeft, totalMinutes], note?, aiPaused?}`.
- Shows ticket number, priority, branch code + name, region and diagnosis, ISP + case ref, IP1/IP2/4G pills, live SLA timer (or a note) and the AI active/paused indicator.
- Sits on `surface-100` column grounds; lifts with `shadow-raised` while dragged.
