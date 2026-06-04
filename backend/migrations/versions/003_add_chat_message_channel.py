"""add chat to message_channel enum

Revision ID: 003_add_chat_message_channel
Revises: 002_expand_user_profile
Create Date: 2026-06-04

"""
from alembic import op

revision = '003_add_chat_message_channel'
down_revision = '002_expand_user_profile'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # PostgreSQL requires COMMIT before ALTER TYPE ADD VALUE outside a transaction
    op.execute("ALTER TYPE message_channel ADD VALUE IF NOT EXISTS 'chat'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values — downgrade is intentionally a no-op
    pass
