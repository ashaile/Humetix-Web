"""add expires_at to contracts and contract_audit_logs table

Revision ID: c3d4e5f6g7h8
Revises: b2c3d4e5f6g7
Create Date: 2026-02-24 03:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c3d4e5f6g7h8'
down_revision = 'b2c3d4e5f6g7'
branch_labels = None
depends_on = None


def upgrade():
    # contracts 테이블에 expires_at 컬럼 추가
    with op.batch_alter_table('contracts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('expires_at', sa.DateTime(), nullable=True))

    # contract_audit_logs 테이블 생성
    op.create_table('contract_audit_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('contract_id', sa.Integer(), nullable=True),
        sa.Column('action', sa.String(length=50), nullable=False),
        sa.Column('actor', sa.String(length=100), nullable=True),
        sa.Column('detail', sa.Text(), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['contract_id'], ['contracts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('contract_audit_logs', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_contract_audit_logs_contract_id'), ['contract_id'], unique=False)


def downgrade():
    with op.batch_alter_table('contract_audit_logs', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_contract_audit_logs_contract_id'))
    op.drop_table('contract_audit_logs')

    with op.batch_alter_table('contracts', schema=None) as batch_op:
        batch_op.drop_column('expires_at')
