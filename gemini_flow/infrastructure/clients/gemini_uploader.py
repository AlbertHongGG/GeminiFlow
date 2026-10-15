import logging
from typing import List, Tuple

from gemini_flow.config import UPLOAD_IMAGE_HEADERS, UPLOAD_IMAGE_URL
from gemini_flow.domain.entities import ImagePayload
from gemini_flow.domain.exceptions import NetworkError
from gemini_flow.domain.interfaces import IHttpClient, IImageUploader

logger = logging.getLogger("gemini_flow.image_uploader")


class GeminiImageUploader(IImageUploader):
    """
    Handles resumable image uploading to Google Gemini's push/scotty upload service.
    Implements the two-stage protocol:
      1. Initiate session with command 'start' and content length declaration.
      2. Upload binary payload with command 'upload, finalize' to obtain the upload reference.
    """

    def __init__(self, http_client: IHttpClient, upload_url: str = UPLOAD_IMAGE_URL):
        self.http_client = http_client
        self.upload_url = upload_url

    async def upload_images(self, images: List[ImagePayload]) -> List[Tuple[str, str]]:
        uploads: List[Tuple[str, str]] = []

        for idx, img in enumerate(images, start=1):
            filename = img.filename or f"image_{idx}.jpg"
            size_bytes = len(img.data)
            logger.info(f"Uploading image {idx}/{len(images)}: '{filename}' ({size_bytes} bytes)...")

            try:
                # Step 1: Initiate upload session
                start_headers = {
                    **UPLOAD_IMAGE_HEADERS,
                    "x-goog-upload-command": "start",
                    "x-goog-upload-header-content-length": str(size_bytes),
                }
                data_name = f"File name: {filename}"
                resp_init = await self.http_client.post_form(
                    self.upload_url,
                    data=data_name,
                    headers=start_headers,
                )

                if resp_init.status_code != 200:
                    body = await resp_init.text()
                    raise NetworkError(
                        f"Failed to initiate image upload session (HTTP {resp_init.status_code}): {body[:200]}"
                    )

                upload_session_url = resp_init.headers.get("x-goog-upload-url")
                if not upload_session_url:
                    raise NetworkError(
                        f"Missing 'x-goog-upload-url' in upload initiation response (HTTP {resp_init.status_code})"
                    )

                # Step 2: Upload binary payload and finalize
                finalize_headers = {
                    **UPLOAD_IMAGE_HEADERS,
                    "x-goog-upload-command": "upload, finalize",
                    "x-goog-upload-offset": "0",
                }
                resp_finalize = await self.http_client.post_form(
                    upload_session_url,
                    data=img.data,
                    headers=finalize_headers,
                )

                if resp_finalize.status_code != 200:
                    body = await resp_finalize.text()
                    raise NetworkError(
                        f"Failed to finalize image upload (HTTP {resp_finalize.status_code}): {body[:200]}"
                    )

                upload_ref = (await resp_finalize.text()).strip()
                if not upload_ref:
                    raise NetworkError("Received empty upload reference from server during finalize stage")

                logger.info(f"Image '{filename}' uploaded successfully (ref: {upload_ref})")
                uploads.append((upload_ref, filename))

            except NetworkError:
                raise
            except Exception as e:
                logger.error(f"Image upload failed for '{filename}': {e}")
                raise NetworkError(f"Image upload failed for '{filename}': {e}") from e

        return uploads
