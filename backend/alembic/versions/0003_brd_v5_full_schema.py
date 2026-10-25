"""0003_brd_v5_full_schema

Revision ID: 0003_brd_v5_full_schema
Revises: 0002_auth_roles_and_audit_logs
Create Date: 2026-10-22 02:20:00+00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.common.database import JSONVariant

revision: str = "0003_brd_v5_full_schema"
down_revision: Union[str, None] = "0002_auth_roles_and_audit_logs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. network_providers additions
    op.add_column(
        "network_providers",
        sa.Column("four_g_hub_ip", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "network_providers",
        sa.Column("welcome_sla_minutes", sa.Integer(), nullable=False, server_default="120"),
    )
    op.add_column(
        "network_providers",
        sa.Column("followup_sla_minutes", sa.Integer(), nullable=False, server_default="300"),
    )

    # 2. branches additions (Columns A-K of Copy of All store ISP (2).xlsx)
    op.add_column(
        "branches",
        sa.Column("ip_1", sa.String(length=128), nullable=False, server_default="10.0.0.1"),
    )
    op.add_column(
        "branches",
        sa.Column("ip_2", sa.String(length=128), nullable=False, server_default="10.0.0.2"),
    )
    op.add_column(
        "branches",
        sa.Column("isp_name", sa.String(length=64), nullable=False, server_default="NOOR"),
    )
    op.add_column(
        "branches",
        sa.Column(
            "isp_contact_mail",
            sa.String(length=255),
            nullable=False,
            server_default="noc@noor.net",
        ),
    )
    op.add_column(
        "branches",
        sa.Column("regional_it_email", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "branches",
        sa.Column("four_g_hub_ip", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "branches",
        sa.Column("ll_circuit_id", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "branches",
        sa.Column("backup_circuit_id", sa.String(length=128), nullable=True),
    )
    op.create_index("ix_branches_isp_name", "branches", ["isp_name"], unique=False)
    op.create_index("ix_branches_region", "branches", ["region"], unique=False)

    # 3. tickets additions
    op.add_column(
        "tickets",
        sa.Column(
            "trigger_source",
            sa.String(length=48),
            nullable=False,
            server_default="DIRECT_EMAIL",
        ),
    )
    op.add_column(
        "tickets",
        sa.Column("sender_email", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "tickets",
        sa.Column("site_contact_phone", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "tickets",
        sa.Column("router_image_paths", JSONVariant, nullable=False, server_default="[]"),
    )
    op.add_column(
        "tickets",
        sa.Column("image_check_passed", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "tickets",
        sa.Column("image_analysis_summary", sa.Text(), nullable=True),
    )
    op.add_column(
        "tickets",
        sa.Column("connection_failure_type", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "tickets",
        sa.Column(
            "isp_welcome_received",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "tickets",
        sa.Column("escalation_reason", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "tickets",
        sa.Column("human_escalated_to", sa.String(length=255), nullable=True),
    )
    op.create_index("ix_tickets_trigger_source", "tickets", ["trigger_source"], unique=False)
    op.create_index(
        "ix_tickets_connection_failure_type",
        "tickets",
        ["connection_failure_type"],
        unique=False,
    )
    op.create_index(
        "ix_tickets_escalation_reason", "tickets", ["escalation_reason"], unique=False
    )

    # 4. diagnostic_runs additions (dual-ping + 4G hub traceroute + nullable ticket_id for sandbox)
    with op.batch_alter_table("diagnostic_runs") as batch_op:
        batch_op.alter_column("ticket_id", existing_type=sa.Integer(), nullable=True)
        batch_op.add_column(sa.Column("branch_code", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("ip_1_up", sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column("ip_2_up", sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column("four_g_hub_detected", sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column("detected_hub_ip", sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column("diagnosis_code", sa.String(length=64), nullable=True))
        batch_op.create_index(
            "ix_diagnostic_runs_branch_code", ["branch_code"], unique=False
        )

    # 5. ticket_emails additions (nullable ticket_id for unmatched triage emails + attachments + raw_headers)
    with op.batch_alter_table("ticket_emails") as batch_op:
        batch_op.alter_column("ticket_id", existing_type=sa.Integer(), nullable=True)
        batch_op.add_column(
            sa.Column("attachments_json", JSONVariant, nullable=False, server_default="[]")
        )
        batch_op.add_column(
            sa.Column("raw_headers", JSONVariant, nullable=False, server_default="{}")
        )
        batch_op.add_column(
            sa.Column("classification_label", sa.String(length=64), nullable=True)
        )
        batch_op.create_index(
            "ix_ticket_emails_classification_label",
            ["classification_label"],
            unique=False,
        )

    # 6. replication_reports & replication_report_rows
    op.create_table(
        "replication_reports",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("message_id", sa.String(length=255), nullable=False),
        sa.Column("subject", sa.String(length=500), nullable=False),
        sa.Column("report_generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("not_updated_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("notified_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "duplicates_skipped_count", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_replication_reports_message_id",
        "replication_reports",
        ["message_id"],
        unique=True,
    )

    op.create_table(
        "replication_report_rows",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("report_id", sa.Integer(), nullable=False),
        sa.Column("branch_code", sa.String(length=64), nullable=False),
        sa.Column("store_name", sa.String(length=200), nullable=False),
        sa.Column("region", sa.String(length=128), nullable=True),
        sa.Column("last_trans_raw", sa.String(length=128), nullable=True),
        sa.Column("business_date", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("regional_it_email", sa.String(length=255), nullable=True),
        sa.Column(
            "regional_it_notified",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("linked_ticket_id", sa.Integer(), nullable=True),
        sa.Column("linked_ticket_number", sa.String(length=32), nullable=True),
        sa.ForeignKeyConstraint(
            ["linked_ticket_id"], ["tickets.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["report_id"], ["replication_reports.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_replication_report_rows_report_id",
        "replication_report_rows",
        ["report_id"],
        unique=False,
    )
    op.create_index(
        "ix_replication_report_rows_branch_code",
        "replication_report_rows",
        ["branch_code"],
        unique=False,
    )
    op.create_index(
        "ix_replication_report_rows_status",
        "replication_report_rows",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_replication_report_rows_linked_ticket_id",
        "replication_report_rows",
        ["linked_ticket_id"],
        unique=False,
    )

    # 7. system_settings
    op.create_table(
        "system_settings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("config_key", sa.String(length=64), nullable=False),
        sa.Column(
            "global_ai_kill_switch",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("mailbox_account", sa.String(length=255), nullable=False),
        sa.Column("imap_host", sa.String(length=255), nullable=False),
        sa.Column("imap_port", sa.Integer(), nullable=False, server_default="993"),
        sa.Column("smtp_host", sa.String(length=255), nullable=False),
        sa.Column("smtp_port", sa.Integer(), nullable=False, server_default="587"),
        sa.Column("poll_interval_sec", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("vllm_endpoint", sa.String(length=255), nullable=False),
        sa.Column("vllm_temperature", sa.Float(), nullable=False, server_default="0.1"),
        sa.Column("vllm_max_tokens", sa.Integer(), nullable=False, server_default="2048"),
        sa.Column(
            "confidence_threshold", sa.Integer(), nullable=False, server_default="80"
        ),
        sa.Column(
            "welcome_sla_minutes", sa.Integer(), nullable=False, server_default="120"
        ),
        sa.Column(
            "followup_interval_minutes",
            sa.Integer(),
            nullable=False,
            server_default="300",
        ),
        sa.Column(
            "max_chasers_before_human", sa.Integer(), nullable=False, server_default="4"
        ),
        sa.Column(
            "max_outbound_emails_per_ticket_hour",
            sa.Integer(),
            nullable=False,
            server_default="6",
        ),
        sa.Column(
            "ignore_auto_submitted",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "diagnostic_timeout_sec", sa.Integer(), nullable=False, server_default="20"
        ),
        sa.Column("ping_count", sa.Integer(), nullable=False, server_default="4"),
        sa.Column(
            "traceroute_max_hops", sa.Integer(), nullable=False, server_default="15"
        ),
        sa.Column(
            "fallback_contacts", JSONVariant, nullable=False, server_default="[]"
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_system_settings_config_key",
        "system_settings",
        ["config_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_table("system_settings")
    op.drop_table("replication_report_rows")
    op.drop_table("replication_reports")

    with op.batch_alter_table("ticket_emails") as batch_op:
        batch_op.drop_index("ix_ticket_emails_classification_label")
        batch_op.drop_column("classification_label")
        batch_op.drop_column("raw_headers")
        batch_op.drop_column("attachments_json")

    with op.batch_alter_table("diagnostic_runs") as batch_op:
        batch_op.drop_index("ix_diagnostic_runs_branch_code")
        batch_op.drop_column("diagnosis_code")
        batch_op.drop_column("detected_hub_ip")
        batch_op.drop_column("four_g_hub_detected")
        batch_op.drop_column("ip_2_up")
        batch_op.drop_column("ip_1_up")
        batch_op.drop_column("branch_code")

    op.drop_index("ix_tickets_escalation_reason", table_name="tickets")
    op.drop_index("ix_tickets_connection_failure_type", table_name="tickets")
    op.drop_index("ix_tickets_trigger_source", table_name="tickets")
    op.drop_column("tickets", "human_escalated_to")
    op.drop_column("tickets", "escalation_reason")
    op.drop_column("tickets", "isp_welcome_received")
    op.drop_column("tickets", "connection_failure_type")
    op.drop_column("tickets", "image_analysis_summary")
    op.drop_column("tickets", "image_check_passed")
    op.drop_column("tickets", "router_image_paths")
    op.drop_column("tickets", "site_contact_phone")
    op.drop_column("tickets", "sender_email")
    op.drop_column("tickets", "trigger_source")

    op.drop_index("ix_branches_region", table_name="branches")
    op.drop_index("ix_branches_isp_name", table_name="branches")
    op.drop_column("branches", "backup_circuit_id")
    op.drop_column("branches", "ll_circuit_id")
    op.drop_column("branches", "four_g_hub_ip")
    op.drop_column("branches", "regional_it_email")
    op.drop_column("branches", "isp_contact_mail")
    op.drop_column("branches", "isp_name")
    op.drop_column("branches", "ip_2")
    op.drop_column("branches", "ip_1")

    op.drop_column("network_providers", "followup_sla_minutes")
    op.drop_column("network_providers", "welcome_sla_minutes")
    op.drop_column("network_providers", "four_g_hub_ip")
