"""Initial schema — all tables

Revision ID: 0001
Revises:
Create Date: 2024-01-01 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── users ────────────────────────────────────────
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('full_name', sa.String(255), nullable=False),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('role', sa.Enum('admin','estimation_engineer','quantity_surveyor','project_manager', name='userrole'), nullable=False),
        sa.Column('phone', sa.String(30), nullable=True),
        sa.Column('company', sa.String(255), nullable=True),
        sa.Column('designation', sa.String(255), nullable=True),
        sa.Column('profile_picture', sa.String(500), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_verified', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('password_reset_token', sa.String(255), nullable=True),
        sa.Column('password_reset_expires', sa.DateTime(), nullable=True),
        sa.Column('last_login', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)
    op.create_index('ix_users_id', 'users', ['id'])

    # ── projects ──────────────────────────────────────
    op.create_table(
        'projects',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('project_code', sa.String(50), nullable=False),
        sa.Column('project_name', sa.String(500), nullable=False),
        sa.Column('client_name', sa.String(255), nullable=False),
        sa.Column('client_contact', sa.String(100), nullable=True),
        sa.Column('client_email', sa.String(255), nullable=True),
        sa.Column('location', sa.String(500), nullable=False),
        sa.Column('city', sa.String(100), nullable=True),
        sa.Column('state', sa.String(100), nullable=True),
        sa.Column('country', sa.String(100), nullable=True, server_default='Pakistan'),
        sa.Column('building_type', sa.Enum('residential','commercial','industrial','institutional','mixed_use', name='buildingtype'), nullable=False),
        sa.Column('num_floors', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('total_built_up_area', sa.Float(), nullable=True),
        sa.Column('plot_area', sa.Float(), nullable=True),
        sa.Column('start_date', sa.Date(), nullable=True),
        sa.Column('expected_completion', sa.Date(), nullable=True),
        sa.Column('status', sa.Enum('draft','active','on_hold','completed','archived', name='projectstatus'), nullable=False, server_default='draft'),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('total_estimated_cost', sa.Float(), nullable=True, server_default='0'),
        sa.Column('currency', sa.String(10), nullable=False, server_default='PKR'),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_projects_id', 'projects', ['id'])
    op.create_index('ix_projects_project_code', 'projects', ['project_code'], unique=True)

    # ── buildings ─────────────────────────────────────
    op.create_table(
        'buildings',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('building_name', sa.String(255), nullable=False, server_default='Main Building'),
        sa.Column('num_floors', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('plot_length', sa.Float(), nullable=True),
        sa.Column('plot_width', sa.Float(), nullable=True),
        sa.Column('excavation_depth', sa.Float(), nullable=True, server_default='1.5'),
        sa.Column('footing_length', sa.Float(), nullable=True, server_default='1.2'),
        sa.Column('footing_width', sa.Float(), nullable=True, server_default='1.2'),
        sa.Column('footing_depth', sa.Float(), nullable=True, server_default='0.3'),
        sa.Column('num_footings', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('pcc_thickness', sa.Float(), nullable=True, server_default='0.075'),
        sa.Column('column_length', sa.Float(), nullable=True, server_default='0.3'),
        sa.Column('column_width', sa.Float(), nullable=True, server_default='0.3'),
        sa.Column('floor_height', sa.Float(), nullable=True, server_default='3.0'),
        sa.Column('num_columns', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('beam_width', sa.Float(), nullable=True, server_default='0.23'),
        sa.Column('beam_depth', sa.Float(), nullable=True, server_default='0.45'),
        sa.Column('total_beam_length', sa.Float(), nullable=True, server_default='0'),
        sa.Column('slab_length', sa.Float(), nullable=True),
        sa.Column('slab_width', sa.Float(), nullable=True),
        sa.Column('slab_thickness', sa.Float(), nullable=True, server_default='0.125'),
        sa.Column('wall_thickness_external', sa.Float(), nullable=True, server_default='0.23'),
        sa.Column('wall_thickness_internal', sa.Float(), nullable=True, server_default='0.115'),
        sa.Column('total_external_wall_length', sa.Float(), nullable=True, server_default='0'),
        sa.Column('total_internal_wall_length', sa.Float(), nullable=True, server_default='0'),
        sa.Column('wall_height', sa.Float(), nullable=True, server_default='3.0'),
        sa.Column('plaster_thickness_external', sa.Float(), nullable=True, server_default='0.020'),
        sa.Column('plaster_thickness_internal', sa.Float(), nullable=True, server_default='0.012'),
        sa.Column('flooring_type', sa.String(100), nullable=True, server_default='tiles'),
        sa.Column('tile_size', sa.Float(), nullable=True, server_default='0.6'),
        sa.Column('tile_wastage_pct', sa.Float(), nullable=True, server_default='10.0'),
        sa.Column('paint_coats', sa.Integer(), nullable=True, server_default='2'),
        sa.Column('num_doors', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('door_width', sa.Float(), nullable=True, server_default='0.9'),
        sa.Column('door_height', sa.Float(), nullable=True, server_default='2.1'),
        sa.Column('num_windows', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('window_width', sa.Float(), nullable=True, server_default='1.2'),
        sa.Column('window_height', sa.Float(), nullable=True, server_default='1.2'),
        sa.Column('steel_percentage_slab', sa.Float(), nullable=True, server_default='1.0'),
        sa.Column('steel_percentage_column', sa.Float(), nullable=True, server_default='2.5'),
        sa.Column('steel_percentage_beam', sa.Float(), nullable=True, server_default='2.0'),
        sa.Column('waterproofing_area', sa.Float(), nullable=True, server_default='0'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_buildings_id', 'buildings', ['id'])

    # ── rooms ─────────────────────────────────────────
    op.create_table(
        'rooms',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('building_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('floor_number', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('room_name', sa.String(255), nullable=False),
        sa.Column('length', sa.Float(), nullable=False),
        sa.Column('width', sa.Float(), nullable=False),
        sa.Column('height', sa.Float(), nullable=True),
        sa.Column('area', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['building_id'], ['buildings.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── materials ─────────────────────────────────────
    op.create_table(
        'materials',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('material_code', sa.String(50), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('category', sa.Enum('cement','aggregate','sand','steel','brick','block','paint','tile','waterproofing','wood','glass','electrical','plumbing','other', name='materialcategory'), nullable=False),
        sa.Column('unit', sa.Enum('kg','ton','bag','m3','m2','lm','no','ltr','gal', name='materialunit'), nullable=False),
        sa.Column('current_rate', sa.Float(), nullable=False),
        sa.Column('rate_per_kg', sa.Float(), nullable=True),
        sa.Column('supplier_name', sa.String(255), nullable=True),
        sa.Column('supplier_contact', sa.String(100), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('last_updated', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_materials_id', 'materials', ['id'])
    op.create_index('ix_materials_material_code', 'materials', ['material_code'], unique=True)

    # ── material_rate_history ─────────────────────────
    op.create_table(
        'material_rate_history',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('material_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('old_rate', sa.Float(), nullable=False),
        sa.Column('new_rate', sa.Float(), nullable=False),
        sa.Column('changed_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('changed_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('notes', sa.String(500), nullable=True),
        sa.ForeignKeyConstraint(['material_id'], ['materials.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['changed_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── estimates ─────────────────────────────────────
    op.create_table(
        'estimates',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('building_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('work_type', sa.Enum(
            'excavation','pcc','rcc_footing','rcc_column','rcc_beam','rcc_slab',
            'brickwork','blockwork','plaster_external','plaster_internal',
            'flooring','tiling','paint_external','paint_internal',
            'steel_reinforcement','waterproofing','doors','windows',
            name='worktype'), nullable=False),
        sa.Column('quantity', sa.Float(), nullable=False, server_default='0'),
        sa.Column('unit', sa.String(30), nullable=False, server_default='m3'),
        sa.Column('calculation_details', postgresql.JSON(), nullable=True),
        sa.Column('cement_bags', sa.Float(), nullable=True, server_default='0'),
        sa.Column('sand_cft', sa.Float(), nullable=True, server_default='0'),
        sa.Column('aggregate_cft', sa.Float(), nullable=True, server_default='0'),
        sa.Column('steel_kg', sa.Float(), nullable=True, server_default='0'),
        sa.Column('bricks_nos', sa.Float(), nullable=True, server_default='0'),
        sa.Column('blocks_nos', sa.Float(), nullable=True, server_default='0'),
        sa.Column('paint_ltr', sa.Float(), nullable=True, server_default='0'),
        sa.Column('tiles_sqm', sa.Float(), nullable=True, server_default='0'),
        sa.Column('material_cost', sa.Float(), nullable=True, server_default='0'),
        sa.Column('labour_cost', sa.Float(), nullable=True, server_default='0'),
        sa.Column('equipment_cost', sa.Float(), nullable=True, server_default='0'),
        sa.Column('total_cost', sa.Float(), nullable=True, server_default='0'),
        sa.Column('is_from_dxf', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['building_id'], ['buildings.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_estimates_id', 'estimates', ['id'])

    # ── boqs ──────────────────────────────────────────
    op.create_table(
        'boqs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('boq_number', sa.String(50), nullable=False),
        sa.Column('revision', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('status', sa.Enum('draft','finalized','approved','revised', name='boqstatus'), nullable=False, server_default='draft'),
        sa.Column('prepared_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('approved_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('approval_date', sa.DateTime(), nullable=True),
        sa.Column('subtotal', sa.Float(), nullable=True, server_default='0'),
        sa.Column('overhead_pct', sa.Float(), nullable=True, server_default='10'),
        sa.Column('overhead_amount', sa.Float(), nullable=True, server_default='0'),
        sa.Column('profit_pct', sa.Float(), nullable=True, server_default='10'),
        sa.Column('profit_amount', sa.Float(), nullable=True, server_default='0'),
        sa.Column('contingency_pct', sa.Float(), nullable=True, server_default='5'),
        sa.Column('contingency_amount', sa.Float(), nullable=True, server_default='0'),
        sa.Column('grand_total', sa.Float(), nullable=True, server_default='0'),
        sa.Column('currency', sa.String(10), nullable=False, server_default='PKR'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['prepared_by'], ['users.id']),
        sa.ForeignKeyConstraint(['approved_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_boqs_id', 'boqs', ['id'])

    # ── boq_items ─────────────────────────────────────
    op.create_table(
        'boq_items',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('boq_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('material_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('item_no', sa.String(20), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('specification', sa.Text(), nullable=True),
        sa.Column('unit', sa.String(30), nullable=False),
        sa.Column('quantity', sa.Float(), nullable=False, server_default='0'),
        sa.Column('rate', sa.Float(), nullable=False, server_default='0'),
        sa.Column('amount', sa.Float(), nullable=False, server_default='0'),
        sa.Column('material_rate', sa.Float(), nullable=True, server_default='0'),
        sa.Column('labour_rate', sa.Float(), nullable=True, server_default='0'),
        sa.Column('equipment_rate', sa.Float(), nullable=True, server_default='0'),
        sa.Column('is_heading', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_provisional', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('work_type', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['boq_id'], ['boqs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['material_id'], ['materials.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_boq_items_id', 'boq_items', ['id'])

    # ── reports ───────────────────────────────────────
    op.create_table(
        'reports',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('generated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('report_type', sa.Enum('project','quantity','boq','cost', name='reporttype'), nullable=False),
        sa.Column('report_format', sa.Enum('pdf','excel','csv', name='reportformat'), nullable=False),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('file_path', sa.String(1000), nullable=True),
        sa.Column('file_size_kb', sa.String(20), nullable=True),
        sa.Column('is_available', sa.Boolean(), server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['generated_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── audit_logs ────────────────────────────────────
    op.create_table(
        'audit_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('action', sa.String(100), nullable=False),
        sa.Column('resource_type', sa.String(100), nullable=True),
        sa.Column('resource_id', sa.String(100), nullable=True),
        sa.Column('details', sa.Text(), nullable=True),
        sa.Column('ip_address', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── inspections ───────────────────────────────────
    op.create_table(
        'inspections',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('inspected_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('inspection_type', sa.Enum('concrete_crack','surface_crack','road_damage','building_safety', name='inspectiontype'), nullable=False),
        sa.Column('image_path', sa.String(1000), nullable=True),
        sa.Column('image_filename', sa.String(500), nullable=True),
        sa.Column('model_name', sa.String(100), nullable=True),
        sa.Column('predicted_class', sa.String(200), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('severity', sa.Enum('none','low','moderate','high','critical', name='severitylevel'), nullable=False, server_default='none'),
        sa.Column('severity_score', sa.Float(), nullable=True),
        sa.Column('detection_boxes', sa.Text(), nullable=True),
        sa.Column('recommendation', sa.Text(), nullable=True),
        sa.Column('repair_urgency', sa.String(50), nullable=True),
        sa.Column('estimated_repair_cost_min', sa.Float(), nullable=True),
        sa.Column('estimated_repair_cost_max', sa.Float(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('is_verified', sa.Boolean(), server_default='false'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['inspected_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_inspections_id', 'inspections', ['id'])


def downgrade() -> None:
    op.drop_table('inspections')
    op.drop_table('audit_logs')
    op.drop_table('reports')
    op.drop_table('boq_items')
    op.drop_table('boqs')
    op.drop_table('estimates')
    op.drop_table('material_rate_history')
    op.drop_table('materials')
    op.drop_table('rooms')
    op.drop_table('buildings')
    op.drop_table('projects')
    op.drop_table('users')

    # Drop enum types
    for enum in ['userrole','buildingtype','projectstatus','materialcategory','materialunit',
                 'worktype','boqstatus','reporttype','reportformat','inspectiontype','severitylevel']:
        op.execute(f'DROP TYPE IF EXISTS {enum}')
