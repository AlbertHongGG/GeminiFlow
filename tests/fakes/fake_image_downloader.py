from pathlib import Path
from tempfile import TemporaryDirectory
from gemini_flow.domain.interfaces import IImageDownloader

class FakeImageDownloader(IImageDownloader):
    def __init__(self, temp_dir: Path = None):
        if temp_dir is None:
            self._tmp = TemporaryDirectory()
            self.output_dir = Path(self._tmp.name)
        else:
            self._tmp = None
            self.output_dir = temp_dir
        self.downloaded_urls = []

    async def download_image(self, url: str, model_name: str) -> Path:
        self.downloaded_urls.append(url)
        dest = self.output_dir / "mock_generated_image.png"
        dest.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR...")
        return dest

    def cleanup(self):
        if self._tmp:
            self._tmp.cleanup()
