import json
import random
import time
import hashlib
import secrets
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Any

from fastapi import FastAPI, HTTPException, Depends, status, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional

from database import init_db, get_user_by_username, get_user_by_email, create_user, get_user_by_id, update_user, get_campaigns, save_campaign, get_content_log, log_content, save_token, get_token_data, delete_token, clean_expired_tokens, SUPABASE_URL, upload_file, list_files, get_file_url, delete_storage_file, SUPABASE_KEY, SUBSCRIPTION_PLANS, create_subscription, get_subscription, get_all_subscriptions, get_pending_subscriptions, activate_subscription, deactivate_subscription, get_referral_code, get_referrals, get_referral_earnings, get_user_by_referral_code, get_referral_commission
from config import UserConfig, WhopConfig, TikTokConfig, YouTubeConfig, PROCESSED_DIR, RAW_DIR, load_config
from pipeline import ContentPipeline
from modules.whop.auto_apply import WhopAutoApply
from modules.content.ingest import ContentIngestor
from modules.content.video_generator import VideoGenerator
from modules.content.audio_generator import AudioGenerator
from modules.content.translator import Translator
from modules.content.templates import VIDEO_INTRO_TEMPLATES, VIDEO_OUTRO_TEMPLATES
from scheduler import BotScheduler

app = FastAPI(title="Clipping Whop", version="1.0.0")
security = HTTPBearer(auto_error=False)

SECRET_KEY = secrets.token_hex(32)
TOKEN_EXPIRY = 2592000  # 30 days
scheduler: Optional[BotScheduler] = None


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(password: str, hash_: str) -> bool:
    return hash_password(password) == hash_


def gen_token(user_id: int) -> str:
    token = secrets.token_hex(32)
    expires = time.time() + TOKEN_EXPIRY
    save_token(token, user_id, expires)
    return token


def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = credentials.credentials
    data = get_token_data(token)
    if not data or data["expires"] < time.time():
        if data:
            delete_token(token)
        raise HTTPException(status_code=401, detail="Token expired")
    user = get_user_by_id(data["user_id"])
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def user_to_config(user: dict) -> UserConfig:
    try:
        keywords = json.loads(user.get("campaign_keywords", '["betway"]'))
    except (json.JSONDecodeError, TypeError):
        keywords = ["betway"]
    try:
        sources = json.loads(user.get("content_sources", '["youtube_replays"]'))
    except (json.JSONDecodeError, TypeError):
        sources = ["youtube_replays"]

    return UserConfig(
        whop=WhopConfig(email=user.get("whop_email", ""), password=user.get("whop_password", "")),
        tiktok=TikTokConfig(session_id=user.get("tiktok_session_id", "")),
        youtube=YouTubeConfig(
            client_id=user.get("youtube_client_id", ""),
            client_secret=user.get("youtube_client_secret", ""),
            refresh_token=user.get("youtube_refresh_token", ""),
        ),
        posts_per_day=user.get("posts_per_day", 3),
        campaign_keywords=keywords,
        content_sources=sources,
        target_language=user.get("target_language", "fr"),
    )


# --- API Routes ---

@app.on_event("startup")
async def startup():
    global scheduler
    if SUPABASE_URL:
        init_db()
        clean_expired_tokens()
        print("[API] Supabase connected")
    else:
        print("[API] ⚠️  Supabase non configure. Definis SUPABASE_URL et SUPABASE_KEY dans les variables d'environnement.")
    cfg = load_config()
    if cfg.active_user:
        try:
            scheduler = BotScheduler()
            scheduler.start()
        except Exception as e:
            print(f"[API] Scheduler startup error: {e}")


@app.get("/api/scheduler/status")
async def scheduler_status():
    if scheduler:
        return scheduler.get_status()
    return {"running": False, "active_user": None, "jobs": []}


