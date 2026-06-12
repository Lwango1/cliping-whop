"""
Betway Clipper - Automated content creation & publishing bot
Supports: Whop scraping, video/audio/image generation, and multi-platform publishing
"""
import sys
import argparse

from config import init_user_interactive, load_config
from scheduler import BotScheduler, run_once
from modules.whop.auto_apply import WhopAutoApply
from utils import init_output

init_output()


def cmd_setup():
    username = init_user_interactive()
    print(f"\n Setup complete for '{username}'!")
    print("Run 'python main.py run' to start the bot.")


def cmd_run():
    scheduler = BotScheduler()
    scheduler.start()


def cmd_once():
    results = run_once()
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


def main():
    parser = argparse.ArgumentParser(
        description="Betway Clipper - Automated content bot"
    )
    parser.add_argument(
        "command",
        nargs="?",
        choices=["setup", "run", "once", "apply", "status"],
        default="status",
        help="setup: configure accounts | run: start scheduler | once: run one cycle | apply: auto-apply to Whop | status: show config",
    )

    args = parser.parse_args()

    commands = {
        "setup": cmd_setup,
        "run": cmd_run,
        "once": cmd_once,
        "apply": cmd_apply,
        "status": cmd_status,
    }

    commands[args.command]()


if __name__ == "__main__":
    main()
