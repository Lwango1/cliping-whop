import json
import time
import random
from pathlib import Path
from typing import Optional

from playwright.sync_api import sync_playwright, Page, Browser

from config import WhopConfig, LOGS_DIR


WHOP_LOGIN_URL = "https://whop.com/login"
WHOP_DASHBOARD_URL = "https://whop.com/dashboard"
WHOP_CAMPAIGNS_URL = "https://whop.com/campaigns"
WHOP_MARKETPLACE_URL = "https://whop.com/marketplace"
WHOP_CONTENT_REWARDS_URL = "https://whop.com/joined/contentrewards/"
WHOP_CONTENT_REWARDS_BOUNTIES = "https://whop.com/joined/contentrewards/new-campaigns-tCNnKkWFafPHwl/app/"
WHOP_DISCOVER_URL = "https://whop.com/discover/"
CONTENT_REWARDS_DISCOVER = "https://contentrewards.com/discover/"


class WhopScraper:
    def __init__(self, whop_cfg: WhopConfig, headless: bool = True):
        self.cfg = whop_cfg
        self.headless = headless
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self.logged_in = False
        self.cookie_path = Path(whop_cfg.cookie_file) if whop_cfg.cookie_file else LOGS_DIR / "whop_cookies.json"

    def _ensure_browser(self):
        if not self.browser:
            p = sync_playwright().start()
            self.browser = p.chromium.launch(headless=self.headless)
            self.page = self.browser.new_page(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )

    def login(self) -> bool:
        self._ensure_browser()
        page = self.page

        try:
            if self.cookie_path.exists():
                with open(self.cookie_path, "r") as f:
                    cookies = json.load(f)
                page.context.add_cookies(cookies)
                page.goto(WHOP_DASHBOARD_URL, timeout=30000)
                if "dashboard" in page.url or "campaigns" in page.url:
                    self.logged_in = True
                    print("[WhopScraper] Logged in via cookies")
                    return True
                print("[WhopScraper] Cookies expired, need re-login")

            page.goto(WHOP_LOGIN_URL, timeout=30000)
            page.wait_for_selector('input[type="email"], input[name="email"]', timeout=10000)

            email_input = page.query_selector('input[type="email"]') or page.query_selector('input[name="email"]')
            if email_input and self.cfg.email:
                email_input.fill(self.cfg.email)
                time.sleep(1)

                continue_btn = page.query_selector('button:has-text("Continue")')
                if continue_btn and continue_btn.is_visible():
                    continue_btn.click()
                    print("[WhopScraper] Email submitted, waiting for OTP...")
                    return False

            print("[WhopScraper] Login requires manual cookie setup")
            print(f"[WhopScraper] To set up: login to whop.com in your browser, then copy cookies to {self.cookie_path}")
            return False

        except Exception as e:
            print(f"[WhopScraper] Login error: {e}")
            return False

    def get_available_campaigns(self) -> list[dict]:
        if not self.logged_in and not self.login():
            return []

        page = self.page
        campaigns = []

        try:
            page.goto(WHOP_CONTENT_REWARDS_URL, timeout=30000)
            time.sleep(5)

            body_text = page.inner_text("body")

            import re
            lines = body_text.split("\n")
            i = 0
            while i < len(lines):
                line = lines[i].strip()
                if line.startswith("Budget: $"):
                    budget = line.replace("Budget: $", "").strip()
                    title = lines[i-1].strip() if i > 0 else "Unknown"
                    if not title or title.isdigit():
                        title = lines[i-2].strip() if i > 1 else "Unknown"

                    platforms = ""
                    url = ""
                    for j in range(i, min(i+10, len(lines))):
                        l = lines[j].strip()
                        if l.startswith("Platforms:"):
                            platforms = l.replace("Platforms:", "").strip()
                        if l.startswith("Campaign link:"):
                            url = l.replace("Campaign link:", "").strip()

                    if title and len(title) > 3:
                        campaigns.append({
                            "title": title[:120],
                            "budget": f"${budget}",
                            "platforms": platforms,
                            "url": url,
                            "status": "open",
                            "source": "whop",
                        })
                i += 1

            if not campaigns:
                for sel in ['[class*="campaign"]', '[class*="Card"]', '[class*="bountie"]']:
                    cards = [c for c in page.query_selector_all(sel) if c.is_visible()]
                    for card in cards[:20]:
                        try:
                            text = card.inner_text()[:200]
                            if "budget" in text.lower() or "campaign" in text.lower():
                                campaigns.append({
                                    "title": text[:80],
                                    "budget": "",
                                    "platforms": "",
                                    "url": "",
                                    "status": "open",
                                    "source": "whop",
                                })
                        except Exception:
                            continue

        except Exception as e:
            print(f"[WhopScraper] Error scraping campaigns: {e}")

        print(f"[WhopScraper] Found {len(campaigns)} campaigns")
        return campaigns

    def get_campaign_details(self, campaign_url: str) -> dict:
        if not self.logged_in and not self.login():
            return {}

        page = self.page
        details = {}

        try:
            page.goto(campaign_url, timeout=30000)
            time.sleep(3)

            text_content = page.inner_text("body")
            details["full_text"] = text_content[:5000]
            details["url"] = campaign_url

            apply_selectors = [
                '[class*="submit"]',
                '[class*="apply"]',
                '[class*="join"]',
                "button:has-text('Apply')",
                "button:has-text('Join')",
                "button:has-text('Submit')",
                "button:has-text('Get Started')",
            ]

            for sel in apply_selectors:
                submission_el = page.query_selector(sel)
                if submission_el and submission_el.is_visible():
                    details["can_apply"] = True
                    details["apply_selector"] = sel
                    break
            else:
                details["can_apply"] = False

        except Exception as e:
            print(f"[WhopScraper] Failed to get campaign details: {e}")

        return details

    def close(self):
        if self.browser:
            try:
                self.browser.close()
            except Exception:
                pass
            self.browser = None
            self.page = None
            self.logged_in = False
