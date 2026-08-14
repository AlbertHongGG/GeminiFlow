import asyncio

from gemini_flow.domain.entities import ChatRequest
from gemini_flow.application.chat_service import ChatService
from gemini_flow.config import AppConfig
from gemini_flow.infrastructure.logging.logger import setup_logging
from gemini_flow.infrastructure.clients.http_client import HttpClient
from gemini_flow.infrastructure.clients.gemini_api.api_client import GeminiAPIClient
from gemini_flow.infrastructure.auth.playwright_auth import PlaywrightAuthService
from gemini_flow.infrastructure.storage.file_cookie_store import FileCookieStore
from gemini_flow.infrastructure.storage.file_session_store import FileSessionStore
from gemini_flow.infrastructure.clients.playwright_downloader import PlaywrightImageDownloader

async def main() -> None:
    config = AppConfig.from_env()
    setup_logging(config)
    
    async with HttpClient(proxy=config.proxy) as http_client:
        cookie_store = FileCookieStore(config.cookies_dir)
        auth_service = PlaywrightAuthService(config.cookies_dir, cookie_store, http_client)
        chat_provider = GeminiAPIClient(http_client)
        session_store = FileSessionStore(config.sessions_dir)
        image_downloader = PlaywrightImageDownloader(config.image_output_dir, cookie_store)
        
        client = ChatService(
            auth_service=auth_service,
            chat_provider=chat_provider,
            session_store=session_store,
            http_client=http_client,
            image_downloader=image_downloader
        )
        
        req = ChatRequest(
            prompt="講一個故事",
            model="gemini-3-pro",
        )

        async for chunk in client.stream_chat(req):
            if chunk.text:
                print(chunk.text, end="", flush=True)

if __name__ == "__main__":
    asyncio.run(main())