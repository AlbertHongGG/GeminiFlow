import logging
import base64
import time
from pathlib import Path
from ..infra.http_client import HttpClient
from ..config import AppConfig

logger = logging.getLogger("gemini_flow.image_handler")

class ImageHandler:
    def __init__(self, http_client: HttpClient, config: AppConfig):
        self.http_client = http_client
        self.config = config

    async def download_image(self, url: str, model: str = "unknown") -> str:
        """
        Downloads an image from a URL or base64 data URI.
        Saves it to configured output directory.
        Returns the absolute local path to the downloaded image.
        """
        out_dir = self.config.image_output_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        filename = f"gemini_{model}_{int(time.time()*1000)}.png"
        out_path = out_dir / filename
        
        try:
            if url.startswith("data:image/"):
                _, b64 = url.split(",", 1)
                out_path.write_bytes(base64.b64decode(b64))
            else:
                img_data = await self.http_client.download_file(url)
                out_path.write_bytes(img_data)
            logger.info(f"Image downloaded to {out_path}")
            return str(out_path.resolve())
        except Exception as e:
            logger.error(f"Failed to download image {url}: {e}")
            raise
