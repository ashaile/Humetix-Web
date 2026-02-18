"""Add status and inquiry admin fields

Revision ID: d2a7f1c3b9a1
Revises: c9f2d12a3e7a
Create Date: 2026-02-19 00:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd2a7f1c3b9a1'
down_revision = 'c9f2d12a3e7a'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('applications', schema=None) as batch_op:
        batch_op.add_column(sa.Column('updated_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('status', sa.String(length=20), nullable=True))
        batch_op.create_index('ix_applications_status', ['status'])
        batch_op.create_index('ix_applications_updated_at', ['updated_at'])
        batch_op.create_index('ix_applications_email', ['email'])

    with op.batch_alter_table('inquiries', schema=None) as batch_op:
        batch_op.add_column(sa.Column('updated_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('status', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('assignee', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('admin_memo', sa.Text(), nullable=True))
        batch_op.create_index('ix_inquiries_status', ['status'])
        batch_op.create_index('ix_inquiries_updated_at', ['updated_at'])
        batch_op.create_index('ix_inquiries_company', ['company'])
        batch_op.create_index('ix_inquiries_name', ['name'])
        batch_op.create_index('ix_inquiries_phone', ['phone'])
        batch_op.create_index('ix_inquiries_email', ['email'])

    op.execute("UPDATE applications SET status='new' WHERE status IS NULL")
    op.execute("UPDATE inquiries SET status='new' WHERE status IS NULL")


def downgrade():
    with op.batch_alter_table('inquiries', schema=None) as batch_op:
        batch_op.drop_index('ix_inquiries_updated_at')
        batch_op.drop_index('ix_inquiries_status')
        batch_op.drop_index('ix_inquiries_email')
        batch_op.drop_index('ix_inquiries_phone')
        batch_op.drop_index('ix_inquiries_name')
        batch_op.drop_index('ix_inquiries_company')
        batch_op.drop_column('admin_memo')
        batch_op.drop_column('assignee')
        batch_op.drop_column('status')
        batch_op.drop_column('updated_at')

    with op.batch_alter_table('applications', schema=None) as batch_op:
        batch_op.drop_index('ix_applications_updated_at')
        batch_op.drop_index('ix_applications_status')
        batch_op.drop_index('ix_applications_email')
        batch_op.drop_column('status')
        batch_op.drop_column('updated_at')
