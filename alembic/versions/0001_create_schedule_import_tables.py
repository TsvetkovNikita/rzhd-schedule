"""create schedule import tables

Revision ID: 0001_create_schedule_import_tables
Revises: 
Create Date: 2026-03-08 18:30:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0001_baseline"
down_revision = None
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "schedule_import_batches",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("station_code", sa.String(length=64), nullable=False),
        sa.Column("station_system", sa.String(length=32), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("request_payload", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "schedule_import_rows",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("batch_id", sa.Integer(), nullable=False),
        sa.Column("source_key", sa.String(length=255), nullable=False),
        sa.Column("train_uid", sa.String(length=255), nullable=True),
        sa.Column("transport_type", sa.String(length=32), nullable=True),
        sa.Column("number", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("arrival", sa.DateTime(timezone=True), nullable=True),
        sa.Column("departure", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sort_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["batch_id"], ["schedule_import_batches.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("batch_id", "source_key", name="uq_schedule_import_rows_batch_source_key"),
    )
    op.create_index(op.f("ix_schedule_import_rows_batch_id"), "schedule_import_rows", ["batch_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_schedule_import_rows_batch_id"), table_name="schedule_import_rows")
    op.drop_table("schedule_import_rows")
    op.drop_table("schedule_import_batches")
