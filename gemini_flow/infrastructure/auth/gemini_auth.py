import json
import logging
from pathlib import Path
from typing import Optional, Dict
from gemini_flow.domain.interfaces import IAuthService, IWebBrowser
from gemini_flow.domain.entities import GeminiTokens
from gemini_flow.domain.exceptions import RequireManualLoginError
from gemini_flow.config import GEMINI_BASE_URL
from gemini_flow.infrastructure.storage.file_cookie_store import FileCookieStore
from gemini_flow.infrastructure.clients.http_client import HttpClient
import re

logger = logging.getLogger("gemini_flow.auth")

class GeminiAuthService(IAuthService):
    def __init__(self, cookies_dir: Path, cookie_store: FileCookieStore, http_client: HttpClient, web_browser: IWebBrowser):
        self.cookies_dir = cookies_dir
        self.cookie_store = cookie_store
        self.http_client = http_client
        self.web_browser = web_browser

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
        
        logger.info("Tokens invalid or missing. Using Web Browser to refresh cookies...")
        cookies_path = self.cookies_dir / "auth_Gemini.json"
        
        try:
            html = await self.web_browser.navigate_and_get_html(
                url=GEMINI_BASE_URL, 
                wait_selector='script:has-text("SNlM0e")'
            )
            tokens = self._extract_tokens(html)
            
            if tokens:
                cookie_export = await self.web_browser.get_cookies()
                cookies_path.write_text(json.dumps(cookie_export, ensure_ascii=False, indent=2), encoding="utf-8")
                logger.info("Cookies refreshed and SNlM0e token verified successfully.")
                return tokens
            else:
                raise RequireManualLoginError(
                    f"Login required (maybe captcha or terms). Please sign in to {GEMINI_BASE_URL} manually."
                )
        except Exception as e:
            if isinstance(e, RequireManualLoginError):
                raise
            raise RuntimeError(f"Failed to refresh tokens via Web Browser: {e}") from e
