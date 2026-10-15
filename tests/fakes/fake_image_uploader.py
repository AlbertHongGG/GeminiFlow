from typing import List, Tuple
from gemini_flow.domain.entities import ImagePayload
from gemini_flow.domain.interfaces import IImageUploader


class FakeImageUploader(IImageUploader):
    def __init__(self, default_ref_prefix: str = "/contrib_service/ttl_1d/fake_upload_"):
        self.default_ref_prefix = default_ref_prefix
        self.uploaded_images: List[ImagePayload] = []

    async def upload_images(self, images: List[ImagePayload]) -> List[Tuple[str, str]]:
        self.uploaded_images.extend(images)
        return [
            (f"{self.default_ref_prefix}{i}", img.filename)
            for i, img in enumerate(images, start=1)
        ]
