"""Add project_files table for BBS cross-file extraction

Revision ID: 0004
Revises: 0003
Create Date: 2024-01-04 00:00:00
"""
from alembic import op
import sqlalchemy as sa

revision      = "0004"
down_revision = "0003"
branch_labels = None
depends_on    = None


def upgrade() -> None:
    op.create_table(
        "project_files",
        sa.Column("id",           sa.String(36), primary_key=True),
        sa.Column("project_id",   sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("filename",      sa.String(500), nullable=False),
        sa.Column("original_name", sa.String(500), nullable=False),
        sa.Column("file_type",     sa.String(30),  nullable=False),
        sa.Column("file_category", sa.String(50),  nullable=True),
        sa.Column("file_path",     sa.String(1000),nullable=True),
        sa.Column("file_size_kb",  sa.Float(),     nullable=True),
        sa.Column("extraction_status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("extracted_data",    sa.Text(),      nullable=True),
        sa.Column("member_count",      sa.Integer(),   nullable=True, server_default="0"),
        sa.Column("member_list",       sa.Text(),      nullable=True),
        sa.Column("extraction_notes",  sa.Text(),      nullable=True),
        sa.Column("uploaded_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at",  sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at",  sa.DateTime(), nullable=True),
    )
    op.create_index("ix_project_files_id",         "project_files", ["id"])
    op.create_index("ix_project_files_project_id", "project_files", ["project_id"])


def downgrade() -> None:
    op.drop_table("project_files")
