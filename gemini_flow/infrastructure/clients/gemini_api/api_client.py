import logging
from typing import AsyncGenerator, Optional, List, Tuple
from gemini_flow.domain.interfaces import IChatProvider
from gemini_flow.domain.entities import ChatRequest, ChatResponseChunk, SessionData, GeminiTokens, ImagePayload
from gemini_flow.domain.exceptions import NetworkError, ProtocolError
from gemini_flow.config import UPLOAD_IMAGE_HEADERS, UPLOAD_IMAGE_URL, GEMINI_REQUEST_URL, REQUEST_BL_PARAM, MODEL_HEADERS
from ..http_client import HttpClient
from .builders.model_builders import get_builder_for_model
from .parser import StreamParser

logger = logging.getLogger("gemini_flow.api_client")

class GeminiAPIClient(IChatProvider):
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

    async def stream_generate(
        self, 
        request: ChatRequest, 
        tokens: GeminiTokens,
        session_data: Optional[SessionData] = None
    ) -> AsyncGenerator[ChatResponseChunk, None]:
        
        conversation_ids = session_data.conversation_ids if session_data else []
        uploads = []
        if request.images:
            logger.info(f"Uploading {len(request.images)} images...")
            uploads = await self.upload_images(request.images)

        builder = get_builder_for_model(request, tokens, uploads, conversation_ids)
        params = builder.build_params(REQUEST_BL_PARAM)
        data = builder.build_payload(MODEL_HEADERS)
        headers = builder.build_headers(MODEL_HEADERS)

        parser = StreamParser()
        emitted_session_ids = False
        final_image_candidate = None
        fallback_image_candidate = None
        
        buffer = ""
        logger.debug("Generating stream...")
        
        async for chunk in self.http_client.post_stream(GEMINI_REQUEST_URL, params=params, data=data, headers=headers):
            buffer += chunk
            while "\n" in buffer:
                raw_line, buffer = buffer.split("\n", 1)
                raw_line = raw_line.rstrip("\r")
                if not raw_line: continue
                
                for url in parser.extract_image_candidates(raw_line):
                    image_type = parser.classify_image_url(url)
                    if image_type == "placeholder":
                        if not fallback_image_candidate: fallback_image_candidate = url
                    elif image_type == "output":
                        final_image_candidate = url

                delta, ids = parser.extract_text_delta(raw_line)
                
                if ids and not emitted_session_ids:
                    emitted_session_ids = True
                    yield ChatResponseChunk(session_ids=ids)

                if delta:
                    yield ChatResponseChunk(text=delta)

        # Flush buffer
        if buffer.strip():
            raw_line = buffer.rstrip("\r\n")
            for url in parser.extract_image_candidates(raw_line):
                image_type = parser.classify_image_url(url)
                if image_type == "placeholder":
                    if not fallback_image_candidate: fallback_image_candidate = url
                elif image_type == "output":
                    final_image_candidate = url
            
            delta, ids = parser.extract_text_delta(raw_line)
            if ids and not emitted_session_ids:
                yield ChatResponseChunk(session_ids=ids)

            if delta:
                yield ChatResponseChunk(text=delta)

        # Return final image
        img_url = final_image_candidate or fallback_image_candidate
        if img_url:
            logger.info(f"Image generation detected: {img_url}")
            # The download image logic will be in ChatService to maintain separation of concerns
            yield ChatResponseChunk(image_url=img_url)
