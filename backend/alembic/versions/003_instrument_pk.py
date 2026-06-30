"""Instrument PK — composite exchange + tradingsymbol for upsert

Revision ID: 003
Revises: 002
Create Date: 2026-06-29
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("instruments_pkey", "instruments", type_="primary")
    op.drop_index("ix_instruments_exchange_symbol", table_name="instruments")
    op.create_primary_key("pk_instruments_exchange_symbol", "instruments", ["exchange", "tradingsymbol"])
    op.create_index("ix_instruments_token", "instruments", ["instrument_token"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_instruments_token", table_name="instruments")
    op.drop_constraint("pk_instruments_exchange_symbol", "instruments", type_="primary")
    op.create_primary_key("instruments_pkey", "instruments", ["instrument_token"])
    op.create_index("ix_instruments_exchange_symbol", "instruments", ["exchange", "tradingsymbol"], unique=True)
