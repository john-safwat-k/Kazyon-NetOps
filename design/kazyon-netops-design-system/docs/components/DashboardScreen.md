# DashboardScreen

Page 2 of the console, the Executive & Live SLA Dashboard (`/dashboard`), assembled from the system's components.

- System health bar (vLLM, mailbox, PostgreSQL, Redis).
- Five KPI cards: open tickets, needs human review, overdue 2h welcome, overdue 4–6h update, Not Updated replication stores.
- Outages by ISP, MTTR by ISP, outages by failure type, outages by region.
- SLA watchlist table, most urgent first.
- Sample data only; wire it to the FastAPI `/dashboard` endpoints and `/ws/tickets`.
