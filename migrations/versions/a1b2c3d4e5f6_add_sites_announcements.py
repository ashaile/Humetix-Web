"""add sites, announcements tables and employees.site_id

Revision ID: a1b2c3d4e5f6
Revises: 2d328d13a043
Create Date: 2026-02-23 17:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '2d328d13a043'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('sites',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('address', sa.String(length=200), nullable=True),
        sa.Column('contact_person', sa.String(length=50), nullable=True),
        sa.Column('contact_phone', sa.String(length=20), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name', name='uq_site_name')
    )
    with op.batch_alter_table('sites', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_sites_name'), ['name'], unique=True)

    op.create_table('announcements',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('category', sa.String(length=20), nullable=False),
        sa.Column('is_pinned', sa.Boolean(), nullable=False),
        sa.Column('author', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('announcements', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_announcements_created_at'), ['created_at'], unique=False)

    with op.batch_alter_table('employees', schema=None) as batch_op:
        batch_op.add_column(sa.Column('site_id', sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f('ix_employees_site_id'), ['site_id'], unique=False)
        batch_op.create_foreign_key('fk_employees_site_id', 'sites', ['site_id'], ['id'], ondelete='SET NULL')


def downgrade():
    with op.batch_alter_table('employees', schema=None) as batch_op:
        batch_op.drop_constraint('fk_employees_site_id', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_employees_site_id'))
        batch_op.drop_column('site_id')

    with op.batch_alter_table('announcements', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_announcements_created_at'))
    op.drop_table('announcements')

    with op.batch_alter_table('sites', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_sites_name'))
    op.drop_table('sites')
