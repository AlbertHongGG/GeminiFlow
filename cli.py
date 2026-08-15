import argparse
import asyncio
import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from gemini_flow.domain.entities import ChatRequest, ImagePayload
from gemini_flow.application.chat_service import ChatService
from gemini_flow.config import AppConfig
from gemini_flow.infrastructure.logging.logger import setup_logging
from gemini_flow.infrastructure.clients.http_client import HttpClient
from gemini_flow.infrastructure.clients.gemini_api.api_client import GeminiAPIClient
from gemini_flow.infrastructure.auth.gemini_auth import GeminiAuthService
from gemini_flow.infrastructure.storage.file_cookie_store import FileCookieStore
from gemini_flow.infrastructure.storage.file_session_store import FileSessionStore
from gemini_flow.infrastructure.clients.gemini_downloader import GeminiImageDownloader
from gemini_flow.infrastructure.browser.playwright_browser import PlaywrightWebBrowser

logger = logging.getLogger("gemini_flow.cli")

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="gemini_flow", description="Gemini CLI Client")
    sub = p.add_subparsers(dest="cmd", required=True)

    chat = sub.add_parser("chat", help="Send a prompt and stream text output")
    chat.add_argument("prompt", help="User prompt")
    chat.add_argument("-m", "--model", default="gemini-3-pro")
    chat.add_argument(
        "--image",
        action="append",
        type=Path,
        default=None,
        help="Attach a local image (repeatable). Example: --image ./photo.png",
    )
    chat.add_argument("--lang", default="zh-TW")
    chat.add_argument("--session-id", default=None, help="Maintain chat history with this session ID")
    chat.add_argument("--system-prompt", default=None, help="System prompt to set context/behavior")
    # Config arguments
    chat.add_argument("--debug", action="store_true", help="Enable debug logging")

    return p

async def _run_chat(args: argparse.Namespace) -> int:
    config = AppConfig.from_env()
    if args.debug:
        config.debug = True
    setup_logging(config)
    
    try:
        images = []
        if args.image:
            for p in args.image:
                data = p.read_bytes()
                images.append(ImagePayload(data=data, filename=p.name))
        
        req = ChatRequest(
            prompt=args.prompt,
            model=args.model,
            language=args.lang,
            images=images,
            session_id=args.session_id,
            system_prompt=args.system_prompt
        )
        
        from gemini_flow.infrastructure.logging.ai_logger import AILogger
        ai_logger = AILogger()
        
        async with HttpClient(proxy=config.proxy) as http_client:
            browser_provider = PlaywrightWebBrowser(config.cookies_dir / ".pw-profile", browser_channel="chrome", headless=True)
            await browser_provider.start()
            
            try:
                cookie_store = FileCookieStore(config.cookies_dir)
                auth_service = GeminiAuthService(config.cookies_dir, cookie_store, http_client, browser_provider)
                chat_provider = GeminiAPIClient(http_client)
                session_store = FileSessionStore(config.sessions_dir)
                image_downloader = GeminiImageDownloader(config.image_output_dir, browser_provider)
            
            client = ChatService(
                auth_service=auth_service,
                chat_provider=chat_provider,
                session_store=session_store,
                http_client=http_client,
                image_downloader=image_downloader
            )
            
            had_output = False
            full_text = []
            response_images = []
            
            async for chunk in client.stream_chat(req):
                if chunk.text:
                    had_output = True
                    full_text.append(chunk.text)
                    print(chunk.text, end="", flush=True)
                if chunk.image_local_path:
                    response_images.append(chunk.image_local_path)
                    print(f"\n[Image downloaded to: {chunk.image_local_path}]")
                elif chunk.image_url:
                    response_images.append(chunk.image_url)
                    print(f"\n[Image URL: {chunk.image_url}]")
            print()
            
            # Log the complete interaction
            ai_logger.log_interaction(req, "".join(full_text), response_images)
            
            if config.debug and not had_output:
                logger.debug("No text chunks were output.")
            finally:
                await browser_provider.stop()
        return 0
    except Exception as e:
        logger.error(f"ERROR: {e}")
        return 1

def main() -> None:
    args = _build_parser().parse_args()
    if args.cmd == "chat":
        raise SystemExit(asyncio.run(_run_chat(args)))
    raise SystemExit(2)

if __name__ == "__main__":
    main()
