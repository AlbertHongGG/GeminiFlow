from __future__ import annotations

import argparse
import asyncio
import json
import base64
from pathlib import Path
from uuid import uuid4
from typing import Any

import aiohttp_cors
from aiohttp import web
from pydantic import ValidationError

from gemini_flow.models import ChatRequest, ImagePayload
from gemini_flow.services.gemini_client import GeminiClient
from gemini_flow.exceptions import AuthenticationError, NetworkError, PayloadError, GeminiFlowError

def _json_dumps(obj: object) -> str:
    return json.dumps(obj, ensure_ascii=False)

def _json_error(message: str, *, status: int = 400) -> web.Response:
    return web.json_response({"error": message}, status=status, dumps=_json_dumps)

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
        raw = await request.read()
        if not raw: raise ValueError("Empty body")
        text = raw.decode("utf-8", errors="ignore")
        obj = json.loads(text)
        
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
            proxy=obj.get("proxy"),
            debug=obj.get("debug", False),
            auto_refresh_cookies=obj.get("auto_refresh_cookies", True),
            save_images=obj.get("save_images", True)
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

    from gemini_flow.infra.ai_logger import AILogger
    logger = AILogger()

    client = GeminiClient()
    text_parts = []
    images_saved = []

    try:
        async for chunk in client.stream_chat(chat_req):
            if chunk.text:
                text_parts.append(chunk.text)
            if chunk.image_saved_path:
                images_saved.append(chunk.image_saved_path)
            elif chunk.image_url:
                images_saved.append(chunk.image_url)
                
        # Log the complete interaction
        logger.log_interaction(chat_req, "".join(text_parts), images_saved)
    except AuthenticationError as e:
        return _json_error(f"Authentication Failed: {e}", status=401)
    except NetworkError as e:
        return _json_error(f"Network Error: {e}", status=502)
    except PayloadError as e:
        return _json_error(f"Payload Error: {e}", status=422)
    except GeminiFlowError as e:
        return _json_error(str(e), status=400)
    except Exception as e:
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

    from gemini_flow.infra.ai_logger import AILogger
    logger = AILogger()
    
    client = GeminiClient()
    full_text = []
    response_images = []
    
    try:
        async for chunk in client.stream_chat(chat_req):
            if chunk.text:
                full_text.append(chunk.text)
                await resp.write(_sse_format(event="text", data={"chunk": chunk.text}))
            if chunk.image_saved_path:
                response_images.append(chunk.image_saved_path)
                await resp.write(_sse_format(event="image", data={"path": chunk.image_saved_path}))
            elif chunk.image_url:
                response_images.append(chunk.image_url)
                await resp.write(_sse_format(event="image", data={"url": chunk.image_url}))
        await resp.write(_sse_format(event="done", data={}))
        
        # Log the complete interaction
        logger.log_interaction(chat_req, "".join(full_text), response_images)
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
        try: await resp.write(_sse_format(event="error", data={"error": f"Internal Server Error: {e}", "status": 500}))
        except Exception: pass

    return resp

def create_app() -> web.Application:
    # 增加 client_max_size 到 50MB 避免大圖上傳時發生 413/400 錯誤
    app = web.Application(client_max_size=1024 * 1024 * 50)
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
    print(f"[server] listening on http://{host}:{port}")
    try:
        while True:
            await asyncio.sleep(3600)
    finally:
        await runner.cleanup()

def main() -> None:
    p = argparse.ArgumentParser(description="gemini_flow HTTP server")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    args = p.parse_args()
    asyncio.run(_serve(host=args.host, port=args.port))

if __name__ == "__main__":
    main()
