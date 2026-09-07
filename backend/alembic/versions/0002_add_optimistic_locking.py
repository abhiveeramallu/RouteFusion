"""add optimistic locking and concurrency events

Revision ID: 0002_add_optimistic_locking
Revises: 0001_initial_schema
Create Date: 2026-09-07 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0002_add_optimistic_locking"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # batch_alter_table works on every backend: on SQLite (which can't ALTER
    # a table to add a foreign key constraint) it transparently uses a
    # copy-and-move strategy, and on Postgres/MySQL it just issues the plain
    # ALTER statements directly — so this migration is safe to run
    # regardless of which database this deployment actually points at.
    with op.batch_alter_table("rides") as batch_op:
        batch_op.add_column(sa.Column("version", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("assigned_driver_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_rides_assigned_driver_id", "drivers", ["assigned_driver_id"], ["id"], ondelete="SET NULL"
        )
        batch_op.create_index("ix_rides_assigned_driver_id", ["assigned_driver_id"], unique=False)

    with op.batch_alter_table("parcels") as batch_op:
        batch_op.add_column(sa.Column("version", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("assigned_driver_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_parcels_assigned_driver_id", "drivers", ["assigned_driver_id"], ["id"], ondelete="SET NULL"
        )
        batch_op.create_index("ix_parcels_assigned_driver_id", ["assigned_driver_id"], unique=False)

    # Backfill assigned_driver_id for rides/parcels that were already
    # confirmed/assigned before this migration ran, from the most recent
    # accepted route_decisions row for each. Without this, an in-progress
    # trip at deploy time would have assigned_driver_id = NULL forever,
    # making it invisible to the new per-driver "active assignment" lookup
    # (get_active_assignment) — an orphaned trip nobody can complete. Runs
    # after the batch_alter_table blocks above, once the columns actually
    # exist as queryable columns on the (possibly rebuilt) table.
    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            UPDATE rides
            SET assigned_driver_id = (
                SELECT rd.driver_id FROM route_decisions rd
                WHERE rd.ride_id = rides.id AND rd.accepted = 1
                ORDER BY rd.created_at DESC LIMIT 1
            )
            WHERE rides.status IN ('confirmed', 'confirmed_solo')
              AND rides.assigned_driver_id IS NULL
            """
        )
    )
    connection.execute(
        sa.text(
            """
            UPDATE parcels
            SET assigned_driver_id = (
                SELECT rd.driver_id FROM route_decisions rd
                WHERE rd.parcel_id = parcels.id AND rd.accepted = 1
                ORDER BY rd.created_at DESC LIMIT 1
            )
            WHERE parcels.status IN ('assigned', 'assigned_solo')
              AND parcels.assigned_driver_id IS NULL
            """
        )
    )

    op.create_table(
        "concurrency_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ride_id", sa.Integer(), nullable=False),
        sa.Column("parcel_id", sa.Integer(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("succeeded", sa.Integer(), nullable=False),
        sa.Column("conflicts", sa.Integer(), nullable=False),
        sa.Column("winner_driver_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["ride_id"], ["rides.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parcel_id"], ["parcels.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["winner_driver_id"], ["drivers.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_concurrency_events_created_at", "concurrency_events", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_concurrency_events_created_at", table_name="concurrency_events")
    op.drop_table("concurrency_events")

    with op.batch_alter_table("parcels") as batch_op:
        batch_op.drop_index("ix_parcels_assigned_driver_id")
        batch_op.drop_constraint("fk_parcels_assigned_driver_id", type_="foreignkey")
        batch_op.drop_column("assigned_driver_id")
        batch_op.drop_column("version")

    with op.batch_alter_table("rides") as batch_op:
        batch_op.drop_index("ix_rides_assigned_driver_id")
        batch_op.drop_constraint("fk_rides_assigned_driver_id", type_="foreignkey")
        batch_op.drop_column("assigned_driver_id")
        batch_op.drop_column("version")
