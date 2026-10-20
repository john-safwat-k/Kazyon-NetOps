"""0001_initial_baseline_schema

Revision ID: 0001_initial_baseline
Revises:
Create Date: 2026-10-20 14:35:00+00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.common.database import JSONVariant

revision: str = "0001_initial_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=128), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role_name", sa.String(length=64), nullable=False),
        sa.Column("is_super_admin", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("permissions", JSONVariant, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "network_providers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("support_email", sa.String(length=255), nullable=False),
        sa.Column("cc_emails", JSONVariant, nullable=False),
        sa.Column("followup_interval_minutes", sa.Integer(), nullable=False),
        sa.Column("account_manager_email", sa.String(length=255), nullable=True),
        sa.Column("escalation_template", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_network_providers_name", "network_providers", ["name"], unique=True)

    op.create_table(
        "branches",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("branch_code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("region", sa.String(length=128), nullable=True),
        sa.Column("address", sa.String(length=500), nullable=True),
        sa.Column("target_ip", sa.String(length=128), nullable=False),
        sa.Column("circuit_id", sa.String(length=128), nullable=False),
        sa.Column("connection_type", sa.String(length=64), nullable=False),
        sa.Column("contact_emails", JSONVariant, nullable=False),
        sa.Column("isp_id", sa.Integer(), nullable=True),
        sa.Column("extra_metadata", JSONVariant, nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["isp_id"], ["network_providers.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_branches_branch_code", "branches", ["branch_code"], unique=True)
    op.create_index("ix_branches_name", "branches", ["name"], unique=False)
    op.create_index("ix_branches_circuit_id", "branches", ["circuit_id"], unique=False)
    op.create_index("ix_branches_isp_id", "branches", ["isp_id"], unique=False)

    op.create_table(
        "tickets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("ticket_number", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=48), nullable=False),
        sa.Column("priority", sa.String(length=24), nullable=False),
        sa.Column("branch_id", sa.Integer(), nullable=True),
        sa.Column("isp_id", sa.Integer(), nullable=True),
        sa.Column("assigned_user_id", sa.Integer(), nullable=True),
        sa.Column("isp_reference_number", sa.String(length=128), nullable=True),
        sa.Column("ai_automation_enabled", sa.Boolean(), nullable=False),
        sa.Column("last_isp_contact_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_followup_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("followup_count", sa.Integer(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["assigned_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["isp_id"], ["network_providers.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tickets_ticket_number", "tickets", ["ticket_number"], unique=True)
    op.create_index("ix_tickets_status", "tickets", ["status"], unique=False)
    op.create_index("ix_tickets_priority", "tickets", ["priority"], unique=False)
    op.create_index("ix_tickets_branch_id", "tickets", ["branch_id"], unique=False)
    op.create_index("ix_tickets_isp_id", "tickets", ["isp_id"], unique=False)
    op.create_index("ix_tickets_assigned_user_id", "tickets", ["assigned_user_id"], unique=False)
    op.create_index("ix_tickets_next_followup_at", "tickets", ["next_followup_at"], unique=False)

    op.create_table(
        "diagnostic_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("ticket_id", sa.Integer(), nullable=False),
        sa.Column("trigger_source", sa.String(length=48), nullable=False),
        sa.Column("result_status", sa.String(length=32), nullable=False),
        sa.Column("summary", sa.String(length=500), nullable=False),
        sa.Column("metrics_json", JSONVariant, nullable=False),
        sa.Column("raw_output", sa.Text(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_diagnostic_runs_ticket_id", "diagnostic_runs", ["ticket_id"], unique=False)
    op.create_index(
        "ix_diagnostic_runs_result_status", "diagnostic_runs", ["result_status"], unique=False
    )

    op.create_table(
        "ticket_emails",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("ticket_id", sa.Integer(), nullable=False),
        sa.Column("thread_type", sa.String(length=24), nullable=False),
        sa.Column("direction", sa.String(length=16), nullable=False),
        sa.Column("message_id", sa.String(length=255), nullable=False),
        sa.Column("in_reply_to", sa.String(length=255), nullable=True),
        sa.Column("sender", sa.String(length=255), nullable=False),
        sa.Column("recipients", JSONVariant, nullable=False),
        sa.Column("cc", JSONVariant, nullable=False),
        sa.Column("subject", sa.String(length=500), nullable=False),
        sa.Column("body_text", sa.Text(), nullable=False),
        sa.Column("body_html", sa.Text(), nullable=True),
        sa.Column("ai_analysis_json", JSONVariant, nullable=False),
        sa.Column("sent_or_received_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ticket_emails_ticket_id", "ticket_emails", ["ticket_id"], unique=False)
    op.create_index("ix_ticket_emails_thread_type", "ticket_emails", ["thread_type"], unique=False)
    op.create_index("ix_ticket_emails_message_id", "ticket_emails", ["message_id"], unique=True)

    op.create_table(
        "ticket_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("ticket_id", sa.Integer(), nullable=False),
        sa.Column("actor_type", sa.String(length=32), nullable=False),
        sa.Column("actor_name", sa.String(length=128), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("summary", sa.String(length=500), nullable=False),
        sa.Column("details_json", JSONVariant, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ticket_events_ticket_id", "ticket_events", ["ticket_id"], unique=False)
    op.create_index("ix_ticket_events_event_type", "ticket_events", ["event_type"], unique=False)


def downgrade() -> None:
    op.drop_table("ticket_events")
    op.drop_table("ticket_emails")
    op.drop_table("diagnostic_runs")
    op.drop_table("tickets")
    op.drop_table("branches")
    op.drop_table("network_providers")
    op.drop_table("users")
