"""user email_verified_at + user_email_verifications for Brevo invite flow

Revision ID: 5f1a9c2d4e6b
Revises: 4d7e8f1a2b3c
Create Date: 2026-04-29

"""
from alembic import op
import sqlalchemy as sa


revision = "5f1a9c2d4e6b"
down_revision = "4d7e8f1a2b3c"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "users",
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(op.f("ix_users_email_verified_at"), "users", ["email_verified_at"], unique=False)

    op.create_table(
        "user_email_verifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("encrypted_password", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_user_email_verifications_user_id"),
        "user_email_verifications",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_user_email_verifications_token_hash"),
        "user_email_verifications",
        ["token_hash"],
        unique=True,
    )
    op.create_index(
        op.f("ix_user_email_verifications_expires_at"),
        "user_email_verifications",
        ["expires_at"],
        unique=False,
    )

    # Existing accounts remain able to sign in (treated as already verified).
    op.execute(
        sa.text("UPDATE users SET email_verified_at = created_at WHERE email_verified_at IS NULL")
    )


def downgrade():
    op.drop_index(op.f("ix_user_email_verifications_expires_at"), table_name="user_email_verifications")
    op.drop_index(op.f("ix_user_email_verifications_token_hash"), table_name="user_email_verifications")
    op.drop_index(op.f("ix_user_email_verifications_user_id"), table_name="user_email_verifications")
    op.drop_table("user_email_verifications")
    op.drop_index(op.f("ix_users_email_verified_at"), table_name="users")
    op.drop_column("users", "email_verified_at")
