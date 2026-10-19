import logging
from typing import AsyncGenerator, Optional
from gemini_flow.domain.entities import ChatRequest, ChatResponseChunk, SessionData, GeminiCredentials
from gemini_flow.domain.interfaces import IAuthService, IChatProvider, ISessionStore, IImageDownloader, IHttpClient
from gemini_flow.domain.exceptions import TokenExpiredError

logger = logging.getLogger("gemini_flow.chat_service")

class ChatService:
    def __init__(
        self, 
        auth_service: IAuthService, 
        chat_provider: IChatProvider, 
        session_store: ISessionStore,
        http_client: IHttpClient,
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
            if session_data is None:
                session_data = SessionData(session_id=request.session_id)

        try:
            credentials = await self.auth_service.ensure_valid_credentials()
        except Exception:
            if not request.auto_refresh_cookies:
                raise
            credentials = await self.auth_service.ensure_valid_credentials()
            
        cookies = credentials.cookies or await self.auth_service.get_cookies_dict()
        self.http_client.update_cookies(cookies)

        try:
            async for chunk in self._execute_stream(request, credentials, session_data):
                yield chunk
        except TokenExpiredError:
            if not request.auto_refresh_cookies:
                raise
            logger.info("Token expired during request. Forcing refresh and retrying...")
            credentials = await self.auth_service.ensure_valid_credentials()
            cookies = credentials.cookies or await self.auth_service.get_cookies_dict()
            self.http_client.update_cookies(cookies)
            
            async for chunk in self._execute_stream(request, credentials, session_data):
                yield chunk

    async def _execute_stream(
        self, 
        request: ChatRequest, 
        credentials: GeminiCredentials, 
        session_data: Optional[SessionData],
    ) -> AsyncGenerator[ChatResponseChunk, None]:
        latest_conv_id = None
        latest_cont_token = None
        async for chunk in self.chat_provider.stream_generate(request, credentials, session_data):
            if chunk.conversation_id:
                latest_conv_id = chunk.conversation_id
            if chunk.continuation_token:
                latest_cont_token = chunk.continuation_token

            if chunk.image_url:
                try:
                    local_path = await self.image_downloader.download_image(chunk.image_url, request.model)
                    chunk.image_local_path = str(local_path.resolve())
                except Exception as e:
                    logger.error(f"Image download failed: {e}")
            yield chunk

        if session_data:
            if latest_conv_id:
                session_data.conversation_id = latest_conv_id
            session_data.advance_turn(latest_cont_token)
            self.session_store.save(session_data)
