"""Add indexes for filter/search columns

Revision ID: b3c6e8a9f1d2
Revises: 84ad86423ef3
Create Date: 2026-02-18 22:05:00.000000

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = 'b3c6e8a9f1d2'
down_revision = '84ad86423ef3'
branch_labels = None
depends_on = None


def upgrade():
    op.create_index('ix_applications_name', 'applications', ['name'])
    op.create_index('ix_applications_phone', 'applications', ['phone'])
    op.create_index('ix_applications_timestamp', 'applications', ['timestamp'])
    op.create_index('ix_applications_gender', 'applications', ['gender'])
    op.create_index('ix_applications_shift', 'applications', ['shift'])
    op.create_index('ix_applications_posture', 'applications', ['posture'])
    op.create_index('ix_applications_overtime', 'applications', ['overtime'])
    op.create_index('ix_applications_holiday', 'applications', ['holiday'])
    op.create_index('ix_applications_advance_pay', 'applications', ['advance_pay'])
    op.create_index('ix_applications_insurance_type', 'applications', ['insurance_type'])
    op.create_index('ix_careers_application_id', 'careers', ['application_id'])


def downgrade():
    op.drop_index('ix_careers_application_id', table_name='careers')
    op.drop_index('ix_applications_insurance_type', table_name='applications')
    op.drop_index('ix_applications_advance_pay', table_name='applications')
    op.drop_index('ix_applications_holiday', table_name='applications')
    op.drop_index('ix_applications_overtime', table_name='applications')
    op.drop_index('ix_applications_posture', table_name='applications')
    op.drop_index('ix_applications_shift', table_name='applications')
    op.drop_index('ix_applications_gender', table_name='applications')
    op.drop_index('ix_applications_timestamp', table_name='applications')
    op.drop_index('ix_applications_phone', table_name='applications')
    op.drop_index('ix_applications_name', table_name='applications')
