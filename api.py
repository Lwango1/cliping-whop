import json
import time
import hashlib
import secrets
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Any

from fastapi import FastAPI, HTTPException, Depends, status, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional

from database import init_db, get_user_by_username, get_user_by_email, create_user, get_user_by_id, update_user, get_campaigns, save_campaign, get_content_log, log_content, save_token, get_token_data, delete_token, clean_expired_tokens, SUPABASE_URL, upload_file, list_files, get_file_url, delete_storage_file, SUPABASE_KEY
from config import UserConfig, WhopConfig, TikTokConfig, YouTubeConfig, InstagramConfig, FacebookConfig, PROCESSED_DIR, RAW_DIR, load_config
from pipeline import ContentPipeline
from modules.whop.auto_apply import WhopAutoApply
from modules.content.ingest import ContentIngestor
from modules.content.video_generator import VideoGenerator
from modules.content.audio_generator import AudioGenerator
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
        instagram=InstagramConfig(
            username=user.get("instagram_username", ""),
            password=user.get("instagram_password", ""),
        ),
        facebook=FacebookConfig(
            page_id=user.get("facebook_page_id", ""),
            access_token=user.get("facebook_access_token", ""),
        ),
        posts_per_day=user.get("posts_per_day", 3),
        campaign_keywords=keywords,
        content_sources=sources,
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


@app.post("/api/register")
async def register(req: RegisterRequest):
    if get_user_by_username(req.username):
        raise HTTPException(400, "Username already exists")
    if get_user_by_email(req.email):
        raise HTTPException(400, "Email already exists")

    user_id = create_user(req.username, req.email, hash_password(req.password))
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

    from config import AppConfig, UserConfig, WhopConfig, TikTokConfig, YouTubeConfig, InstagramConfig, FacebookConfig, save_config, load_config
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
            instagram=InstagramConfig(username=user.get("instagram_username", "") or data.get("instagram_username", ""), password=user.get("instagram_password", "") or data.get("instagram_password", "")),
            facebook=FacebookConfig(page_id=user.get("facebook_page_id", "") or data.get("facebook_page_id", ""), access_token=user.get("facebook_access_token", "") or data.get("facebook_access_token", "")),
            posts_per_day=data.get("posts_per_day", user.get("posts_per_day", 3)),
            campaign_keywords=data.get("campaign_keywords", user.get("campaign_keywords", ["world cup"])),
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
    if SUPABASE_KEY:
        try:
            items = list_files()
            files = []
            for item in items:
                name = item.get("name", "")
                ext = Path(name).suffix.lower()
                if ext not in (".mp4", ".mp3", ".jpg", ".png"):
                    continue
                url = get_file_url(name)
                files.append({
                    "name": name,
                    "path": url or name,
                    "size": item.get("metadata", {}).get("size", 0),
                    "size_str": "",
                    "ext": ext,
                    "modified": item.get("created_at", ""),
                    "url": url,
                })
            files.sort(key=lambda x: x["name"], reverse=True)
            return files
        except Exception as e:
            print(f"[API] Supabase list error: {e}")

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


class GenerateFromURLRequest(BaseModel):
    url: str
    start_time: float = 10
    duration: float = 60
    team_home: str = ""
    team_away: str = ""
    score_home: str = ""
    score_away: str = ""


@app.post("/api/generate-from-url")
async def generate_from_url(req: GenerateFromURLRequest, user: dict = Depends(get_current_user)):
    try:
        downloaded = ContentIngestor.download_youtube_replay(
            req.url,
            max_duration=300,
            output_dir=RAW_DIR,
        )
        if not downloaded:
            raise HTTPException(400, "Failed to download video from URL")

        clip = VideoGenerator.generate_pro_clip(
            input_video=downloaded,
            output_name=f"custom_{int(time.time())}",
            start_time=req.start_time,
            duration=req.duration,
            team_home=req.team_home,
            team_away=req.team_away,
            score_home=req.score_home,
            score_away=req.score_away,
            add_ken_burns=True,
            add_color_grade=True,
            add_scoreboard=bool(req.team_home),
            add_intro=True,
            add_outro=True,
        )
        if not clip:
            raise HTTPException(500, "Failed to create clip")

        vo = AudioGenerator.generate_voiceover(output_name=f"vo_custom_{int(time.time())}")
        if vo:
            mixed = AudioGenerator.mix_audio_with_video(clip, vo, f"final_{int(time.time())}")
            if mixed:
                clip = mixed

        log_content(user["id"], f"Custom clip from URL", "video", "manual", "created", file_path=clip.name)

        file_url = None
        if SUPABASE_KEY:
            storage_path = f"user_{user['id']}/{clip.name}"
            upload_file(clip, storage_path)
            file_url = get_file_url(storage_path)

        if file_url:
            return {"ok": True, "file": file_url, "name": clip.name}
        return {"ok": True, "file": str(clip.relative_to(Path(__file__).parent).as_posix()), "name": clip.name}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Generation error: {e}")


@app.delete("/api/content-files")
async def delete_content_file(path: str, user: dict = Depends(get_current_user)):
    if SUPABASE_KEY:
        try:
            delete_storage_file(path)
            log_content(user["id"], "Deleted file", "file", "manual", "deleted", file_path=path)
            return {"ok": True}
        except Exception as e:
            raise HTTPException(500, f"Delete error: {e}")

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
