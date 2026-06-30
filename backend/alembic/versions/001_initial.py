"""Initial schema

Revision ID: 001
Revises:
Create Date: 2026-06-29
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("is_active", sa.Boolean(), default=True),
    )
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "global_state",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("kill_switch", sa.Boolean(), default=False),
        sa.Column("kill_switch_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "broker_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("label", sa.String(100), nullable=False),
        sa.Column("broker", sa.String(50), default="zerodha"),
        sa.Column("api_key_enc", sa.Text(), nullable=False),
        sa.Column("api_secret_enc", sa.Text(), nullable=False),
        sa.Column("totp_secret_enc", sa.Text(), nullable=True),
        sa.Column("zerodha_user_id", sa.String(50), nullable=True),
        sa.Column("capital", sa.Numeric(18, 2), default=100000),
        sa.Column("auto_login", sa.Boolean(), default=False),
        sa.Column("enabled", sa.Boolean(), default=True),
        sa.Column("access_token_enc", sa.Text(), nullable=True),
        sa.Column("token_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "strategies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("instrument_type", sa.String(50), default="equity_intraday"),
        sa.Column("symbol", sa.String(50), nullable=False),
        sa.Column("entry_tf", sa.String(10), default="5minute"),
        sa.Column("htf", sa.String(10), default="15minute"),
        sa.Column("params_json", postgresql.JSONB(), default={}),
        sa.Column("risk_pct", sa.Numeric(8, 4), default=1.0),
        sa.Column("rr_ratio", sa.Numeric(8, 2), default=2.0),
        sa.Column("atr_band_json", postgresql.JSONB(), default={}),
        sa.Column("spread_cap", sa.Numeric(10, 4), default=0.5),
        sa.Column("avoid_open_min", sa.Integer(), default=15),
        sa.Column("avoid_close_min", sa.Integer(), default=15),
        sa.Column("max_trades_day", sa.Integer(), default=10),
        sa.Column("daily_max_loss", sa.Numeric(18, 2), default=5000),
        sa.Column("consec_loss_limit", sa.Integer(), default=3),
        sa.Column("enabled", sa.Boolean(), default=False),
        sa.Column("paper_mode", sa.Boolean(), default=True),
        sa.Column("running", sa.Boolean(), default=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "strategy_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("strategy_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("strategies.id", ondelete="CASCADE")),
        sa.Column("broker_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("broker_accounts.id", ondelete="CASCADE")),
        sa.Column("enabled", sa.Boolean(), default=True),
    )

    op.create_table(
        "signals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("strategy_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("strategies.id", ondelete="CASCADE")),
        sa.Column("ts", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("side", sa.String(10), nullable=False),
        sa.Column("tf", sa.String(10), nullable=False),
        sa.Column("price", sa.Numeric(18, 4), nullable=False),
        sa.Column("indicator_snapshot_json", postgresql.JSONB(), default={}),
        sa.Column("acted", sa.Boolean(), default=False),
        sa.Column("paper", sa.Boolean(), default=True),
    )

    op.create_table(
        "orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("broker_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("broker_accounts.id", ondelete="CASCADE")),
        sa.Column("strategy_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("strategies.id", ondelete="SET NULL"), nullable=True),
        sa.Column("kite_order_id", sa.String(50), nullable=True),
        sa.Column("side", sa.String(10), nullable=False),
        sa.Column("symbol", sa.String(50), nullable=False),
        sa.Column("qty", sa.Integer(), nullable=False),
        sa.Column("price", sa.Numeric(18, 4), nullable=True),
        sa.Column("order_type", sa.String(20), default="LIMIT"),
        sa.Column("status", sa.String(20), default="PENDING"),
        sa.Column("parent_order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("orders.id"), nullable=True),
        sa.Column("ts", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("raw_json", postgresql.JSONB(), default={}),
        sa.Column("paper", sa.Boolean(), default=True),
    )

    op.create_table(
        "trades",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("broker_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("broker_accounts.id", ondelete="CASCADE")),
        sa.Column("strategy_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("strategies.id", ondelete="SET NULL"), nullable=True),
        sa.Column("entry_order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("orders.id"), nullable=True),
        sa.Column("exit_order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("orders.id"), nullable=True),
        sa.Column("side", sa.String(10), nullable=False),
        sa.Column("symbol", sa.String(50), nullable=False),
        sa.Column("qty", sa.Integer(), nullable=False),
        sa.Column("entry_price", sa.Numeric(18, 4), nullable=False),
        sa.Column("exit_price", sa.Numeric(18, 4), nullable=True),
        sa.Column("pnl", sa.Numeric(18, 2), nullable=True),
        sa.Column("exit_reason", sa.String(50), nullable=True),
        sa.Column("opened_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paper", sa.Boolean(), default=True),
    )

    op.create_table(
        "positions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("broker_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("broker_accounts.id", ondelete="CASCADE")),
        sa.Column("symbol", sa.String(50), nullable=False),
        sa.Column("qty", sa.Integer(), nullable=False),
        sa.Column("avg_price", sa.Numeric(18, 4), nullable=False),
        sa.Column("side", sa.String(10), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("strategy_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("strategies.id", ondelete="SET NULL"), nullable=True),
        sa.Column("stop_loss", sa.Numeric(18, 4), nullable=True),
        sa.Column("target", sa.Numeric(18, 4), nullable=True),
        sa.Column("paper", sa.Boolean(), default=True),
    )

    op.create_table(
        "risk_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("broker_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("broker_accounts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("strategy_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("strategies.id", ondelete="SET NULL"), nullable=True),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "audit_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("target", sa.String(255), nullable=True),
        sa.Column("meta_json", postgresql.JSONB(), default={}),
        sa.Column("ts", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_table("risk_events")
    op.drop_table("positions")
    op.drop_table("trades")
    op.drop_table("orders")
    op.drop_table("signals")
    op.drop_table("strategy_accounts")
    op.drop_table("strategies")
    op.drop_table("broker_accounts")
    op.drop_table("global_state")
    op.drop_table("users")
