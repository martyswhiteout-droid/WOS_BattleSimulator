-- shell/db/migrations/001_init.sql
-- Purpose: full production schema for the WoS Battle Simulator shell.
-- Implements PRODUCTION_PLAN.md §2.2 (data model) and §2.4 (limits inputs);
-- supports PRODUCTION_CRITERIA.md §C (paywall state) and §D (usage_events for
-- quotas + sweep detection).
--
-- Identity lives in Clerk; this schema is a data-only mirror keyed by
-- clerk_user_id. The shell is the ONLY database client (service-role,
-- server-side). RLS is enabled on every table as defense-in-depth: with no
-- anon/authenticated policies, PostgREST-style clients see nothing; the
-- shell's direct service-role connection is unaffected.

BEGIN;

-- ---------------------------------------------------------------------------
-- users — local mirror of Clerk identities (for joins)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    clerk_user_id  TEXT PRIMARY KEY,
    email          TEXT,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- profiles — display metadata
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS profiles (
    clerk_user_id  TEXT PRIMARY KEY REFERENCES users(clerk_user_id) ON DELETE CASCADE,
    display_name   TEXT,
    game_server    TEXT,
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- subscriptions — updated ONLY by verified Stripe webhook or admin action
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS subscriptions (
    clerk_user_id           TEXT PRIMARY KEY REFERENCES users(clerk_user_id) ON DELETE CASCADE,
    stripe_customer_id      TEXT,
    stripe_subscription_id  TEXT UNIQUE,
    plan                    TEXT NOT NULL DEFAULT 'free',
    status                  TEXT NOT NULL DEFAULT 'inactive',
    current_period_end      TIMESTAMPTZ,
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_subscriptions_customer
    ON subscriptions (stripe_customer_id);

-- ---------------------------------------------------------------------------
-- entitlements — plan -> quotas. SINGLE SOURCE OF TRUTH for tier limits
-- (PRODUCTION_CRITERIA D2). Seeded: free = 5 sims/day, 0 OCR;
-- pro = 100 sims/day, 30 OCR/day; max_runs 1000 per simulation request.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS entitlements (
    plan             TEXT PRIMARY KEY,
    daily_sim_quota  INTEGER NOT NULL,
    daily_ocr_quota  INTEGER NOT NULL,
    max_runs         INTEGER NOT NULL
);

INSERT INTO entitlements (plan, daily_sim_quota, daily_ocr_quota, max_runs)
VALUES
    ('free', 5,   0,  1000),
    ('pro',  100, 30, 1000)
ON CONFLICT (plan) DO UPDATE
    SET daily_sim_quota = EXCLUDED.daily_sim_quota,
        daily_ocr_quota = EXCLUDED.daily_ocr_quota,
        max_runs        = EXCLUDED.max_runs;

-- ---------------------------------------------------------------------------
-- usage_events — append-only; feeds daily quotas, per-IP caps, burst window
-- AND sweep detection (PRODUCTION_CRITERIA D2/D3).
--   request_fingerprint = sha256 of normalized body (sorted keys, troop
--     values rounded to nearest 100).
--   fp_fields = per-leaf-field value hashes of the same normalized body;
--     lets sweep_scan detect "many near-identical queries differing in one
--     field" without storing raw payloads (intentional addition to §2.2).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS usage_events (
    id                   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    clerk_user_id        TEXT NOT NULL,
    ip_hash              TEXT,
    endpoint             TEXT NOT NULL,
    kind                 TEXT NOT NULL,          -- 'sim' | 'ocr'
    request_fingerprint  TEXT,
    fp_fields            JSONB,
    troops_own           BIGINT,
    troops_enemy         BIGINT,
    ts                   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_usage_events_user_ts
    ON usage_events (clerk_user_id, ts);
CREATE INDEX IF NOT EXISTS idx_usage_events_fingerprint
    ON usage_events (request_fingerprint);
CREATE INDEX IF NOT EXISTS idx_usage_events_ip_ts
    ON usage_events (ip_hash, ts);

-- ---------------------------------------------------------------------------
-- ocr_jobs — upload ref, image hash (cache key), extraction + validation
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ocr_jobs (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clerk_user_id     TEXT NOT NULL,
    upload_ref        TEXT,
    image_hash        TEXT,
    status            TEXT NOT NULL DEFAULT 'pending',  -- pending|ok|partial|failed
    extracted         JSONB,
    validator_verdict JSONB,
    cost_usd          NUMERIC(10, 5),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ocr_jobs_image_hash ON ocr_jobs (image_hash);
CREATE INDEX IF NOT EXISTS idx_ocr_jobs_user ON ocr_jobs (clerk_user_id, created_at);

-- ---------------------------------------------------------------------------
-- saved_scenarios — schema_version mandatory (PRODUCTION_CRITERIA B1/B4)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS saved_scenarios (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clerk_user_id   TEXT NOT NULL REFERENCES users(clerk_user_id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    schema_version  TEXT NOT NULL,
    payload         JSONB NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_saved_scenarios_user
    ON saved_scenarios (clerk_user_id, created_at);

-- ---------------------------------------------------------------------------
-- audit_log — admin/security events. dedup_key (UNIQUE, nullable) doubles as
-- the idempotency ledger for Stripe webhook event ids and sweep flags.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS audit_log (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    event_type  TEXT NOT NULL,
    actor       TEXT,
    subject     TEXT,
    detail      JSONB,
    dedup_key   TEXT UNIQUE,
    ts          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_audit_log_type_ts ON audit_log (event_type, ts);
CREATE INDEX IF NOT EXISTS idx_audit_log_subject ON audit_log (subject);

-- ---------------------------------------------------------------------------
-- RLS: enabled everywhere; no policies for anon/authenticated (deny-all for
-- API-gateway roles). Service-role-only policies are created when the
-- Supabase `service_role` exists; on vanilla Postgres (CI) the DO blocks
-- no-op. The shell's own connection (table owner / service role) is the only
-- intended client.
-- ---------------------------------------------------------------------------
ALTER TABLE users            ENABLE ROW LEVEL SECURITY;
ALTER TABLE profiles         ENABLE ROW LEVEL SECURITY;
ALTER TABLE subscriptions    ENABLE ROW LEVEL SECURITY;
ALTER TABLE entitlements     ENABLE ROW LEVEL SECURITY;
ALTER TABLE usage_events     ENABLE ROW LEVEL SECURITY;
ALTER TABLE ocr_jobs         ENABLE ROW LEVEL SECURITY;
ALTER TABLE saved_scenarios  ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_log        ENABLE ROW LEVEL SECURITY;

DO $$
DECLARE
    t TEXT;
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
        FOREACH t IN ARRAY ARRAY['users', 'profiles', 'subscriptions',
                                 'entitlements', 'usage_events', 'ocr_jobs',
                                 'saved_scenarios', 'audit_log'] LOOP
            EXECUTE format(
                'DROP POLICY IF EXISTS service_role_all ON %I', t);
            EXECUTE format(
                'CREATE POLICY service_role_all ON %I FOR ALL TO service_role '
                'USING (true) WITH CHECK (true)', t);
        END LOOP;
    END IF;
    -- Belt-and-braces: strip default grants from Supabase API roles if present.
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        FOREACH t IN ARRAY ARRAY['users', 'profiles', 'subscriptions',
                                 'entitlements', 'usage_events', 'ocr_jobs',
                                 'saved_scenarios', 'audit_log'] LOOP
            EXECUTE format('REVOKE ALL ON %I FROM anon', t);
        END LOOP;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        FOREACH t IN ARRAY ARRAY['users', 'profiles', 'subscriptions',
                                 'entitlements', 'usage_events', 'ocr_jobs',
                                 'saved_scenarios', 'audit_log'] LOOP
            EXECUTE format('REVOKE ALL ON %I FROM authenticated', t);
        END LOOP;
    END IF;
END $$;

COMMIT;
