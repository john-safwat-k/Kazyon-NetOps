# Walkthrough — Proactive 3-Hour Full Fleet Diagnostic Scan & Settings Controls (2026-10-27)

## Summary
Added a **Proactive 3-Hour Full Fleet Diagnostic Scan** capability so the AI Network Support Agent automatically runs the full Dual-Ping (`IP 1` Router + `IP 2` Switch) + `ORANGE`/`WE` 4G Hub Traceroute suite across all active branches every **3 hours** (`180` minutes by default), initiates the appropriate autonomous ticket workflow for confirmed failing sites, and provides one-click **Stop / Enable** and safety configuration controls in **AI & SLA Settings (Page 12)**.

## Key Changes
1. **Contracts & Database Schema (`0007_proactive_fleet_scan.py`)**:
   - Added `TicketTriggerSource.PROACTIVE_SCAN = "PROACTIVE_SCAN"` and `EscalationReason.MASS_OUTAGE_SUSPECTED = "MASS_OUTAGE_SUSPECTED"` in `backend/app/common/contracts.py`.
   - Extended `SystemSettings` (`backend/app/ticketing/models.py`) with `fleet_scan_enabled` (`False` by default), `fleet_scan_interval_minutes` (`180`), `fleet_scan_window_start` (`"08:00"`), `fleet_scan_window_end` (`"23:00"`), and `fleet_scan_mass_outage_pct` (`5`).
   - Created `FleetScanRun` (`fleet_scan_runs`) to audit every scheduled or manual scan (`suite_id`, `triggered_by`, `status`, `total_branches`, `failing_initial`, `recovered_on_retest`, `confirmed_down`, `duplicates_skipped`, `created_ticket_numbers`, `summary`, `details_json`, `started_at`, `finished_at`).

2. **Proactive Scan Engine & Per-Diagnosis Flow Routing (`backend/app/agent/workflow.py`)**:
   - Implemented `run_proactive_fleet_scan`:
     - **Step 1 (Fast Fleet Sweep)**: Runs `run_full_branch_diagnostic_suite` (`ping_count=1`) across active stores.
     - **Step 2 (Two-Strike Confirmation Re-test)**: Re-tests any non-`PASS` store with `execute_dual_ping_and_traceroute(ping_count=4)` to filter out transient single-packet drops (`recovered_on_retest`).
     - **Step 3 (Mass Outage Circuit Breaker)**: If confirmed failing branches exceed `fleet_scan_mass_outage_pct` (default `5%`), halts ticket creation, marks the run `MASS_OUTAGE_GUARD`, and sends a single `[MASS OUTAGE GUARD] Proactive Fleet Scan Halted` alert email (`MASS_OUTAGE_SUSPECTED`) to NOC/Admin.
     - **Step 4 (Mid-Scan Abort & Deduplication)**: Re-checks `fleet_scan_enabled` and `global_ai_kill_switch` before opening each ticket (aborting immediately with `status="ABORTED"` if stopped from Settings), and skips branches that already have an open ticket (`duplicates_skipped`).
     - **Step 5 (Per-Diagnosis Autonomous Flow Initiation)**:
       - `FULL_OUTAGE` -> Creates `PROACTIVE_SCAN` ticket, transitions to `AWAITING_REGIONAL_IT`, and emails Regional IT requesting a router inspection photo + on-site contact mobile number.
       - `LOCAL_LOOP_DOWN_ON_4G` -> Creates `PROACTIVE_SCAN` ticket (`router_photo_verified=True`), transitions directly to `ESCALATED_TO_ISP`, sends the ISP escalation email (with `2h` Welcome SLA & `5h` follow-up timers), and emails Regional IT/Branch for the on-site phone number.
       - `INTERNAL_LAN_SWITCH` -> Creates `PROACTIVE_SCAN` ticket, transitions to `INTERNAL_LAN_ISSUE`, and emails Regional IT with a switch diagnostic alert (zero ISP emails sent).
     - Respects `require_admin_approval_before_action` by routing proposed actions through `_gate_or_ require_admin_approval` when Approval Mode is enabled.

3. **Background Scheduler & Settings API (`backend/app/agent/scheduler.py`, `backend/app/ticketing/router.py`, `backend/app/ticketing/service.py`)**:
   - Integrated `run_scheduled_fleet_scan_if_due` into the background agent loop (`run_email_loop_cycle_once`), checking `fleet_scan_enabled`, `global_ai_kill_switch`, Cairo store-hours window (`is_within_store_window`), and elapsed interval (`>= fleet_scan_interval_minutes`).
   - Added `cancel_active_fleet_scan()` hook inside `update_system_settings` so disabling `fleet_scan_enabled` or turning on `global_ai_kill_switch` cancels any running background scan task immediately.
   - Added `GET /api/v1/settings/fleet-scans` and `POST /api/v1/settings/fleet-scans/run-now`.

4. **Frontend Settings & Filter Controls (`frontend/src/views/SettingsView.tsx`, `KanbanBoardView.tsx`, `TicketsListView.tsx`)**:
   - Added the **Proactive 3-Hour Full Fleet Diagnostic Scan** card on Page 12 (`SettingsView.tsx`) with:
     - One-click **Stop Proactive Fleet Scan / Enable 3h Proactive Scan** button (`persists immediately via PUT /api/v1/settings`) and native `<input type="checkbox" switch>` toggle.
     - Configuration inputs for scan interval (`180` mins default), Cairo store-hours window (`08:00` – `23:00`), and mass outage circuit breaker (`5%`).
     - Manual **Run full scan & start flows now** and **Dry run (preview only)** buttons plus a live recent scan history table.
   - Added `PROACTIVE_SCAN` to the Trigger filter dropdowns on the Kanban Board and Tickets List views.

## Verification
- **Backend Pytest**: `241 passed` (including 5 dedicated tests in `backend/tests/test_proactive_fleet_scan.py`).
- **Ruff & Mypy**: `ruff format --check app/ tests/`, `ruff check app/ tests/`, and `mypy app/` all passed with zero warnings/errors.
- **Frontend Build**: `npm run build` (`tsc --noEmit && vite build`) succeeded cleanly.
