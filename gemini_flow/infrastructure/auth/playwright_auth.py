import sys
import json
import logging
from pathlib import Path
from typing import Optional, Dict
from gemini_flow.domain.interfaces import IAuthService
from gemini_flow.domain.entities import GeminiTokens
from gemini_flow.domain.exceptions import AuthenticationError, RequireManualLoginError
from gemini_flow.config import GEMINI_BASE_URL
from gemini_flow.infrastructure.storage.file_cookie_store import FileCookieStore
from gemini_flow.infrastructure.clients.http_client import HttpClient
import re

logger = logging.getLogger("gemini_flow.auth")

class PlaywrightAuthService(IAuthService):
    def __init__(self, cookies_dir: Path, cookie_store: FileCookieStore, http_client: HttpClient):
        self.cookies_dir = cookies_dir
        self.cookie_store = cookie_store
        self.http_client = http_client
        self.profile_dir = cookies_dir / ".pw-profile"
        self.browser_channel = "chrome"

    async def get_cookies_dict(self) -> Dict[str, str]:
        return self.cookie_store.get_google_cookies()

    async def _fetch_tokens_via_http(self, cookies: Dict[str, str]) -> Optional[GeminiTokens]:
        try:
            self.http_client.update_cookies(cookies)
            html = await self.http_client.get_text(GEMINI_BASE_URL)
            return self._extract_tokens(html)
        except Exception as e:
            logger.debug(f"Failed to fetch tokens via HTTP: {e}")
            return None

    def _extract_tokens(self, html: str) -> Optional[GeminiTokens]:
        snlm0e_match = re.search(r'SNlM0e\\":\\"(.*?)\\"', html)
        if not snlm0e_match:
            snlm0e_match = re.search(r'SNlM0e":"(.*?)"', html)
        snlm0e = snlm0e_match.group(1) if snlm0e_match else None

        sid_match = re.search(r'"FdrFJe":"([\d-]+)"', html)
        sid = sid_match.group(1) if sid_match else None

        if not snlm0e:
            return None
        return GeminiTokens(snlm0e=snlm0e, sid=sid)

    async def ensure_valid_tokens(self) -> GeminiTokens:
        try:
            cookies = self.cookie_store.get_google_cookies()
            tokens = await self._fetch_tokens_via_http(cookies)
            if tokens:
                return tokens
        except Exception:
            pass
        
        logger.info(f"Tokens invalid or missing. Launching Playwright to refresh cookies... (profile: {self.profile_dir})")
        cookies_path = self.cookies_dir / "auth_Gemini.json"
        
        try:
            from playwright.async_api import async_playwright
        except ImportError as e:
            raise AuthenticationError("Playwright is not installed.") from e

        self.cookies_dir.mkdir(parents=True, exist_ok=True)
        self.profile_dir.mkdir(parents=True, exist_ok=True)

        async with async_playwright() as p:
            launch_kwargs = {
                "user_data_dir": str(self.profile_dir),
                "headless": True,
                "channel": self.browser_channel
            }
            if sys.platform == "darwin":
                launch_kwargs["args"] = ["--password-store=basic", "--use-mock-keychain"]

            try:
                ctx = await p.chromium.launch_persistent_context(**launch_kwargs)
            except Exception as e:
                raise AuthenticationError(f"Playwright failed to launch. Close any running Chrome instances using {self.profile_dir}. Error: {e}") from e

            try:
                page = await ctx.new_page()
                await page.goto(GEMINI_BASE_URL, wait_until="domcontentloaded")
                
                # Wait briefly for potential redirects or JS to load WIZ_global_data
                try:
                    await page.wait_for_selector('script:has-text("SNlM0e")', timeout=5000)
                except Exception:
                    pass

                html = await page.content()
                tokens = self._extract_tokens(html)
                
                if tokens:
                    cookie_export = await ctx.cookies()
                    cookies_path.write_text(json.dumps(cookie_export, ensure_ascii=False, indent=2), encoding="utf-8")
                    logger.info("Cookies refreshed and SNlM0e token verified successfully.")
                    return tokens
                else:
                    mac_args = " --password-store=basic --use-mock-keychain" if sys.platform == "darwin" else ""
                    raise RequireManualLoginError(
                        f"Login required (maybe captcha or terms). Please sign in to {GEMINI_BASE_URL} manually using a normal Chrome profile at: "
                        f"{self.profile_dir.absolute()} (launch browser with --user-data-dir pointing to that folder{mac_args})."
                    )
            finally:
                await ctx.close()
