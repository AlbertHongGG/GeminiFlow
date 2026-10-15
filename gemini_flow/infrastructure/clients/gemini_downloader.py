import re
import logging
from pathlib import Path
from datetime import datetime
from gemini_flow.domain.interfaces import IImageDownloader, IWebBrowser

logger = logging.getLogger("gemini_flow.downloader")

class GeminiImageDownloader(IImageDownloader):
    def __init__(self, output_dir: Path, web_browser: IWebBrowser):
        self.output_dir = output_dir
        self.web_browser = web_browser
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def normalize_image_url(url: str) -> str:
        """Normalizes Google User Content URLs to request the full-resolution image (=s0-d)."""
        if "googleusercontent.com" in url:
            parts = url.split("?", 1)
            base = parts[0]
            if "=" in base:
                base = re.sub(r'=[^=]*$', '=s0-d', base)
            else:
                base += "=s0-d"
            return base + ("?" + parts[1] if len(parts) > 1 else "")
        return url

    async def download_image(self, url: str, model_name: str) -> Path:
        normalized_url = self.normalize_image_url(url)
        logger.debug(f"Attempting to download via Web Browser: {normalized_url}")
        
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp_str}_{model_name}_generated.png"
        file_path = self.output_dir / filename
        
        return await self.web_browser.download_file(normalized_url, file_path)
