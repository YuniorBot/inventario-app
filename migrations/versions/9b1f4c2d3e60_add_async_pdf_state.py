"""add async pdf state

Revision ID: 9b1f4c2d3e60
Revises: 8a6d8f1c3b21
Create Date: 2026-05-05 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "9b1f4c2d3e60"
down_revision = "8a6d8f1c3b21"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("inventario", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "pdf_status",
                sa.String(length=20),
                nullable=False,
                server_default="not_started",
            )
        )
        batch_op.add_column(sa.Column("pdf_filename", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("pdf_error", sa.Text(), nullable=True))
        batch_op.add_column(
            sa.Column("pdf_requested_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("pdf_generated_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("pdf_version", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.add_column(sa.Column("pdf_job_id", sa.String(length=100), nullable=True))
        batch_op.create_index(batch_op.f("ix_inventario_pdf_status"), ["pdf_status"], unique=False)

    with op.batch_alter_table("inventario", schema=None) as batch_op:
        batch_op.alter_column("pdf_status", server_default=None)
        batch_op.alter_column("pdf_version", server_default=None)


def downgrade():
    with op.batch_alter_table("inventario", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_inventario_pdf_status"))
        batch_op.drop_column("pdf_job_id")
        batch_op.drop_column("pdf_version")
        batch_op.drop_column("pdf_generated_at")
        batch_op.drop_column("pdf_requested_at")
        batch_op.drop_column("pdf_error")
        batch_op.drop_column("pdf_filename")
        batch_op.drop_column("pdf_status")
