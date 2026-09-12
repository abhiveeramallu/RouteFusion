"""add driver declines

Revision ID: 0003_add_driver_declines
Revises: 0002_add_optimistic_locking
Create Date: 2026-09-12 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0003_add_driver_declines"
down_revision = "0002_add_optimistic_locking"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "driver_declines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("driver_id", sa.Integer(), nullable=False),
        sa.Column("ride_id", sa.Integer(), nullable=True),
        sa.Column("parcel_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["driver_id"], ["drivers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ride_id"], ["rides.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parcel_id"], ["parcels.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_driver_declines_driver_ride", "driver_declines", ["driver_id", "ride_id"], unique=False)
    op.create_index("ix_driver_declines_driver_parcel", "driver_declines", ["driver_id", "parcel_id"], unique=False)
    op.create_index("ix_driver_declines_created_at", "driver_declines", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_driver_declines_created_at", table_name="driver_declines")
    op.drop_index("ix_driver_declines_driver_parcel", table_name="driver_declines")
    op.drop_index("ix_driver_declines_driver_ride", table_name="driver_declines")
    op.drop_table("driver_declines")
