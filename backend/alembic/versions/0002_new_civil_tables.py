"""Add SOR, Measurement, RateAnalysis, Billing tables

Revision ID: 0002
Revises: 0001
Create Date: 2024-01-02 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0002'
down_revision: Union[str, None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── sor_items ──────────────────────────────────────
    op.create_table(
        'sor_items',
        sa.Column('id',             sa.String(36), primary_key=True),
        sa.Column('item_code',      sa.String(50),  nullable=False, unique=True),
        sa.Column('description',    sa.Text(),      nullable=False),
        sa.Column('specification',  sa.Text(),      nullable=True),
        sa.Column('category',       sa.String(50),  nullable=False, server_default='other'),
        sa.Column('sub_category',   sa.String(100), nullable=True),
        sa.Column('unit',           sa.String(30),  nullable=False),
        sa.Column('basic_rate',     sa.Float(),     nullable=False, server_default='0'),
        sa.Column('material_rate',  sa.Float(),     nullable=True,  server_default='0'),
        sa.Column('labour_rate',    sa.Float(),     nullable=True,  server_default='0'),
        sa.Column('equipment_rate', sa.Float(),     nullable=True,  server_default='0'),
        sa.Column('rate_source',    sa.String(30),  nullable=False, server_default='custom'),
        sa.Column('rate_year',      sa.Integer(),   nullable=True),
        sa.Column('rate_location',  sa.String(100), nullable=True),
        sa.Column('formula_type',   sa.String(50),  nullable=True),
        sa.Column('formula_note',   sa.Text(),      nullable=True),
        sa.Column('mix_design',     sa.String(30),  nullable=True),
        sa.Column('is_active',      sa.Boolean(),   nullable=False, server_default='true'),
        sa.Column('is_system',      sa.Boolean(),   nullable=False, server_default='false'),
        sa.Column('tags',           sa.String(500), nullable=True),
        sa.Column('notes',          sa.Text(),      nullable=True),
        sa.Column('created_at',     sa.DateTime(),  nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at',     sa.DateTime(),  nullable=True),
    )
    op.create_index('ix_sor_items_id',        'sor_items', ['id'])
    op.create_index('ix_sor_items_item_code', 'sor_items', ['item_code'], unique=True)

    # ── measurement_books ──────────────────────────────
    op.create_table(
        'measurement_books',
        sa.Column('id',                  sa.String(36), primary_key=True),
        sa.Column('project_id',          sa.String(36), sa.ForeignKey('projects.id',  ondelete='CASCADE'), nullable=False),
        sa.Column('building_id',         sa.String(36), sa.ForeignKey('buildings.id', ondelete='SET NULL'), nullable=True),
        sa.Column('boq_id',              sa.String(36), sa.ForeignKey('boqs.id',      ondelete='SET NULL'), nullable=True),
        sa.Column('mb_number',           sa.String(50),  nullable=False),
        sa.Column('title',               sa.String(500), nullable=False, server_default='Measurement Book'),
        sa.Column('description',         sa.Text(),      nullable=True),
        sa.Column('prepared_by',         sa.String(36),  sa.ForeignKey('users.id'), nullable=True),
        sa.Column('checked_by',          sa.String(255), nullable=True),
        sa.Column('date_of_measurement', sa.DateTime(),  nullable=True),
        sa.Column('is_approved',         sa.Boolean(),   nullable=False, server_default='false'),
        sa.Column('notes',               sa.Text(),      nullable=True),
        sa.Column('created_at',          sa.DateTime(),  nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at',          sa.DateTime(),  nullable=True),
    )
    op.create_index('ix_measurement_books_id', 'measurement_books', ['id'])

    # ── measurement_items ──────────────────────────────
    op.create_table(
        'measurement_items',
        sa.Column('id',                 sa.String(36), primary_key=True),
        sa.Column('book_id',            sa.String(36), sa.ForeignKey('measurement_books.id', ondelete='CASCADE'), nullable=False),
        sa.Column('sor_item_id',        sa.String(36), sa.ForeignKey('sor_items.id'), nullable=True),
        sa.Column('sort_order',         sa.Integer(),  nullable=False, server_default='0'),
        sa.Column('is_heading',         sa.Boolean(),  nullable=False, server_default='false'),
        sa.Column('item_ref',           sa.String(50), nullable=True),
        sa.Column('description',        sa.Text(),     nullable=False),
        sa.Column('unit',               sa.String(30), nullable=True),
        sa.Column('length',             sa.Float(),    nullable=True),
        sa.Column('width',              sa.Float(),    nullable=True),
        sa.Column('height',             sa.Float(),    nullable=True),
        sa.Column('nos',                sa.Float(),    nullable=True, server_default='1'),
        sa.Column('quantity',           sa.Float(),    nullable=True, server_default='0'),
        sa.Column('formula_display',    sa.Text(),     nullable=True),
        sa.Column('is_manual_override', sa.Boolean(),  nullable=False, server_default='false'),
        sa.Column('override_reason',    sa.String(500), nullable=True),
        sa.Column('is_deduction',       sa.Boolean(),  nullable=False, server_default='false'),
        sa.Column('deduction_ref',      sa.String(100), nullable=True),
        sa.Column('notes',              sa.Text(),     nullable=True),
        sa.Column('created_at',         sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at',         sa.DateTime(), nullable=True),
    )
    op.create_index('ix_measurement_items_id', 'measurement_items', ['id'])

    # ── rate_analyses ──────────────────────────────────
    op.create_table(
        'rate_analyses',
        sa.Column('id',              sa.String(36), primary_key=True),
        sa.Column('sor_item_id',     sa.String(36), sa.ForeignKey('sor_items.id',  ondelete='CASCADE'), nullable=False),
        sa.Column('project_id',      sa.String(36), sa.ForeignKey('projects.id',   ondelete='SET NULL'), nullable=True),
        sa.Column('title',           sa.String(500), nullable=False),
        sa.Column('unit',            sa.String(30),  nullable=False),
        sa.Column('location',        sa.String(100), nullable=True),
        sa.Column('rate_year',       sa.String(10),  nullable=True),
        sa.Column('material_total',  sa.Float(),     nullable=False, server_default='0'),
        sa.Column('labour_total',    sa.Float(),     nullable=False, server_default='0'),
        sa.Column('equipment_total', sa.Float(),     nullable=False, server_default='0'),
        sa.Column('direct_cost',     sa.Float(),     nullable=False, server_default='0'),
        sa.Column('wastage_pct',     sa.Float(),     nullable=False, server_default='5'),
        sa.Column('wastage_amount',  sa.Float(),     nullable=False, server_default='0'),
        sa.Column('overhead_pct',    sa.Float(),     nullable=False, server_default='10'),
        sa.Column('overhead_amount', sa.Float(),     nullable=False, server_default='0'),
        sa.Column('profit_pct',      sa.Float(),     nullable=False, server_default='10'),
        sa.Column('profit_amount',   sa.Float(),     nullable=False, server_default='0'),
        sa.Column('final_rate',      sa.Float(),     nullable=False, server_default='0'),
        sa.Column('is_template',     sa.Boolean(),   nullable=False, server_default='false'),
        sa.Column('notes',           sa.Text(),      nullable=True),
        sa.Column('created_at',      sa.DateTime(),  nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at',      sa.DateTime(),  nullable=True),
    )
    op.create_index('ix_rate_analyses_id', 'rate_analyses', ['id'])

    # ── rate_components ────────────────────────────────
    op.create_table(
        'rate_components',
        sa.Column('id',             sa.String(36), primary_key=True),
        sa.Column('analysis_id',    sa.String(36), sa.ForeignKey('rate_analyses.id', ondelete='CASCADE'), nullable=False),
        sa.Column('material_id',    sa.String(36), sa.ForeignKey('materials.id'), nullable=True),
        sa.Column('component_type', sa.String(20),  nullable=False),
        sa.Column('description',    sa.String(500), nullable=False),
        sa.Column('unit',           sa.String(30),  nullable=False),
        sa.Column('quantity',       sa.Float(),     nullable=False, server_default='0'),
        sa.Column('rate',           sa.Float(),     nullable=False, server_default='0'),
        sa.Column('amount',         sa.Float(),     nullable=False, server_default='0'),
        sa.Column('sort_order',     sa.Float(),     nullable=False, server_default='0'),
    )
    op.create_index('ix_rate_components_id', 'rate_components', ['id'])

    # ── ra_bills ───────────────────────────────────────
    op.create_table(
        'ra_bills',
        sa.Column('id',                sa.String(36), primary_key=True),
        sa.Column('project_id',        sa.String(36), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('boq_id',            sa.String(36), sa.ForeignKey('boqs.id',     ondelete='CASCADE'), nullable=False),
        sa.Column('bill_number',       sa.String(50),  nullable=False),
        sa.Column('bill_date',         sa.DateTime(),  nullable=True),
        sa.Column('period_from',       sa.DateTime(),  nullable=True),
        sa.Column('period_to',         sa.DateTime(),  nullable=True),
        sa.Column('status',            sa.String(20),  nullable=False, server_default='draft'),
        sa.Column('contractor_name',   sa.String(255), nullable=True),
        sa.Column('prepared_by',       sa.String(36),  sa.ForeignKey('users.id'), nullable=True),
        sa.Column('certified_by',      sa.String(255), nullable=True),
        sa.Column('current_amount',    sa.Float(),     nullable=False, server_default='0'),
        sa.Column('cumulative_amount', sa.Float(),     nullable=False, server_default='0'),
        sa.Column('previous_amount',   sa.Float(),     nullable=False, server_default='0'),
        sa.Column('deductions',        sa.Float(),     nullable=False, server_default='0'),
        sa.Column('net_payable',       sa.Float(),     nullable=False, server_default='0'),
        sa.Column('allow_excess',      sa.Boolean(),   nullable=False, server_default='false'),
        sa.Column('notes',             sa.Text(),      nullable=True),
        sa.Column('created_at',        sa.DateTime(),  nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at',        sa.DateTime(),  nullable=True),
    )
    op.create_index('ix_ra_bills_id', 'ra_bills', ['id'])

    # ── ra_bill_items ──────────────────────────────────
    op.create_table(
        'ra_bill_items',
        sa.Column('id',                  sa.String(36), primary_key=True),
        sa.Column('bill_id',             sa.String(36), sa.ForeignKey('ra_bills.id',   ondelete='CASCADE'), nullable=False),
        sa.Column('boq_item_id',         sa.String(36), sa.ForeignKey('boq_items.id'), nullable=True),
        sa.Column('item_no',             sa.String(20),  nullable=False),
        sa.Column('description',         sa.Text(),      nullable=False),
        sa.Column('unit',                sa.String(30),  nullable=False),
        sa.Column('rate',                sa.Float(),     nullable=False, server_default='0'),
        sa.Column('boq_quantity',        sa.Float(),     nullable=False, server_default='0'),
        sa.Column('previous_quantity',   sa.Float(),     nullable=False, server_default='0'),
        sa.Column('current_quantity',    sa.Float(),     nullable=False, server_default='0'),
        sa.Column('cumulative_quantity', sa.Float(),     nullable=False, server_default='0'),
        sa.Column('balance_quantity',    sa.Float(),     nullable=False, server_default='0'),
        sa.Column('current_amount',      sa.Float(),     nullable=False, server_default='0'),
        sa.Column('cumulative_amount',   sa.Float(),     nullable=False, server_default='0'),
        sa.Column('previous_amount',     sa.Float(),     nullable=False, server_default='0'),
        sa.Column('is_heading',          sa.Boolean(),   nullable=False, server_default='false'),
        sa.Column('remarks',             sa.String(500), nullable=True),
    )
    op.create_index('ix_ra_bill_items_id', 'ra_bill_items', ['id'])


def downgrade() -> None:
    op.drop_table('ra_bill_items')
    op.drop_table('ra_bills')
    op.drop_table('rate_components')
    op.drop_table('rate_analyses')
    op.drop_table('measurement_items')
    op.drop_table('measurement_books')
    op.drop_table('sor_items')
