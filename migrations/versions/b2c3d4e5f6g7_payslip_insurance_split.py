"""payslip: 4대보험 분리 컬럼 + is_manual 추가

Revision ID: b2c3d4e5f6g7
Revises: a1b2c3d4e5f6
Create Date: 2026-02-23 22:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b2c3d4e5f6g7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('payslips', schema=None) as batch_op:
        batch_op.add_column(sa.Column('pension', sa.Integer(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('health_ins', sa.Integer(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('longterm_care', sa.Integer(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('employment_ins', sa.Integer(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('is_manual', sa.Boolean(), nullable=False, server_default='0'))


def downgrade():
    with op.batch_alter_table('payslips', schema=None) as batch_op:
        batch_op.drop_column('is_manual')
        batch_op.drop_column('employment_ins')
        batch_op.drop_column('longterm_care')
        batch_op.drop_column('health_ins')
        batch_op.drop_column('pension')