@app.post("/api/scheduler/start")
async def scheduler_start(user: dict = Depends(get_current_user)):
    global scheduler
    if scheduler and scheduler.is_running:
        return {"ok": True, "status": "already_running"}
    try:
        scheduler = BotScheduler()
        ok = scheduler.start()
        return {"ok": ok, "status": "started" if ok else "failed"}
    except Exception as e:
        raise HTTPException(500, f"Scheduler error: {e}")


@app.post("/api/scheduler/stop")
async def scheduler_stop(user: dict = Depends(get_current_user)):
    global scheduler
    if scheduler:
        scheduler.stop()
    return {"ok": True, "status": "stopped"}


@app.post("/api/run-whop-apply")
async def run_whop_apply(user: dict = Depends(get_current_user)):
    cfg = user_to_config(user)
    if not cfg.whop.email:
        raise HTTPException(400, "Whop credentials not configured")
    try:
        applier = WhopAutoApply(cfg, headless=True)
        applier.run_auto_apply(max_applications=5)
        return {"ok": True}
    except Exception as e:
        raise HTTPException(500, f"Whop error: {e}")


class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str
    ref: Optional[str] = None


@app.post("/api/register")
async def register(req: RegisterRequest):
    if get_user_by_username(req.username):
        raise HTTPException(400, "Username already exists")
    if get_user_by_email(req.email):
        raise HTTPException(400, "Email already exists")

    referred_by = None
    if req.ref:
        referrer = get_user_by_referral_code(req.ref.strip())
        if referrer:
            referred_by = referrer["id"]

    user_id = create_user(req.username, req.email, hash_password(req.password), referred_by=referred_by)
    if not user_id:
        raise HTTPException(500, "Failed to create user")

    token = gen_token(user_id)
    return {"token": token, "user_id": user_id, "username": req.username}


class LoginRequest(BaseModel):
    username: str
    password: str


@app.post("/api/login")
async def login(req: LoginRequest):
    user = get_user_by_username(req.username)
    if not user or not verify_password(req.password, user["password_hash"]):
        raise HTTPException(401, "Invalid credentials")

    token = gen_token(user["id"])
    return {"token": token, "user_id": user["id"], "username": user["username"]}


@app.post("/api/logout")
async def logout(user: dict = Depends(get_current_user), credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)):
    if credentials:
        delete_token(credentials.credentials)
    return {"ok": True}


@app.get("/api/me")
async def get_me(user: dict = Depends(get_current_user)):
    safe = {k: v for k, v in user.items() if k != "password_hash"}
    return safe


@app.put("/api/settings")
async def update_settings(data: dict, user: dict = Depends(get_current_user)):
    update_user(user["id"], **data)

    from config import AppConfig, UserConfig, WhopConfig, TikTokConfig, YouTubeConfig, save_config, load_config
    try:
        cfg = load_config()
        u = UserConfig(
            whop=WhopConfig(email=user.get("whop_email", "") or data.get("whop_email", ""), password=user.get("whop_password", "") or data.get("whop_password", "")),
            tiktok=TikTokConfig(session_id=user.get("tiktok_session_id", "") or data.get("tiktok_session_id", ""), csrf_token=user.get("tiktok_csrf_token", "") or data.get("tiktok_csrf_token", "")),
            youtube=YouTubeConfig(
                client_id=user.get("youtube_client_id", "") or data.get("youtube_client_id", ""),
                client_secret=user.get("youtube_client_secret", "") or data.get("youtube_client_secret", ""),
                refresh_token=user.get("youtube_refresh_token", "") or data.get("youtube_refresh_token", ""),
            ),
            posts_per_day=data.get("posts_per_day", user.get("posts_per_day", 3)),
            campaign_keywords=data.get("campaign_keywords", user.get("campaign_keywords", ["world cup"])),
            target_language=data.get("target_language", user.get("target_language", "en")),
        )
        cfg.users[user["username"]] = u
        cfg.active_user = user["username"]
        save_config(cfg)
    except Exception as e:
        print(f"[API] Config save error (non-blocking): {e}")

    return {"ok": True}


