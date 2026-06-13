import os
import json
import time
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv(Path(__file__).parent / ".env")

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

_supabase: Optional[Client] = None


def get_supabase() -> Client:
    global _supabase
    if _supabase is None:
        _supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _supabase


def init_db():
    pass


# --- User functions ---

def create_user(username: str, email: str, password_hash: str) -> Optional[int]:
    try:
        data = {
            "username": username,
            "email": email,
            "password_hash": password_hash,
            "created_at": time.time(),
        }
        res = get_supabase().table("users").insert(data).execute()
        if res.data:
            return res.data[0]["id"]
    except Exception as e:
        print(f"[DB] create_user error: {e}")
    return None


def get_user_by_username(username: str) -> Optional[dict]:
    try:
        res = get_supabase().table("users").select("*").eq("username", username).limit(1).execute()
        if res.data:
            return res.data[0]
    except Exception as e:
        print(f"[DB] get_user_by_username error: {e}")
    return None


def get_user_by_email(email: str) -> Optional[dict]:
    try:
        res = get_supabase().table("users").select("*").eq("email", email).limit(1).execute()
        if res.data:
            return res.data[0]
    except Exception as e:
        print(f"[DB] get_user_by_email error: {e}")
    return None


def get_user_by_id(user_id: int) -> Optional[dict]:
    try:
        res = get_supabase().table("users").select("*").eq("id", user_id).limit(1).execute()
        if res.data:
            return res.data[0]
    except Exception as e:
        print(f"[DB] get_user_by_id error: {e}")
    return None


def update_user(user_id: int, **kwargs):
    allowed = [
        "whop_email", "whop_password", "tiktok_session_id", "tiktok_csrf_token",
        "youtube_client_id", "youtube_client_secret", "youtube_refresh_token",
        "instagram_username", "instagram_password", "facebook_page_id",
        "facebook_access_token", "posts_per_day", "campaign_keywords", "content_sources"
    ]
    updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
    if not updates:
        return
    try:
        get_supabase().table("users").update(updates).eq("id", user_id).execute()
    except Exception as e:
        print(f"[DB] update_user error: {e}")


# --- Campaign functions ---

def save_campaign(user_id: int, title: str, platform: str, url: str = "", budget: str = "", status: str = "pending"):
    try:
        data = {
            "user_id": user_id,
            "title": title,
            "platform": platform,
            "url": url,
            "budget": budget,
            "status": status,
            "applied_at": time.time() if status == "applied" else None,
        }
        get_supabase().table("campaigns").insert(data).execute()
    except Exception as e:
        print(f"[DB] save_campaign error: {e}")


def get_campaigns(user_id: int, limit: int = 20) -> list[dict]:
    try:
        res = get_supabase().table("campaigns").select("*").eq("user_id", user_id).order("id", desc=True).limit(limit).execute()
        return res.data if res.data else []
    except Exception as e:
        print(f"[DB] get_campaigns error: {e}")
    return []


# --- Content log functions ---

def log_content(user_id: int, event_name: str, content_type: str, platform: str = "", status: str = "created", file_path: str = "", error: str = ""):
    try:
        data = {
            "user_id": user_id,
            "event_name": event_name,
            "content_type": content_type,
            "platform": platform,
            "status": status,
            "file_path": file_path,
            "published_at": time.time() if status == "published" else None,
            "error": error,
        }
        get_supabase().table("content_log").insert(data).execute()
    except Exception as e:
        print(f"[DB] log_content error: {e}")


def get_content_log(user_id: int, limit: int = 20) -> list[dict]:
    try:
        res = get_supabase().table("content_log").select("*").eq("user_id", user_id).order("id", desc=True).limit(limit).execute()
        return res.data if res.data else []
    except Exception as e:
        print(f"[DB] get_content_log error: {e}")
    return []


# --- Token functions ---

def save_token(token: str, user_id: int, expires: float):
    try:
        data = {"token": token, "user_id": user_id, "expires": expires}
        get_supabase().table("tokens").upsert(data).execute()
    except Exception as e:
        print(f"[DB] save_token error: {e}")


def get_token_data(token: str) -> Optional[dict]:
    try:
        res = get_supabase().table("tokens").select("*").eq("token", token).limit(1).execute()
        if res.data:
            return res.data[0]
    except Exception as e:
        print(f"[DB] get_token_data error: {e}")
    return None


def delete_token(token: str):
    try:
        get_supabase().table("tokens").delete().eq("token", token).execute()
    except Exception as e:
        print(f"[DB] delete_token error: {e}")


def clean_expired_tokens():
    try:
        get_supabase().table("tokens").delete().lt("expires", time.time()).execute()
    except Exception as e:
        print(f"[DB] clean_expired_tokens error: {e}")
