from pathlib import Path
from typing import Optional, Sequence
import json
from ..exceptions import AuthenticationError
from ..config import REQUIRED_COOKIE_NAME, GEMINI_BASE_URL

import logging

logger = logging.getLogger("gemini_flow.auth")

def has_required_cookie(cookie_export: Sequence[dict]) -> bool:
    for c in cookie_export:
        try:
            if c.get("name") == REQUIRED_COOKIE_NAME and c.get("value"):
                return True
        except Exception:
            continue
    return False

def looks_like_login_redirect(url: str) -> bool:
    u = (url or "").lower()
    return (
        "accounts.google.com" in u
        or "servicelogin" in u
        or "/signin" in u
        or "oauth" in u
    )

class AuthManager:
    def __init__(self, cookies_dir: Path):
        self.cookies_dir = cookies_dir
        self.cookies_path = cookies_dir / "auth_Gemini.json"
        self.profile_dir = cookies_dir / ".pw-profile"
        self.browser_channel = "chrome"

    async def _export_cookies_with_playwright(self, headless: bool) -> bool:
        try:
            from playwright.async_api import async_playwright
        except ImportError as e:
            raise AuthenticationError("Playwright is not installed.") from e

        self.cookies_path.parent.mkdir(parents=True, exist_ok=True)
        self.profile_dir.mkdir(parents=True, exist_ok=True)

        async with async_playwright() as p:
            launch_kwargs = {
                "user_data_dir": str(self.profile_dir),
                "headless": headless,
                "channel": self.browser_channel
            }

            ctx = await p.chromium.launch_persistent_context(**launch_kwargs)
            try:
                page = await ctx.new_page()
                await page.goto(GEMINI_BASE_URL, wait_until="domcontentloaded")

                cookie_export = await ctx.cookies()
                has_cookie = has_required_cookie(cookie_export)
                logged_in = has_cookie and not looks_like_login_redirect(page.url)

                logger.debug(f"playwright headless={headless} url={page.url} cookies={len(cookie_export)} has_{REQUIRED_COOKIE_NAME}={has_cookie}")

                if not logged_in:
                    return False

                self.cookies_path.write_text(
                    json.dumps(cookie_export, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                return True
            finally:
                await ctx.close()

    async def ensure_cookies(self) -> Path:
        logger.info("Attempting headless refresh of Gemini cookies...")
        try:
            success = await self._export_cookies_with_playwright(headless=True)
        except Exception as e:
            logger.debug(f"playwright launch failed channel={self.browser_channel!r}: {e}")
            raise AuthenticationError(f"Playwright error: {e}") from e

        if success:
            logger.info("Gemini cookies refreshed successfully (headless).")
            return self.cookies_path

        raise AuthenticationError(
            f"Missing required cookie: {REQUIRED_COOKIE_NAME}. "
            f"Please sign in to {GEMINI_BASE_URL} using a normal Chrome/Edge profile at: "
            f"{self.profile_dir} (launch browser with --user-data-dir pointing to that folder), then rerun."
        )
