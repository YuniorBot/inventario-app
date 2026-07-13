"""add inventory creator

Revision ID: d4e5f6a7b8c9
Revises: c1a2b3d4e5f6
Create Date: 2026-07-13 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d4e5f6a7b8c9"
down_revision = "c1a2b3d4e5f6"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("inventario", schema=None) as batch_op:
        batch_op.add_column(sa.Column("created_by_id", sa.Integer(), nullable=True))
        batch_op.create_index(
            batch_op.f("ix_inventario_created_by_id"), ["created_by_id"], unique=False
        )
        batch_op.create_foreign_key(
            batch_op.f("fk_inventario_created_by_id_usuario"),
            "usuario",
            ["created_by_id"],
            ["id"],
        )


def downgrade():
    with op.batch_alter_table("inventario", schema=None) as batch_op:
        batch_op.drop_constraint(
            batch_op.f("fk_inventario_created_by_id_usuario"), type_="foreignkey"
        )
        batch_op.drop_index(batch_op.f("ix_inventario_created_by_id"))
        batch_op.drop_column("created_by_id")
