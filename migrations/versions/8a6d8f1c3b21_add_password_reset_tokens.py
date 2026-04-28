"""add password reset tokens

Revision ID: 8a6d8f1c3b21
Revises: 7c5d2a1b4e90
Create Date: 2026-04-28 20:15:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "8a6d8f1c3b21"
down_revision = "7c5d2a1b4e90"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "password_reset_token",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuario.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    with op.batch_alter_table("password_reset_token", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_password_reset_token_usuario_id"), ["usuario_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_password_reset_token_token_hash"), ["token_hash"], unique=True
        )
        batch_op.create_index(
            batch_op.f("ix_password_reset_token_expires_at"), ["expires_at"], unique=False
        )


def downgrade():
    with op.batch_alter_table("password_reset_token", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_password_reset_token_expires_at"))
        batch_op.drop_index(batch_op.f("ix_password_reset_token_token_hash"))
        batch_op.drop_index(batch_op.f("ix_password_reset_token_usuario_id"))

    op.drop_table("password_reset_token")
