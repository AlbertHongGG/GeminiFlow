import argparse
import asyncio
import json
import base64
import logging
from pathlib import Path
from typing import Any
import os

import aiohttp_cors
from aiohttp import web
from pydantic import ValidationError

from gemini_flow.domain.entities import ChatRequest, ImagePayload
from gemini_flow.application.chat_service import ChatService
from gemini_flow.domain.exceptions import AuthenticationError, NetworkError, PayloadError, GeminiFlowError
from gemini_flow.config import AppConfig
from gemini_flow.infrastructure.logging.logger import setup_logging
from gemini_flow.infrastructure.clients.http_client import HttpClient
from gemini_flow.infrastructure.clients.gemini_api.api_client import GeminiAPIClient
from gemini_flow.infrastructure.auth.gemini_auth import GeminiAuthService
from gemini_flow.infrastructure.storage.file_cookie_store import FileCookieStore
from gemini_flow.infrastructure.storage.file_session_store import FileSessionStore
from gemini_flow.infrastructure.clients.gemini_downloader import GeminiImageDownloader
from gemini_flow.infrastructure.browser.playwright_browser import PlaywrightWebBrowser

logger = logging.getLogger("gemini_flow.server")

def _json_dumps(obj: object) -> str:
    return json.dumps(obj, ensure_ascii=False)

def _json_error(message: str, *, status: int = 400) -> web.Response:
    return web.json_response({"error": message}, status=status, dumps=_json_dumps)

def _get_url_for_image(request: web.Request, filepath: str) -> str:
    filename = Path(filepath).name
    return f"{request.scheme}://{request.host}/images/{filename}"

def _decode_base64_image(value: str, index: int) -> ImagePayload:
    if value.startswith("data:image/"):
        header, b64 = value.split(",", 1)
        mime = header.split(";", 1)[0].split(":", 1)[1].lower()
        ext = {
            "image/png": "png",
            "image/jpeg": "jpg",
            "image/webp": "webp",
        }.get(mime, "png")
        payload = "".join(b64.split())
        padding = (-len(payload)) % 4
        if padding: payload += "=" * padding
        data = base64.b64decode(payload, validate=False)
        return ImagePayload(data=data, filename=f"upload_{index + 1}.{ext}")

    payload = "".join(value.split())
    padding = (-len(payload)) % 4
    if padding: payload += "=" * padding
    data = base64.b64decode(payload, validate=False)
    return ImagePayload(data=data, filename=f"upload_{index + 1}.png")

async def _read_chat_request(request: web.Request) -> ChatRequest:
    try:
        if not request.can_read_body:
            raise ValueError("Empty body")
        obj = await request.json()
        
        # parse images
        images = []
        if "images" in obj and isinstance(obj["images"], list):
            for i, val in enumerate(obj["images"]):
                if isinstance(val, str):
                    images.append(_decode_base64_image(val, i))
        
        req = ChatRequest(
            prompt=obj.get("prompt"),
            system_prompt=obj.get("system_prompt"),
            model=obj.get("model", "gemini-3-pro"),
            language=obj.get("language", "zh-TW"),
            images=images,
            session_id=obj.get("session_id"),
            auto_refresh_cookies=obj.get("auto_refresh_cookies", True)
        )
        return req
    except ValidationError as e:
        raise ValueError(f"Invalid parameters: {e}")
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON body: {e}")
    except ValueError:
        raise
    except Exception as e:
        raise Exception(f"Failed to read request: {e}")

async def health(_: web.Request) -> web.Response:
    return web.json_response({"ok": True}, dumps=_json_dumps)

async def chat(request: web.Request) -> web.Response:
    try:
        chat_req = await _read_chat_request(request)
    except web.HTTPRequestEntityTooLarge:
        return _json_error("Payload too large. Please upload smaller images (limit is 50MB).", status=413)
    except ValueError as e:
        return _json_error(str(e), status=400)
    except Exception as e:
        return _json_error(str(e), status=500)

    from gemini_flow.infrastructure.logging.ai_logger import AILogger
    ai_logger = AILogger()

    config = request.app["config"]
    http_client = request.app["http_client"]
    browser_provider = request.app["browser_provider"]
    
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
    
    text_parts = []
    images_saved = []

    try:
        async for chunk in client.stream_chat(chat_req):
            if chunk.text:
                text_parts.append(chunk.text)
            if chunk.image_local_path:
                images_saved.append(_get_url_for_image(request, chunk.image_local_path))
            elif chunk.image_url:
                images_saved.append(chunk.image_url)
                
        # Log the complete interaction
        ai_logger.log_interaction(chat_req, "".join(text_parts), images_saved)
    except AuthenticationError as e:
        return _json_error(f"Authentication Failed: {e}", status=401)
    except NetworkError as e:
        return _json_error(f"Network Error: {e}", status=502)
    except PayloadError as e:
        return _json_error(f"Payload Error: {e}", status=422)
    except GeminiFlowError as e:
        return _json_error(str(e), status=400)
    except Exception as e:
        logger.exception("Internal Server Error in chat")
        return _json_error(f"Internal Server Error: {e}", status=500)

    return web.json_response({"text": "".join(text_parts), "images": images_saved}, dumps=_json_dumps)

