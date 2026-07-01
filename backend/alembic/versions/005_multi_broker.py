"""Multi-broker support — broker_order_id, client_id, pin, refresh token.

Revision ID: 005
Revises: 004
"""

from alembic import op
import sqlalchemy as sa

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("orders", "kite_order_id", new_column_name="broker_order_id")
    op.add_column("broker_accounts", sa.Column("client_id", sa.String(50), nullable=True))
    op.add_column("broker_accounts", sa.Column("pin_enc", sa.Text(), nullable=True))
    op.add_column("broker_accounts", sa.Column("refresh_token_enc", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("broker_accounts", "refresh_token_enc")
    op.drop_column("broker_accounts", "pin_enc")
    op.drop_column("broker_accounts", "client_id")
    op.alter_column("orders", "broker_order_id", new_column_name="kite_order_id")
