"""merge branches and add missing tables/columns

Revision ID: d5e6f7g8h9i0
Revises: 64427fd5d4cc, c3d4e5f6g7h8
Create Date: 2026-02-24 17:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd5e6f7g8h9i0'
down_revision = ('64427fd5d4cc', 'c3d4e5f6g7h8')
branch_labels = None
depends_on = None


def upgrade():
    # 1) contracts.batch_id 컬럼 추가 (대량전송용)
    with op.batch_alter_table('contracts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('batch_id', sa.String(length=50), nullable=True))
        batch_op.create_index('ix_contracts_batch_id', ['batch_id'], unique=False)

    # 2) leave_accruals 테이블 생성
    op.create_table('leave_accruals',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('employee_id', sa.Integer(), nullable=False),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('month', sa.Integer(), nullable=False),
        sa.Column('accrual_type', sa.String(length=20), nullable=False),
        sa.Column('days', sa.Float(), nullable=False),
        sa.Column('remaining', sa.Float(), nullable=False),
        sa.Column('description', sa.String(length=200), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['employee_id'], ['employees.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('employee_id', 'year', 'month', name='uq_leave_accrual_emp_year_month'),
    )
    with op.batch_alter_table('leave_accruals', schema=None) as batch_op:
        batch_op.create_index('ix_leave_accruals_employee_id', ['employee_id'], unique=False)
        batch_op.create_index('ix_leave_accruals_year', ['year'], unique=False)

    # 3) leave_usages 테이블 생성
    op.create_table('leave_usages',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('employee_id', sa.Integer(), nullable=False),
        sa.Column('accrual_id', sa.Integer(), nullable=True),
        sa.Column('use_date', sa.Date(), nullable=False),
        sa.Column('days', sa.Float(), nullable=False),
        sa.Column('description', sa.String(length=200), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['accrual_id'], ['leave_accruals.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['employee_id'], ['employees.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('leave_usages', schema=None) as batch_op:
        batch_op.create_index('ix_leave_usages_employee_id', ['employee_id'], unique=False)
        batch_op.create_index('ix_leave_usages_use_date', ['use_date'], unique=False)

    # 4) leave_balances.carryover 컬럼 추가
    with op.batch_alter_table('leave_balances', schema=None) as batch_op:
        batch_op.add_column(sa.Column('carryover', sa.Float(), server_default='0', nullable=True))

    # 5) employees.insurance_type 컬럼 추가
    with op.batch_alter_table('employees', schema=None) as batch_op:
        batch_op.add_column(sa.Column('insurance_type', sa.String(length=20), nullable=True))


def downgrade():
    with op.batch_alter_table('employees', schema=None) as batch_op:
        batch_op.drop_column('insurance_type')

    with op.batch_alter_table('leave_balances', schema=None) as batch_op:
        batch_op.drop_column('carryover')

    with op.batch_alter_table('leave_usages', schema=None) as batch_op:
        batch_op.drop_index('ix_leave_usages_use_date')
        batch_op.drop_index('ix_leave_usages_employee_id')
    op.drop_table('leave_usages')

    with op.batch_alter_table('leave_accruals', schema=None) as batch_op:
        batch_op.drop_index('ix_leave_accruals_year')
        batch_op.drop_index('ix_leave_accruals_employee_id')
    op.drop_table('leave_accruals')

    with op.batch_alter_table('contracts', schema=None) as batch_op:
        batch_op.drop_index('ix_contracts_batch_id')
        batch_op.drop_column('batch_id')
