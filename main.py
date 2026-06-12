"""
Clipping Whop - Automated content creation & publishing bot
Web interface: http://localhost:8000
"""
import sys
import argparse
import uvicorn

from config import init_user_interactive, load_config
from scheduler import BotScheduler, run_once as scheduler_once
from modules.whop.auto_apply import WhopAutoApply
from utils import init_output

init_output()


def cmd_setup():
    username = init_user_interactive()
    print(f"\n Setup complete for '{username}'!")
    print("Run 'python main.py run' to start the CLI bot, or 'python main.py web' for the web interface.")


def cmd_run():
    scheduler = BotScheduler()
    scheduler.start()


def cmd_once():
    results = scheduler_once()
    print(f"\nDone: {results}")


def cmd_apply():
    config = load_config()
    if not config.active_user:
        print("No active user. Run 'python main.py setup' first.")
        return
    user_cfg = config.users[config.active_user]
    applier = WhopAutoApply(user_cfg, headless=config.headless_browser)
    applier.run_auto_apply(max_applications=10)


def cmd_status():
    config = load_config()
    if not config.active_user:
        print("No active user configured.")
        return
    user = config.users[config.active_user]
    print(f"Active user: {config.active_user}")
    print(f"  Whop:      {'✅' if user.whop.email else '❌'} {user.whop.email}")
    print(f"  TikTok:    {'✅' if user.tiktok.session_id else '❌'}")
    print(f"  YouTube:   {'✅' if user.youtube.client_id else '❌'}")
    print(f"  Instagram: {'✅' if user.instagram.username else '❌'}")
    print(f"  Facebook:  {'✅' if user.facebook.page_id else '❌'}")
    print(f"  Posts/day: {user.posts_per_day}")
    print(f"  Keywords:  {', '.join(user.campaign_keywords)}")


def cmd_web():
    from api import app
    print("Starting web interface at http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")


def main():
    parser = argparse.ArgumentParser(
        description="Clipping Whop - Automated content bot"
    )
    parser.add_argument(
        "command",
        nargs="?",
        choices=["setup", "run", "once", "apply", "status", "web"],
        default="web",
        help="setup: configure accounts | run: CLI scheduler | once: run one cycle | apply: auto-apply to Whop | status: show config | web: start web interface (default)",
    )

    args = parser.parse_args()

    commands = {
        "setup": cmd_setup,
        "run": cmd_run,
        "once": cmd_once,
        "apply": cmd_apply,
        "status": cmd_status,
        "web": cmd_web,
    }

    commands[args.command]()


if __name__ == "__main__":
    main()
