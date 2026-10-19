from typing import List
from gemini_flow.domain.entities import ImagePayload, UploadedImageAttachment
from gemini_flow.domain.interfaces import IImageUploader


class FakeImageUploader(IImageUploader):
    def __init__(self, default_ref_prefix: str = "/contrib_service/ttl_1d/fake_upload_"):
        self.default_ref_prefix = default_ref_prefix
        self.uploaded_images: List[ImagePayload] = []

    async def upload_images(self, images: List[ImagePayload]) -> List[UploadedImageAttachment]:
        self.uploaded_images.extend(images)
        return [
            UploadedImageAttachment(
                ref_url=f"{self.default_ref_prefix}{i}",
                filename=img.filename,
                mime_type="image/jpeg",
                attachment_uuid=f"uuid_{i}",
            )
            for i, img in enumerate(images, start=1)
        ]
