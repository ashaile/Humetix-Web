"""Add inquiries table

Revision ID: c9f2d12a3e7a
Revises: b3c6e8a9f1d2
Create Date: 2026-02-18 23:20:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c9f2d12a3e7a'
down_revision = 'b3c6e8a9f1d2'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'inquiries',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('company', sa.String(length=100), nullable=False),
        sa.Column('name', sa.String(length=50), nullable=False),
        sa.Column('phone', sa.String(length=30), nullable=False),
        sa.Column('email', sa.String(length=100), nullable=True),
        sa.Column('message', sa.Text(), nullable=True),
    )
    op.create_index('ix_inquiries_created_at', 'inquiries', ['created_at'])


def downgrade():
    op.drop_index('ix_inquiries_created_at', table_name='inquiries')
    op.drop_table('inquiries')
