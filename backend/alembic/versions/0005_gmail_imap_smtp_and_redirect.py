"""0005_gmail_and_redirect

Revision ID: 0005_gmail_and_redirect
Revises: 0004_smtp_security_and_enable
Create Date: 2026-10-25 09:10:00+00:00

Adds Gmail / IMAP & SMTP runtime authentication fields (`imap_use_ssl`, `imap_folder`,
`imap_username`, `imap_password_encrypted`, `smtp_username`, `smtp_password_encrypted`) and
an optional safe sandbox redirect recipient (`test_redirect_email`) to `system_settings`.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0005_gmail_and_redirect"
down_revision: Union[str, None] = "0004_smtp_security_and_enable"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "system_settings",
        sa.Column("imap_use_ssl", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "system_settings",
        sa.Column("imap_folder", sa.String(length=128), nullable=False, server_default="INBOX"),
    )
    op.add_column(
        "system_settings",
        sa.Column("imap_username", sa.String(length=255), nullable=False, server_default=""),
    )
    op.add_column(
        "system_settings",
        sa.Column("imap_password_encrypted", sa.Text(), nullable=False, server_default=""),
    )
    op.add_column(
        "system_settings",
        sa.Column("smtp_username", sa.String(length=255), nullable=False, server_default=""),
    )
    op.add_column(
        "system_settings",
        sa.Column("smtp_password_encrypted", sa.Text(), nullable=False, server_default=""),
    )
    op.add_column(
        "system_settings",
        sa.Column("test_redirect_email", sa.String(length=255), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("system_settings", "test_redirect_email")
    op.drop_column("system_settings", "smtp_password_encrypted")
    op.drop_column("system_settings", "smtp_username")
    op.drop_column("system_settings", "imap_password_encrypted")
    op.drop_column("system_settings", "imap_username")
    op.drop_column("system_settings", "imap_folder")
    op.drop_column("system_settings", "imap_use_ssl")
