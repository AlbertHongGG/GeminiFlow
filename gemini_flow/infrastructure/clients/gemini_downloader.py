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
        
    async def download_image(self, url: str, model_name: str) -> Path:
        logger.debug(f"Attempting to download via Web Browser: {url}")
        
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp_str}_{model_name}_generated.png"
        file_path = self.output_dir / filename
        
        return await self.web_browser.download_file(url, file_path)
