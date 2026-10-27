"""0007_proactive_fleet_scan

Revision ID: 0007_fleet_scan
Revises: 0006_admin_approval
Create Date: 2026-10-27 12:00:00+00:00

Adds the Proactive Fleet Scan settings to `system_settings` (enabled flag, interval,
store-hours window, mass-outage guard threshold) and the `fleet_scan_runs` history table.
All new columns carry a `server_default`, so existing rows are valid without a backfill.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0007_fleet_scan"
down_revision: Union[str, None] = "0006_admin_approval"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

JSONVariant = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    op.add_column(
        "system_settings",
        sa.Column("fleet_scan_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "system_settings",
        sa.Column(
            "fleet_scan_interval_minutes", sa.Integer(), nullable=False, server_default="180"
        ),
    )
    op.add_column(
        "system_settings",
        sa.Column(
            "fleet_scan_window_start", sa.String(length=5), nullable=False, server_default="08:00"
        ),
    )
    op.add_column(
        "system_settings",
        sa.Column(
            "fleet_scan_window_end", sa.String(length=5), nullable=False, server_default="23:00"
        ),
    )
    op.add_column(
        "system_settings",
        sa.Column("fleet_scan_mass_outage_pct", sa.Integer(), nullable=False, server_default="5"),
    )

    op.create_table(
        "fleet_scan_runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("suite_id", sa.String(length=64), nullable=True),
        sa.Column("triggered_by", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("total_branches", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failing_initial", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("recovered_on_retest", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("confirmed_down", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duplicates_skipped", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_ticket_numbers", JSONVariant, nullable=False),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("details_json", JSONVariant, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_fleet_scan_runs_suite_id", "fleet_scan_runs", ["suite_id"])
    op.create_index("ix_fleet_scan_runs_status", "fleet_scan_runs", ["status"])
    op.create_index("ix_fleet_scan_runs_started_at", "fleet_scan_runs", ["started_at"])


def downgrade() -> None:
    op.drop_index("ix_fleet_scan_runs_started_at", table_name="fleet_scan_runs")
    op.drop_index("ix_fleet_scan_runs_status", table_name="fleet_scan_runs")
    op.drop_index("ix_fleet_scan_runs_suite_id", table_name="fleet_scan_runs")
    op.drop_table("fleet_scan_runs")
    op.drop_column("system_settings", "fleet_scan_mass_outage_pct")
    op.drop_column("system_settings", "fleet_scan_window_end")
    op.drop_column("system_settings", "fleet_scan_window_start")
    op.drop_column("system_settings", "fleet_scan_interval_minutes")
    op.drop_column("system_settings", "fleet_scan_enabled")
