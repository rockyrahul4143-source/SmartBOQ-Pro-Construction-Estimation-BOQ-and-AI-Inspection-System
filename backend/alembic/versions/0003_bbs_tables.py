"""Add BBS tables (Bar Bending Schedule)

Revision ID: 0003
Revises: 0002
Create Date: 2024-01-03 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision     = "0003"
down_revision = "0002"
branch_labels = None
depends_on    = None


def upgrade() -> None:
    op.create_table(
        "bbs_sheets",
        sa.Column("id",           sa.String(36), primary_key=True),
        sa.Column("project_id",   sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sheet_number", sa.String(50),  nullable=False),
        sa.Column("title",        sa.String(500), nullable=False),
        sa.Column("member_type",  sa.String(30),  nullable=False, server_default="beam"),
        sa.Column("mode",         sa.String(20),  nullable=False, server_default="manual"),
        sa.Column("drawing_ref",  sa.String(200), nullable=True),
        sa.Column("drawing_file", sa.String(500), nullable=True),
        sa.Column("fck",          sa.Integer(),   nullable=False, server_default="20"),
        sa.Column("fy",           sa.Integer(),   nullable=False, server_default="500"),
        sa.Column("clear_cover",  sa.Float(),     nullable=True),
        sa.Column("bond_type",    sa.String(20),  nullable=False, server_default="deformed"),
        sa.Column("is_approved",  sa.Boolean(),   nullable=False, server_default="false"),
        sa.Column("prepared_by",  sa.String(36),  sa.ForeignKey("users.id"), nullable=True),
        sa.Column("checked_by",   sa.String(255), nullable=True),
        sa.Column("notes",        sa.Text(),      nullable=True),
        sa.Column("created_at",   sa.DateTime(),  nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at",   sa.DateTime(),  nullable=True),
    )
    op.create_index("ix_bbs_sheets_id",         "bbs_sheets", ["id"])
    op.create_index("ix_bbs_sheets_project_id", "bbs_sheets", ["project_id"])

    op.create_table(
        "bbs_bars",
        sa.Column("id",           sa.String(36), primary_key=True),
        sa.Column("sheet_id",     sa.String(36), sa.ForeignKey("bbs_sheets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sort_order",   sa.Integer(),  nullable=False, server_default="0"),
        sa.Column("is_heading",   sa.Boolean(),  nullable=False, server_default="false"),
        sa.Column("bar_mark",     sa.String(50),  nullable=True),
        sa.Column("position",     sa.String(100), nullable=True),
        sa.Column("member_mark",  sa.String(100), nullable=True),
        sa.Column("floor_level",  sa.String(50),  nullable=True),
        sa.Column("dia_mm",       sa.Integer(),   nullable=True),
        sa.Column("bar_shape",    sa.String(50),  nullable=False, server_default="straight"),
        sa.Column("num_bars",     sa.Integer(),   nullable=True, server_default="0"),
        sa.Column("clear_span_mm",     sa.Float(), nullable=True),
        sa.Column("support_near_mm",   sa.Float(), nullable=True),
        sa.Column("support_far_mm",    sa.Float(), nullable=True),
        sa.Column("section_b_mm",      sa.Float(), nullable=True),
        sa.Column("section_d_mm",      sa.Float(), nullable=True),
        sa.Column("cover_mm",          sa.Float(), nullable=True),
        sa.Column("spacing_mm",        sa.Float(), nullable=True),
        sa.Column("storey_height_mm",  sa.Float(), nullable=True),
        sa.Column("zone_length_mm",    sa.Float(), nullable=True),
        sa.Column("has_hook_near",     sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("has_hook_far",      sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("hook_type",         sa.String(20), nullable=False, server_default="standard"),
        sa.Column("lap_mm",            sa.Float(), nullable=True),
        sa.Column("dev_length_mm",     sa.Float(), nullable=True),
        sa.Column("cutting_length_mm", sa.Float(), nullable=True),
        sa.Column("total_length_mm",   sa.Float(), nullable=True),
        sa.Column("unit_weight_kg_per_m", sa.Float(), nullable=True),
        sa.Column("total_weight_kg",   sa.Float(), nullable=True),
        sa.Column("formula",    sa.Text(),     nullable=True),
        sa.Column("source",     sa.String(50), nullable=False, server_default="manual"),
        sa.Column("status",     sa.String(50), nullable=False, server_default="calculated"),
        sa.Column("remarks",    sa.Text(),     nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_bbs_bars_id",       "bbs_bars", ["id"])
    op.create_index("ix_bbs_bars_sheet_id", "bbs_bars", ["sheet_id"])


def downgrade() -> None:
    op.drop_table("bbs_bars")
    op.drop_table("bbs_sheets")
