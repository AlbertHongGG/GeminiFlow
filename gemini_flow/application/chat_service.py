import logging
import time
import base64
from pathlib import Path
from typing import AsyncGenerator
from gemini_flow.domain.entities import ChatRequest, ChatResponseChunk, SessionData
from gemini_flow.domain.interfaces import IAuthService, IChatProvider, ISessionStore, IImageDownloader
from gemini_flow.domain.exceptions import TokenExpiredError
from gemini_flow.infrastructure.clients.http_client import HttpClient

logger = logging.getLogger("gemini_flow.chat_service")

class ChatService:
    def __init__(
        self, 
        auth_service: IAuthService, 
        chat_provider: IChatProvider, 
        session_store: ISessionStore,
        http_client: HttpClient,
        image_downloader: IImageDownloader
    ):
        self.auth_service = auth_service
        self.chat_provider = chat_provider
        self.session_store = session_store
        self.http_client = http_client
        self.image_downloader = image_downloader

    async def stream_chat(self, request: ChatRequest) -> AsyncGenerator[ChatResponseChunk, None]:
        session_data = None
        if request.session_id:
            session_data = self.session_store.load(request.session_id)

        try:
            tokens = await self.auth_service.ensure_valid_tokens()
        except Exception:
            if not request.auto_refresh_cookies:
                raise
            tokens = await self.auth_service.ensure_valid_tokens()
            
        cookies = await self.auth_service.get_cookies_dict()
        self.http_client.update_cookies(cookies)

        try:
            async for chunk in self._execute_stream(request, tokens, session_data, cookies):
                yield chunk
        except TokenExpiredError:
            if not request.auto_refresh_cookies:
                raise
            logger.info("Token expired during request. Forcing refresh and retrying...")
            # We assume ensure_valid_tokens will try Playwright if HTTP fetch fails
            # But since HTTP fetch uses cached cookies, we might need to force refresh.
            # The current playwright_auth tries HTTP first. If we got TokenExpiredError, HTTP fetch might fail too, triggering Playwright.
            tokens = await self.auth_service.ensure_valid_tokens()
            cookies = await self.auth_service.get_cookies_dict()
            self.http_client.update_cookies(cookies)
            
            async for chunk in self._execute_stream(request, tokens, session_data, cookies):
                yield chunk

    async def _execute_stream(self, request: ChatRequest, tokens, session_data, cookies: dict) -> AsyncGenerator[ChatResponseChunk, None]:
        async for chunk in self.chat_provider.stream_generate(request, tokens, session_data):
            if chunk.session_ids and request.session_id:
                new_session_data = SessionData(session_id=request.session_id, conversation_ids=chunk.session_ids)
                self.session_store.save(new_session_data)
                
            if chunk.image_url:
                img_url = chunk.image_url
                if "googleusercontent.com" in img_url:
                    import re
                    parts = img_url.split("?", 1)
                    base = parts[0]
                    if "=" in base:
                        base = re.sub(r'=[^=]*$', '=s0-d', base)
                    else:
                        base += "=s0-d"
                    img_url = base + ("?" + parts[1] if len(parts) > 1 else "")
                    
                try:
                    local_path = await self.image_downloader.download_image(img_url, request.model)
                    chunk.image_local_path = str(local_path.resolve())
                except Exception as e:
                    logger.error(f"Image download failed: {e}")
            yield chunk
