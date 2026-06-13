-- Exécute ce SQL dans Supabase SQL Editor (https://supabase.com/dashboard/project/_/sql/new)
-- pour créer les tables nécessaires.

CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at DOUBLE PRECISION NOT NULL DEFAULT EXTRACT(EPOCH FROM now()),
    is_active INTEGER DEFAULT 1,
    whop_email TEXT DEFAULT '',
    whop_password TEXT DEFAULT '',
    tiktok_session_id TEXT DEFAULT '',
    tiktok_csrf_token TEXT DEFAULT '',
    youtube_client_id TEXT DEFAULT '',
    youtube_client_secret TEXT DEFAULT '',
    youtube_refresh_token TEXT DEFAULT '',
    instagram_username TEXT DEFAULT '',
    instagram_password TEXT DEFAULT '',
    facebook_page_id TEXT DEFAULT '',
    facebook_access_token TEXT DEFAULT '',
    posts_per_day INTEGER DEFAULT 3,
    campaign_keywords TEXT DEFAULT '["world cup","canada","football"]',
    content_sources TEXT DEFAULT '["youtube_replays","sports_api"]'
);

CREATE TABLE IF NOT EXISTS tokens (
    token TEXT PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires DOUBLE PRECISION NOT NULL
);

CREATE TABLE IF NOT EXISTS campaigns (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    platform TEXT DEFAULT 'whop',
    url TEXT DEFAULT '',
    budget TEXT DEFAULT '',
    status TEXT DEFAULT 'pending',
    applied_at DOUBLE PRECISION
);

CREATE TABLE IF NOT EXISTS content_log (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    event_name TEXT DEFAULT '',
    content_type TEXT DEFAULT 'video',
    platform TEXT DEFAULT '',
    status TEXT DEFAULT 'created',
    file_path TEXT DEFAULT '',
    published_at DOUBLE PRECISION,
    error TEXT DEFAULT ''
);
