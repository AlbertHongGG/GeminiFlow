import logging
import json
import time
from pathlib import Path
from playwright.async_api import async_playwright
from gemini_flow.domain.interfaces import IImageDownloader
from gemini_flow.infrastructure.storage.file_cookie_store import FileCookieStore

logger = logging.getLogger("gemini_flow.downloader")

class PlaywrightImageDownloader(IImageDownloader):
    def __init__(self, output_dir: Path, cookie_store: FileCookieStore):
        self.output_dir = output_dir
        self.cookie_store = cookie_store
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    async def download_image(self, url: str, model_name: str) -> Path:
        logger.debug(f"Attempting to download via Playwright: {url}")
        cookies_path = self.cookie_store.cookies_dir / "auth_Gemini.json"
        
        pw_cookies = []
        if cookies_path.exists():
            try:
                pw_cookies = json.loads(cookies_path.read_text(encoding="utf-8"))
            except Exception as e:
                logger.warning(f"Failed to load playwright cookies for download: {e}")
                
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, channel="chrome")
            context = await browser.new_context()
            if pw_cookies:
                await context.add_cookies(pw_cookies)
                
            try:
                response = await context.request.get(url)
                if not response.ok:
                    raise Exception(f"Playwright download failed: {response.status} {response.status_text}")
                    
                body = await response.body()
                
                from datetime import datetime
                timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"{timestamp_str}_{model_name}_generated.png"
                file_path = self.output_dir / filename
                file_path.write_bytes(body)
                return file_path
            finally:
                await browser.close()
