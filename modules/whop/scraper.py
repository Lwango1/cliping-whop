import json
import time
from pathlib import Path
from typing import Optional

from playwright.sync_api import sync_playwright, Page, Browser

from config import WhopConfig, LOGS_DIR


WHOP_LOGIN_URL = "https://whop.com/login"
WHOP_DASHBOARD_URL = "https://whop.com/dashboard"
WHOP_CAMPAIGNS_URL = "https://whop.com/campaigns"


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
                    return True

            page.goto(WHOP_LOGIN_URL, timeout=30000)
            page.wait_for_selector('input[type="email"]', timeout=10000)
            page.fill('input[type="email"]', self.cfg.email)
            page.fill('input[type="password"]', self.cfg.password)
            page.click('button[type="submit"]')
            time.sleep(3)

            if page.url != WHOP_DASHBOARD_URL:
                page.wait_for_url("**/dashboard", timeout=20000)

            cookies = page.context.cookies()
            self.cookie_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.cookie_path, "w") as f:
                json.dump(cookies, f)

            self.logged_in = True
            return True

        except Exception as e:
            print(f"[WhopScraper] Login failed: {e}")
            return False

    def get_available_campaigns(self) -> list[dict]:
        if not self.logged_in and not self.login():
            return []

        page = self.page
        campaigns = []

        try:
            page.goto(WHOP_CAMPAIGNS_URL, timeout=30000)
            time.sleep(3)

            cards = page.query_selector_all('[class*="campaign"], [class*="Card"], [class*="offer"]')
            for card in cards:
                try:
                    title_el = card.query_selector("h2, h3, [class*='title']")
                    title = title_el.inner_text().strip() if title_el else ""

                    budget_el = card.query_selector('[class*="budget"], [class*="price"]')
                    budget = budget_el.inner_text().strip() if budget_el else ""

                    status_el = card.query_selector('[class*="status"]')
                    status = status_el.inner_text().strip() if status_el else "unknown"

                    link_el = card.query_selector("a")
                    url = page.evaluate("(el) => el.href", link_el) if link_el else ""

                    if title:
                        campaigns.append({
                            "title": title,
                            "budget": budget,
                            "status": status,
                            "url": url,
                            "source": "whop"
                        })
                except Exception:
                    continue

        except Exception as e:
            print(f"[WhopScraper] Failed to fetch campaigns: {e}")

        return campaigns

    def get_campaign_details(self, campaign_url: str) -> dict:
        if not self.logged_in and not self.login():
            return {}

        page = self.page
        details = {}

        try:
            page.goto(campaign_url, timeout=30000)
            time.sleep(2)

            text_content = page.inner_text("body")
            details["full_text"] = text_content[:5000]
            details["url"] = campaign_url

            criteria_el = page.query_selector('[class*="criteria"], [class*="requirements"]')
            if criteria_el:
                details["criteria"] = criteria_el.inner_text().strip()

            submission_el = page.query_selector('[class*="submit"], [class*="apply"], button:has-text("Apply")')
            if submission_el:
                details["can_apply"] = submission_el.is_visible()

        except Exception as e:
            print(f"[WhopScraper] Failed to get campaign details: {e}")

        return details

    def close(self):
        if self.browser:
            self.browser.close()
            self.browser = None
            self.page = None
            self.logged_in = False
