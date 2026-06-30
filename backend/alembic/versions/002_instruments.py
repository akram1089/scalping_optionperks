"""Initial instruments master tables

Revision ID: 002
Revises: 001
Create Date: 2026-06-29
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "instruments",
        sa.Column("instrument_token", sa.Integer(), primary_key=True),
        sa.Column("exchange", sa.String(10), nullable=False),
        sa.Column("tradingsymbol", sa.String(100), nullable=False),
        sa.Column("exchange_token", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("last_price", sa.Numeric(18, 4), nullable=True),
        sa.Column("expiry", sa.Date(), nullable=True),
        sa.Column("strike", sa.Numeric(18, 4), nullable=True),
        sa.Column("tick_size", sa.Numeric(18, 4), nullable=True),
        sa.Column("lot_size", sa.Integer(), server_default="1"),
        sa.Column("instrument_type", sa.String(20), nullable=True),
        sa.Column("segment", sa.String(20), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_instruments_exchange", "instruments", ["exchange"])
    op.create_index("ix_instruments_tradingsymbol", "instruments", ["tradingsymbol"])
    op.create_index("ix_instruments_instrument_type", "instruments", ["instrument_type"])
    op.create_index("ix_instruments_segment", "instruments", ["segment"])
    op.create_index("ix_instruments_is_active", "instruments", ["is_active"])
    op.create_index(
        "ix_instruments_exchange_symbol",
        "instruments",
        ["exchange", "tradingsymbol"],
        unique=True,
    )

    op.create_table(
        "instrument_sync_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(20), server_default="running"),
        sa.Column("source", sa.String(50), server_default="kite_csv"),
        sa.Column("rows_upserted", sa.Integer(), server_default="0"),
        sa.Column("rows_deactivated", sa.Integer(), server_default="0"),
        sa.Column("error_detail", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("instrument_sync_log")
    op.drop_index("ix_instruments_exchange_symbol", table_name="instruments")
    op.drop_index("ix_instruments_is_active", table_name="instruments")
    op.drop_index("ix_instruments_segment", table_name="instruments")
    op.drop_index("ix_instruments_instrument_type", table_name="instruments")
    op.drop_index("ix_instruments_tradingsymbol", table_name="instruments")
    op.drop_index("ix_instruments_exchange", table_name="instruments")
    op.drop_table("instruments")
