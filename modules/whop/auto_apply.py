import time
import random
from typing import Optional

from config import UserConfig, LOGS_DIR
from modules.whop.scraper import WhopScraper


class WhopAutoApply:
    def __init__(self, user_cfg: UserConfig, headless: bool = True):
        self.cfg = user_cfg
        self.scraper = WhopScraper(user_cfg.whop, headless=headless)
        self.apply_log = LOGS_DIR / "apply_log.txt"

    def find_target_campaigns(self) -> list[dict]:
        all_campaigns = self.scraper.get_available_campaigns()
        keywords = [k.lower() for k in self.cfg.campaign_keywords]

        matching = []
        for c in all_campaigns:
            title_lower = c.get("title", "").lower()
            if any(kw in title_lower for kw in keywords):
                matching.append(c)
                print(f"  [{c['title']}] -> match")

        return matching

    def apply_to_campaign(self, campaign: dict) -> bool:
        details = self.scraper.get_campaign_details(campaign["url"])
        if not details:
            print(f"  Skipping {campaign['title']} (no details)")
            return False

        if not details.get("can_apply"):
            print(f"  {campaign['title']} -> no apply button")
            return False

        page = self.scraper.page
        try:
            apply_btn = page.query_selector('[class*="submit"], [class*="apply"], button:has-text("Apply")')
            if not apply_btn:
                print(f"  {campaign['title']} -> apply button not found")
                return False

            apply_btn.click()
            time.sleep(random.uniform(2, 4))

            textareas = page.query_selector_all("textarea")
            if textareas:
                message = self._generate_apply_message(campaign)
                textareas[0].fill(message)
                time.sleep(1)

                submit_btn = page.query_selector('button[type="submit"], button:has-text("Submit")')
                if submit_btn:
                    submit_btn.click()
                    time.sleep(2)

            with open(self.apply_log, "a", encoding="utf-8") as f:
                f.write(f"[{campaign['title']}] Applied at {time.ctime()}\n")

            print(f"  Applied to {campaign['title']}")
            return True

        except Exception as e:
            print(f"  Apply failed for {campaign['title']}: {e}")
            return False

    def _generate_apply_message(self, campaign: dict) -> str:
        return (
            "Hi team,\n\n"
            "I specialize in creating high-engagement sports content for the Canadian market. "
            "I can produce daily video clips, highlights, and promotional content "
            "for the World Cup campaign across TikTok, YouTube, Instagram, and Facebook.\n\n"
            "Looking forward to contributing!\n\nBest regards"
        )

    def run_auto_apply(self, max_applications: int = 5) -> dict:
        result = {"campaigns_found": 0, "campaigns_applied": 0}
        try:
            if not self.scraper.login():
                print("[WhopAutoApply] Login failed")
                return result

            targets = self.find_target_campaigns()
            result["campaigns_found"] = len(targets)
            print(f"\nFound {len(targets)} matching campaigns")

            applied = 0
            for camp in targets:
                if applied >= max_applications:
                    break
                success = self.apply_to_campaign(camp)
                if success:
                    applied += 1
                time.sleep(random.uniform(3, 6))

            result["campaigns_applied"] = applied
            print(f"Applied to {applied} campaign(s)")

        finally:
            self.scraper.close()
        return result