def _sse_format(*, event: str, data: object) -> bytes:
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n".encode("utf-8")

async def stream(request: web.Request) -> web.StreamResponse:
    try:
        chat_req = await _read_chat_request(request)
    except web.HTTPRequestEntityTooLarge:
        return _json_error("Payload too large. Please upload smaller images (limit is 50MB).", status=413)
    except ValueError as e:
        return _json_error(str(e), status=400)
    except Exception as e:
        return _json_error(str(e), status=500)

    resp = web.StreamResponse(
        status=200,
        headers={
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
    await resp.prepare(request)

    from gemini_flow.infrastructure.logging.ai_logger import AILogger
    ai_logger = AILogger()
    
    config = request.app["config"]
    http_client = request.app["http_client"]
    browser_provider = request.app["browser_provider"]
    
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
    
    full_text = []
    response_images = []
    
    try:
        async for chunk in client.stream_chat(chat_req):
            if chunk.text:
                full_text.append(chunk.text)
                await resp.write(_sse_format(event="text", data={"chunk": chunk.text}))
            if chunk.image_local_path:
                img_url = _get_url_for_image(request, chunk.image_local_path)
                response_images.append(img_url)
                await resp.write(_sse_format(event="image", data={"url": img_url}))
            elif chunk.image_url:
                response_images.append(chunk.image_url)
                await resp.write(_sse_format(event="image", data={"url": chunk.image_url}))
        await resp.write(_sse_format(event="done", data={}))
        
        # Log the complete interaction
        ai_logger.log_interaction(chat_req, "".join(full_text), response_images)
    except ConnectionResetError:
        pass
    except AuthenticationError as e:
        try: await resp.write(_sse_format(event="error", data={"error": f"Authentication Failed: {e}", "status": 401}))
        except Exception: pass
    except NetworkError as e:
        try: await resp.write(_sse_format(event="error", data={"error": f"Network Error: {e}", "status": 502}))
        except Exception: pass
    except PayloadError as e:
        try: await resp.write(_sse_format(event="error", data={"error": f"Payload Error: {e}", "status": 422}))
        except Exception: pass
    except Exception as e:
        logger.exception("Internal Server Error in stream")
        try: await resp.write(_sse_format(event="error", data={"error": f"Internal Server Error: {e}", "status": 500}))
        except Exception: pass

    return resp

async def init_app_state(app: web.Application):
    # Initialize global state
    config = AppConfig.from_env()
    setup_logging(config)
    
    # Store config and create http client context
    app["config"] = config
    app["http_client"] = HttpClient(proxy=config.proxy)
    app["browser_provider"] = PlaywrightWebBrowser(config.cookies_dir / ".pw-profile", browser_channel="chrome", headless=True)
    
    # Enter the context manager manually for app lifecycle
    await app["http_client"].__aenter__()
    await app["browser_provider"].start()
    
    # Ensure image directory exists
    config.image_output_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info("Application state initialized.")

async def cleanup_app_state(app: web.Application):
    if "browser_provider" in app:
        await app["browser_provider"].stop()
        logger.info("Browser provider stopped.")
    if "http_client" in app:
        await app["http_client"].__aexit__(None, None, None)
        logger.info("HTTP Client context closed.")

def create_app() -> web.Application:
    app = web.Application(client_max_size=1024 * 1024 * 50)
    
    app.on_startup.append(init_app_state)
    app.on_cleanup.append(cleanup_app_state)
    
    config = AppConfig.from_env()
    config.image_output_dir.mkdir(parents=True, exist_ok=True)
    app.router.add_static("/images", config.image_output_dir)
    
    app.router.add_get("/health", health)
    app.router.add_post("/chat", chat)
    app.router.add_post("/stream", stream)
    cors = aiohttp_cors.setup(
        app,
        defaults={
            "*": aiohttp_cors.ResourceOptions(
                allow_credentials=True,
                expose_headers="*",
                allow_headers="*",
            )
        },
    )
    for route in list(app.router.routes()):
        cors.add(route)
    return app

async def _serve(*, host: str, port: int) -> None:
    app = create_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host=host, port=port)
    await site.start()
    
    logging.getLogger("gemini_flow.server").info(f"Listening on http://{host}:{port}")
    
    try:
        while True:
            await asyncio.sleep(3600)
    finally:
        await runner.cleanup()

def main() -> None:
    p = argparse.ArgumentParser(description="gemini_flow HTTP server")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=5000)
    p.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = p.parse_args()
    
    if args.debug:
        os.environ["DEBUG"] = "1"
        
    asyncio.run(_serve(host=args.host, port=args.port))

if __name__ == "__main__":
    main()
