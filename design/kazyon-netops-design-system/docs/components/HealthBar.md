# HealthBar

Live status strip for the platform's dependencies: vLLM, the mailbox, PostgreSQL and Redis.

- `services`: `[{name, detail, state: 'ok' | 'degraded' | 'down'}]`.
- Each state carries a dot and a word (Healthy / Degraded / Down).
