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

def create_user(username: str, email: str, password_hash: str, referred_by: Optional[int] = None) -> Optional[int]:
    try:
        data = {
            "username": username,
            "email": email,
            "password_hash": password_hash,
            "created_at": time.time(),
            "referral_code": generate_referral_code(int(time.time() * 1000)),
        }
        if referred_by:
            data["referred_by"] = referred_by
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


# --- Subscription functions ---

SUBSCRIPTION_PLANS = {
    "free": {"name": "Free", "price": 0, "price_label": "0$", "features": ["1 campagne/jour", "Contenu basique", "Support email"]},
    "starter": {"name": "Starter", "price": 5, "price_label": "5$/mois", "features": ["10 campagnes/jour", "Contenu premium", "Publication auto", "Support prioritaire"]},
    "pro": {"name": "Pro", "price": 10, "price_label": "10$/mois", "features": ["Campagnes illimitées", "Contenu pro HD", "Multi-plateforme", "Support VIP", "API access"]},
}


def create_subscription(user_id: int, plan: str, tx_hash: str, status: str = "pending") -> Optional[int]:
    try:
        now = time.time()
        user = get_user_by_id(user_id)
        referred_by = user.get("referred_by") if user else None
        commission_rate = None
        if referred_by:
            existing = get_referrals(referred_by)
            idx = len(existing) if existing else 0
            commission_rate = get_referral_commission(idx)
        data = {
            "user_id": user_id,
            "plan": plan,
            "status": status,
            "tx_hash": tx_hash,
            "paid_at": now,
            "expires_at": now + 2592000,
            "created_at": now,
            "referred_by": referred_by,
            "commission_rate": commission_rate,
        }
        res = get_supabase().table("subscriptions").insert(data).execute()
        if res.data:
            return res.data[0]["id"]
    except Exception as e:
        print(f"[DB] create_subscription error: {e}")
    return None


def get_subscription(user_id: int) -> Optional[dict]:
    try:
        res = get_supabase().table("subscriptions").select("*").eq("user_id", user_id).order("id", desc=True).limit(1).execute()
        if res.data:
            return res.data[0]
    except Exception as e:
        print(f"[DB] get_subscription error: {e}")
    return None


def get_all_subscriptions(limit: int = 50) -> list[dict]:
    try:
        res = get_supabase().table("subscriptions").select("*").order("id", desc=True).limit(limit).execute()
        return res.data if res.data else []
    except Exception as e:
        print(f"[DB] get_all_subscriptions error: {e}")
    return []


def get_pending_subscriptions() -> list[dict]:
    try:
        res = get_supabase().table("subscriptions").select("*").eq("status", "pending").limit(50).execute()
        return res.data if res.data else []
    except Exception as e:
        print(f"[DB] get_pending_subscriptions error: {e}")
    return []


def activate_subscription(subscription_id: int):
    try:
        now = time.time()
        get_supabase().table("subscriptions").update({
            "status": "active",
            "paid_at": now,
            "expires_at": now + 2592000,
        }).eq("id", subscription_id).execute()
    except Exception as e:
        print(f"[DB] activate_subscription error: {e}")


def deactivate_subscription(subscription_id: int):
    try:
        get_supabase().table("subscriptions").update({"status": "expired"}).eq("id", subscription_id).execute()
    except Exception as e:
        print(f"[DB] deactivate_subscription error: {e}")


# --- Referral functions ---

REFERRAL_TIERS = [
    (0, 0.20),   # 1er filleul → 20%
    (1, 0.10),   # 2e filleul  → 10%
    (2, 0.05),   # 3e+ filleul → 5%
]

def get_referral_commission(referral_index: int) -> float:
    for threshold, rate in REFERRAL_TIERS:
        if referral_index >= threshold:
            result = rate
    return result

def generate_referral_code(seed) -> str:
    import hashlib
    h = hashlib.md5(f"{seed}".encode()).hexdigest()[:8]
    return h


def get_referral_code(user_id: int) -> Optional[str]:
    try:
        res = get_supabase().table("users").select("referral_code").eq("id", user_id).limit(1).execute()
        if res.data and res.data[0].get("referral_code"):
            return res.data[0]["referral_code"]
    except:
        pass
    return None


def set_referral_code(user_id: int, code: str):
    try:
        get_supabase().table("users").update({"referral_code": code}).eq("id", user_id).execute()
    except Exception as e:
        print(f"[DB] set_referral_code error: {e}")


def get_user_by_referral_code(code: str) -> Optional[dict]:
    try:
        res = get_supabase().table("users").select("*").eq("referral_code", code).limit(1).execute()
        if res.data:
            return res.data[0]
    except:
        pass
    return None


def get_referrals(user_id: int) -> list[dict]:
    try:
        res = get_supabase().table("users").select("id, username, email, created_at").eq("referred_by", user_id).order("id", desc=True).execute()
        return res.data if res.data else []
    except Exception as e:
        print(f"[DB] get_referrals error: {e}")
    return []


def get_referral_earnings(user_id: int) -> float:
    try:
        res = get_supabase().table("subscriptions").select("plan, commission_rate").eq("referred_by", user_id).eq("status", "active").execute()
        total = 0
        if res.data:
            for sub in res.data:
                plan_price = SUBSCRIPTION_PLANS.get(sub["plan"], {}).get("price", 0)
                rate = sub.get("commission_rate") or 0.05
                total += plan_price * rate
        return total
    except Exception as e:
        print(f"[DB] get_referral_earnings error: {e}")
    return 0.0


# --- Storage functions ---

def upload_file(local_path: Path, storage_path: str, bucket: str = "clips") -> Optional[str]:
    try:
        with open(local_path, "rb") as f:
            res = get_supabase().storage.from_(bucket).upload(storage_path, f, {"upsert": "true"})
        return storage_path
    except Exception as e:
        print(f"[DB] upload_file error: {e}")
    return None


def list_files(bucket: str = "clips") -> list[dict]:
    try:
        res = get_supabase().storage.from_(bucket).list()
        return res if res else []
    except Exception as e:
        print(f"[DB] list_files error: {e}")
    return []


def bucket_exists(bucket: str = "clips") -> bool:
    try:
        get_supabase().storage.from_(bucket).list(limit=1)
        return True
    except Exception:
        return False


def get_file_url(path: str, bucket: str = "clips") -> Optional[str]:
    try:
        res = get_supabase().storage.from_(bucket).get_public_url(path)
        return res
    except Exception as e:
        print(f"[DB] get_file_url error: {e}")
    return None


def delete_storage_file(path: str, bucket: str = "clips"):
    try:
        get_supabase().storage.from_(bucket).remove([path])
    except Exception as e:
        print(f"[DB] delete_storage_file error: {e}")
