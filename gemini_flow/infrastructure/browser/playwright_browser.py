import logging
import sys
from pathlib import Path
from typing import Optional
from playwright.async_api import async_playwright, Playwright, BrowserContext

from gemini_flow.domain.interfaces import IWebBrowser

logger = logging.getLogger(__name__)

class PlaywrightWebBrowser(IWebBrowser):
    def __init__(self, profile_dir: Path, browser_channel: str = "chrome", headless: bool = True):
        self.profile_dir = profile_dir
        self.browser_channel = browser_channel
        self.headless = headless
        
        self._playwright: Optional[Playwright] = None
        self._browser_context: Optional[BrowserContext] = None

    async def start(self) -> None:
        if self._browser_context is not None:
            return
            
        logger.info(f"Starting Playwright web browser... (profile: {self.profile_dir})")
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        
        self._playwright_mgr = async_playwright()
        self._playwright = await self._playwright_mgr.__aenter__()
        
        launch_kwargs = {
            "user_data_dir": str(self.profile_dir),
            "headless": self.headless,
            "channel": self.browser_channel,
        }
        
        if sys.platform == "darwin":
            launch_kwargs["args"] = ["--password-store=basic", "--use-mock-keychain"]

        try:
            self._browser_context = await self._playwright.chromium.launch_persistent_context(**launch_kwargs)
            logger.info("Playwright browser started successfully.")
        except Exception as e:
            logger.error(f"Playwright failed to launch. Error: {e}")
            await self.stop()
            raise RuntimeError(f"Failed to start Playwright browser: {e}") from e

    async def stop(self) -> None:
        if self._browser_context:
            logger.info("Closing Playwright browser...")
            await self._browser_context.close()
            self._browser_context = None
            
        if self._playwright:
            await self._playwright_mgr.__aexit__(None, None, None)
            self._playwright = None
            logger.info("Playwright browser stopped.")

    async def navigate_and_get_html(self, url: str, wait_selector: str, timeout: int = 5000) -> str:
        if not self._browser_context:
            raise RuntimeError("Browser is not started.")
            
        page = await self._browser_context.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded")
            try:
                await page.wait_for_selector(wait_selector, timeout=timeout)
            except Exception:
                pass
            return await page.content()
        finally:
            await page.close()
            
    async def get_cookies(self) -> list[dict]:
        if not self._browser_context:
            raise RuntimeError("Browser is not started.")
        return await self._browser_context.cookies()
        
    async def download_file(self, url: str, dest_path: Path) -> Path:
        if not self._browser_context:
            raise RuntimeError("Browser is not started.")
            
        response = await self._browser_context.request.get(url)
        if not response.ok:
            raise Exception(f"File download failed: {response.status} {response.status_text}")
            
        body = await response.body()
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        dest_path.write_bytes(body)
        return dest_path
