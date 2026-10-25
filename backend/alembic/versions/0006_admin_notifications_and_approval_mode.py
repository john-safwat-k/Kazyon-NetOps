"""0006_admin_approval

Revision ID: 0006_admin_approval
Revises: 0005_gmail_and_redirect
Create Date: 2026-10-25 14:30:00+00:00

Adds `admin_notification_email`, `notify_admin_on_every_action`, and
`require_admin_approval_before_action` to `system_settings`, plus
`pending_admin_action_json` to `tickets` so the AI agent can email the admin on
every action and optionally pause for admin approval in the console before
executing outbound emails or ticket state changes.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0006_admin_approval"
down_revision: Union[str, None] = "0005_gmail_and_redirect"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

JSONVariant = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    op.add_column(
        "system_settings",
        sa.Column(
            "admin_notification_email",
            sa.String(length=255),
            nullable=False,
            server_default="admin@kazyon.com",
        ),
    )
    op.add_column(
        "system_settings",
        sa.Column(
            "notify_admin_on_every_action",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )
    op.add_column(
        "system_settings",
        sa.Column(
            "require_admin_approval_before_action",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "tickets",
        sa.Column("pending_admin_action_json", JSONVariant, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tickets", "pending_admin_action_json")
    op.drop_column("system_settings", "require_admin_approval_before_action")
    op.drop_column("system_settings", "notify_admin_on_every_action")
    op.drop_column("system_settings", "admin_notification_email")
