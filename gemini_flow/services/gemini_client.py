import logging
from typing import AsyncGenerator
from ..models import ChatRequest, ChatResponseChunk, SessionData
from ..config import AppConfig, REQUEST_BL_PARAM, MODEL_HEADERS
from ..infra.cookie_manager import CookieManager
from ..infra.auth import AuthManager
from ..infra.http_client import HttpClient
from ..core.protocol_builder import ProtocolBuilder
from ..core.response_parser import ResponseParser
from .gemini_api import GeminiAPI
from .image_handler import ImageHandler
from .session_manager import SessionManager

logger = logging.getLogger("gemini_flow.client")

class GeminiClient:
    def __init__(self, config: AppConfig, http_client: HttpClient):
        self.config = config
        self.http_client = http_client
        self.cookie_manager = CookieManager(config.cookies_dir)
        self.auth_manager = AuthManager(config.cookies_dir)
        self.api = GeminiAPI(http_client)
        self.image_handler = ImageHandler(http_client, config)
        self.session_manager = SessionManager()

    async def stream_chat(self, request: ChatRequest) -> AsyncGenerator[ChatResponseChunk, None]:
        logger.info(f"Starting chat stream for model: {request.model}")
        
        # 1. Ensure Auth
        try:
            cookies = self.cookie_manager.get_google_cookies()
        except Exception:
            if not request.auto_refresh_cookies:
                raise
            await self.auth_manager.ensure_cookies()
            cookies = self.cookie_manager.get_google_cookies()
        
        self.http_client.update_cookies(cookies)

        # 2. Get Tokens
        try:
            tokens = await self.api.fetch_tokens()
        except Exception:
            if not request.auto_refresh_cookies:
                raise
            logger.info("Tokens expired or invalid, refreshing cookies...")
            await self.auth_manager.ensure_cookies()
            cookies = self.cookie_manager.get_google_cookies()
            self.http_client.update_cookies(cookies)
            tokens = await self.api.fetch_tokens()

        # 3. Upload Images
        uploads = []
        if request.images:
            logger.info(f"Uploading {len(request.images)} images...")
            uploads = await self.api.upload_images(request.images)

        # 4. Handle Sessions
        conversation_ids = []
        if request.session_id:
            sess = self.session_manager.load(request.session_id)
            if sess:
                conversation_ids = sess.conversation_ids

        # 5. Build Protocol
        combined_prompt = request.prompt
        if request.system_prompt:
            combined_prompt = f"System:\n{request.system_prompt}\n\nUser:\n{request.prompt}"

        builder = ProtocolBuilder(
            prompt=combined_prompt,
            language=request.language,
            model=request.model,
            tokens=tokens,
            uploads=uploads,
            conversation_ids=conversation_ids
        )

        params = builder.build_params(REQUEST_BL_PARAM)
        data = builder.build_payload(MODEL_HEADERS)
        headers = builder.build_headers(MODEL_HEADERS)

        # 6. Stream and Parse
        parser = ResponseParser()
        emitted_session_ids = False
        final_image_candidate = None
        fallback_image_candidate = None
        
        buffer = ""
        logger.debug("Generating stream...")
        async for chunk in self.api.stream_generate(params, data, headers):
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
                    if request.session_id:
                        self.session_manager.save(SessionData(session_id=request.session_id, conversation_ids=ids))

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
                emitted_session_ids = True
                yield ChatResponseChunk(session_ids=ids)
                if request.session_id:
                    self.session_manager.save(SessionData(session_id=request.session_id, conversation_ids=ids))

            if delta:
                yield ChatResponseChunk(text=delta)

        # 7. Post-process Image
        img_url = final_image_candidate or fallback_image_candidate
        if img_url:
            logger.info(f"Image generation detected: {img_url}")
            
            if final_image_candidate:
                try:
                    local_path = await self.image_handler.download_image(img_url, request.model)
                    yield ChatResponseChunk(image_local_path=local_path)
                except Exception as e:
                    logger.error(f"Failed to download generated image: {e}")
                    yield ChatResponseChunk(image_url=img_url)
            else:
                yield ChatResponseChunk(image_url=img_url)
        
        logger.info("Chat stream completed.")
