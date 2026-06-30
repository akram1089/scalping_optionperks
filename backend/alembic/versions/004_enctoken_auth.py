"""Add enctoken auth mode fields

Revision ID: 004
Revises: 003
Create Date: 2026-06-30
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "broker_accounts",
        sa.Column("auth_mode", sa.String(20), server_default="kite_connect", nullable=False),
    )
    op.add_column("broker_accounts", sa.Column("password_enc", sa.Text(), nullable=True))
    op.add_column("broker_accounts", sa.Column("enctoken_enc", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("broker_accounts", "enctoken_enc")
    op.drop_column("broker_accounts", "password_enc")
    op.drop_column("broker_accounts", "auth_mode")
