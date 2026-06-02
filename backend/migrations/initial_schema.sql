--initial schema for g. paste into supabase sql editor and run.
--equivalent to `alembic upgrade head` against an empty db.
--mirrors backend/models/*.py + design doc data model. timestamps stored utc.

CREATE EXTENSION IF NOT EXISTS "pgcrypto";  --for gen_random_uuid()

--enums
DO $$ BEGIN CREATE TYPE comm_style          AS ENUM ('brief','detailed');                          EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE preferred_channel   AS ENUM ('sms','call');                                EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE task_status         AS ENUM ('PENDING','IN_PROGRESS','ESCALATION_PENDING','COMPLETED','FAILED'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE message_direction   AS ENUM ('inbound','outbound');                        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE message_channel     AS ENUM ('sms','voice');                               EXCEPTION WHEN duplicate_object THEN NULL; END $$;

--users
CREATE TABLE IF NOT EXISTS users (
    id                 UUID              PRIMARY KEY DEFAULT gen_random_uuid(),
    phone_number       VARCHAR(20)       NOT NULL UNIQUE,
    email              VARCHAR(255)      UNIQUE,
    full_name          VARCHAR(120),     --display name shown in profile
    comm_style         comm_style        NOT NULL DEFAULT 'brief',
    preferred_channel  preferred_channel NOT NULL DEFAULT 'sms',
    blocked_windows    JSONB,
    calendar_token     TEXT,             --encrypted google oauth (calendar)
    gmail_token        TEXT,             --encrypted google oauth (gmail)
    created_at         TIMESTAMPTZ       NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_users_phone_number ON users (phone_number);

--backfill for existing dbs that pre-date full_name. safe to re-run.
ALTER TABLE users ADD COLUMN IF NOT EXISTS full_name VARCHAR(120);

--tasks
CREATE TABLE IF NOT EXISTS tasks (
    id                   UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id              UUID         NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status               task_status  NOT NULL DEFAULT 'PENDING',
    type                 VARCHAR(50)  NOT NULL,
    description          TEXT         NOT NULL,
    plan_steps           JSONB,
    force_overlap        BOOLEAN      NOT NULL DEFAULT FALSE,  -- parent approved adding event despite calendar conflict
    escalation_deadline  TIMESTAMPTZ,
    created_at           TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_tasks_user_id ON tasks (user_id);
CREATE INDEX IF NOT EXISTS ix_tasks_status  ON tasks (status);

--[GenAI Use] Prompt: write a postgres plpgsql trigger function that sets the updated_at column to 
--the current timestamp whenever a row in the tasks table is updated. Then create a trigger that calls this function
--before any update is made to the tasks table. 
--[GenAI Use] LLM Response: 
--auto-touch updated_at
CREATE OR REPLACE FUNCTION set_updated_at() RETURNS TRIGGER AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_tasks_updated_at ON tasks;
CREATE TRIGGER trg_tasks_updated_at
    BEFORE UPDATE ON tasks
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
--[GenAI Use] Response end
--[GenAI Use] REflect: the above trigger will ensure that on every row update the updated_at column is appropriately updated,
--however this functionality still needs to be tested

--messages
CREATE TABLE IF NOT EXISTS messages (
    id          UUID                PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id     UUID                REFERENCES tasks(id) ON DELETE SET NULL,
    user_id     UUID                REFERENCES users(id) ON DELETE CASCADE,
    direction   message_direction   NOT NULL,
    channel     message_channel     NOT NULL,
    content     TEXT                NOT NULL,
    timestamp   TIMESTAMPTZ         NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_messages_task_id   ON messages (task_id);
CREATE INDEX IF NOT EXISTS ix_messages_user_id   ON messages (user_id);
CREATE INDEX IF NOT EXISTS ix_messages_timestamp ON messages (timestamp);

--preferences
CREATE TABLE IF NOT EXISTS preferences (
    user_id  UUID         NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    key      VARCHAR(100) NOT NULL,
    value    TEXT         NOT NULL,
    PRIMARY KEY (user_id, key)
);
CREATE INDEX IF NOT EXISTS ix_preferences_user_id ON preferences (user_id);

--family_members - dependents / household members surfaced in profile page
CREATE TABLE IF NOT EXISTS family_members (
    id          UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID         NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name        VARCHAR(120) NOT NULL,
    relation    VARCHAR(60),                       --"Spouse", "Son", "Daughter", free-text
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_family_members_user_id ON family_members (user_id);

--contacts - third parties G may call/text on the user's behalf (schools, offices, etc.)
CREATE TABLE IF NOT EXISTS contacts (
    id          UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID         NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name        VARCHAR(120) NOT NULL,
    role        VARCHAR(120),                      --"Office Manager", "Pediatrician"
    org         VARCHAR(160),                      --"Mark's School", "Cedar Medical"
    phone       VARCHAR(40),                       --any format, normalized at call-time
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_contacts_user_id ON contacts (user_id);

--providers - preferred service providers G defaults to when booking/referring
CREATE TABLE IF NOT EXISTS providers (
    id          UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID         NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name        VARCHAR(120) NOT NULL,
    specialty   VARCHAR(120),                      --"Dentist", "Pediatrician", "Plumber"
    practice    VARCHAR(160),                      --practice / business name, optional
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_providers_user_id ON providers (user_id);
