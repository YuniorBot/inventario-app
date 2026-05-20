"""add video processing state

Revision ID: c1a2b3d4e5f6
Revises: 9b1f4c2d3e60
Create Date: 2026-05-20 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c1a2b3d4e5f6"
down_revision = "9b1f4c2d3e60"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("foto", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("tipo", sa.String(length=20), nullable=False, server_default="image")
        )
        batch_op.add_column(sa.Column("archivo_original", sa.String(length=255), nullable=True))
        batch_op.add_column(
            sa.Column(
                "processing_status",
                sa.String(length=30),
                nullable=False,
                server_default="ready",
            )
        )
        batch_op.add_column(sa.Column("processing_error", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("size_bytes", sa.BigInteger(), nullable=True))
        batch_op.add_column(sa.Column("duration_seconds", sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f("ix_foto_tipo"), ["tipo"], unique=False)
        batch_op.create_index(
            batch_op.f("ix_foto_processing_status"), ["processing_status"], unique=False
        )

    with op.batch_alter_table("foto", schema=None) as batch_op:
        batch_op.alter_column("tipo", server_default=None)
        batch_op.alter_column("processing_status", server_default=None)


def downgrade():
    with op.batch_alter_table("foto", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_foto_processing_status"))
        batch_op.drop_index(batch_op.f("ix_foto_tipo"))
        batch_op.drop_column("duration_seconds")
        batch_op.drop_column("size_bytes")
        batch_op.drop_column("processing_error")
        batch_op.drop_column("processing_status")
        batch_op.drop_column("archivo_original")
        batch_op.drop_column("tipo")
