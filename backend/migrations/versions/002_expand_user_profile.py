"""expand users with profile-page knobs; collapse google tokens to JSONB;
add family_members.phone_number

Adds the columns needed to persist everything the Profile page collects:
call urgency threshold, keep-free windows, active days, morning digest config,
escalation behavior, tone, reminder lead time, and conflict handling.

Also reconciles the schema with the code refactor that replaced the separate
`calendar_token` / `gmail_token` columns on users with a single `google_oauth`
JSONB. The earlier refactor landed in code but didn't ship a migration --
this catches the schema up.

And adds `phone_number` to family_members so the family-list form in the
profile page has a column to write into.

Revision ID: 002_expand_user_profile
Revises: 001_add_auth_fields
Create Date: 2026-06-01

"""
from alembic import op
import sqlalchemy as sa


revision = "002_expand_user_profile"
down_revision = "001_add_auth_fields"
branch_labels = None
depends_on = None


_CALL_URGENCY_VALUES = ("any", "high", "never")
_DIGEST_CONTENT_VALUES = ("calendar", "calendar+email", "calendar+tasks")
_TONE_VALUES = ("casual", "formal")
_CONFLICT_HANDLING_VALUES = ("suggest", "flag")


def upgrade() -> None:
    bind = op.get_bind()

    #new enum types
    call_urgency_enum = sa.Enum(
        *_CALL_URGENCY_VALUES, name="call_urgency"
    )
    digest_content_enum = sa.Enum(
        *_DIGEST_CONTENT_VALUES, name="digest_content"
    )
    tone_enum = sa.Enum(*_TONE_VALUES, name="tone")
    conflict_handling_enum = sa.Enum(
        *_CONFLICT_HANDLING_VALUES, name="conflict_handling"
    )

    call_urgency_enum.create(bind, checkfirst=True)
    digest_content_enum.create(bind, checkfirst=True)
    tone_enum.create(bind, checkfirst=True)
    conflict_handling_enum.create(bind, checkfirst=True)

    #users: catch up to the google_oauth refactor. the earlier in-code swap
    #from calendar_token + gmail_token -> google_oauth JSONB never shipped a
    #migration, so different databases are in different states:
    #  - shared Supabase: already has google_oauth, legacy cols already gone
    #  - any fresh / teammate dev db: still has the legacy cols, no google_oauth
    #guard each op against the live schema so this section is a no-op when
    #already applied and a real catch-up when not.
    inspector = sa.inspect(bind)
    user_cols = {c["name"] for c in inspector.get_columns("users")}

    if "google_oauth" not in user_cols:
        op.add_column(
            "users",
            sa.Column("google_oauth", sa.dialects.postgresql.JSONB(), nullable=True),
        )
    if "calendar_token" in user_cols:
        op.drop_column("users", "calendar_token")
    if "gmail_token" in user_cols:
        op.drop_column("users", "gmail_token")

    #users: new profile-page columns
    op.add_column(
        "users",
        sa.Column(
            "call_urgency_threshold",
            call_urgency_enum,
            nullable=False,
            server_default="high",
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "keep_free_windows",
            sa.dialects.postgresql.JSONB(),
            nullable=True,
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "active_days",
            sa.dialects.postgresql.JSONB(),
            nullable=True,
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "morning_digest_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )
    op.add_column(
        "users",
        sa.Column("morning_digest_time", sa.String(length=5), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column(
            "morning_digest_content",
            digest_content_enum,
            nullable=False,
            server_default="calendar",
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "morning_digest_travel_time",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "escalation_timeout_minutes",
            sa.Integer(),
            nullable=False,
            server_default="30",
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "auto_approve_low_risk",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "max_reminders",
            sa.Integer(),
            nullable=False,
            server_default="3",
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "tone",
            tone_enum,
            nullable=False,
            server_default="casual",
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "reminder_lead_time_minutes",
            sa.Integer(),
            nullable=False,
            server_default="60",
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "conflict_handling",
            conflict_handling_enum,
            nullable=False,
            server_default="suggest",
        ),
    )

    #family_members: phone_number
    op.add_column(
        "family_members",
        sa.Column("phone_number", sa.String(length=20), nullable=True),
    )


def downgrade() -> None:
    bind = op.get_bind()

    #family_members
    op.drop_column("family_members", "phone_number")

    #users: drop new profile-page columns
    op.drop_column("users", "conflict_handling")
    op.drop_column("users", "reminder_lead_time_minutes")
    op.drop_column("users", "tone")
    op.drop_column("users", "max_reminders")
    op.drop_column("users", "auto_approve_low_risk")
    op.drop_column("users", "escalation_timeout_minutes")
    op.drop_column("users", "morning_digest_travel_time")
    op.drop_column("users", "morning_digest_content")
    op.drop_column("users", "morning_digest_time")
    op.drop_column("users", "morning_digest_enabled")
    op.drop_column("users", "active_days")
    op.drop_column("users", "keep_free_windows")
    op.drop_column("users", "call_urgency_threshold")

    #users: restore legacy google token columns
    op.add_column(
        "users",
        sa.Column("gmail_token", sa.Text(), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("calendar_token", sa.Text(), nullable=True),
    )
    op.drop_column("users", "google_oauth")

    #drop enum types
    sa.Enum(name="conflict_handling").drop(bind, checkfirst=True)
    sa.Enum(name="tone").drop(bind, checkfirst=True)
    sa.Enum(name="digest_content").drop(bind, checkfirst=True)
    sa.Enum(name="call_urgency").drop(bind, checkfirst=True)
