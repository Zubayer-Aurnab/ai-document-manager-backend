"""document_categories table + company_settings singleton

Revision ID: 4d7e8f1a2b3c
Revises: 2822c0c1779a
Create Date: 2026-04-28

"""
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa


revision = "4d7e8f1a2b3c"
down_revision = "2822c0c1779a"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "document_categories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("slug", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("document_categories", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_document_categories_slug"), ["slug"], unique=True)

    op.create_table(
        "company_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_name", sa.String(length=200), nullable=True),
        sa.Column("legal_name", sa.String(length=200), nullable=True),
        sa.Column("tagline", sa.String(length=300), nullable=True),
        sa.Column("email", sa.String(length=200), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("address_line1", sa.String(length=200), nullable=True),
        sa.Column("address_line2", sa.String(length=200), nullable=True),
        sa.Column("city", sa.String(length=120), nullable=True),
        sa.Column("state_region", sa.String(length=120), nullable=True),
        sa.Column("postal_code", sa.String(length=40), nullable=True),
        sa.Column("country", sa.String(length=100), nullable=True),
        sa.Column("website", sa.String(length=300), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    now = datetime.now(timezone.utc)
    cats = sa.table(
        "document_categories",
        sa.column("id", sa.Integer),
        sa.column("name", sa.String),
        sa.column("slug", sa.String),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    op.bulk_insert(
        cats,
        [
            {"id": 1, "name": "General", "slug": "general", "created_at": now, "updated_at": now},
            {"id": 2, "name": "Legal", "slug": "legal", "created_at": now, "updated_at": now},
            {"id": 3, "name": "HR", "slug": "hr", "created_at": now, "updated_at": now},
            {"id": 4, "name": "Finance", "slug": "finance", "created_at": now, "updated_at": now},
            {"id": 5, "name": "Operations", "slug": "operations", "created_at": now, "updated_at": now},
        ],
    )
    co = sa.table(
        "company_settings",
        sa.column("id", sa.Integer),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    op.bulk_insert(co, [{"id": 1, "created_at": now, "updated_at": now}])


def downgrade():
    op.drop_table("company_settings")
    with op.batch_alter_table("document_categories", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_document_categories_slug"))
    op.drop_table("document_categories")
