import logging
from typing import List, Tuple, AsyncGenerator
from ..infra.http_client import HttpClient
from ..config import UPLOAD_IMAGE_HEADERS, UPLOAD_IMAGE_URL, GEMINI_BASE_URL, GEMINI_REQUEST_URL
from ..exceptions import NetworkError, AuthenticationError
from ..core.protocol_builder import extract_tokens
from ..models import ImagePayload

logger = logging.getLogger("gemini_flow.api")

class GeminiAPI:
    def __init__(self, http_client: HttpClient):
        self.http_client = http_client

    async def upload_images(self, images: List[ImagePayload]) -> List[Tuple[str, str]]:
        uploads = []
        for img in images:
            try:
                headers = {
                    **UPLOAD_IMAGE_HEADERS,
                    "size": str(len(img.data)),
                    "x-goog-upload-command": "start",
                }
                data_name = f"File name: {img.filename}" if img.filename else None
                resp = await self.http_client.post_form(UPLOAD_IMAGE_URL, data=data_name, headers=headers)
                upload_url = resp.headers.get("X-Goog-Upload-Url")
                if not upload_url:
                    raise NetworkError("Missing X-Goog-Upload-Url")
                
                headers["x-goog-upload-command"] = "upload, finalize"
                headers["X-Goog-Upload-Offset"] = "0"
                resp = await self.http_client.post_form(upload_url, data=img.data, headers=headers)
                upload_ref = await resp.text()
                uploads.append((upload_ref, img.filename))
            except Exception as e:
                logger.error(f"Image upload failed: {e}")
                raise NetworkError(f"Image upload failed: {e}") from e
        return uploads

    async def fetch_tokens(self) -> str:
        html = await self.http_client.get_text(GEMINI_BASE_URL)
        tokens = extract_tokens(html)
        if not tokens:
            raise AuthenticationError("Tokens not found, cookies might be expired.")
        return tokens

    async def stream_generate(self, params: dict, data: dict, headers: dict) -> AsyncGenerator[str, None]:
        async for chunk in self.http_client.post_stream(GEMINI_REQUEST_URL, params=params, data=data, headers=headers):
            yield chunk
