"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-06-30 12:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False, server_default="rider"),
        sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=False)

    op.create_table(
        "drivers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("vehicle_type", sa.String(length=100), nullable=False, server_default="Hybrid Cab"),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="available"),
        sa.Column("current_lat", sa.Float(), nullable=False),
        sa.Column("current_lng", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("user_id", name="uq_drivers_user_id"),
    )
    op.create_index("ix_drivers_status", "drivers", ["status"], unique=False)
    op.create_index("ix_drivers_created_at", "drivers", ["created_at"], unique=False)
    op.create_index("ix_drivers_current_location", "drivers", ["current_lat", "current_lng"], unique=False)

    op.create_table(
        "rides",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("pickup_name", sa.String(length=255), nullable=False),
        sa.Column("drop_name", sa.String(length=255), nullable=False),
        sa.Column("pickup_lat", sa.Float(), nullable=False),
        sa.Column("pickup_lng", sa.Float(), nullable=False),
        sa.Column("drop_lat", sa.Float(), nullable=False),
        sa.Column("drop_lng", sa.Float(), nullable=False),
        sa.Column("passenger_count", sa.Integer(), nullable=False),
        sa.Column("ride_type", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="open"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_rides_created_by_user_id", "rides", ["created_by_user_id"], unique=False)
    op.create_index("ix_rides_status", "rides", ["status"], unique=False)
    op.create_index("ix_rides_created_at", "rides", ["created_at"], unique=False)

    op.create_table(
        "parcels",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("pickup_name", sa.String(length=255), nullable=False),
        sa.Column("drop_name", sa.String(length=255), nullable=False),
        sa.Column("pickup_lat", sa.Float(), nullable=False),
        sa.Column("pickup_lng", sa.Float(), nullable=False),
        sa.Column("drop_lat", sa.Float(), nullable=False),
        sa.Column("drop_lng", sa.Float(), nullable=False),
        sa.Column("parcel_weight", sa.Float(), nullable=False),
        sa.Column("parcel_type", sa.String(length=100), nullable=False),
        sa.Column("priority", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="open"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_parcels_created_by_user_id", "parcels", ["created_by_user_id"], unique=False)
    op.create_index("ix_parcels_status", "parcels", ["status"], unique=False)
    op.create_index("ix_parcels_created_at", "parcels", ["created_at"], unique=False)

    op.create_table(
        "route_decisions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("driver_id", sa.Integer(), nullable=False),
        sa.Column("ride_id", sa.Integer(), nullable=False),
        sa.Column("parcel_id", sa.Integer(), nullable=False),
        sa.Column("efficiency_score", sa.Float(), nullable=False),
        sa.Column("extra_distance", sa.Float(), nullable=False),
        sa.Column("extra_time", sa.Float(), nullable=False),
        sa.Column("overlap_distance", sa.Float(), nullable=False),
        sa.Column("recommendation", sa.String(length=50), nullable=False),
        sa.Column("accepted", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["driver_id"], ["drivers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ride_id"], ["rides.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parcel_id"], ["parcels.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_route_decisions_accepted", "route_decisions", ["accepted"], unique=False)
    op.create_index("ix_route_decisions_created_at", "route_decisions", ["created_at"], unique=False)
    op.create_index(
        "ix_route_decisions_trip_pair_created_at",
        "route_decisions",
        ["ride_id", "parcel_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("jti", sa.String(length=64), nullable=False),
        sa.Column("token_hash", sa.String(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("jti", name="uq_refresh_tokens_jti"),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"], unique=False)
    op.create_index("ix_refresh_tokens_expires_at", "refresh_tokens", ["expires_at"], unique=False)
    op.create_index("ix_refresh_tokens_created_at", "refresh_tokens", ["created_at"], unique=False)

    op.create_table(
        "token_blacklist",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("jti", sa.String(length=64), nullable=False),
        sa.Column("token_type", sa.String(length=20), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("jti", name="uq_token_blacklist_jti"),
    )
    op.create_index("ix_token_blacklist_jti", "token_blacklist", ["jti"], unique=True)
    op.create_index("ix_token_blacklist_token_type", "token_blacklist", ["token_type"], unique=False)
    op.create_index("ix_token_blacklist_expires_at", "token_blacklist", ["expires_at"], unique=False)
    op.create_index("ix_token_blacklist_created_at", "token_blacklist", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_token_blacklist_created_at", table_name="token_blacklist")
    op.drop_index("ix_token_blacklist_expires_at", table_name="token_blacklist")
    op.drop_index("ix_token_blacklist_token_type", table_name="token_blacklist")
    op.drop_index("ix_token_blacklist_jti", table_name="token_blacklist")
    op.drop_table("token_blacklist")

    op.drop_index("ix_refresh_tokens_created_at", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_expires_at", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_user_id", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")

    op.drop_index("ix_route_decisions_trip_pair_created_at", table_name="route_decisions")
    op.drop_index("ix_route_decisions_created_at", table_name="route_decisions")
    op.drop_index("ix_route_decisions_accepted", table_name="route_decisions")
    op.drop_table("route_decisions")

    op.drop_index("ix_parcels_created_at", table_name="parcels")
    op.drop_index("ix_parcels_status", table_name="parcels")
    op.drop_index("ix_parcels_created_by_user_id", table_name="parcels")
    op.drop_table("parcels")

    op.drop_index("ix_rides_created_at", table_name="rides")
    op.drop_index("ix_rides_status", table_name="rides")
    op.drop_index("ix_rides_created_by_user_id", table_name="rides")
    op.drop_table("rides")

    op.drop_index("ix_drivers_current_location", table_name="drivers")
    op.drop_index("ix_drivers_created_at", table_name="drivers")
    op.drop_index("ix_drivers_status", table_name="drivers")
    op.drop_table("drivers")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
