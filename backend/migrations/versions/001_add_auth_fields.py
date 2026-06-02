"""add name, password_hash, make phone_number nullable

Revision ID: 001_add_auth_fields
Revises:
Create Date: 2026-06-01

"""
from alembic import op
import sqlalchemy as sa

revision = '001_add_auth_fields'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('name', sa.String(255), nullable=True))
    op.add_column('users', sa.Column('password_hash', sa.String(255), nullable=True))
    op.alter_column('users', 'phone_number', existing_type=sa.String(20), nullable=True)
    op.create_index('ix_users_email', 'users', ['email'], unique=True, if_not_exists=True)


def downgrade() -> None:
    op.drop_index('ix_users_email', table_name='users')
    op.drop_column('users', 'password_hash')
    op.drop_column('users', 'name')
    op.alter_column('users', 'phone_number', existing_type=sa.String(20), nullable=False)
