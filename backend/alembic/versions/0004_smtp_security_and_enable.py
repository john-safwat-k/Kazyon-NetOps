"""0004_smtp_security_and_enable

Revision ID: 0004_smtp_security_and_enable
Revises: 0003_brd_v5_full_schema
Create Date: 2026-10-22 14:00:00+00:00

Adds the SMTP connection mode and an explicit "outbound delivery enabled" switch to
`system_settings`, so Page 12 drives real sending. Both columns have server defaults, so
existing rows stay valid and delivery stays off until an admin enables it.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0004_smtp_security_and_enable"
down_revision: Union[str, None] = "0003_brd_v5_full_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "system_settings",
        sa.Column(
            "smtp_security", sa.String(length=16), nullable=False, server_default="starttls"
        ),
    )
    op.add_column(
        "system_settings",
        sa.Column("smtp_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("system_settings", "smtp_enabled")
    op.drop_column("system_settings", "smtp_security")
