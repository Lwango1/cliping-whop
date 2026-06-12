import sqlite3
import json
import time
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

DB_PATH = Path(__file__).parent / "data" / "clipping_whop.db"


def get_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at REAL NOT NULL,
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
            campaign_keywords TEXT DEFAULT '["betway","world cup","canada"]',
            content_sources TEXT DEFAULT '["youtube_replays","sports_api"]'
        );

        CREATE TABLE IF NOT EXISTS campaigns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            platform TEXT DEFAULT 'whop',
            url TEXT DEFAULT '',
            budget TEXT DEFAULT '',
            status TEXT DEFAULT 'pending',
            applied_at REAL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS content_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            event_name TEXT DEFAULT '',
            content_type TEXT DEFAULT 'video',
            platform TEXT DEFAULT '',
            status TEXT DEFAULT 'created',
            file_path TEXT DEFAULT '',
            published_at REAL,
            error TEXT DEFAULT '',
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
    """)
    conn.commit()
    conn.close()


# --- User functions ---

def create_user(username: str, email: str, password_hash: str) -> Optional[int]:
    conn = get_db()
    try:
        cur = conn.execute(
            "INSERT INTO users (username, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
            (username, email, password_hash, time.time())
        )
        conn.commit()
        return cur.lastrowid
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()


def get_user_by_username(username: str) -> Optional[dict]:
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_email(email: str) -> Optional[dict]:
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_id(user_id: int) -> Optional[dict]:
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_user(user_id: int, **kwargs):
    allowed = [
        "whop_email", "whop_password", "tiktok_session_id", "tiktok_csrf_token",
        "youtube_client_id", "youtube_client_secret", "youtube_refresh_token",
        "instagram_username", "instagram_password", "facebook_page_id",
        "facebook_access_token", "posts_per_day", "campaign_keywords", "content_sources"
    ]
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return
    sets = ", ".join(f"{k} = ?" for k in updates)
    vals = list(updates.values())
    vals.append(user_id)
    conn = get_db()
    conn.execute(f"UPDATE users SET {sets} WHERE id = ?", vals)
    conn.commit()
    conn.close()


# --- Campaign functions ---

def save_campaign(user_id: int, title: str, platform: str, url: str = "", budget: str = "", status: str = "pending"):
    conn = get_db()
    conn.execute(
        "INSERT INTO campaigns (user_id, title, platform, url, budget, status, applied_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (user_id, title, platform, url, budget, status, time.time() if status == "applied" else None)
    )
    conn.commit()
    conn.close()


def get_campaigns(user_id: int, limit: int = 20) -> list[dict]:
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM campaigns WHERE user_id = ? ORDER BY id DESC LIMIT ?",
        (user_id, limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --- Content log functions ---

def log_content(user_id: int, event_name: str, content_type: str, platform: str = "", status: str = "created", file_path: str = "", error: str = ""):
    conn = get_db()
    conn.execute(
        "INSERT INTO content_log (user_id, event_name, content_type, platform, status, file_path, published_at, error) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (user_id, event_name, content_type, platform, status, file_path, time.time() if status == "published" else None, error)
    )
    conn.commit()
    conn.close()


def get_content_log(user_id: int, limit: int = 20) -> list[dict]:
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM content_log WHERE user_id = ? ORDER BY id DESC LIMIT ?",
        (user_id, limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