@app.post("/api/run-pipeline")
async def run_pipeline(user: dict = Depends(get_current_user)):
    cfg = user_to_config(user)
    pipeline = ContentPipeline(cfg)
    try:
        results = pipeline.run_full_pipeline()
        log_content(user["id"], "Pipeline complete", "full", "all", "created")
        return results
    except Exception as e:
        log_content(user["id"], "Pipeline run", "full", "all", "error", error=str(e))
        raise HTTPException(500, f"Pipeline error: {e}")





@app.get("/api/campaigns")
async def list_campaigns(user: dict = Depends(get_current_user)):
    return get_campaigns(user["id"])


@app.get("/api/content-log")
async def content_log(user: dict = Depends(get_current_user)):
    return get_content_log(user["id"])


@app.get("/api/stats")
async def get_stats(user: dict = Depends(get_current_user)):
    campaigns = get_campaigns(user["id"])
    content = get_content_log(user["id"])
    return {
        "total_campaigns": len(campaigns),
        "applied_campaigns": sum(1 for c in campaigns if c["status"] == "applied"),
        "total_content": len(content),
        "published_content": sum(1 for c in content if c["status"] == "published"),
        "errors": sum(1 for c in content if c["status"] == "error"),
    }


# --- Content files ---

@app.get("/api/content-files")
async def list_content_files(user: dict = Depends(get_current_user)):
    files = []
    for ext in ("*.mp4", "*.mp3", "*.jpg", "*.png"):
        for p in [PROCESSED_DIR, RAW_DIR]:
            if p.exists():
                for f in p.rglob(ext):
                    size = f.stat().st_size
                    rel = f.relative_to(Path(__file__).parent)
                    files.append({
                        "name": f.name,
                        "path": str(rel.as_posix()),
                        "size": size,
                        "size_str": f"{size / 1024 / 1024:.1f} MB" if size > 1024*1024 else f"{size / 1024:.1f} KB",
                        "ext": f.suffix.lower(),
                        "modified": f.stat().st_mtime,
                    })
    files.sort(key=lambda x: x["modified"], reverse=True)
    return files


class GenerateClipRequest(BaseModel):
    url: str
    start_time: float = 10
    duration: float = 120
    num_clips: int = 1
    target_language: str = "fr"


