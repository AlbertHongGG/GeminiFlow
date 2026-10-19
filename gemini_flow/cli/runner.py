import argparse
import asyncio
import logging
import sys
from typing import List, Optional

from gemini_flow.application.chat_service import ChatService
from gemini_flow.config import AppConfig
from gemini_flow.domain.entities import ChatRequest, ImagePayload
from gemini_flow.domain.exceptions import GeminiFlowError, PromptInputError
from gemini_flow.infrastructure.auth.gemini_auth import GeminiAuthService
from gemini_flow.infrastructure.browser.playwright_browser import PlaywrightWebBrowser
from gemini_flow.infrastructure.clients.gemini_api.webchannel_client import GeminiWebChannelClient
from gemini_flow.infrastructure.clients.gemini_downloader import GeminiImageDownloader
from gemini_flow.infrastructure.clients.http_client import HttpClient
from gemini_flow.infrastructure.logging.ai_logger import AILogger
from gemini_flow.infrastructure.logging.logger import setup_logging
from gemini_flow.infrastructure.storage.file_cookie_store import FileCookieStore
from gemini_flow.infrastructure.storage.file_session_store import FileSessionStore
from .parser import create_parser
from .prompt_resolver import PromptResolver

logger = logging.getLogger("gemini_flow.cli")


async def _consume_stream(
    client: ChatService,
    req: ChatRequest,
    ai_logger: AILogger,
    debug: bool = False,
) -> None:
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

    if debug and not had_output:
        logger.debug("No text chunks were output.")


async def _run_chat(args: argparse.Namespace, chat_service: Optional[ChatService] = None) -> int:
    config = AppConfig.from_env()
    if args.debug:
        config.debug = True
    setup_logging(config)

    try:
        # Resolve user prompt (from inline argument or file)
        prompt = PromptResolver.resolve_prompt(args.prompt, args.file)

        # Resolve system prompt (from inline argument or file)
        system_prompt = PromptResolver.resolve_system_prompt(args.system_prompt, args.system_prompt_file)

        # Process image attachments
        images = []
        if args.image:
            for p in args.image:
                if not p.exists():
                    sys.stderr.write(f"Error: Image file not found: {p}\n")
                    return 1
                data = p.read_bytes()
                images.append(ImagePayload(data=data, filename=p.name))

        req = ChatRequest(
            prompt=prompt,
            model=args.model,
            thinking=args.thinking,
            language=args.lang,
            images=images,
            session_id=args.session_id,
            system_prompt=system_prompt,
        )

        ai_logger = AILogger()

        if chat_service is not None:
            await _consume_stream(chat_service, req, ai_logger, config.debug)
            return 0

        async with HttpClient(proxy=config.proxy) as http_client:
            browser_provider = PlaywrightWebBrowser(
                config.cookies_dir / ".pw-profile",
                browser_channel="chrome",
                headless=True,
            )

            try:
                cookie_store = FileCookieStore(config.cookies_dir)
                auth_service = GeminiAuthService(
                    config.cookies_dir, cookie_store, http_client, browser_provider
                )
                chat_provider = GeminiWebChannelClient(http_client)
                session_store = FileSessionStore(config.sessions_dir)
                image_downloader = GeminiImageDownloader(config.image_output_dir, browser_provider)

                client = ChatService(
                    auth_service=auth_service,
                    chat_provider=chat_provider,
                    session_store=session_store,
                    http_client=http_client,
                    image_downloader=image_downloader,
                )

                await _consume_stream(client, req, ai_logger, config.debug)
            finally:
                await browser_provider.stop()
        return 0

    except PromptInputError as e:
        sys.stderr.write(f"Error: {e}\n")
        return 1
    except GeminiFlowError as e:
        sys.stderr.write(f"Error: {e}\n")
        logger.error(f"GeminiFlow failure: {e}", exc_info=config.debug)
        return 1
    except Exception as e:
        sys.stderr.write(f"Unexpected error: {e}\n")
        logger.error(f"ERROR: {e}", exc_info=True)
        return 1


def run_cli(
    args_list: Optional[List[str]] = None,
    chat_service: Optional[ChatService] = None,
) -> int:
    parser = create_parser()
    args = parser.parse_args(args_list)

    if args.cmd == "chat":
        ret = asyncio.run(_run_chat(args, chat_service=chat_service))
        if args_list is None:
            raise SystemExit(ret)
        return ret

    if args_list is None:
        raise SystemExit(2)
    return 2