@app.post("/api/generate-from-url")
async def generate_from_url(req: GenerateClipRequest, user: dict = Depends(get_current_user)):
    try:
        translator = Translator(req.target_language)
        tts_voice = translator.get_tts_voice()

        downloaded = await ContentIngestor.download_youtube_replay(
            req.url,
            max_duration=req.num_clips * req.duration + 120,
            output_dir=RAW_DIR,
        )
        if isinstance(downloaded, str):
            raise HTTPException(400, f"Download failed: {downloaded}")
        if not downloaded:
            raise HTTPException(400, "Download returned no file")

        total_duration = VideoGenerator.get_video_duration(downloaded)
        if total_duration <= 0:
            raise HTTPException(400, "Could not determine video duration")

        available = total_duration - req.start_time
        if available < req.duration:
            raise HTTPException(400, f"Video too short ({total_duration:.0f}s). Need at least {req.start_time + req.duration:.0f}s for one {req.duration}s clip.")

        actual_num = min(req.num_clips, int(available // req.duration))
        clips_generated = []

        for i in range(actual_num):
            start = req.start_time + (i * req.duration)

            intro_text = translator.translate(random.choice(VIDEO_INTRO_TEMPLATES)["text"])
            outro_text = translator.translate(random.choice(VIDEO_OUTRO_TEMPLATES)["text"])

            clip = VideoGenerator.generate_pro_clip(
                input_video=downloaded,
                output_name=f"custom_{int(time.time())}_{i+1}",
                start_time=start,
                duration=req.duration,
                add_ken_burns=True,
                add_color_grade=True,
                add_intro=True,
                add_outro=True,
                intro_text=intro_text,
                outro_text=outro_text,
            )
            if not clip:
                continue

            vo_text = translator.translate(random.choice([
                "This is absolutely incredible! You have to see this!",
                "Wait till the end, it gets wild!",
                "I can't believe this is real!",
                "This moment was absolutely insane!",
                "The best thing you'll see today!",
            ]))

            vo_path, _ = AudioGenerator.generate_voiceover(
                text=vo_text, output_name=f"vo_custom_{int(time.time())}_{i+1}", voice=tts_voice,
            )
            if vo_path and req.duration > 10:
                mixed = AudioGenerator.mix_audio_with_video(clip, vo_path, f"final_{int(time.time())}_{i+1}")
                if mixed:
                    clip = mixed

            subtitled = VideoGenerator.add_subtitles(clip, vo_text, f"sub_{int(time.time())}_{i+1}", duration=req.duration)
            if subtitled:
                clip = subtitled

            clips_generated.append(clip)

        if not clips_generated:
            raise HTTPException(500, "Failed to create any clip")

        log_content(user["id"], f"Generated {len(clips_generated)} clips from URL", "video", "manual", "created")

        for f in list(PROCESSED_DIR.glob("_pro_*.mp4")):
            f.unlink(missing_ok=True)

        clip_data = []
        for c in clips_generated:
            rel_path = str(c.relative_to(Path(__file__).parent).as_posix())
            clip_data.append({"file": str(c.name), "path": rel_path})

        return {"ok": True, "clips": clip_data, "count": len(clip_data)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Generation error: {e}")


@app.get("/api/download")
async def download_file(path: str, token: str = ""):
    user = None
    if token:
        data = get_token_data(token)
        if data and data["expires"] >= time.time():
            user = get_user_by_id(data["user_id"])
    if not user:
        raise HTTPException(401, "Not authenticated")
    file_path = Path(__file__).parent / path
    if not file_path.exists() or not str(file_path.resolve()).startswith(str(Path(__file__).parent.resolve())):
        raise HTTPException(404, "File not found")
    return FileResponse(str(file_path), media_type="video/mp4", filename=file_path.name, headers={"Content-Disposition": f"attachment; filename=\"{file_path.name}\""})

@app.delete("/api/content-files")
async def delete_content_file(path: str, user: dict = Depends(get_current_user)):
    if path.startswith("http"):
        raise HTTPException(400, "Cannot delete remote files from here")

    file_path = Path(__file__).parent / path
    storage_dir = Path(__file__).parent / "storage"
    try:
        file_path = file_path.resolve(strict=False)
    except (ValueError, OSError):
        raise HTTPException(400, "Invalid path")
    if not str(file_path).startswith(str(storage_dir.resolve())):
        raise HTTPException(400, "Access denied")
    if not file_path.exists():
        raise HTTPException(404, "File not found")
    try:
        file_path.unlink()
        log_content(user["id"], f"Deleted file", file_path.suffix, "manual", "deleted", file_path=str(file_path))
        return {"ok": True}
    except Exception as e:
        raise HTTPException(500, f"Delete error: {e}")


# --- Subscription endpoints ---

CRYPTO_WALLET_ADDRESS = "0xb365cfcd75f6425e05eb072a7c97032c8d21ad28"


@app.get("/api/subscription/plans")
async def subscription_plans():
    return {"plans": SUBSCRIPTION_PLANS}


OWNER_USERNAMES = {"lwango1"}

@app.get("/api/subscription/my")
async def my_subscription(user: dict = Depends(get_current_user)):
    is_owner = user.get("username") in OWNER_USERNAMES
    sub = get_subscription(user["id"])
    if is_owner:
        return {
            "plan": "owner",
            "status": "active",
            "tx_hash": None,
            "paid_at": None,
            "expires_at": None,
            "created_at": None,
            "is_owner": True,
        }
    if sub:
        return {
            "plan": sub["plan"],
            "status": sub["status"],
            "tx_hash": sub["tx_hash"],
            "paid_at": sub["paid_at"],
            "expires_at": sub["expires_at"],
            "created_at": sub["created_at"],
            "is_owner": False,
        }
    return {"plan": "free", "status": "active", "paid_at": None, "expires_at": None, "created_at": None, "is_owner": False}


class VerifyPaymentRequest(BaseModel):
    plan: str
    tx_hash: str


@app.post("/api/subscription/verify")
async def verify_payment(req: VerifyPaymentRequest, user: dict = Depends(get_current_user)):
    if req.plan not in SUBSCRIPTION_PLANS:
        raise HTTPException(400, "Plan invalide")
    if not req.tx_hash.strip():
        raise HTTPException(400, "Hash de transaction requis")
    existing = get_subscription(user["id"])
    if existing and existing["status"] == "active":
        return {"ok": True, "message": "Vous avez déjà un abonnement actif"}
    sub_id = create_subscription(user["id"], req.plan, req.tx_hash.strip(), status="pending")
    if not sub_id:
        raise HTTPException(500, "Erreur lors de la création de l'abonnement")
    return {"ok": True, "subscription_id": sub_id, "message": "Paiement en attente de confirmation"}


class ConfirmPaymentRequest(BaseModel):
    subscription_id: int


@app.post("/api/subscription/confirm")
async def confirm_payment(req: ConfirmPaymentRequest, user: dict = Depends(get_current_user)):
    if user.get("role") != "admin" and user.get("username") not in OWNER_USERNAMES:
        raise HTTPException(403, "Accès réservé aux administrateurs")
    activate_subscription(req.subscription_id)
    return {"ok": True, "message": "Abonnement activé"}


@app.get("/api/subscription/pending")
async def pending_subscriptions(user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(403, "Accès réservé aux administrateurs")
    return get_pending_subscriptions()


@app.get("/api/subscription/all")
async def all_subscriptions(user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(403, "Accès réservé aux administrateurs")
    return get_all_subscriptions()


@app.get("/api/subscription/address")
async def subscription_address():
    return {"address": CRYPTO_WALLET_ADDRESS, "network": "BNB (BEP-20 / BSC)"}


# --- Referral endpoints ---

@app.get("/api/referral/info")
async def referral_info(user: dict = Depends(get_current_user)):
    code = get_referral_code(user["id"])
    if not code:
        from database import generate_referral_code, set_referral_code
        code = generate_referral_code(f"{user['id']}-{user['username']}")
        set_referral_code(user["id"], code)
    referrals = get_referrals(user["id"])
    referral_count = len(referrals) if referrals else 0
    next_rate = get_referral_commission(referral_count)
    return {
        "code": code,
        "link": f"https://cliping-whop.onrender.com?ref={code}",
        "commission": int(next_rate * 100),
        "earnings": get_referral_earnings(user["id"]),
        "referral_count": referral_count,
        "tiers": [
            {"min": 0, "rate": 20},
            {"min": 1, "rate": 10},
            {"min": 2, "rate": 5},
        ],
    }


@app.get("/api/referral/list")
async def referral_list(user: dict = Depends(get_current_user)):
    return {"referrals": get_referrals(user["id"])}


# --- Serve static files ---

ASSETS_DIR = Path(__file__).parent / "assets"
if ASSETS_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR)), name="assets")

STORAGE_DIR = Path(__file__).parent / "storage"
if STORAGE_DIR.exists():
    app.mount("/storage", StaticFiles(directory=str(STORAGE_DIR)), name="storage")


# --- Web UI ---

HTML_DIR = Path(__file__).parent / "templates"


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def index():
    html = (HTML_DIR / "index.html").read_text(encoding="utf-8")
    return html

@app.head("/", include_in_schema=False)
async def index_head():
    return HTMLResponse()


@app.get("/app", response_class=HTMLResponse)
async def app_page():
    html = (HTML_DIR / "dashboard.html").read_text(encoding="utf-8")
    return html
